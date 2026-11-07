"""DataUpdateCoordinator for DessMonitor Solar Universal."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DessSolarAPI, DessSolarError
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .device_support import (
    get_parameter_sensor_names,
    map_sensor_title,
    needs_parameter_fetch,
)

_LOGGER = logging.getLogger(__name__)


class DessSolarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central data coordinator managing telemetry, parameters, and controls."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DessSolarAPI,
        config_entry: ConfigEntry,
    ) -> None:
        self.api = api
        self.config_entry = config_entry
        self.entry_id = config_entry.entry_id

        raw_interval = config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        try:
            update_interval = int(raw_interval)
            # Ensure safe polling interval (at least 10s) to prevent cloud API rate limiting / timeout cascade
            if update_interval < 10 or update_interval >= 60:
                update_interval = 10
        except (ValueError, TypeError):
            update_interval = 10

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.title})",
            update_interval=timedelta(seconds=int(update_interval)),
        )

        self._devices_metadata: list[dict[str, Any]] = []
        self._collectors_metadata: list[dict[str, Any]] = []
        self._cached_ctrl_fields: dict[str, list[dict[str, Any]]] = {}
        self._cached_ctrl_values: dict[str, dict[str, Any]] = {}
        self.diagnostics_dump: dict[str, Any] = {}
        self._day_battery_charge: dict[str, float] = {}
        self._day_battery_discharge: dict[str, float] = {}
        self._energy_last_calc_date: dict[str, str] = {}
        self._energy_last_calc_time: dict[str, datetime] = {}
        self._last_ctrl_fetch_time: dict[str, datetime] = {}
        self._last_local_telemetry: dict[str, Any] | None = None
        self._last_local_telemetry_time: float = 0.0
        self._last_cloud_poll_time: float = 0.0
        self._load_energy_data()
        self._load_ctrl_data()

    async def async_initial_setup(self) -> None:
        """Discover collectors and devices during component setup."""
        _LOGGER.info("Starting DessSolar device and collector discovery")
        raw_devices = await self.api.get_all_devices()
        collectors = await self.api.get_collectors()
        self._collectors_metadata = collectors

        collector_by_pn = {c.get("pn"): c for c in collectors if c.get("pn")}

        devices: list[dict[str, Any]] = []

        if raw_devices:
            for d in raw_devices:
                pn = d.get("pn")
                coll = collector_by_pn.get(pn, {"pn": pn, "alias": d.get("collalias", pn), "pid": d.get("pid")})
                devices.append({"device": d, "collector": coll})
        else:
            # Fallback if raw_devices empty
            for coll in collectors:
                pn = coll.get("pn")
                if not pn:
                    continue
                coll_devs = await self.api.get_collector_devices(pn)
                for d in coll_devs:
                    devices.append({"device": d, "collector": coll})

        self._devices_metadata = devices
        _LOGGER.info(
            "Discovery complete: found %d collector(s) and %d device(s)",
            len(self._collectors_metadata),
            len(devices),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest telemetry from DessMonitor Cloud."""
        now = time.time()
        local_streaming = (
            self._last_local_telemetry is not None
            and (now - self._last_local_telemetry_time) < 15.0
        )
        if local_streaming and self.data and (now - self._last_cloud_poll_time) < 60.0:
            return self.data

        self._last_cloud_poll_time = now

        if not self._devices_metadata:
            try:
                await self.async_initial_setup()
            except Exception as err:
                self.diagnostics_dump["last_error"] = f"Failed discovering devices: {err}"
                await self.async_dump_debug_file()
                raise UpdateFailed(f"Failed discovering collectors: {err}") from err

        results: dict[str, dict[str, Any]] = {}

        for dev_entry in self._devices_metadata:
            device = dev_entry["device"]
            collector = dev_entry["collector"]

            sn = device.get("sn")
            pn = collector.get("pn") or device.get("pn")
            devcode = device.get("devcode")
            devaddr = device.get("devaddr", 1)
            pid = collector.get("pid") or device.get("pid")

            if not sn or not pn or devcode is None:
                continue

            try:
                # 1. Fetch real-time telemetry, energy flow, and parameters in parallel
                need_params = needs_parameter_fetch(devcode)
                tasks = [
                    self.api.get_device_last_data(pn, devcode, devaddr, sn),
                    self.api.get_device_energy_flow(pn, devcode, devaddr, sn),
                ]
                if need_params:
                    tasks.append(self.api.get_device_parameters(pn, devcode, devaddr, sn))
                if pid:
                    tasks.append(self.api.get_device_summary_data(pid))

                fetch_res = await asyncio.gather(*tasks, return_exceptions=True)

                raw_last_data = fetch_res[0] if (len(fetch_res) > 0 and isinstance(fetch_res[0], list) and len(fetch_res[0]) > 0) else None
                has_primary_telemetry = (
                    raw_last_data is not None
                    and len(raw_last_data) >= 30
                    and any(
                        (str(pt.get("title") or "").strip().lower() in ("grid voltage", "operating mode", "output voltage"))
                        for pt in raw_last_data
                    )
                )
                if not has_primary_telemetry:
                    # Primary telemetry fetch failed, timed out, or returned incomplete list
                    cached = self.data.get(sn) if self.data else None
                    if cached and len(cached.get("data", [])) >= 30:
                        _LOGGER.warning(
                            "Primary telemetry fetch incomplete for inverter %s (points: %d). Retaining valid cached data.",
                            sn,
                            len(raw_last_data) if raw_last_data else 0,
                        )
                        results[sn] = cached
                        continue
                    else:
                        raise UpdateFailed(f"Primary telemetry fetch failed or incomplete on startup for inverter {sn}")
                else:
                    last_data = list(raw_last_data)
                flow_data = fetch_res[1] if (len(fetch_res) > 1 and isinstance(fetch_res[1], list)) else []
                if flow_data:
                    self._merge_flow_points(last_data, flow_data, devcode)

                idx = 2
                if need_params:
                    if len(fetch_res) > idx and isinstance(fetch_res[idx], dict):
                        self._merge_parameter_points(last_data, fetch_res[idx], devcode)
                    idx += 1

                if pid:
                    if len(fetch_res) > idx and isinstance(fetch_res[idx], dict):
                        dev_sum = fetch_res[idx].get(sn)
                        if dev_sum:
                            self._merge_summary_points(last_data, dev_sum, devcode)

                # 2. Fetch control fields metadata (cached)
                if sn not in self._cached_ctrl_fields or not self._cached_ctrl_fields[sn]:
                    try:
                        ctrl_fields = await self.api.get_device_control_fields(pn, devcode, devaddr, sn)
                        self._cached_ctrl_fields[sn] = ctrl_fields
                    except Exception as ctrl_err:
                        _LOGGER.debug("Control fields fetch skipped for %s: %s", sn, ctrl_err)
                        self._cached_ctrl_fields[sn] = []

                # 3. Use cached control values (never block telemetry polling)
                ctrl_values = self._cached_ctrl_values.get(sn, {})

                # 4. Merge control settings into telemetry points (e.g. Main Output Priority)
                self._merge_control_points(last_data, ctrl_values, self._cached_ctrl_fields[sn], devcode)

                # 7. Track battery daily energy & Ensure critical sensors
                self._track_battery_energy(sn, last_data, devcode)
                self._ensure_critical_sensors(last_data, devcode, sn)

                # Append data source tag and merge fresh local triage if available
                if self._last_local_telemetry and (time.time() - self._last_local_telemetry_time < 15.0):
                    self._apply_triage_points(last_data, self._last_local_telemetry)
                else:
                    last_data.append({"title": "Data Source", "val": "Cloud", "unit": ""})

                results[sn] = {
                    "device": device,
                    "collector": collector,
                    "data": last_data,
                    "ctrl_fields": self._cached_ctrl_fields[sn],
                    "ctrl_values": ctrl_values or self._cached_ctrl_values.get(sn, {}),
                }
                _LOGGER.info(
                    "Updated inverter %s (devcode %s): %d data points, %d control options",
                    sn,
                    devcode,
                    len(last_data),
                    len(self._cached_ctrl_fields[sn]),
                )

            except DessSolarError as err:
                _LOGGER.warning("Telemetry update failed for inverter %s: %s", sn, err)
                if sn in self.data if self.data else False:
                    results[sn] = self.data[sn]
                    for pt in results[sn]["data"]:
                        if pt.get("title") == "Data Source":
                            pt["val"] = "Cached Cloud"
                else:
                    self.diagnostics_dump["last_error"] = f"Failed updating device {sn}: {err}"
                    await self.async_dump_debug_file()
                    raise UpdateFailed(f"Failed updating device {sn}: {err}") from err

        self.diagnostics_dump = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "devices_metadata": self._devices_metadata,
            "collectors_metadata": self._collectors_metadata,
            "results_summary": {sn: len(d.get("data", [])) for sn, d in results.items()},
            "last_error": None,
        }
        await self.async_dump_debug_file()

        return results

    def _apply_triage_points(self, data_points: list[dict[str, Any]], triage: dict[str, Any]) -> None:
        """Merge high-speed local triage telemetry into data points and set Data Source to Local."""
        pt_map: dict[str, dict[str, Any]] = {}
        for pt in data_points:
            t = pt.get("title") or pt.get("name")
            if t:
                pt_map[str(t).strip().lower()] = pt

        targets = {
            "output_power": ["output active power", "output power"],
            "load_power": ["load power"],
            "solar_total_power": ["total pv power", "pv power"],
            "pv1_power": ["pv1 charger power", "pv1 power"],
            "pv2_power": ["pv2 charger power", "pv2 power"],
            "grid_voltage": ["grid voltage"],
            "output_voltage": ["output voltage", "ac output voltage"],
            "load_percentage": ["load percentage", "load percent"],
            "pv1_voltage": ["pv1 voltage"],
            "pv2_voltage": ["pv2 voltage"],
            "pv1_current": ["pv1 charger current", "pv1 current"],
            "pv2_current": ["pv2 charger current", "pv2 current"],
            "battery_voltage": ["battery voltage"],
            "battery_current": ["battery current"],
            "battery_power": ["battery power", "battery active power"],
            "battery_soc": ["battery soc"],
            "inverter_temperature": ["inverter temperature", "inv module termperature"],
        }

        for k, val in triage.items():
            if k in targets:
                for tgt in targets[k]:
                    if tgt in pt_map:
                        pt_map[tgt]["val"] = val
                    else:
                        data_points.append({"title": tgt.title(), "val": val, "unit": ""})

        # Set Data Source to Local
        if "data source" in pt_map:
            pt_map["data source"]["val"] = "Local"
        else:
            data_points.append({"title": "Data Source", "val": "Local", "unit": ""})

    def async_receive_local_triage(self, triage_data: dict[str, Any]) -> None:
        """Receive high-speed local triage telemetry (3s) from em11000_bridge."""
        now = time.time()
        self._last_local_telemetry = triage_data
        self._last_local_telemetry_time = now

        if not self.data:
            return

        for sn, dev_entry in self.data.items():
            device_meta = dev_entry.get("device", {})
            devcode = device_meta.get("devcode", 6515)
            last_data = dev_entry.get("data", [])

            self._apply_triage_points(last_data, triage_data)
            self._track_battery_energy(sn, last_data, devcode)
            self._ensure_critical_sensors(last_data, devcode, sn)

        self.async_set_updated_data(self.data)

    def _merge_parameter_points(
        self,
        last_data: list[dict[str, Any]],
        params_data: dict[str, dict[str, Any]],
        devcode: int,
    ) -> None:
        """Merge wanted parameters (e.g. PV1/PV2 voltages/powers) into last_data."""
        wanted = get_parameter_sensor_names(devcode)
        if not wanted or not params_data:
            return

        existing_titles = {pt.get("title") for pt in last_data if pt.get("title")}
        mapped_existing = {map_sensor_title(devcode, t) for t in existing_titles if t}
        existing_titles.update(mapped_existing)

        for name, info in params_data.items():
            param_id = info.get("id", "")
            if name in wanted or param_id in wanted:
                mapped_name = map_sensor_title(devcode, name)
                if name not in existing_titles and mapped_name not in existing_titles:
                    last_data.append(
                        {
                            "title": name,
                            "val": info.get("value", ""),
                            "unit": info.get("unit", ""),
                        }
                    )
                    existing_titles.add(name)
                    if mapped_name:
                        existing_titles.add(mapped_name)

    def _merge_summary_points(
        self,
        last_data: list[dict[str, Any]],
        summary: dict[str, Any],
        devcode: int,
    ) -> None:
        """Merge summary counters while strictly eliminating duplicates."""
        existing_titles = {pt.get("title") for pt in last_data if pt.get("title")}
        mapped_existing = {map_sensor_title(devcode, t) for t in existing_titles if t}
        existing_titles.update(mapped_existing)

        summary_candidates = [
            ("Today generation", summary.get("energyToday"), "kWh"),
            ("Total generation", summary.get("energyTotal"), "kWh"),
            ("Output Active Power", summary.get("outpower"), "kW"),
            ("SOC", summary.get("soc"), "%"),
        ]

        for title, val, unit in summary_candidates:
            if val is not None and val != "":
                mapped = map_sensor_title(devcode, title)
                if title not in existing_titles and mapped not in existing_titles:
                    last_data.append({"title": title, "val": val, "unit": unit})
                    existing_titles.add(title)
                    if mapped:
                        existing_titles.add(mapped)

    def _merge_control_points(
        self,
        last_data: list[dict[str, Any]],
        ctrl_values: dict[str, Any],
        ctrl_fields: list[dict[str, Any]],
        devcode: int,
    ) -> None:
        """Merge configurable settings into telemetry points for sensors expecting them."""
        existing_titles = {str(pt.get("title")).strip().lower() for pt in last_data if pt.get("title")}

        for field in ctrl_fields:
            fid = field.get("id")
            fname = field.get("name")
            if not fid or not fname or fid not in ctrl_values:
                continue

            raw_val = ctrl_values[fid]
            if raw_val is None:
                continue

            mapped_name = map_sensor_title(devcode, fname)
            # If items map exists, convert key to human-readable label
            items = field.get("item", [])
            val_str = str(raw_val)
            for it in items:
                if str(it.get("key")) == val_str:
                    val_str = str(it.get("val", val_str))
                    break

            norm_fname = fname.strip().lower()
            norm_mapped = mapped_name.strip().lower() if mapped_name else ""

            if norm_fname not in existing_titles and norm_mapped not in existing_titles:
                last_data.append(
                    {
                        "title": mapped_name or fname,
                        "val": val_str,
                        "unit": field.get("unit", ""),
                        "id": fid,
                    }
                )
                existing_titles.add(norm_fname)
                if norm_mapped:
                    existing_titles.add(norm_mapped)

    def _get_storage_path(self) -> str:
        """Return path to persistent energy storage file."""
        config_dir = getattr(self.hass.config, "config_dir", None) or os.getcwd()
        return os.path.join(config_dir, ".storage", "dess_solar_energy.json")

    def _load_energy_data(self) -> None:
        """Load persisted daily energy from storage or HA state."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            path = self._get_storage_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if saved.get("date") == today_str:
                    self._day_battery_charge = {k: min(float(v), 60.0) for k, v in saved.get("charges", {}).items()}
                    self._day_battery_discharge = {k: min(float(v), 60.0) for k, v in saved.get("discharges", {}).items()}
                    for k in self._day_battery_charge:
                        self._energy_last_calc_date[k] = today_str
                    _LOGGER.info("Restored persisted daily battery energy for %s", today_str)
                    return
        except Exception as err:
            _LOGGER.debug("Could not load persisted energy file: %s", err)

        # Fallback: Check HA states
        try:
            chg_st = self.hass.states.get("sensor.home_energy_em11000_day_battery_charge")
            if chg_st and chg_st.state not in ("unknown", "unavailable", "None", ""):
                val = float(chg_st.state)
                if 0 < val <= 60.0:
                    for sn in self._devices_metadata:
                        self._day_battery_charge[sn] = val
                        self._energy_last_calc_date[sn] = today_str

            dis_st = self.hass.states.get("sensor.home_energy_em11000_day_battery_discharge")
            if dis_st and dis_st.state not in ("unknown", "unavailable", "None", ""):
                val = float(dis_st.state)
                if 0 < val <= 60.0:
                    for sn in self._devices_metadata:
                        self._day_battery_discharge[sn] = val
                        self._energy_last_calc_date[sn] = today_str
        except Exception as err:
            _LOGGER.debug("Could not restore energy from HA states: %s", err)

    def _persist_energy_data(self) -> None:
        """Save daily battery energy to storage file."""
        try:
            path = self._get_storage_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            today_str = datetime.now().strftime("%Y-%m-%d")
            data = {
                "date": today_str,
                "charges": self._day_battery_charge,
                "discharges": self._day_battery_discharge,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as err:
            _LOGGER.debug("Could not persist energy file: %s", err)

    def _get_ctrl_storage_path(self) -> str:
        """Return path to persistent control parameters storage file."""
        config_dir = getattr(self.hass.config, "config_dir", None) or os.getcwd()
        return os.path.join(config_dir, ".storage", "dess_solar_ctrl_values.json")

    def _load_ctrl_data(self) -> None:
        """Load persisted inverter control settings from storage file."""
        try:
            path = self._get_ctrl_storage_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._cached_ctrl_values = saved.get("values", {})
                    if "fields" in saved:
                        self._cached_ctrl_fields = saved.get("fields", {})
                    _LOGGER.info("Restored %d persisted inverter control settings", sum(len(v) for v in self._cached_ctrl_values.values()))
        except Exception as err:
            _LOGGER.debug("Could not load persisted control values file: %s", err)

    def _persist_ctrl_data(self) -> None:
        """Save inverter control settings to storage file."""
        try:
            path = self._get_ctrl_storage_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "timestamp": datetime.now().isoformat(),
                "values": self._cached_ctrl_values,
                "fields": self._cached_ctrl_fields,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as err:
            _LOGGER.warning("Failed persisting control values file: %s", err)

    def _track_battery_energy(self, sn: str, last_data: list[dict[str, Any]], devcode: int) -> None:
        """Calculate and integrate day battery charge and discharge energy (kWh)."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        if self._energy_last_calc_date.get(sn) != today_str:
            self._energy_last_calc_date[sn] = today_str
            self._day_battery_charge[sn] = 0.0
            self._day_battery_discharge[sn] = 0.0
            self._energy_last_calc_time[sn] = datetime.now()
            self._persist_energy_data()

        # Extract Solar PV Power & Today Generation for physical bounds checking
        pv_pow = 0.0
        today_pv_kwh = None
        grid_in_pow = 0.0
        for pt in last_data:
            t = str(pt.get("title") or pt.get("name") or pt.get("par") or "").strip().lower()
            m = str(map_sensor_title(devcode, t) or "").strip().lower()
            if (
                t in ("solar total power", "pv power", "total pv power", "pv_output_power", "pv total charging power", "total pv charging power")
                or m in ("solar total power", "pv power", "total pv power", "pv total charger power")
            ):
                try:
                    pv_cand = float(pt.get("val", 0))
                    if str(pt.get("unit", "")).strip().lower() == "kw":
                        pv_cand *= 1000.0
                    pv_pow = max(pv_pow, pv_cand)
                except (ValueError, TypeError):
                    pass
            elif (
                t in ("daily pv energy generation", "today generation", "energy today", "energy_today", "today pv energy generation")
                or m in ("energy today", "today generation", "daily pv energy generation")
            ):
                try:
                    cand_kwh = float(pt.get("val", 0))
                    if cand_kwh > 0:
                        today_pv_kwh = cand_kwh
                except (ValueError, TypeError):
                    pass
            elif (
                t in ("grid power", "grid_power", "grid_active_power")
                or m in ("grid power", "grid active power")
            ):
                try:
                    gp_cand = float(pt.get("val", 0))
                    if str(pt.get("unit", "")).strip().lower() == "kw":
                        gp_cand *= 1000.0
                    if gp_cand > 0:
                        grid_in_pow = gp_cand
                except (ValueError, TypeError):
                    pass

        # Fallback to device metadata or HA state if today_pv_kwh is still None
        if today_pv_kwh is None or today_pv_kwh <= 0.0:
            for dev in self._devices_metadata:
                d = dev.get("device", {})
                if str(d.get("sn", "")).strip().upper() == sn.upper():
                    try:
                        et = float(d.get("energyToday", 0))
                        if et > 0:
                            today_pv_kwh = et
                            break
                    except (ValueError, TypeError):
                        pass

        if today_pv_kwh is None or today_pv_kwh <= 0.0:
            for cand_id in (
                f"sensor.home_energy_{sn.lower()}_energy_today",
                "sensor.home_energy_em11000_energy_today",
                "sensor.em11000_energy_today",
            ):
                st = self.hass.states.get(cand_id)
                if st and st.state not in ("unknown", "unavailable", "None", ""):
                    try:
                        today_pv_kwh = float(st.state)
                        break
                    except (ValueError, TypeError):
                        pass

        p_val = None
        for pt in last_data:
            t = pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id")
            if not t:
                continue
            str_t = str(t).strip().lower()
            mapped = map_sensor_title(devcode, str(t)).strip().lower()
            if str_t in ("battery power", "battery_active_power") or mapped == "battery power":
                v = pt.get("val")
                if v is not None and v != "":
                    try:
                        p_val = float(v)
                        unit = str(pt.get("unit", "")).strip().lower()
                        # Only multiply if explicitly reported as kW
                        if unit == "kw":
                            p_val *= 1000.0
                        break
                    except (ValueError, TypeError):
                        pass

        if p_val is None or abs(p_val) <= 0.05:
            # Fallback to Battery Voltage * Battery Current
            bv = None
            bc = None
            for pt in last_data:
                t = str(pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id") or "").strip().lower()
                m = map_sensor_title(devcode, t).strip().lower()
                if t in ("battery voltage", "eybond_read_24") or m == "battery voltage":
                    try:
                        bv = float(pt.get("val"))
                    except (ValueError, TypeError):
                        pass
                elif t in ("battery current", "eybond_read_25") or m == "battery current":
                    try:
                        bc = float(pt.get("val"))
                    except (ValueError, TypeError):
                        pass
            if bv is not None and bc is not None and abs(bc) > 0.05:
                # If solar is 0 and grid is 0, battery CANNOT be charging!
                if pv_pow <= 10.0 and grid_in_pow <= 10.0:
                    p_val = -(bv * abs(bc))  # Discharging
                else:
                    load_pow = 0.0
                    for pt in last_data:
                        t = str(pt.get("title") or "").strip().lower()
                        if t in ("load power", "output active power", "outpower", "output power", "load_active_power"):
                            try:
                                lpf = float(pt.get("val", 0))
                                if str(pt.get("unit", "")).strip().lower() == "kw" or (0.05 < lpf < 50.0):
                                    lpf *= 1000.0
                                load_pow = lpf
                            except (ValueError, TypeError):
                                pass
                    if pv_pow > (load_pow + 20.0):
                        p_val = bv * abs(bc)  # Excess PV charges battery
                    else:
                        p_val = -(bv * abs(bc))  # Discharging to support load

        # Physical Sanity Checking on battery power:
        if p_val is not None:
            if p_val > 0 and pv_pow <= 10.0 and grid_in_pow <= 10.0:
                p_val = 0.0  # Cannot charge with zero generation source
            elif p_val > 0:
                max_avail_charge = pv_pow + grid_in_pow + 30.0
                p_val = min(p_val, max_avail_charge)

        now = datetime.now()
        last_t = self._energy_last_calc_time.get(sn)
        self._energy_last_calc_time[sn] = now

        if last_t is not None and p_val is not None:
            dt_hours = (now - last_t).total_seconds() / 3600.0
            if 0 < dt_hours <= 0.5:
                if p_val > 5.0:  # Charging (W)
                    added = (p_val / 1000.0) * dt_hours
                    self._day_battery_charge[sn] = round(self._day_battery_charge.get(sn, 0.0) + added, 5)
                    self._persist_energy_data()
                elif p_val < -5.0:  # Discharging (W)
                    added = (abs(p_val) / 1000.0) * dt_hours
                    self._day_battery_discharge[sn] = round(self._day_battery_discharge.get(sn, 0.0) + added, 5)
                    self._persist_energy_data()

        # Sanity boundary cap: Day battery charge cannot physically exceed today's solar generation
        if today_pv_kwh is not None and today_pv_kwh > 0.1:
            max_allowed = today_pv_kwh + 0.05
            current_charge = self._day_battery_charge.get(sn, 0.0)
            if current_charge > max_allowed:
                # If corrupted or inflated, cap immediately to realistic battery absorption (max 70% of generation)
                realistic_val = round(today_pv_kwh, 2)
                self._day_battery_charge[sn] = realistic_val
                self._persist_energy_data()

    def get_day_battery_charge(self, sn: str) -> float:
        """Return integrated daily battery charge in kWh."""
        return round(self._day_battery_charge.get(sn, 0.0), 2)

    def get_day_battery_discharge(self, sn: str) -> float:
        """Return integrated daily battery discharge in kWh."""
        return round(self._day_battery_discharge.get(sn, 0.0), 2)

    def _ensure_critical_sensors(
        self,
        last_data: list[dict[str, Any]],
        devcode: int,
        sn: str | None = None,
    ) -> None:
        """Ensure critical sensors exist with accurate data."""
        points_by_title: dict[str, Any] = {}
        for pt in last_data:
            t = pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id")
            if t:
                points_by_title[str(t).strip().lower()] = pt.get("val")
                mapped = map_sensor_title(devcode, str(t))
                if mapped:
                    points_by_title[mapped.strip().lower()] = pt.get("val")

        # 1. Output Apparent Power (VA)
        if "output apparent power" not in points_by_title or points_by_title.get("output apparent power") in (None, "", "None"):
            v = points_by_title.get("output voltage")
            curr = points_by_title.get("output current")
            s_val = None
            try:
                if v is not None and curr is not None:
                    vf = float(v)
                    cf = float(curr)
                    if vf > 0 and cf >= 0:
                        s_val = round(vf * cf)
            except (ValueError, TypeError):
                pass

            if s_val is None:
                lp = points_by_title.get("load power") or points_by_title.get("output active power")
                try:
                    if lp is not None:
                        lpf = float(lp)
                        s_val = round(lpf / 0.95) if lpf > 0 else 0
                except (ValueError, TypeError):
                    pass

            if s_val is not None:
                last_data.append({
                    "title": "Output Apparent Power",
                    "val": str(s_val),
                    "unit": "VA",
                })
                points_by_title["output apparent power"] = str(s_val)

        # 2. Load Percentage (%)
        if "load percentage" not in points_by_title or points_by_title.get("load percentage") in (None, "", "None"):
            lp = points_by_title.get("load power") or points_by_title.get("output active power")
            rated_power = 11000.0
            pct_val = None
            try:
                if lp is not None:
                    lpf = float(lp)
                    pct_val = round((lpf / rated_power) * 100.0, 1)
                    pct_val = max(0.0, min(100.0, pct_val))
            except (ValueError, TypeError):
                pass

            if pct_val is not None:
                last_data.append({
                    "title": "Load Percentage",
                    "val": str(pct_val),
                    "unit": "%",
                })
                points_by_title["load percentage"] = str(pct_val)

        # 3. Output Current (A)
        curr_val = None
        for k in ("output current", "output_current", "ac output current", "ac_output_current", "load current"):
            raw_c = points_by_title.get(k)
            if raw_c not in (None, "", "None"):
                try:
                    cf = float(raw_c)
                    if cf > 0.05:
                        curr_val = cf
                        break
                except (ValueError, TypeError):
                    pass

        # If current is missing or <= 0.05 while there is load power, calculate from P / V
        lp_raw = (
            points_by_title.get("load power")
            or points_by_title.get("output active power")
            or points_by_title.get("output power")
            or points_by_title.get("outpower")
            or points_by_title.get("load_active_power")
        )
        ov_raw = points_by_title.get("output voltage") or points_by_title.get("ac output voltage")

        ovf = 230.3
        if ov_raw not in (None, "", "None"):
            try:
                ovf_cand = float(ov_raw)
                if ovf_cand > 50.0:
                    ovf = ovf_cand
            except (ValueError, TypeError):
                pass

        lp_watts = 0.0
        if lp_raw not in (None, "", "None"):
            try:
                lpf = float(lp_raw)
                if 0.05 < lpf < 50.0:
                    lpf *= 1000.0
                if lpf > 0:
                    lp_watts = lpf
            except (ValueError, TypeError):
                pass

        if curr_val is None or curr_val <= 0.05:
            if lp_watts > 10.0:
                curr_val = round(lp_watts / ovf, 1)
            else:
                curr_val = 0.0

        found_existing = False
        for p in last_data:
            pt_t = str(p.get("title") or p.get("name") or p.get("par") or "").strip().lower()
            mapped = map_sensor_title(devcode, str(p.get("title") or "")).strip().lower()
            if pt_t in ("output current", "output_current", "ac output current", "ac_output_current", "load current") or mapped == "output current":
                p["val"] = str(curr_val)
                p["unit"] = "A"
                found_existing = True

        if not found_existing:
            last_data.append({
                "title": "Output Current",
                "val": str(curr_val),
                "unit": "A",
            })
        points_by_title["output current"] = str(curr_val)

        # 4. Main Output Priority
        has_out = any(k in points_by_title and points_by_title.get(k) not in (None, "", "None") for k in ("main output priority", "output priority", "current output priority"))
        if not has_out:
            last_data.append({
                "title": "Main Output Priority",
                "val": "SBU",
                "unit": "",
            })
            points_by_title["main output priority"] = "SBU"

        # 4. Charger Source Priority
        has_chg = any(k in points_by_title and points_by_title.get(k) not in (None, "", "None") for k in ("charger source priority", "current charging priority", "charge priority"))
        if not has_chg:
            last_data.append({
                "title": "Charger Source Priority",
                "val": "OSO",
                "unit": "",
            })
            points_by_title["charger source priority"] = "OSO"

        # 5. Battery SOH (%)
        if "battery soh" not in points_by_title:
            last_data.append({"title": "Battery SOH", "val": "100.0", "unit": "%"})
            points_by_title["battery soh"] = "100.0"

        # 6. Battery Rated Capacity (Ah)
        if "battery rated capacity" not in points_by_title:
            last_data.append({"title": "Battery Rated Capacity", "val": "800.0", "unit": "Ah"})
            points_by_title["battery rated capacity"] = "800.0"

        # 7. Battery Power / Direction / Charge & Discharge Power
        bp = None
        for k in ("battery power", "battery_active_power"):
            if k in points_by_title and points_by_title[k] not in (None, "", "None"):
                try:
                    bp = float(points_by_title[k])
                except (ValueError, TypeError):
                    pass
                if bp is not None:
                    break

        if "battery current direction" not in points_by_title:
            dir_val = "Charging" if (bp is not None and bp > 15.0) else ("Discharging" if (bp is not None and bp < -15.0) else "Idle")
            last_data.append({"title": "Battery Current Direction", "val": dir_val, "unit": ""})
            points_by_title["battery current direction"] = dir_val

        if "battery charge power" not in points_by_title:
            chg_p = round(bp, 1) if (bp is not None and bp > 0) else 0.0
            last_data.append({"title": "Battery Charge Power", "val": str(chg_p), "unit": "W"})
            points_by_title["battery charge power"] = str(chg_p)

        if "battery discharge power" not in points_by_title:
            dis_p = round(abs(bp), 1) if (bp is not None and bp < 0) else 0.0
            last_data.append({"title": "Battery Discharge Power", "val": str(dis_p), "unit": "W"})
            points_by_title["battery discharge power"] = str(dis_p)

        # 8. Battery Remaining Energy Wh
        if "battery remaining energy wh" not in points_by_title:
            soc_val = points_by_title.get("soc") or points_by_title.get("battery soc")
            try:
                soc = float(soc_val) if soc_val not in (None, "") else 100.0
            except (ValueError, TypeError):
                soc = 100.0
            rem_wh = round((soc / 100.0) * 38400.0, 0)
            last_data.append({"title": "Battery Remaining Energy Wh", "val": str(rem_wh), "unit": "Wh"})
            points_by_title["battery remaining energy wh"] = str(rem_wh)

        # 9. Day Battery Charge & Discharge Energy (kWh)
        if sn:
            chg_kwh = self.get_day_battery_charge(sn)
            dis_kwh = self.get_day_battery_discharge(sn)
            found_chg = False
            found_dis = False
            for p in last_data:
                pt_t = str(p.get("title") or "").strip().lower()
                mapped = map_sensor_title(devcode, str(p.get("title") or "")).strip().lower()
                if pt_t in ("day battery charge", "day_battery_charge") or mapped == "day battery charge":
                    p["val"] = str(chg_kwh)
                    p["unit"] = "kWh"
                    found_chg = True
                elif pt_t in ("day battery discharge", "day_battery_discharge") or mapped == "day battery discharge":
                    p["val"] = str(dis_kwh)
                    p["unit"] = "kWh"
                    found_dis = True
            if not found_chg:
                last_data.append({"title": "Day Battery Charge", "val": str(chg_kwh), "unit": "kWh"})
            if not found_dis:
                last_data.append({"title": "Day Battery Discharge", "val": str(dis_kwh), "unit": "kWh"})

    async def _fetch_active_control_values(
        self,
        pn: str,
        devcode: int,
        devaddr: int,
        sn: str,
        ctrl_fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Fetch current settings for all configurable fields."""
        values: dict[str, Any] = {}
        target_fields = [
            f for f in ctrl_fields
            if f.get("id") and "_ctrl_" not in f.get("id")
        ]
        if not target_fields:
            return values

        for field in target_fields:
            fid = field.get("id")
            if not fid:
                continue
            try:
                val_data = await asyncio.wait_for(
                    self.api.get_device_control_value(pn, devcode, devaddr, sn, fid),
                    timeout=2.0,
                )
                val = val_data.get("val")
                if val is not None:
                    values[fid] = val
                await asyncio.sleep(0.06)
            except Exception:
                pass
        return values

    async def async_refresh_all_control_values(self, sn: str) -> None:
        """Force fetch all configuration parameters from device and push to HA entities."""
        device_entry = self.data.get(sn, {}) if self.data else {}
        device_meta = device_entry.get("device", {})
        collector_meta = device_entry.get("collector", {})
        pn = collector_meta.get("pn") or device_meta.get("pn")
        devcode = device_meta.get("devcode")
        devaddr = device_meta.get("devaddr", 1)

        if not devcode and self._devices_metadata:
            for entry in self._devices_metadata:
                if entry.get("device", {}).get("sn") == sn:
                    device_meta = entry.get("device", {})
                    collector_meta = entry.get("collector", {})
                    pn = collector_meta.get("pn") or device_meta.get("pn")
                    devcode = device_meta.get("devcode")
                    devaddr = device_meta.get("devaddr", 1)
                    break

        pn = pn or "Q0032094972706"
        devcode = devcode or 6515
        devaddr = devaddr or 1

        fields = self._cached_ctrl_fields.get(sn, [])
        if not fields:
            fields = await self.api.get_device_control_fields(pn, devcode, devaddr, sn)
            self._cached_ctrl_fields[sn] = fields

        values = await self._fetch_active_control_values(pn, devcode, devaddr, sn, fields)
        if values:
            self._cached_ctrl_values[sn] = {**self._cached_ctrl_values.get(sn, {}), **values}
            self._persist_ctrl_data()
        self._last_ctrl_fetch_time[sn] = datetime.now()

        if self.data and sn in self.data:
            self.data[sn]["ctrl_values"] = self._cached_ctrl_values.get(sn, {})
            self.async_set_updated_data(self.data)

    async def async_execute_control(
        self,
        pn: str,
        devcode: int,
        devaddr: int,
        sn: str,
        field_id: str,
        value: str | int | float,
    ) -> bool:
        """Execute inverter control update and refresh state."""
        success = await self.api.execute_device_control(pn, devcode, devaddr, sn, field_id, value)
        if success:
            if sn in self._cached_ctrl_values:
                self._cached_ctrl_values[sn][field_id] = str(value)
            # Schedule immediate refresh
            await self.async_request_refresh()
        return success

    def _merge_flow_points(
        self,
        last_data: list[dict[str, Any]],
        flow_data: list[dict[str, Any]],
        devcode: int,
    ) -> None:
        """Merge energy flow metrics (battery, pv, grid, load active power) into last_data."""
        if not flow_data:
            return
        existing_titles = {
            pt.get("title") or pt.get("name") or pt.get("par") for pt in last_data
        }
        mapped_existing = {map_sensor_title(devcode, t) for t in existing_titles if t}
        existing_titles.update(mapped_existing)

        for pt in flow_data:
            title = pt.get("title")
            val = pt.get("val")
            unit = pt.get("unit", "")
            if not title or val is None or val == "":
                continue
            mapped = map_sensor_title(devcode, title)
            if title not in existing_titles and mapped not in existing_titles:
                last_data.append({"title": title, "val": val, "unit": unit})
                existing_titles.add(title)
                if mapped:
                    existing_titles.add(mapped)

    async def async_dump_debug_file(self) -> str:
        """Dump comprehensive debug data to a JSON file in the HA config directory."""
        try:
            dump_data = {
                "dump_time": datetime.now(timezone.utc).isoformat(),
                "coordinator_name": self.name,
                "entry_id": self.entry_id,
                "devices_metadata": self._devices_metadata,
                "collectors_metadata": self._collectors_metadata,
                "cached_ctrl_fields": self._cached_ctrl_fields,
                "cached_ctrl_values": self._cached_ctrl_values,
                "coordinator_data": self.data,
                "raw_api_responses": self.api.last_raw_responses,
                "last_error": self.diagnostics_dump.get("last_error"),
            }
            path = self.hass.config.path("dess_solar_debug.json")

            def _write():
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(dump_data, f, indent=2, ensure_ascii=False)

            await self.hass.async_add_executor_job(_write)
            _LOGGER.info("DessSolar debug diagnostics written to %s", path)
            return path
        except Exception as err:
            _LOGGER.error("Failed writing dess_solar_debug.json: %s", err)
            return ""


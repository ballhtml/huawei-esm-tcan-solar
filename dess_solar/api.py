"""DessMonitor Cloud API client for DessMonitor Solar Universal."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import aiohttp
from homeassistant.helpers.storage import Store

from .const import API_BASE_URL, APP_ID, APP_VERSION

_LOGGER = logging.getLogger(__name__)


class DessSolarError(Exception):
    """Base exception for DessSolar API failures."""


class DessSolarAuthError(DessSolarError):
    """Authentication failure."""


def _mask_identifier(value: str | None) -> str:
    """Mask credentials/identifiers for clean logs."""
    if not value:
        return "***"
    trimmed = value.strip()
    if len(trimmed) <= 3:
        return "***"
    return f"{trimmed[:3]}***"


class DessSolarAPI:
    """Async API Client for DessMonitor / SmartESS platform."""

    def __init__(
        self,
        username: str,
        password: str,
        company_key: str = "bnrl_frRFjEz8Mkn",
        session: aiohttp.ClientSession | None = None,
        store: Store | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.company_key = company_key
        self.base_url = API_BASE_URL

        self._session = session
        self._close_session = False
        self._store = store

        self.token: str | None = None
        self.secret: str | None = None
        self.token_expire: int | None = None
        self.last_raw_responses: dict[str, Any] = {}

        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True

    async def close(self) -> None:
        """Close HTTP session if privately owned."""
        if self._session and self._close_session:
            await self._session.close()

    @staticmethod
    def _sha1(data: str) -> str:
        """Generate lowercase SHA-1 hash."""
        return hashlib.sha1(data.encode("utf-8")).hexdigest().lower()

    def _generate_signature(self, salt: str, action_string: str) -> str:
        """Generate API signature based on token state."""
        if self.token and self.secret:
            signature_string = f"{salt}{self.secret}{self.token}{action_string}"
        else:
            pwd_sha1 = self._sha1(self.password)
            signature_string = f"{salt}{pwd_sha1}{action_string}"
        return self._sha1(signature_string)

    def _is_token_expired(self) -> bool:
        """Check if cached token is nearing expiration (5-minute safety buffer)."""
        if not self.token_expire:
            return False
        return int(time.time()) >= (self.token_expire - 300)

    async def _make_request(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        timeout_seconds: int = 8,
    ) -> dict[str, Any]:
        """Execute signed API request."""
        self._ensure_session()
        await self._ensure_token(action)

        salt = str(int(time.time() * 1000))
        action_string = f"&action={action}"
        if params:
            for k, v in sorted(params.items()):
                action_string += f"&{k}={v}"

        signature = self._generate_signature(salt, action_string)
        url = f"{self.base_url}?sign={signature}&salt={salt}"
        if self.token and action != "authSource":
            url += f"&token={self.token}"
        url += action_string

        try:
            async with asyncio.timeout(timeout_seconds):
                assert self._session is not None
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    self.last_raw_responses[action] = data
        except asyncio.TimeoutError as err:
            _LOGGER.error("API request '%s' timed out after %ds", action, timeout_seconds)
            raise DessSolarError(f"Request timeout for {action}") from err
        except aiohttp.ClientResponseError as err:
            _LOGGER.error("HTTP %s error on action '%s': %s", err.status, action, err.message)
            raise DessSolarError(f"HTTP error {err.status}: {err.message}") from err
        except Exception as err:
            _LOGGER.error("Request failed for action '%s': %s", action, err)
            raise DessSolarError(f"Request failed: {err}") from err

        return self._validate_api_response(action, data)

    def _ensure_session(self) -> None:
        if not self._session:
            raise DessSolarError("HTTP Session not initialized")

    async def _ensure_token(self, action: str) -> None:
        if action == "authSource":
            return
        if self._is_token_expired() or not self.token:
            _LOGGER.debug("Refreshing token before action '%s'", action)
            await self.authenticate()

    @staticmethod
    def _validate_api_response(action: str, data: dict[str, Any]) -> dict[str, Any]:
        err_code = data.get("err", 0)
        if err_code != 0:
            error_msg = data.get("desc", f"API error {err_code}")
            _LOGGER.error("API returned error %s on action '%s': %s", err_code, action, error_msg)
            if err_code in (1001, 1002, 1003, 1004):
                raise DessSolarAuthError(error_msg)
            raise DessSolarError(error_msg)
        return data

    async def authenticate(self) -> bool:
        """Authenticate user against DessMonitor API."""
        _LOGGER.debug("Authenticating user: %s", _mask_identifier(self.username))
        try:
            self.token = None
            self.secret = None
            self.token_expire = None

            auth_params = {
                "usr": self.username,
                "company-key": self.company_key,
                "source": "1",
                "_app_client_": "web",
                "_app_id_": APP_ID,
                "_app_version_": APP_VERSION,
            }

            response = await self._make_request("authSource", auth_params)
            dat = response.get("dat", {})
            self.token = dat.get("token")
            self.secret = dat.get("secret")
            expire = dat.get("expire")

            if not self.token or not self.secret:
                raise DessSolarAuthError("No auth token received from API")

            if expire:
                self.token_expire = int(time.time()) + int(expire)

            if self._store:
                await self._save_token()

            _LOGGER.info("Authentication successful for %s", _mask_identifier(self.username))
            return True
        except Exception as err:
            _LOGGER.error("Authentication failed for user %s: %s", _mask_identifier(self.username), err)
            raise DessSolarAuthError(f"Authentication failed: {err}") from err

    async def load_saved_token(self) -> bool:
        """Load cached token from persistent store if valid."""
        if not self._store:
            return False
        try:
            data = await self._store.async_load()
            if not data:
                return False
            token = data.get("token")
            secret = data.get("secret")
            expire = data.get("token_expire")
            if token and secret and expire and int(time.time()) < (expire - 300):
                self.token = token
                self.secret = secret
                self.token_expire = expire
                _LOGGER.debug("Reused cached token, valid for %ds", expire - int(time.time()))
                return True
            await self.clear_saved_token()
        except Exception as err:
            _LOGGER.debug("Failed loading cached token: %s", err)
        return False

    async def _save_token(self) -> None:
        if self._store and self.token:
            try:
                await self._store.async_save(
                    {
                        "token": self.token,
                        "secret": self.secret,
                        "token_expire": self.token_expire,
                    }
                )
            except Exception as err:
                _LOGGER.debug("Failed saving token: %s", err)

    async def clear_saved_token(self) -> None:
        if self._store:
            try:
                await self._store.async_remove()
            except Exception:
                pass
        self.token = None
        self.secret = None
        self.token_expire = None

    # --- Device & Collector Discovery Endpoints ---

    # --- Device & Collector Discovery Endpoints ---

    async def get_all_devices(self) -> list[dict[str, Any]]:
        """Fetch all devices under this account using webQueryDeviceEs and collector fallback."""
        # 1. Primary: Direct query via webQueryDeviceEs (works across all account types)
        try:
            res = await self._make_request(
                "webQueryDeviceEs",
                {"pagesize": 50, "source": "1", "i18n": "en_US"}
            )
            devices = res.get("dat", {}).get("device", [])
            if devices:
                _LOGGER.info("Discovered %d device(s) via webQueryDeviceEs", len(devices))
                return devices
        except Exception as err:
            _LOGGER.debug("Direct webQueryDeviceEs failed: %s", err)

        # 2. Fallback: Query collectors and their devices
        devices = []
        collectors = await self.get_collectors()
        for coll in collectors:
            pn = coll.get("pn")
            if not pn:
                continue
            try:
                coll_devs = await self.get_collector_devices(pn)
                for d in coll_devs:
                    d.setdefault("pn", pn)
                    d.setdefault("collalias", coll.get("collalias") or coll.get("alias"))
                    devices.append(d)
            except Exception as err:
                _LOGGER.debug("Failed getting devices for collector %s: %s", pn, err)

        return devices

    async def get_collectors(self) -> list[dict[str, Any]]:
        """Fetch all collectors under this account."""
        collectors: list[dict[str, Any]] = []

        # 1. Try webQueryCollectorsEs without pid
        try:
            coll_res = await self._make_request(
                "webQueryCollectorsEs", {"pagesize": 50, "source": "1", "i18n": "en_US"}
            )
            batch = coll_res.get("dat", {}).get("collector", [])
            if batch:
                collectors.extend(batch)
                return collectors
        except Exception as err:
            _LOGGER.debug("Direct webQueryCollectorsEs without pid skipped: %s", err)

        # 2. Fallback to queryPlants
        try:
            plants_res = await self._make_request("queryPlants", {"pagesize": 50})
            plants = plants_res.get("dat", {}).get("plant", [])
            for plant in plants:
                pid = plant.get("pid")
                if not pid:
                    continue
                page = 0
                while True:
                    coll_res = await self._make_request(
                        "webQueryCollectorsEs", {"pid": pid, "page": page, "pagesize": 50, "source": "1"}
                    )
                    dat = coll_res.get("dat", {})
                    batch = dat.get("collector", [])
                    if not batch:
                        break
                    collectors.extend(batch)
                    total = dat.get("total", 0)
                    if len(collectors) >= total or len(batch) < 50:
                        break
                    page += 1
        except Exception as err:
            _LOGGER.debug("queryPlants collector discovery failed: %s", err)

        return collectors

    async def get_collector_devices(self, pn: str) -> list[dict[str, Any]]:
        """Fetch devices attached to a given collector PN."""
        res = await self._make_request("queryCollectorDevices", {"pn": pn})
        return res.get("dat", {}).get("dev", [])

    # --- Telemetry Endpoints ---

    @staticmethod
    def _extract_pars_dict(dat: dict[str, Any], out: list[dict[str, Any]]) -> None:
        """Flatten nested pars dictionary tree into uniform point dictionaries."""
        pars = dat.get("pars")
        if isinstance(pars, dict):
            for group, items in pars.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            out.append({
                                "title": item.get("par") or item.get("title") or item.get("name") or item.get("id"),
                                "val": item.get("val"),
                                "unit": item.get("unit", ""),
                                "id": item.get("id", ""),
                            })
        elif isinstance(pars, list):
            for item in pars:
                if isinstance(item, dict):
                    out.append({
                        "title": item.get("par") or item.get("title") or item.get("name") or item.get("id"),
                        "val": item.get("val"),
                        "unit": item.get("unit", ""),
                        "id": item.get("id", ""),
                    })

    async def get_device_last_data(
        self, pn: str, devcode: int, devaddr: int, sn: str
    ) -> list[dict[str, Any]]:
        """Query real-time measurement telemetry points (merges queryDeviceLastData & querySPDeviceLastData)."""
        data_points: list[dict[str, Any]] = []
        existing_keys: set[str] = set()

        def _add_point(pt: dict[str, Any]) -> None:
            t = pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id")
            if not t:
                return
            key = str(t).strip().lower()
            fid = str(pt.get("id", "")).strip().lower()
            if key not in existing_keys and (not fid or fid not in existing_keys):
                data_points.append(pt)
                existing_keys.add(key)
                if fid:
                    existing_keys.add(fid)

        # 1. Try queryDeviceLastData
        try:
            params = {
                "pn": pn,
                "devcode": devcode,
                "devaddr": devaddr,
                "sn": sn,
                "i18n": "en",
            }
            res = await self._make_request("queryDeviceLastData", params)
            dat = res.get("dat")
            raw_pts: list[dict[str, Any]] = []
            if isinstance(dat, list):
                for item in dat:
                    if isinstance(item, dict):
                        raw_pts.append({
                            "title": item.get("title") or item.get("name") or item.get("par"),
                            "val": item.get("val"),
                            "unit": item.get("unit", ""),
                            "id": item.get("id", ""),
                        })
            elif isinstance(dat, dict):
                self._extract_pars_dict(dat, raw_pts)
            for p in raw_pts:
                _add_point(p)
        except Exception as err:
            _LOGGER.debug("queryDeviceLastData failed: %s", err)

        # 2. Always query querySPDeviceLastData to capture rich split-phase / inverter measurement telemetry
        try:
            params_sp = {
                "pn": pn,
                "devcode": devcode,
                "devaddr": devaddr,
                "sn": sn,
                "i18n": "en_US",
                "source": "1",
            }
            res_sp = await self._make_request("querySPDeviceLastData", params_sp)
            dat_sp = res_sp.get("dat", {})
            raw_sp_pts: list[dict[str, Any]] = []
            if isinstance(dat_sp, dict):
                self._extract_pars_dict(dat_sp, raw_sp_pts)
            elif isinstance(dat_sp, list):
                for item in dat_sp:
                    if isinstance(item, dict):
                        raw_sp_pts.append({
                            "title": item.get("title") or item.get("name") or item.get("par"),
                            "val": item.get("val"),
                            "unit": item.get("unit", ""),
                            "id": item.get("id", ""),
                        })
            for p in raw_sp_pts:
                _add_point(p)
        except Exception as err:
            _LOGGER.debug("querySPDeviceLastData failed: %s", err)

        return data_points

    async def get_device_energy_flow(
        self, pn: str, devcode: int, devaddr: int, sn: str
    ) -> list[dict[str, Any]]:
        """Fetch real-time flow power metrics (webQueryDeviceEnergyFlowEs)."""
        flow_points: list[dict[str, Any]] = []
        try:
            res = await self._make_request(
                "webQueryDeviceEnergyFlowEs",
                {"pn": pn, "devcode": devcode, "devaddr": devaddr, "sn": sn, "i18n": "en_US", "source": "1"}
            )
            dat = res.get("dat", {})
            for group_key in ("bt_status", "pv_status", "gd_status", "bc_status"):
                items = dat.get(group_key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            flow_points.append({
                                "title": item.get("par") or item.get("name"),
                                "val": item.get("val"),
                                "unit": item.get("unit", ""),
                                "id": item.get("par", ""),
                            })
        except Exception as err:
            _LOGGER.debug("webQueryDeviceEnergyFlowEs failed: %s", err)
        return flow_points

    async def get_device_parameters(
        self, pn: str, devcode: int, devaddr: int, sn: str
    ) -> dict[str, dict[str, Any]]:
        """Query detailed parameter registry (queryDeviceParsEs)."""
        params = {
            "pn": pn,
            "devcode": devcode,
            "devaddr": devaddr,
            "sn": sn,
            "i18n": "en_US",
            "source": "1",
        }
        res = await self._make_request("queryDeviceParsEs", params)
        parameters = res.get("dat", {}).get("parameter", [])
        result = {}
        for p in parameters:
            name = p.get("name") or p.get("par", "")
            result[name] = {
                "value": p.get("val", ""),
                "unit": p.get("unit", ""),
                "id": p.get("par", ""),
                "name": p.get("name", ""),
            }
        return result

    async def get_device_summary_data(self, pid: int) -> dict[str, dict[str, Any]]:
        """Fetch project-wide inverter summary (webQueryDeviceEs)."""
        res = await self._make_request("webQueryDeviceEs", {"pid": pid, "pagesize": 50, "source": "1"})
        devices = res.get("dat", {}).get("device", [])
        summary: dict[str, dict[str, Any]] = {}
        for dev in devices:
            sn = dev.get("sn")
            if not sn:
                continue
            summary[sn] = {
                "energyToday": dev.get("energyToday"),
                "energyTotal": dev.get("energyTotal"),
                "energyYear": dev.get("energyYear"),
                "outpower": dev.get("outpower"),
                "status": dev.get("status"),
                "soc": dev.get("soc"),
            }
        return summary

    # --- Controls & Settings Endpoints ---

    async def get_device_control_fields(
        self, pn: str, devcode: int, devaddr: int, sn: str
    ) -> list[dict[str, Any]]:
        """Fetch available inverter control fields (queryDeviceCtrlField)."""
        params = {
            "pn": pn,
            "devcode": devcode,
            "devaddr": devaddr,
            "sn": sn,
            "i18n": "en_US",
            "source": "1",
        }
        res = await self._make_request("queryDeviceCtrlField", params)
        dat = res.get("dat")
        if isinstance(dat, dict):
            return dat.get("field", [])
        if isinstance(dat, list):
            return dat
        return []

    async def get_device_control_value(
        self, pn: str, devcode: int, devaddr: int, sn: str, field_id: str
    ) -> dict[str, Any]:
        """Fetch active value of one control setting (queryDeviceCtrlValue)."""
        params = {
            "pn": pn,
            "devcode": devcode,
            "devaddr": devaddr,
            "sn": sn,
            "id": field_id,
            "i18n": "en_US",
            "source": "1",
        }
        res = await self._make_request("queryDeviceCtrlValue", params, timeout_seconds=3)
        return res.get("dat", {})

    async def execute_device_control(
        self,
        pn: str,
        devcode: int,
        devaddr: int,
        sn: str,
        field_id: str,
        value: str | int | float,
    ) -> bool:
        """Send inverter configuration update (ctrlDevice)."""
        params = {
            "pn": pn,
            "devcode": devcode,
            "devaddr": devaddr,
            "sn": sn,
            "id": field_id,
            "val": str(value),
            "i18n": "en_US",
            "source": "1",
        }
        _LOGGER.info(
            "Executing inverter setting '%s' = %s on %s (devcode %s)",
            field_id,
            value,
            sn,
            devcode,
        )
        res = await self._make_request("ctrlDevice", params)
        err = res.get("err", 0)
        return err == 0

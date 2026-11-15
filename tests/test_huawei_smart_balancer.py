import difflib
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def extract_c_block(text: str, marker: str) -> str:
    idx = text.find(marker)
    return text[idx : idx + 1500] if idx >= 0 else ""


class TestHardwareFirmwareContracts(unittest.TestCase):
    def test_smart_balancer_header_exists_with_explicit_fsm(self):
        hdr = ROOT / "huawei_smart_balancer.h"
        self.assertTrue(hdr.exists(), "huawei_smart_balancer.h must exist")
        src = hdr.read_text(encoding="utf-8")
        for sym in (
            "enum class PackBalMode",
            "NORMAL_OPEN",
            "DISCH_THROTTLED",
            "DISCH_RELEASING",
            "CHG_DIVERTING",
            "RESERVE_CUTOFF",
            "class HuaweiSmartBalancer",
            "class PylontechDclStabilizer",
            "active_wake_",
            "hog_epochs",
            "boot_settled_",
            "std::max(14.0f, weighted_fair_a * 1.65f)",
            "in.max_single_pack_disch_a >= 21.0f",
            "in.disch_curr_delta >= 17.0f",
            "reassert_disch",
            "reassert_chg",
        ):
            self.assertIn(sym, src)

    def test_shared_wake_cooldown_never_wiped_on_clear(self):
        shared = (ROOT / "tcan_telemetry_shared.h").read_text(encoding="utf-8")
        # Ensure force_m3 == 0 branch never zeroes g_eq_last_mode3_ms[idx]
        slot_fn = shared[shared.index("exec_huawei_bms_equalizer_slot") :]
        self.assertNotIn("g_eq_last_mode3_ms[idx] = 0;", slot_fn)
        self.assertIn("huawei_smart_balancer.h", shared)
        self.assertIn("g_eq_wake_attempts", slot_fn)
        self.assertIn("g_eq_reassert_disch", shared)
        self.assertIn("15000UL", slot_fn)
        self.assertIn("if (idx >= 4)", slot_fn)
        # Never issue FC 0x10 write to 0x000E inside equalizer slot (Huawei ESM rejects with Ex 2)
        slot_body = slot_fn[: slot_fn.index("apply_remote_pack8_cmd")]
        slot_code_only = re.sub(r"//.*", "", slot_body)
        self.assertNotIn("0x000E", slot_code_only)
        self.assertIn("Wake RAM unlock refresh", slot_code_only)
        for ms in ("180000UL", "300000UL", "600000UL"):
            self.assertIn(ms, slot_fn)
        self.assertIn("apply_remote_pack8_cmd", shared)

    def test_no_mode3_wake_when_already_mode3_in_8pack_and_bridge(self):
        yaml_8p = (ROOT / "huawei-esm-t-can485-8pack-prod.yaml").read_text(encoding="utf-8")
        self.assertNotIn("(mode_int != 3 || (pi > -0.5f && total_i <= -8.0f))", yaml_8p)
        self.assertIn("HuaweiSmartBalancer s_smart_balancer", yaml_8p)
        self.assertIn("s_smart_balancer.evaluate", yaml_8p)

        yaml_br = (ROOT / "huawei-esm-tcan-inverter-bridge-prod.yaml").read_text(encoding="utf-8")
        self.assertIn('apply_remote_pack8_cmd(fm3, dcoef, ccoef, "CAN 0x35F")', yaml_br)
        self.assertIn('apply_remote_pack8_cmd(fm3, dcoef, ccoef, "UDP 18888")', yaml_br)
        self.assertIn("for (int iter = 0; iter < 8; iter++)", yaml_br)
        self.assertIn("g_last_can_frame_ms", yaml_br)
        self.assertIn("std::isfinite(pi8) && std::isfinite(psoc8)", yaml_br)
        # Local Pack 8 wake fallback must only trigger when m8 != 3 continuously >= 30s
        fallback = extract_c_block(yaml_br, "Local Autonomous Equalizer Fallback for Pack 8")
        self.assertNotEqual(fallback, "")
        self.assertIn("m8 != 3", fallback)
        self.assertNotIn("m8 != 3 || pi8 >", fallback)
        self.assertIn(">= 30000", fallback)
        wake_script = extract_c_block(yaml_br, "- id: wake_pack8_script")
        self.assertIn("< 180000", wake_script)

    def test_pylontech_dcl_uses_schmitt_stabilizer(self):
        pylon = (ROOT / "components_v4" / "pylontech_emulator" / "pylontech_emulator.h").read_text(
            encoding="utf-8"
        )
        self.assertIn("v6.6.0-PRO", pylon)
        self.assertIn("PylontechDclStabilizer", pylon)
        self.assertIn("dcl_stabilizer_.evaluate", pylon)
        chg_fn = pylon[pylon.index("get_dynamic_charge_limit_100ma") : pylon.index("get_dynamic_discharge_limit_100ma")]
        self.assertNotIn("DCL_DELTA_V", chg_fn)
        self.assertNotIn("DCL_KNEE_3.02V", chg_fn)
        self.assertIn("chg_curr_delta >= 22.0f", chg_fn)
        self.assertIn("pi >= 0.5f", chg_fn)
        self.assertIn("last_chg_guard_mask_", chg_fn)
        self.assertIn('ESP_LOGV(TAG, "Inverter RX', pylon)
        self.assertNotIn('ESP_LOGI(TAG, "Inverter RX', pylon)

    def test_public_and_prod_yaml_pairs_only_differ_in_wifi_credentials(self):
        pairs = [
            ("huawei-esm-t-can485-8pack.yaml", "huawei-esm-t-can485-8pack-prod.yaml"),
            ("huawei-esm-tcan-inverter-bridge.yaml", "huawei-esm-tcan-inverter-bridge-prod.yaml"),
        ]
        for pub_name, prod_name in pairs:
            pub = (ROOT / pub_name).read_text(encoding="utf-8").splitlines()
            prod = (ROOT / prod_name).read_text(encoding="utf-8").splitlines()
            diff_lines = [
                line
                for line in difflib.unified_diff(pub, prod, pub_name, prod_name, n=0)
                if (line.startswith("+") or line.startswith("-"))
                and not line.startswith("+++")
                and not line.startswith("---")
            ]
            # Only ssid and password lines (2 removed + 2 added = 4 changed lines) may differ
            self.assertEqual(
                len(diff_lines),
                4,
                f"{pub_name} and {prod_name} drifted outside Wi-Fi credentials:\n"
                + "\n".join(diff_lines[:20]),
            )
            for dl in diff_lines:
                self.assertRegex(dl, r"(ssid:|password:)")


if __name__ == "__main__":
    unittest.main()

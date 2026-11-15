#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace huawei_smart_ctrl {

enum class PackBalMode : uint8_t {
  NORMAL_OPEN = 0,
  DISCH_THROTTLED = 1,
  DISCH_RELEASING = 2,
  CHG_DIVERTING = 3,
  RESERVE_CUTOFF = 4,
};

struct PackInput {
  bool online{false};
  float current_a{0.0f};   // < 0 discharging, > 0 charging
  float voltage_v{0.0f};   // cell-stack voltage (0x0001)
  float soc_pct{0.0f};     // 0..100
  int mode{3};             // 0x000E: 0=Sleep, 1=Offline, 2=Charge, 3=Discharge, 4=Standby
};

struct PackControl {
  PackBalMode disch_state{PackBalMode::NORMAL_OPEN};
  bool chg_diverting{false};
  uint16_t disch_coef{1000};
  uint16_t chg_coef{1000};
  bool force_wake{false};
  uint8_t sleep_epochs{0};
  uint8_t hog_epochs{0};
  bool dirty{false};
  bool reassert_disch{false};
  bool reassert_chg{false};

  PackBalMode summary_mode() const {
    if (disch_state == PackBalMode::RESERVE_CUTOFF) return PackBalMode::RESERVE_CUTOFF;
    if (disch_state == PackBalMode::DISCH_THROTTLED) return PackBalMode::DISCH_THROTTLED;
    if (disch_state == PackBalMode::DISCH_RELEASING) return PackBalMode::DISCH_RELEASING;
    if (chg_diverting) return PackBalMode::CHG_DIVERTING;
    return PackBalMode::NORMAL_OPEN;
  }
};

struct BankBalanceSummary {
  bool balance_eval_ran{false};
  uint8_t cmd_mask{0};
  float total_i{0.0f};
  float fair_disch_i{0.0f};
  float min_pi{0.0f};
  int lead_disch_pack{-1};
  int usable_disch{0};
  int sleeping_m2{0};
  bool charge_divert_active{false};
  bool charge_voltage_done{false};
};

class HuaweiSmartBalancer {
 public:
  static constexpr uint32_t kBootSettleMs = 35000;
  static constexpr uint32_t kEvalEpochMs = 38000;

  static constexpr float kReserveCutoffSoc = 25.0f;
  static constexpr float kReserveCutoffV = 48.0f;
  static constexpr float kReserveRecoverSoc = 30.0f;
  static constexpr float kReserveRecoverV = 49.0f;

  static constexpr uint16_t kOpenCoef = 1000;
  static constexpr uint16_t kDischMinCoef = 60;      // 6.0A floor keeps ESM DC/DC stage smoothly biased
  static constexpr uint16_t kChgMinCoef = 30;        // 3.0A floor for top-balancing high packs
  static constexpr uint16_t kDischDeadbandCoef = 20; // +/- 2.0A avoids redundant Modbus writes
  static constexpr uint16_t kChgDeadbandCoef = 20;
  static constexpr uint16_t kReleaseStepCoef = 50;   // +5.0A/epoch stepped ramp prevents -21A surge
  static constexpr uint16_t kReleaseSnapCoef = 280;  // Safe to open to 100A once >= 28A with no hogging

  static constexpr float kIdleReleaseTotalA = -3.0f;
  static constexpr float kLightLoadReleaseTotalA = -10.0f;
  static constexpr float kHighSocBonusGap = 4.0f;
  static constexpr float kInvertedSocGap = 5.0f;

  void reset() {
    boot_initialized_ = false;
    boot_settled_ = false;
    eval_initialized_ = false;
    boot_ms_ = 0;
    last_eval_ms_ = 0;
    charge_divert_active_ = false;
    charge_voltage_done_ = false;
    for (int i = 0; i < 8; i++) {
      packs_[i] = PackControl{};
      prev_online_[i] = false;
      active_wake_[i] = false;
    }
  }

  const PackControl &pack(int idx) const { return packs_[idx]; }

  BankBalanceSummary evaluate(const PackInput in[8], uint32_t now_ms) {
    BankBalanceSummary sum{};
    if (!boot_initialized_) {
      boot_initialized_ = true;
      boot_ms_ = now_ms;
    }

    // Detect offline -> online transitions while preserving persistent active_wake_ across non-eval ticks
    for (int i = 0; i < 8; i++) {
      packs_[i].dirty = false;
      packs_[i].reassert_disch = false;
      packs_[i].reassert_chg = false;
      packs_[i].force_wake = active_wake_[i];
      if (in[i].online && !prev_online_[i]) {
        packs_[i].dirty = true;
      } else if (!in[i].online && prev_online_[i]) {
        active_wake_[i] = false;
        packs_[i].force_wake = false;
        packs_[i].sleep_epochs = 0;
        packs_[i].hog_epochs = 0;
      }
      prev_online_[i] = in[i].online;
    }

    // Safety Pass (runs on every tick): Individual 25% / 48.0V reserve cutoff
    for (int i = 0; i < 8; i++) {
      if (!in[i].online || !valid_pack(in[i])) continue;
      PackControl &pc = packs_[i];
      if (in[i].soc_pct <= kReserveCutoffSoc || in[i].voltage_v <= kReserveCutoffV) {
        bool wake_cleared = active_wake_[i];
        active_wake_[i] = false;
        pc.force_wake = false;
        if (pc.disch_state != PackBalMode::RESERVE_CUTOFF || pc.disch_coef != 0 || wake_cleared) {
          pc.disch_state = PackBalMode::RESERVE_CUTOFF;
          pc.disch_coef = 0;
          pc.sleep_epochs = 0;
          pc.hog_epochs = 0;
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      } else if (pc.disch_state == PackBalMode::RESERVE_CUTOFF &&
                 in[i].soc_pct >= kReserveRecoverSoc && in[i].voltage_v >= kReserveRecoverV) {
        pc.disch_state = PackBalMode::NORMAL_OPEN;
        pc.disch_coef = kOpenCoef;
        pc.dirty = true;
        sum.cmd_mask |= (uint8_t)(1U << i);
      }
    }

    // Aggregate telemetry for reporting and epoch pacing
    float min_usable_soc = 100.0f;
    float max_usable_soc = 0.0f;
    float total_headroom = 0.0f;
    float min_all_soc = 100.0f;
    float max_all_soc = 0.0f;
    int all_online = 0;

    for (int i = 0; i < 8; i++) {
      if (!in[i].online || !valid_pack(in[i])) continue;
      all_online++;
      sum.total_i += in[i].current_a;
      if (in[i].soc_pct < min_all_soc) min_all_soc = in[i].soc_pct;
      if (in[i].soc_pct > max_all_soc) max_all_soc = in[i].soc_pct;
      if (in[i].current_a < sum.min_pi) {
        sum.min_pi = in[i].current_a;
        sum.lead_disch_pack = i + 1;
      }
      if (packs_[i].disch_state != PackBalMode::RESERVE_CUTOFF &&
          in[i].soc_pct > kReserveCutoffSoc && in[i].voltage_v > kReserveCutoffV) {
        sum.usable_disch++;
        if (in[i].soc_pct < min_usable_soc) min_usable_soc = in[i].soc_pct;
        if (in[i].soc_pct > max_usable_soc) max_usable_soc = in[i].soc_pct;
        total_headroom += std::max(1.0f, in[i].soc_pct - kReserveCutoffSoc);
        if (in[i].mode != 3 && in[i].soc_pct > 28.0f && in[i].voltage_v > 48.5f) {
          sum.sleeping_m2++;
        }
      }
    }

    sum.fair_disch_i = (sum.usable_disch > 0) ? (sum.total_i / (float)sum.usable_disch) : 0.0f;
    sum.charge_divert_active = charge_divert_active_;
    sum.charge_voltage_done = charge_voltage_done_;

    // Wait once for initial full 7-pack poll epoch before running balancing logic (rollover-safe)
    if (!boot_settled_) {
      if ((uint32_t)(now_ms - boot_ms_) < kBootSettleMs) {
        return sum;
      }
      boot_settled_ = true;
    }
    if (eval_initialized_ && ((uint32_t)(now_ms - last_eval_ms_) < kEvalEpochMs)) {
      return sum;
    }
    if (all_online == 0) {
      return sum;
    }

    eval_initialized_ = true;
    last_eval_ms_ = now_ms;
    sum.balance_eval_ran = true;

    for (int i = 0; i < 8; i++) {
      if (!in[i].online || !valid_pack(in[i])) continue;
      if (packs_[i].disch_state == PackBalMode::RESERVE_CUTOFF && in[i].current_a <= -3.5f) {
        packs_[i].reassert_disch = true;
        packs_[i].dirty = true;
        sum.cmd_mask |= (uint8_t)(1U << i);
      }
    }

    evaluate_discharge_plane(in, total_headroom, min_usable_soc, max_usable_soc, sum);
    evaluate_charge_plane(in, min_all_soc, max_all_soc, sum);

    sum.charge_divert_active = charge_divert_active_;
    sum.charge_voltage_done = charge_voltage_done_;
    return sum;
  }

 private:
  bool boot_initialized_{false};
  bool boot_settled_{false};
  bool eval_initialized_{false};
  uint32_t boot_ms_{0};
  uint32_t last_eval_ms_{0};
  bool charge_divert_active_{false};
  bool charge_voltage_done_{false};
  PackControl packs_[8]{};
  bool prev_online_[8]{false};
  bool active_wake_[8]{false};

  static bool valid_pack(const PackInput &p) {
    return std::isfinite(p.current_a) && std::isfinite(p.voltage_v) && std::isfinite(p.soc_pct) &&
           p.voltage_v > 20.0f && p.voltage_v < 65.0f && p.soc_pct >= 0.0f && p.soc_pct <= 100.0f;
  }

  static uint16_t quantize_coef(float amps, uint16_t min_coef, uint16_t max_coef) {
    int32_t rounded = ((int32_t)(amps * 10.0f + 5.0f) / 10) * 10;
    if (rounded < (int32_t)min_coef) rounded = (int32_t)min_coef;
    if (rounded > (int32_t)max_coef) rounded = (int32_t)max_coef;
    return (uint16_t)rounded;
  }

  void evaluate_discharge_plane(const PackInput in[8],
                                float total_headroom,
                                float min_usable_soc,
                                float max_usable_soc,
                                BankBalanceSummary &sum) {
    if (sum.total_i > kIdleReleaseTotalA || sum.usable_disch < 2) {
      for (int i = 0; i < 8; i++) {
        PackControl &pc = packs_[i];
        pc.sleep_epochs = 0;
        pc.hog_epochs = 0;
        bool wake_cleared = active_wake_[i];
        active_wake_[i] = false;
        pc.force_wake = false;
        if (pc.disch_state == PackBalMode::DISCH_THROTTLED ||
            pc.disch_state == PackBalMode::DISCH_RELEASING || wake_cleared) {
          if (pc.disch_state == PackBalMode::DISCH_THROTTLED ||
              pc.disch_state == PackBalMode::DISCH_RELEASING) {
            pc.disch_state = PackBalMode::NORMAL_OPEN;
          }
          if (pc.disch_coef != kOpenCoef && pc.disch_state != PackBalMode::RESERVE_CUTOFF) {
            pc.disch_coef = kOpenCoef;
          }
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      }
      return;
    }

    // Track how active packs and max-SOC packs are sharing the load
    int active_disch_packs = 0;
    float max_soc_pack_avg_disch = 0.0f;
    int max_soc_pack_cnt = 0;
    for (int i = 0; i < 8; i++) {
      if (!in[i].online || !valid_pack(in[i])) continue;
      if (packs_[i].disch_state == PackBalMode::RESERVE_CUTOFF) continue;
      if (in[i].current_a <= -0.8f) active_disch_packs++;
      if (in[i].soc_pct >= max_usable_soc - 2.0f) {
        max_soc_pack_avg_disch += (in[i].current_a < 0.0f) ? (-in[i].current_a) : 0.0f;
        max_soc_pack_cnt++;
      }
    }
    if (max_soc_pack_cnt > 0) {
      max_soc_pack_avg_disch /= (float)max_soc_pack_cnt;
    }

    float abs_total_a = -sum.total_i;
    float equal_fair_a = abs_total_a / (float)sum.usable_disch;

    for (int i = 0; i < 8; i++) {
      if (!in[i].online || !valid_pack(in[i])) continue;
      PackControl &pc = packs_[i];
      if (pc.disch_state == PackBalMode::RESERVE_CUTOFF) continue;

      float disch_a = (in[i].current_a < 0.0f) ? (-in[i].current_a) : 0.0f;
      float headroom = std::max(1.0f, in[i].soc_pct - kReserveCutoffSoc);
      float weight = std::clamp((headroom * (float)sum.usable_disch) / std::max(1.0f, total_headroom), 0.55f, 1.75f);
      float weighted_fair_a = equal_fair_a * weight;

      bool is_high_helper = (in[i].soc_pct >= min_usable_soc + kHighSocBonusGap);
      bool is_low_soc_hog = (in[i].soc_pct <= max_usable_soc - kInvertedSocGap) &&
                            (max_soc_pack_avg_disch < std::max(1.0f, equal_fair_a * 0.45f));

      float allow_limit_a = std::max(11.5f, weighted_fair_a * 1.85f);
      if (is_high_helper) {
        allow_limit_a = std::max(18.0f, weighted_fair_a * 2.25f);
      } else if (is_low_soc_hog) {
        allow_limit_a = std::max(7.5f, weighted_fair_a * 1.45f);
      }
      if (sum.sleeping_m2 > 0 && abs_total_a >= 12.0f) {
        allow_limit_a = std::min(allow_limit_a, std::max(8.0f, weighted_fair_a * 1.50f));
      }

      float desired_cap_a = (is_high_helper && sum.sleeping_m2 == 0)
                                ? std::max(14.0f, weighted_fair_a * 1.65f)
                                : (is_high_helper
                                       ? std::max(7.5f, weighted_fair_a * 1.45f)
                                       : std::max(6.0f, weighted_fair_a * 1.35f));
      uint16_t desired_coef = quantize_coef(desired_cap_a, kDischMinCoef, 400);

      // Sleep watchdog: strictly Mode != 3 sustained >= 2 consecutive epochs under >= 12A load
      if (in[i].mode != 3 && abs_total_a >= 12.0f && in[i].soc_pct > 28.0f && in[i].voltage_v > 48.5f) {
        if (pc.sleep_epochs < 250) pc.sleep_epochs++;
        if (pc.sleep_epochs >= 2) {
          active_wake_[i] = true;
          pc.force_wake = true;
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      } else {
        pc.sleep_epochs = 0;
        if (active_wake_[i]) {
          active_wake_[i] = false;
          pc.force_wake = false;
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      }

      if (pc.disch_state == PackBalMode::NORMAL_OPEN) {
        bool heavy_imbalance = (abs_total_a >= 22.0f && disch_a >= 10.0f &&
                                disch_a >= weighted_fair_a * 1.55f && active_disch_packs <= 3);
        bool hog_cond = (abs_total_a >= 12.0f && disch_a >= allow_limit_a) || heavy_imbalance;
        if (hog_cond) {
          if (pc.hog_epochs < 250) pc.hog_epochs++;
        } else {
          pc.hog_epochs = 0;
        }
        // Require 2-epoch persistence against polling skew, except fast-clamp severe single-pack surges >= 20A
        bool fast_surge = (abs_total_a >= 12.0f && disch_a >= 20.0f);
        if (pc.hog_epochs >= 2 || fast_surge) {
          pc.disch_state = PackBalMode::DISCH_THROTTLED;
          pc.disch_coef = desired_coef;
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      } else if (pc.disch_state == PackBalMode::DISCH_THROTTLED) {
        pc.hog_epochs = 0;
        float cur_lim_a = pc.disch_coef * 0.1f;
        bool riding_cap = (disch_a >= (cur_lim_a * 0.78f - 0.5f));
        bool severe_condition = (disch_a >= allow_limit_a) || (sum.sleeping_m2 > 0 && abs_total_a >= 12.0f);

        if ((sum.total_i > kLightLoadReleaseTotalA && !severe_condition) ||
            (!riding_cap && disch_a < allow_limit_a * 0.85f && sum.sleeping_m2 == 0)) {
          pc.disch_state = PackBalMode::DISCH_RELEASING;
          uint16_t next_c = (pc.disch_coef >= kReleaseSnapCoef)
                                ? kOpenCoef
                                : std::min((uint16_t)kOpenCoef, (uint16_t)(pc.disch_coef + kReleaseStepCoef));
          if (next_c >= kOpenCoef) {
            pc.disch_state = PackBalMode::NORMAL_OPEN;
          }
          if (next_c != pc.disch_coef) {
            pc.disch_coef = next_c;
            pc.dirty = true;
            sum.cmd_mask |= (uint8_t)(1U << i);
          }
        } else {
          // Track load changes within deadband; clamp downward immediately, slew upward (+5A/epoch)
          int32_t diff = (int32_t)desired_coef - (int32_t)pc.disch_coef;
          if (std::abs(diff) >= (int32_t)kDischDeadbandCoef) {
            uint16_t next_c = (diff > 0)
                                  ? std::min(desired_coef, (uint16_t)(pc.disch_coef + kReleaseStepCoef))
                                  : desired_coef;
            if (next_c != pc.disch_coef) {
              pc.disch_coef = next_c;
              pc.dirty = true;
              sum.cmd_mask |= (uint8_t)(1U << i);
            }
          }
          // Closed-loop compliance guard: re-assert active cap if BMS ignores limit (e.g. peer reboot/dropped packet)
          if (pc.disch_coef < kOpenCoef && disch_a >= (pc.disch_coef * 0.1f + 3.5f)) {
            pc.reassert_disch = true;
            pc.dirty = true;
            sum.cmd_mask |= (uint8_t)(1U << i);
          }
        }
      } else if (pc.disch_state == PackBalMode::DISCH_RELEASING) {
        pc.hog_epochs = 0;
        // Closed-loop overshoot guard: if stepping UP caused surge/single-pack monopoly, back off smoothly!
        bool release_overshoot = (disch_a >= allow_limit_a) ||
                                 (abs_total_a >= 16.0f && disch_a >= 13.0f && active_disch_packs <= 2);
        if (release_overshoot) {
          uint16_t backoff_c = (pc.disch_coef > kDischMinCoef + 30)
                                   ? (uint16_t)(pc.disch_coef - 30)
                                   : kDischMinCoef;
          pc.disch_state = PackBalMode::DISCH_THROTTLED;
          bool violated = (backoff_c < kOpenCoef && disch_a >= (backoff_c * 0.1f + 3.5f));
          if (backoff_c != pc.disch_coef || violated) {
            pc.disch_coef = backoff_c;
            if (violated) pc.reassert_disch = true;
            pc.dirty = true;
            sum.cmd_mask |= (uint8_t)(1U << i);
          }
        } else if (pc.disch_coef >= kReleaseSnapCoef || sum.total_i > kLightLoadReleaseTotalA) {
          pc.disch_state = PackBalMode::NORMAL_OPEN;
          if (pc.disch_coef != kOpenCoef) {
            pc.disch_coef = kOpenCoef;
            pc.dirty = true;
            sum.cmd_mask |= (uint8_t)(1U << i);
          }
        } else {
          uint16_t next_c = std::min((uint16_t)kOpenCoef, (uint16_t)(pc.disch_coef + kReleaseStepCoef));
          if (next_c >= kOpenCoef) {
            pc.disch_state = PackBalMode::NORMAL_OPEN;
          }
          if (next_c != pc.disch_coef) {
            pc.disch_coef = next_c;
            pc.dirty = true;
            sum.cmd_mask |= (uint8_t)(1U << i);
          }
        }
      }
    }
  }

  void evaluate_charge_plane(const PackInput in[8],
                             float min_all_soc,
                             float max_all_soc,
                             BankBalanceSummary &sum) {
    if (sum.total_i < 2.0f) {
      charge_voltage_done_ = false;
    }

    float spread = max_all_soc - min_all_soc;
    int high_count = 0;
    int hungry_count = 0;
    float max_hungry_v = 0.0f;
    bool is_high_mask[8] = {false};

    for (int i = 0; i < 8; i++) {
      if (!in[i].online || !valid_pack(in[i])) continue;
      bool is_high = (in[i].soc_pct >= 92.0f && in[i].soc_pct >= (min_all_soc + 7.0f)) ||
                     (in[i].soc_pct >= 86.0f && min_all_soc < 78.0f && in[i].soc_pct >= (min_all_soc + 12.0f)) ||
                     (in[i].soc_pct >= (min_all_soc + 15.0f)) ||
                     (in[i].voltage_v >= 53.0f && in[i].soc_pct >= (min_all_soc + 5.0f));
      if (is_high) {
        is_high_mask[i] = true;
        high_count++;
      } else {
        hungry_count++;
        if (in[i].voltage_v > max_hungry_v) max_hungry_v = in[i].voltage_v;
      }
    }

    if (hungry_count > 0) {
      if (max_hungry_v >= 53.20f) charge_voltage_done_ = true;
      else if (max_hungry_v < 51.80f) charge_voltage_done_ = false;
    }

    if (!charge_divert_active_) {
      if (sum.total_i >= 5.0f && spread >= 8.0f && min_all_soc < 92.0f &&
          !charge_voltage_done_ && high_count > 0 && hungry_count > 0) {
        charge_divert_active_ = true;
      }
    } else {
      if (sum.total_i < 2.5f || spread <= 4.0f || min_all_soc >= 95.0f ||
          charge_voltage_done_ || high_count == 0 || hungry_count == 0) {
        charge_divert_active_ = false;
      }
    }

    if (charge_divert_active_ && high_count > 0 && hungry_count > 0 && !charge_voltage_done_) {
      float hungry_target_a = 20.0f * (float)hungry_count;
      float excess_a = std::max(0.0f, sum.total_i - hungry_target_a);
      float per_high_a = excess_a / (float)high_count;
      uint16_t dyn_chg_coef = quantize_coef(per_high_a, kChgMinCoef, kOpenCoef);

      for (int i = 0; i < 8; i++) {
        if (!in[i].online || !valid_pack(in[i])) continue;
        PackControl &pc = packs_[i];
        if (is_high_mask[i]) {
          int32_t diff = (int32_t)dyn_chg_coef - (int32_t)pc.chg_coef;
          bool violated = (pc.chg_diverting && pc.chg_coef < kOpenCoef &&
                           in[i].current_a >= (pc.chg_coef * 0.1f + 3.5f));
          if (!pc.chg_diverting || std::abs(diff) >= (int32_t)kChgDeadbandCoef || violated) {
            pc.chg_diverting = true;
            pc.chg_coef = dyn_chg_coef;
            if (violated) pc.reassert_chg = true;
            pc.dirty = true;
            sum.cmd_mask |= (uint8_t)(1U << i);
          }
        } else if (pc.chg_diverting || pc.chg_coef < kOpenCoef) {
          pc.chg_diverting = false;
          pc.chg_coef = kOpenCoef;
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      }
    } else {
      charge_divert_active_ = false;
      for (int i = 0; i < 8; i++) {
        PackControl &pc = packs_[i];
        if (pc.chg_diverting || pc.chg_coef < kOpenCoef) {
          pc.chg_diverting = false;
          pc.chg_coef = kOpenCoef;
          pc.dirty = true;
          sum.cmd_mask |= (uint8_t)(1U << i);
        }
      }
    }
  }
};

struct DclInput {
  float soc_pct{100.0f};
  float voltage_v{51.2f};
  float temp_c{25.0f};
  float current_a{0.0f};
  float min_pack_v{0.0f};
  float pack_delta_v{0.0f};
  uint16_t min_cell_mv{0};
  float max_single_pack_disch_a{0.0f};
  float disch_curr_delta{0.0f};
  int online_packs_count{0};
  int active_disch_count{0};
};

struct DclOutput {
  uint16_t limit_100ma{2500};
  const char *reason{"DISCHARGE_NORMAL (250A)"};
  bool tier_changed{false};
};

class PylontechDclStabilizer {
 public:
  static constexpr uint32_t kUpwardDwellMs = 10000;

  void reset() {
    initialized_ = false;
    dv_tier_ = 0;
    cd_tier_ = 0;
    surge_active_ = false;
    committed_limit_ = 2500;
    committed_reason_ = "DISCHARGE_NORMAL (250A)";
    last_change_ms_ = 0;
  }

  DclOutput evaluate(const DclInput &in, uint32_t now_ms) {
    DclOutput out{};

    // 1. Schmitt triggers for pack voltage spread and active current imbalance
    if (dv_tier_ == 0) {
      if (in.pack_delta_v >= 0.70f) dv_tier_ = 2;
      else if (in.pack_delta_v >= 0.50f) dv_tier_ = 1;
    } else if (dv_tier_ == 1) {
      if (in.pack_delta_v >= 0.70f) dv_tier_ = 2;
      else if (in.pack_delta_v <= 0.36f) dv_tier_ = 0;
    } else {
      if (in.pack_delta_v <= 0.36f) dv_tier_ = 0;
      else if (in.pack_delta_v <= 0.52f) dv_tier_ = 1;
    }

    bool valid_curr_compare = (in.active_disch_count >= 2 && in.current_a <= -12.0f);
    if (!valid_curr_compare) {
      if (in.active_disch_count < 2 || in.current_a > -10.0f) cd_tier_ = 0;
    } else if (cd_tier_ == 0) {
      if (in.disch_curr_delta >= 17.0f) cd_tier_ = 2;
      else if (in.disch_curr_delta >= 12.0f) cd_tier_ = 1;
    } else if (cd_tier_ == 1) {
      if (in.disch_curr_delta >= 17.0f) cd_tier_ = 2;
      else if (in.disch_curr_delta <= 8.5f) cd_tier_ = 0;
    } else {
      if (in.disch_curr_delta <= 8.5f) cd_tier_ = 0;
      else if (in.disch_curr_delta <= 13.0f) cd_tier_ = 1;
    }

    if (!surge_active_) {
      if ((in.max_single_pack_disch_a >= 18.0f && in.disch_curr_delta >= 10.0f) ||
          in.max_single_pack_disch_a >= 21.0f) {
        surge_active_ = true;
      }
    } else {
      if (in.max_single_pack_disch_a <= 15.0f &&
          (in.disch_curr_delta <= 11.0f || in.max_single_pack_disch_a <= 14.0f)) {
        surge_active_ = false;
      }
    }

    // 2. Select tightest candidate limit and matching authoritative reason
    uint16_t raw_limit = 2500;
    const char *raw_reason = "DISCHARGE_NORMAL (250A)";
    bool emergency_or_knee = false;

    auto pick_tighter = [&](uint16_t cand_limit, const char *cand_reason, bool is_safety) {
      if (cand_limit < raw_limit) {
        raw_limit = cand_limit;
        raw_reason = cand_reason;
        if (is_safety) emergency_or_knee = true;
      }
    };

    // Priority Safety Knee & Low-Voltage Floor (bypasses upward dwell)
    if (in.min_cell_mv > 1500 && in.min_cell_mv <= 3020) {
      pick_tighter(200, "DCL_KNEE_3.02V (20A)", true);
    } else if (in.soc_pct <= 18.0f || in.voltage_v <= 47.5f ||
               (in.min_pack_v > 20.0f && in.min_pack_v <= 47.0f) ||
               (in.min_cell_mv > 1500 && in.min_cell_mv <= 3080)) {
      pick_tighter(400, "DCL_FLOOR_3.08V (40A)", true);
    } else if (in.soc_pct <= 24.0f || in.voltage_v <= 48.0f ||
               (in.min_pack_v > 20.0f && in.min_pack_v <= 47.5f) ||
               (in.min_cell_mv > 1500 && in.min_cell_mv <= 3150) ||
               (in.temp_c >= 50.0f)) {
      pick_tighter(800, "DCL_SOFT_3.15V (80A)", true);
    } else if (in.min_cell_mv > 1500 && in.min_cell_mv <= 3200) {
      pick_tighter(1400, "DCL_STEP_3.20V (140A)", true);
    }

    if (surge_active_) {
      uint16_t balanced_cap = (uint16_t)std::max(800, in.online_packs_count * 80);
      pick_tighter(balanced_cap,
                   (in.max_single_pack_disch_a >= 16.0f && in.disch_curr_delta < 5.0f)
                       ? "DCL_OUTLIER_CLAMP (80A)"
                       : "DCL_PACK_EQUALIZING (80A)",
                   false);
    }

    if (cd_tier_ == 2) pick_tighter(800, "DCL_CURR_IMBALANCE (80A)", false);
    else if (cd_tier_ == 1) pick_tighter(1000, "DCL_CURR_IMBALANCE (100A)", false);

    if (dv_tier_ == 2) pick_tighter(800, "DCL_DELTA_V (80A)", false);
    else if (dv_tier_ == 1) pick_tighter(1000, "DCL_DELTA_V (100A)", false);

    // 3. Apply instantaneous drop on tightening, 10s dwell on upward recovery (rollover-safe)
    bool accept = false;
    if (!initialized_ || emergency_or_knee || raw_limit < committed_limit_) {
      accept = (!initialized_ || raw_limit != committed_limit_ || raw_reason != committed_reason_);
    } else if (raw_limit > committed_limit_) {
      accept = ((uint32_t)(now_ms - last_change_ms_) >= kUpwardDwellMs);
    } else if (raw_reason != committed_reason_) {
      accept = ((uint32_t)(now_ms - last_change_ms_) >= kUpwardDwellMs);
    }

    if (accept) {
      out.tier_changed = initialized_ && (committed_reason_ != raw_reason || committed_limit_ != raw_limit);
      initialized_ = true;
      committed_limit_ = raw_limit;
      committed_reason_ = raw_reason;
      last_change_ms_ = now_ms;
    }

    out.limit_100ma = committed_limit_;
    out.reason = committed_reason_;
    return out;
  }

 private:
  bool initialized_{false};
  uint8_t dv_tier_{0};
  uint8_t cd_tier_{0};
  bool surge_active_{false};
  uint16_t committed_limit_{2500};
  const char *committed_reason_{"DISCHARGE_NORMAL (250A)"};
  uint32_t last_change_ms_{0};
};

}  // namespace huawei_smart_ctrl

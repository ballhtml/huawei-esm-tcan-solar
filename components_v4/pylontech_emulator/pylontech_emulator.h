// pylontech_emulator.h — Pylontech BMS Protocol Emulator for ESPHome
// Version 6.0.0-PRO (Project V2 Dedicated Architecture)
// Fixes Applied:
//  1. Strict Hex-Encoded ASCII for String IDs (CID2 0x51, 0x93, 0x94, 0x95)
//  2. High-EMI Noise Immunity Filter (No early buffer drop on burst noise during >60A / 3000W charge)
//  3. Safe Inverter Handshake & Soft Current Throttling to prevent Inverter Error 04 / 4b cut-offs
//  4. Clean Fallback & Stale Watchdog
#pragma once

#include "esphome/core/component.h"
#include "esphome/components/uart/uart.h"
#include "esphome/components/sensor/sensor.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#include <algorithm>
#include <string>
#include <vector>
#include "tcan_telemetry_shared.h"

namespace esphome {
namespace pylontech_emulator {

static const char *const TAG = "pylontech_emulator";

inline const char* g_li2_throttling_reason = "NORMAL (140A)";
inline bool g_li2_auto_calibrated_100 = false;
inline uint32_t g_last_can_frame_ms = 0;
inline float g_li2_target_charge_v = 53.8f;

class PylontechEmulator : public Component, public uart::UARTDevice {
 public:
  void set_soc_sensor(sensor::Sensor *s) { soc_sensor_ = s; }
  void set_voltage_sensor(sensor::Sensor *s) { voltage_sensor_ = s; }
  void set_current_sensor(sensor::Sensor *s) { current_sensor_ = s; }
  void set_temp_sensor(sensor::Sensor *s) { temp_sensor_ = s; }
  void set_query_count_sensor(sensor::Sensor *s) { query_count_sensor_ = s; }
  void set_flow_control_pin(int pin) { tx_enable_pin_ = pin; }

  void ping_telemetry() {
    last_telemetry_ms_ = millis();
  }

  float get_setup_priority() const override { return setup_priority::LATE; }

  void setup() override {
    if (tx_enable_pin_ >= 0) {
      gpio_reset_pin((gpio_num_t)tx_enable_pin_);
      gpio_set_direction((gpio_num_t)tx_enable_pin_, GPIO_MODE_OUTPUT);
      gpio_set_level((gpio_num_t)tx_enable_pin_, 0);  // RX mode default
    }
    ESP_LOGI(TAG, "Pylontech Emulator v6.0.0-PRO (Project V2) Initialized (flow_ctrl_pin=%d)", tx_enable_pin_);
  }

  void loop() override {
    if (query_count_ == 0 && (millis() - last_diag_ms_ >= 5000)) {
      last_diag_ms_ = millis();
      ESP_LOGI(TAG, "DIAG Inverter UART: GPIO33=%d GPIO32=%d | valid_rx=%lu | zero_rx=%lu | Q=%lu",
               gpio_get_level(GPIO_NUM_33), gpio_get_level(GPIO_NUM_32), (unsigned long)raw_rx_count_, (unsigned long)zero_rx_count_, (unsigned long)query_count_);
    }

    // Read serial bytes with high EMI noise tolerance (bounded per tick to prevent WDT starvation)
    int max_bytes = 64;
    while (available() && max_bytes-- > 0) {
      uint8_t byte;
      read_byte(&byte);
      raw_rx_count_++;
      ESP_LOGI(TAG, "Inverter RX [%lu]: 0x%02X ('%c')", (unsigned long)raw_rx_count_, byte, (byte >= 32 && byte <= 126) ? (char)byte : '.');

      if (byte == '~') {
        // Start of Frame (SOI)
        rx_buffer_.clear();
        rx_buffer_ += (char)byte;
        receiving_ = true;
        rx_start_ms_ = millis();
      } else if (receiving_) {
        // Filter out NUL / non-printable noise characters except CR (\r)
        // In high charging EMI (3kW / 60A+), garbage pulses may arrive on floating/unisolated lines.
        // We drop single garbage bytes instead of discarding the entire receiving frame!
        if (byte == '\r') {
          rx_buffer_ += '\r';
          process_frame(rx_buffer_);
          rx_buffer_.clear();
          receiving_ = false;
        } else if ((byte >= '0' && byte <= '9') || (byte >= 'A' && byte <= 'F') || (byte >= 'a' && byte <= 'f') || byte == ' ') {
          // Valid ASCII hexadecimal character or space
          rx_buffer_ += (char)byte;
          if (rx_buffer_.length() > 200) {
            rx_buffer_.clear();
            receiving_ = false;
          }
        } else {
          // Minor noise byte received during frame transmission: ignore byte to prevent framing break
          ESP_LOGD(TAG, "Ignored EMI noise byte 0x%02X during active frame RX", byte);
        }
      }
    }

    // Frame timeout: 500ms
    if (receiving_ && (millis() - rx_start_ms_ > 500)) {
      ESP_LOGD(TAG, "Frame timeout: discarded %zu bytes", rx_buffer_.length());
      rx_buffer_.clear();
      receiving_ = false;
    }
  }

 private:
  sensor::Sensor *soc_sensor_{nullptr};
  sensor::Sensor *voltage_sensor_{nullptr};
  sensor::Sensor *current_sensor_{nullptr};
  sensor::Sensor *temp_sensor_{nullptr};
  sensor::Sensor *query_count_sensor_{nullptr};
  int tx_enable_pin_{-1};
  std::string rx_buffer_;
  bool receiving_{false};
  uint32_t rx_start_ms_{0};
  uint32_t query_count_{0};
  uint32_t raw_rx_count_{0};
  uint32_t zero_rx_count_{0};
  uint32_t last_diag_ms_{0};

  float get_voltage() {
    return (voltage_sensor_ && voltage_sensor_->has_state()) ? voltage_sensor_->state : 51.2f;
  }
  float get_current() {
    return (current_sensor_ && current_sensor_->has_state()) ? current_sensor_->state : 0.0f;
  }
  float get_soc() {
    if (full_charge_calibrated_) return 100.0f;
    return (soc_sensor_ && soc_sensor_->has_state()) ? soc_sensor_->state : 100.0f;
  }
  float get_temp() {
    return (temp_sensor_ && temp_sensor_->has_state()) ? temp_sensor_->state : 25.0f;
  }

  bool charge_enabled_{true};
  bool discharge_enabled_{true};
  bool low_cutoff_latched_{false};

  uint16_t current_charge_limit_100ma_{1400};
  uint32_t last_limit_step_ms_{0};

  uint32_t full_charge_start_ms_{0};
  bool full_charge_calibrated_{false};

  uint32_t last_telemetry_ms_{0};

  bool is_bms_data_fresh() {
    bool has_sensors = (voltage_sensor_ && voltage_sensor_->has_state()) || (soc_sensor_ && soc_sensor_->has_state());
    if (!has_sensors) return false;
    // Data must have arrived within the last 15 seconds!
    if (last_telemetry_ms_ == 0 || (millis() - last_telemetry_ms_ > 15000)) {
      return false;
    }
    return true;
  }

  uint16_t get_max_cell_voltage_mv() {
    uint16_t max_mv = 0;
    if (g_li2_max_cell_mv > 1500 && g_li2_max_cell_mv < 4500) {
      max_mv = g_li2_max_cell_mv;
    }
    bool direct_ok = is_tcan_direct_available();
    for (int p = 0; p < 8; p++) {
      // Pack 8 (p == 7) is polled locally on Board 109, so check it even if UDP 5005 is temporarily delayed
      if (p < 7 && !direct_ok) continue;
      if (!g_tcan_direct_pkt.packs[p].is_online) continue;
      for (int c = 0; c < 15; c++) {
        uint16_t mv = g_tcan_direct_pkt.packs[p].cells_mv[c];
        if (mv > 2000 && mv < 4500) {
          if (mv > max_mv) max_mv = mv;
        }
      }
    }
    return max_mv;
  }

  uint16_t get_min_cell_voltage_mv() {
    uint16_t min_mv = 9999;
    if (g_reported_min_cell_mv > 1500 && g_reported_min_cell_mv < 4500) {
      min_mv = g_reported_min_cell_mv;
    }
    bool direct_ok = is_tcan_direct_available();
    for (int p = 0; p < 8; p++) {
      if (p < 7 && !direct_ok) continue;
      if (!g_tcan_direct_pkt.packs[p].is_online) continue;
      for (int c = 0; c < 15; c++) {
        uint16_t mv = g_tcan_direct_pkt.packs[p].cells_mv[c];
        if (mv > 1500 && mv < 4500) {
          if (mv < min_mv) min_mv = mv;
        }
      }
    }
    return (min_mv < 9000) ? min_mv : 0;
  }

  float get_min_pack_voltage_v() {
    float min_v = 99.0f;
    if (g_reported_min_pack_v > 20.0f && g_reported_min_pack_v < 65.0f) {
      min_v = g_reported_min_pack_v;
    }
    bool direct_ok = is_tcan_direct_available();
    for (int p = 0; p < 8; p++) {
      if (p < 7 && !direct_ok) continue;
      if (!g_tcan_direct_pkt.packs[p].is_online) continue;
      float pv = g_tcan_direct_pkt.packs[p].voltage_x100 * 0.01f;
      if (pv > 20.0f && pv < 65.0f) {
        if (pv < min_v) min_v = pv;
      }
    }
    return (min_v < 90.0f) ? min_v : 0.0f;
  }

  void update_protection_states() {
    bool fresh = is_bms_data_fresh();
    g_li2_bms_fresh = fresh;
    if (!fresh) {
      charge_enabled_ = true;       // ALWAYS allow charging so solar/mains can wake up battery!
      discharge_enabled_ = false;   // Temporarily disallow discharge until BMS telemetry arrives (do NOT latch low_cutoff_latched_)
      g_li2_charge_enabled = charge_enabled_;
      g_li2_discharge_enabled = discharge_enabled_;
      g_li2_low_cutoff_latched = low_cutoff_latched_;
      g_li2_charge_limit_a = 0.0f;
      g_li2_discharge_limit_a = 0.0f;
      return;
    }
    float soc = get_soc();
    float v = get_voltage();
    float temp = get_temp();
    uint16_t max_cell = get_max_cell_voltage_mv();
    uint16_t min_cell = get_min_cell_voltage_mv();
    float min_pack_v = get_min_pack_voltage_v();

    g_li2_max_cell_mv = max_cell;
    g_li2_min_cell_mv = min_cell;
    g_li2_min_pack_v = min_pack_v;

    // 1. Overcharge & Over-Temperature Protection with Hysteresis (Max 53.6V, Cell >= 3.60V, or Temp >= 52C)
    if (v >= 53.6f || (soc >= 100.0f && v >= 53.3f) || (max_cell >= 3600) || (temp >= 52.0f)) {
      charge_enabled_ = false;
    } else if (!charge_enabled_ && v <= 53.0f && soc <= 98.0f &&
               (max_cell == 0 || max_cell <= 3450) && (temp <= 47.0f)) {
      charge_enabled_ = true;
    }

    // 2. Multi-Layer Discharge Protection & Anti-Hunting Latch:
    //    - Bank Level: System Average SOC <= 20% or System Average Voltage <= 47.5V
    //    - Hardware Floor: Any pack <= 46.5V or any cell <= 3.000V (prevents Huawei BMS UVP sleep)
    //    - Anti-Hunting Sag Filter: If in low zone (SOC <= 25% or V <= 48.0V), cut off early if any cell <= 3.020V or pack <= 46.8V
    //    - Thermal Cutoff: Max Temp >= 55.0C
    //    - Recovery Hysteresis (when low_cutoff_latched_):
    //        Must charge back to SOC >= 45.0% AND System Voltage >= 49.8V
    //        Weakest pack >= 48.8V, weakest cell >= 3200mV, temp <= 48.0C
    bool low_sag_trip = (soc <= 25.0f || v <= 48.0f) && ((min_cell > 1500 && min_cell <= 3020) || (min_pack_v > 20.0f && min_pack_v <= 46.8f));
    bool low_bank_trip = (soc <= 20.0f) || (v <= 47.5f);
    bool low_pack_trip = (min_pack_v > 20.0f && min_pack_v <= 46.5f) || (min_cell > 1500 && min_cell <= 3000);
    bool high_temp_trip = (temp >= 55.0f);

    if (low_bank_trip || low_pack_trip || low_sag_trip || high_temp_trip) {
      if (!low_cutoff_latched_ || discharge_enabled_) {
        ESP_LOGW(TAG, "DISCHARGE CUT-OFF (ANTI-HUNTING LATCH): SOC=%.1f%% SysV=%.2fV MinPackV=%.2fV MinCell=%umV Temp=%.1fC",
                 soc, v, min_pack_v, min_cell, temp);
      }
      low_cutoff_latched_ = true;
      discharge_enabled_ = false;
    } else if (!low_cutoff_latched_) {
      // Telemetry is fresh and no low-cutoff latch is active: allow normal discharge
      discharge_enabled_ = true;
    } else if (((soc >= 45.0f && v >= 49.8f) || (soc >= 50.0f && v >= 49.5f)) &&
               (min_pack_v <= 20.0f || min_pack_v >= 48.8f) &&
               (min_cell == 0 || min_cell >= 3200) && (temp <= 48.0f)) {
      ESP_LOGI(TAG, "DISCHARGE RE-ENABLED FROM LOW CUTOFF: SOC=%.1f%% SysV=%.2fV MinPackV=%.2fV MinCell=%umV",
               soc, v, min_pack_v, min_cell);
      low_cutoff_latched_ = false;
      discharge_enabled_ = true;
    }

    g_li2_charge_enabled = charge_enabled_;
    g_li2_discharge_enabled = discharge_enabled_;
    g_li2_low_cutoff_latched = low_cutoff_latched_;
  }

  // Charge current limit (in 0.1A units)
  uint16_t get_dynamic_charge_limit_100ma() {
    update_protection_states();
    if (!is_bms_data_fresh() || !charge_enabled_) {
      g_li2_charge_limit_a = 0.0f;
      current_charge_limit_100ma_ = 0;
      return 0;    // 0.0A when full or BMS stale
    }
    float soc = get_soc();
    float v = get_voltage();
    float temp = get_temp();
    uint16_t target_limit = 1400;  // 140.0A base max for 8-pack Huawei ESM bank

    // Stage 1: Coarse SOC & Bank Voltage limits
    if (soc >= 98.0f || v >= 53.4f) {
      target_limit = std::min(target_limit, (uint16_t)150);  // 15.0A (Float/balance)
    } else if (soc >= 90.0f || v >= 53.0f) {
      target_limit = std::min(target_limit, (uint16_t)400);  // 40.0A (Absorption)
    }

    // Stage 2: Fine-grained LiFePO4 Cell Knee Tapering (prevents sudden runaway >3.42V)
    uint16_t max_cell = get_max_cell_voltage_mv();
    uint16_t min_cell = get_min_cell_voltage_mv();
    uint16_t cell_delta_mv = (max_cell > min_cell && min_cell > 1500) ? (max_cell - min_cell) : 0;

    if (max_cell >= 3600) {
      target_limit = 0;    // 0.0A (Immediate stop before Huawei BMS 3.65V OVP trip)
      ESP_LOGW(TAG, "CELL SPIKE CRITICAL: Max cell %u mV >= 3600 mV -> Charge stopped (0.0A)", max_cell);
    } else if (max_cell >= 3550) {
      target_limit = std::min(target_limit, (uint16_t)60);  // 6.0A balance trickle
      ESP_LOGW(TAG, "CELL SPIKE 3.55V: Max cell %u mV -> Throttled to 6.0A", max_cell);
    } else if (max_cell >= 3500) {
      target_limit = std::min(target_limit, (uint16_t)150); // 15.0A
      ESP_LOGI(TAG, "CELL SPIKE 3.50V: Max cell %u mV -> Throttled to 15.0A", max_cell);
    } else if (max_cell >= 3460) {
      target_limit = std::min(target_limit, (uint16_t)300); // 30.0A
    } else if (max_cell >= 3420) {
      target_limit = std::min(target_limit, (uint16_t)600); // 60.0A
    }

    // Stage 3: Cell Imbalance Throttling (give passive balancers time when delta is high)
    if (v >= 52.5f && cell_delta_mv >= 80 && max_cell >= 3400) {
      target_limit = std::min(target_limit, (uint16_t)200); // 20.0A
      ESP_LOGI(TAG, "CELL DELTA HIGH: %u mV imbalance -> Throttled to 20.0A for balancing", cell_delta_mv);
    } else if (v >= 52.0f && cell_delta_mv >= 50 && max_cell >= 3400) {
      target_limit = std::min(target_limit, (uint16_t)400); // 40.0A
    }

    // Stage 3b: Pack Current Imbalance Throttling (protects pack taking excessive unequal current)
    float min_pack_i = 999.0f;
    float max_pack_i = -999.0f;
    int active_i_count = 0;
    for (int p = 0; p < 8; p++) {
      if (!g_tcan_direct_pkt.packs[p].is_online) continue;
      float pi = g_tcan_direct_pkt.packs[p].current_x10 * 0.1f;
      if (pi < min_pack_i) min_pack_i = pi;
      if (pi > max_pack_i) max_pack_i = pi;
      active_i_count++;
    }
    float curr_delta_a = (active_i_count > 1 && max_pack_i > min_pack_i) ? (max_pack_i - min_pack_i) : 0.0f;

    if (v >= 51.5f && curr_delta_a >= 25.0f) {
      target_limit = std::min(target_limit, (uint16_t)350); // 35.0A
      ESP_LOGW(TAG, "PACK CURRENT IMBALANCE: Delta %.1fA -> Throttled to 35.0A", curr_delta_a);
    } else if (v >= 51.0f && curr_delta_a >= 18.0f) {
      target_limit = std::min(target_limit, (uint16_t)500); // 50.0A
    }

    // Stage 4: Preventive thermal derating
    if (temp >= 50.0f) {
      target_limit = std::min(target_limit, (uint16_t)200); // 20.0A
    } else if (temp >= 46.0f) {
      target_limit = std::min(target_limit, (uint16_t)500); // 50.0A
    }

    // Feature 1: Auto-Calibration SOC 100% (Full-Charge Sync - from mitpylon)
    float cur_a = get_current();
    if (v >= 53.2f && max_cell >= 3450 && cur_a >= 0.0f && cur_a <= 5.0f && is_bms_data_fresh()) {
      if (full_charge_start_ms_ == 0) {
        full_charge_start_ms_ = millis();
      } else if (millis() - full_charge_start_ms_ >= 180000) {  // 3 minutes
        if (!full_charge_calibrated_) {
          full_charge_calibrated_ = true;
          g_li2_auto_calibrated_100 = true;
          ESP_LOGI(TAG, "FULL CHARGE AUTO-CALIBRATION: Conditions met (V=%.2fV MaxCell=%umV I=%.1fA) -> SOC synced to 100%%",
                   v, max_cell, cur_a);
        }
      }
    } else if (v < 52.8f || max_cell < 3400 || cur_a < -1.0f) {
      full_charge_start_ms_ = 0;
      full_charge_calibrated_ = false;
      g_li2_auto_calibrated_100 = false;
    }

    // Feature 2: Determine Live Throttling Reason (Charge & Discharge aware)
    if (!is_bms_data_fresh()) {
      g_li2_throttling_reason = "BMS_OFFLINE (0A)";
    } else if (!discharge_enabled_ && cur_a < -1.0f) {
      g_li2_throttling_reason = "DISCHARGE_CUTOFF (0A)";
    } else if (!charge_enabled_) {
      g_li2_throttling_reason = "CHARGE_PROHIBITED (0A)";
    } else if (cur_a < -2.0f) {
      // Discharging status
      if (min_cell > 1500 && min_cell <= 3020) {
        g_li2_throttling_reason = "DCL_KNEE_3.02V (15A)";
      } else if (min_cell > 1500 && min_cell <= 3050 || soc <= 20.0f) {
        g_li2_throttling_reason = "DCL_FLOOR_3.05V (30A)";
      } else if (min_cell > 1500 && min_cell <= 3100 || soc <= 30.0f) {
        g_li2_throttling_reason = "DCL_SOFT_3.10V (60A)";
      } else if (min_cell > 1500 && min_cell <= 3150) {
        g_li2_throttling_reason = "DCL_STEP_3.15V (100A)";
      } else {
        g_li2_throttling_reason = "DISCHARGE_NORMAL (300A)";
      }
    } else if (max_cell >= 3600) {
      g_li2_throttling_reason = "CELL_SPIKE_3.60V (0A)";
    } else if (max_cell >= 3550) {
      g_li2_throttling_reason = "CELL_TRICKLE_3.55V (6A)";
    } else if (max_cell >= 3500) {
      g_li2_throttling_reason = "CELL_KNEE_3.50V (15A)";
    } else if (max_cell >= 3460) {
      g_li2_throttling_reason = "CELL_KNEE_3.46V (30A)";
    } else if (max_cell >= 3420) {
      g_li2_throttling_reason = "CELL_KNEE_3.42V (60A)";
    } else if (v >= 52.5f && cell_delta_mv >= 80 && max_cell >= 3400) {
      g_li2_throttling_reason = "CELL_DELTA_IMBALANCE (20A)";
    } else if (v >= 52.0f && cell_delta_mv >= 50 && max_cell >= 3400) {
      g_li2_throttling_reason = "CELL_DELTA_MODERATE (40A)";
    } else if (temp >= 50.0f) {
      g_li2_throttling_reason = "HIGH_TEMP_DERATE (20A)";
    } else if (temp >= 46.0f) {
      g_li2_throttling_reason = "HIGH_TEMP_DERATE (50A)";
    } else if (soc >= 98.0f || v >= 53.4f) {
      g_li2_throttling_reason = "FLOAT_BALANCE (15A)";
    } else if (soc >= 90.0f || v >= 53.0f) {
      g_li2_throttling_reason = "ABSORPTION (40A)";
    } else {
      g_li2_throttling_reason = "NORMAL_BULK (140A)";
    }

    // Safety: Hard cutoff must happen instantly without ramping!
    if (target_limit == 0) {
      current_charge_limit_100ma_ = 0;
    } else {
      // Slew-rate limiter: smooth ramp down (max 15A step down) and ramp up (max 10A step up)
      // to avoid triggering Inverter Error 04 / MPPT DC-bus surge
      uint32_t now = millis();
      if (last_limit_step_ms_ == 0 || (now - last_limit_step_ms_ >= 800)) {
        last_limit_step_ms_ = now;
        if (current_charge_limit_100ma_ > target_limit) {
          uint16_t step_down = 150;  // 15.0A per step
          if (current_charge_limit_100ma_ > target_limit + step_down) {
            current_charge_limit_100ma_ -= step_down;
          } else {
            current_charge_limit_100ma_ = target_limit;
          }
        } else if (current_charge_limit_100ma_ < target_limit) {
          uint16_t step_up = 100;    // 10.0A per step
          if (current_charge_limit_100ma_ + step_up < target_limit) {
            current_charge_limit_100ma_ += step_up;
          } else {
            current_charge_limit_100ma_ = target_limit;
          }
        }
      }
    }

    g_li2_charge_limit_a = current_charge_limit_100ma_ * 0.1f;
    return current_charge_limit_100ma_;
  }

  // Discharge current limit (in 0.1A units)
  uint16_t get_dynamic_discharge_limit_100ma() {
    update_protection_states();
    if (!is_bms_data_fresh() || !discharge_enabled_) {
      g_li2_discharge_limit_a = 0.0f;
      return 0;    // 0.0A (Cut-off to Mains Bypass)
    }
    float soc = get_soc();
    float v = get_voltage();
    float temp = get_temp();
    float min_pack_v = get_min_pack_voltage_v();
    uint16_t min_cell = get_min_cell_voltage_mv();

    uint16_t limit = 3000;  // 300.0A base max for 8-pack bank
    // Stage 1: Fine-grained Low-Cell Knee Tapering (prevents sudden Inverter / BMS UVP trip)
    if (min_cell > 1500 && min_cell <= 3020) {
      limit = 150;  // 15.0A emergency knee: forces inverter to shift load to grid smoothly
      ESP_LOGW(TAG, "DISCHARGE KNEE 3.02V: Min cell %u mV <= 3020 mV -> Throttled to 15.0A", min_cell);
    } else if (soc <= 20.0f || v <= 47.8f ||
        (min_pack_v > 20.0f && min_pack_v <= 47.0f) ||
        (min_cell > 1500 && min_cell <= 3050)) {
      limit = 300;  // 30.0A critical floor
    } else if (soc <= 30.0f || v <= 48.5f ||
        (min_pack_v > 20.0f && min_pack_v <= 47.5f) ||
        (min_cell > 1500 && min_cell <= 3100) ||
        (temp >= 50.0f)) {
      limit = 600;  // 60.0A soft step-down
    } else if (min_cell > 1500 && min_cell <= 3150) {
      limit = 1000; // 100.0A moderate step-down
    }
    g_li2_discharge_limit_a = limit * 0.1f;
    return limit;
  }

  uint16_t calculate_checksum(const std::string &data) {
    uint32_t sum = 0;
    for (char c : data) {
      sum += (uint8_t)c;
    }
    uint16_t checksum = (uint16_t)(~sum + 1);
    return checksum;
  }

  uint16_t encode_length(uint16_t len) {
    if (len == 0) return 0x0000;
    uint16_t sum = (len & 0x0F) + ((len >> 4) & 0x0F) + ((len >> 8) & 0x0F);
    uint16_t chksum = (~sum + 1) & 0x0F;
    return (chksum << 12) | (len & 0x0FFF);
  }

  std::string to_hex_2(uint8_t val) {
    char buf[3];
    snprintf(buf, sizeof(buf), "%02X", val);
    return std::string(buf);
  }

  std::string to_hex_4(uint16_t val) {
    char buf[5];
    snprintf(buf, sizeof(buf), "%04X", val);
    return std::string(buf);
  }

  // Converts plain ASCII text into Hex-Encoded ASCII string as required by Pylontech CID2 spec
  std::string to_hex_ascii_string(const std::string &text) {
    std::string hex_out = "";
    for (char c : text) {
      hex_out += to_hex_2((uint8_t)c);
    }
    return hex_out;
  }

  void process_frame(const std::string &frame) {
    if (frame.length() < 13 || frame.front() != '~' || frame.back() != '\r') {
      return;
    }

    // Validate incoming checksum if frame length is sufficient
    if (frame.length() >= 7) {
      std::string body = frame.substr(1, frame.length() - 6);
      std::string chk_str = frame.substr(frame.length() - 5, 4);
      uint16_t received_chk = (uint16_t)strtol(chk_str.c_str(), nullptr, 16);
      uint16_t calc_chk = calculate_checksum(body);
      if (received_chk != calc_chk) {
        ESP_LOGD(TAG, "Frame rejected: checksum mismatch (recv=0x%04X calc=0x%04X)", received_chk, calc_chk);
        return;
      }
    }

    query_count_++;
    if (query_count_sensor_ != nullptr) {
      query_count_sensor_->publish_state(query_count_);
    }

    std::string ver = frame.substr(1, 2);
    std::string adr = frame.substr(3, 2);
    std::string cid1 = frame.substr(5, 2);
    std::string cid2_str = frame.substr(7, 2);

    uint8_t cid2_val = (uint8_t)strtol(cid2_str.c_str(), nullptr, 16);
    std::string info = "";
    std::string rtn = "00";  // Return Code: 00 = Normal / OK

    switch (cid2_val) {
      case 0x42:  // Get Analog Data
        info = build_analog_data(adr);
        break;

      case 0x44:  // Get Alarm Information
        info = build_alarm_info(adr);
        break;

      case 0x47:  // Get System Parameters
        info = build_system_params(adr);
        break;

      case 0x4F:  // Get Protocol Version
        info = build_protocol_info();
        break;

      case 0x51:  // Get Manufacturer Info (Hex encoded string)
        info = build_manufacturer_info();
        break;

      case 0x61:  // Get System Analog Data (V3.5 System-level)
        info = build_system_analog_data_61(adr);
        break;

      case 0x62:  // Get System Alarm Info (V3.5 System-level)
        info = build_system_alarm_62();
        break;

      case 0x63:  // Get System Charge / Discharge Management Info
      case 0x92:  // Voltronic / Maxsky Inverters equivalent
        info = build_charge_mgmt_info_63();
        break;

      case 0x93:  // Get Module Serial Number (Hex encoded string)
        info = build_serial_number(adr);
        break;

      case 0x94:  // Get Software / Hardware Version (Hex encoded string)
        info = build_version_info();
        break;

      case 0x95:  // Get Manufacturer / Model Name (Hex encoded string)
        info = build_model_name_95();
        break;

      case 0x96:  // Get Protocol Version
        info = build_protocol_info();
        break;

      default:
        ESP_LOGW(TAG, "Unhandled CID2 command: 0x%02X -> Responding with CID2 Invalid (04)", cid2_val);
        rtn = "04";  // CID2 Invalid
        break;
    }

    // Build Response Frame
    uint16_t lenid = info.length();
    uint16_t length_encoded = encode_length(lenid);

    std::string payload = ver + adr + cid1 + rtn + to_hex_4(length_encoded) + info;
    uint16_t chk = calculate_checksum(payload);
    std::string full_frame = "~" + payload + to_hex_4(chk) + "\r";

    // Transmit over RS485 with Direction Pin Management
    if (tx_enable_pin_ >= 0) {
      gpio_set_level((gpio_num_t)tx_enable_pin_, 1);  // Set TX mode
      esp_rom_delay_us(80);
    }

    write_str(full_frame.c_str());
    flush();  // Flush hardware TX FIFO before releasing direction line
    esp_rom_delay_us(150);

    if (tx_enable_pin_ >= 0) {
      gpio_set_level((gpio_num_t)tx_enable_pin_, 0);  // Return to RX mode
    }

    ESP_LOGI(TAG, "Responded to CID2=0x%02X (ADR=%s, info_len=%d, query_count=%lu)",
             cid2_val, adr.c_str(), (int)info.length(), (unsigned long)query_count_);
  }

  // ---- CID2 0x42: Get Analog Data ----
  std::string build_analog_data(const std::string &adr) {
    float voltage_v = get_voltage();
    float current_a = get_current();
    float soc_percent = get_soc();
    float temp_c = get_temp();

    uint16_t pack_voltage_mv = (uint16_t)(voltage_v * 1000.0f);
    int16_t pack_current_100ma = (int16_t)(current_a * 10.0f);
    uint16_t cell_avg_mv = (uint16_t)(pack_voltage_mv / 15);

    std::string info = "";
    info += "01";  // Command Group ID / Pack Index

    // 15 Cell Voltages (in mV) - Huawei ESM 15S
    info += "0F";  // 15 cells (0x0F)
    // Populate real 15 cell voltages from direct telemetry if available
    int best_p = -1;
    uint16_t highest_c = 0;
    for (int p = 0; p < 8; p++) {
      if (!g_tcan_direct_pkt.packs[p].is_online) continue;
      for (int c = 0; c < 15; c++) {
        uint16_t mv = g_tcan_direct_pkt.packs[p].cells_mv[c];
        if (mv > highest_c && mv < 4500) {
          highest_c = mv;
          best_p = p;
        }
      }
    }
    if (best_p >= 0 && g_tcan_direct_pkt.packs[best_p].cells_mv[0] > 2000) {
      for (int c = 0; c < 15; c++) {
        uint16_t mv = g_tcan_direct_pkt.packs[best_p].cells_mv[c];
        info += to_hex_4((mv > 2000 && mv < 4500) ? mv : cell_avg_mv);
      }
    } else {
      for (int c = 0; c < 15; c++) {
        info += to_hex_4(cell_avg_mv);
      }
    }

    // 5 Temperature Probes (in Kelvin * 10)
    uint16_t temp_k10 = (uint16_t)(temp_c * 10.0f + 2731.5f);
    info += "05";  // 5 sensors
    for (int t = 0; t < 5; t++) {
      info += to_hex_4(temp_k10);
    }

    // Pack Current (0.1A signed) & Total Voltage (mV)
    info += to_hex_4((uint16_t)pack_current_100ma);
    info += to_hex_4(pack_voltage_mv);

    // Remaining & Total Capacity in 10mAh
    uint32_t total_cap_10mah = 80000;  // 800.0 Ah (8x 100Ah ESM packs)
    uint32_t remain_cap_10mah = (uint32_t)(total_cap_10mah * (soc_percent / 100.0f));

    info += to_hex_4((uint16_t)(remain_cap_10mah & 0xFFFF));
    info += "03";  // Defined fields count
    info += to_hex_4((uint16_t)(total_cap_10mah & 0xFFFF));
    info += to_hex_4(150);  // Cycle count

    return info;
  }

  // ---- CID2 0x44: Get Alarm Info ----
  std::string build_alarm_info(const std::string &adr) {
    float voltage_v = get_voltage();
    float temp_c = get_temp();
    uint16_t max_cell = get_max_cell_voltage_mv();
    uint16_t min_cell = get_min_cell_voltage_mv();

    std::string info = "";
    info += "01";  // Pack Index
    info += "0F";  // 15 cells alarm flags (00 = normal, 01 = undervoltage, 02 = overvoltage)
    for (int c = 0; c < 15; c++) {
      uint8_t cell_alarm = 0x00;
      if (max_cell >= 3600) cell_alarm = 0x02;
      else if (min_cell > 1500 && min_cell <= 3000) cell_alarm = 0x01;
      info += to_hex_2(cell_alarm);
    }
    info += "05";  // 5 temperature alarm flags (00 = normal, 02 = high temp)
    uint8_t temp_alarm = (temp_c >= 52.0f) ? 0x02 : 0x00;
    for (int t = 0; t < 5; t++) {
      info += to_hex_2(temp_alarm);
    }
    // Charge current alarm (02 = charge stopped / OVP)
    info += (!charge_enabled_) ? "02" : "00";
    // Total voltage alarm
    if (voltage_v >= 53.6f) info += "02";
    else if (voltage_v <= 46.5f) info += "01";
    else info += "00";
    // Discharge current alarm (02 = discharge cutoff)
    info += (!discharge_enabled_) ? "02" : "00";
    // Status 1: Alarm Summary Bitfield
    uint8_t st1 = 0x00;
    if (max_cell >= 3600) st1 |= 0x01;                       // Bit 0: Cell Over-Voltage
    if (min_cell > 1500 && min_cell <= 3000) st1 |= 0x02;    // Bit 1: Cell Under-Voltage
    if (voltage_v >= 53.6f) st1 |= 0x04;                     // Bit 2: Module Over-Voltage
    if (voltage_v <= 46.5f) st1 |= 0x08;                     // Bit 3: Module Under-Voltage
    if (!charge_enabled_) st1 |= 0x40;                       // Bit 6: Charge Prohibited
    if (!discharge_enabled_) st1 |= 0x80;                    // Bit 7: Discharge Prohibited
    info += to_hex_2(st1);
    info += "00";  // Status 2
    info += "00";  // Status 3
    info += "00";  // Status 4
    info += "00";  // Status 5
    return info;
  }

  // ---- CID2 0x47: Get System Parameters ----
  std::string build_system_params(const std::string &adr) {
    uint16_t chg_limit = get_dynamic_charge_limit_100ma();
    uint16_t dis_limit = get_dynamic_discharge_limit_100ma();

    std::string info = "";
    info += to_hex_4(3650);   // Cell High Voltage Limit: 3.650V
    info += to_hex_4(3133);   // Cell Low Voltage Limit: 3.133V (47.0V / 15)
    info += to_hex_4(3067);   // Cell Under Voltage Limit: 3.067V (46.0V / 15)
    info += to_hex_4(3281);   // Charge High Temp Limit: 55°C
    info += to_hex_4(2731);   // Charge Low Temp Limit: 0°C
    info += to_hex_4(chg_limit); // Dynamic Max Charge Current Limit (0.1A)
    info += to_hex_4(55000);  // Module High Voltage Limit: 55.000V
    info += to_hex_4(47000);  // Module Low Voltage Limit: 47.000V
    info += to_hex_4(46000);  // Module Under Voltage Limit: 46.000V
    info += to_hex_4(3331);   // Discharge High Temp Limit: 60°C
    info += to_hex_4(2631);   // Discharge Low Temp Limit: -10°C
    info += to_hex_4(dis_limit); // Dynamic Max Discharge Current Limit (0.1A)
    return info;
  }

  // ---- CID2 0x61: Get System Analog Data ----
  std::string build_system_analog_data_61(const std::string &adr) {
    float voltage_v = get_voltage();
    float current_a = get_current();
    float soc_percent = get_soc();
    float temp_c = get_temp();

    uint16_t voltage_mv = (uint16_t)(voltage_v * 1000.0f);
    int16_t current_ca = (int16_t)(current_a * 100.0f);  // In 0.01A (centi-Ampere)
    uint8_t soc_val = (uint8_t)std::max(0, std::min(100, (int)soc_percent));
    uint16_t cycles = 150;
    uint8_t soh = 100;

    uint16_t cell_avg_mv = (uint16_t)(voltage_mv / 15);
    uint16_t real_max_cell = get_max_cell_voltage_mv();
    uint16_t real_min_cell = get_min_cell_voltage_mv();
    uint16_t max_cell_v = (real_max_cell > 2000) ? real_max_cell : (cell_avg_mv + 10);
    uint16_t min_cell_v = (real_min_cell > 1500) ? real_min_cell : (cell_avg_mv - 10);
    uint16_t temp_k10 = (uint16_t)(temp_c * 10.0f + 2731.5f);

    char buf[128];
    snprintf(buf, sizeof(buf),
             "%04X%04X%02X%04X%04X%02X%02X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X%04X",
             voltage_mv,
             (uint16_t)current_ca,
             soc_val,
             cycles,
             cycles,
             soh,
             soh,
             max_cell_v,
             0x0101,
             min_cell_v,
             0x0108,
             temp_k10,
             temp_k10,
             0x0103,
             temp_k10,
             0x0109,
             temp_k10,
             temp_k10,
             0x0101,
             temp_k10,
             0x0101,
             temp_k10,
             temp_k10,
             0x0101,
             temp_k10,
             0x0101);

    return std::string(buf);
  }

  // ---- CID2 0x62: Get System Alarm Info ----
  std::string build_system_alarm_62() {
    return "00000000";
  }

  // Dynamic Charge Voltage Limit (mitpylon Float Step-Down)
  uint16_t get_dynamic_charge_voltage_mv() {
    float soc = get_soc();
    uint16_t max_cell = get_max_cell_voltage_mv();
    
    uint16_t target_mv = 53800; // 53.8V (~3.58V/cell bulk fast charge)
    // Float stage: when max cell >= 3480 mV or SOC >= 98%
    if (max_cell >= 3550 || soc >= 99.0f) {
      target_mv = 53000; // 53.0V (~3.53V/cell float holding - zero cell stress)
    } else if (max_cell >= 3480 || soc >= 98.0f) {
      target_mv = 53200; // 53.2V (~3.54V/cell absorption float)
    }
    g_li2_target_charge_v = (float)target_mv * 0.001f;
    return target_mv;
  }

  // ---- CID2 0x63 / 0x92: Get Charge/Discharge Management Info ----
  std::string build_charge_mgmt_info_63() {
    uint16_t chg_limit = get_dynamic_charge_limit_100ma();
    uint16_t dis_limit = get_dynamic_discharge_limit_100ma();
    uint16_t chg_v_mv = get_dynamic_charge_voltage_mv();

    std::string info = "";
    info += to_hex_4(chg_v_mv);  // Dynamic Charge Voltage Limit (53.8V -> 53.2V -> 53.0V Float Step-Down)
    info += to_hex_4(46500);     // Discharge Voltage Cut-off Limit: 46.500V (Matches Working Proven Config)
    info += to_hex_4(chg_limit); // Dynamic Charge Current Limit (0.1A)
    info += to_hex_4(dis_limit); // Dynamic Discharge Current Limit (0.1A)
    uint8_t flags = 0x00;
    if (charge_enabled_) flags |= 0x80;        // Bit 7: Charge enable (cleared on OVP / cell spike >= 3.60V / thermal trip)
    if (is_bms_data_fresh() && discharge_enabled_) flags |= 0x40; // Bit 6: Discharge enable
    info += to_hex_2(flags);
    return info;
  }

  // ---- CID2 0x93: Get Serial Number (Hex Encoded ASCII) ----
  std::string build_serial_number(const std::string &adr) {
    return to_hex_ascii_string("PPT0010020030040");
  }

  // ---- CID2 0x94: Software / Hardware Version (Hex Encoded ASCII) ----
  std::string build_version_info() {
    return to_hex_ascii_string("V2.8");
  }

  // ---- CID2 0x95: Manufacturer / Model Name (Hex Encoded ASCII) ----
  std::string build_model_name_95() {
    return to_hex_ascii_string("US2000");
  }

  // ---- CID2 0x51: Manufacturer Info (Hex Encoded ASCII) ----
  std::string build_manufacturer_info() {
    return to_hex_ascii_string("PYLON   ");
  }

  // ---- CID2 0x4F / 0x96: Protocol Version ----
  std::string build_protocol_info() {
    return "20";
  }
};

}  // namespace pylontech_emulator
}  // namespace esphome

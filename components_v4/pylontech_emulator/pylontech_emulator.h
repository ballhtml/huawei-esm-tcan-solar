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
    return (soc_sensor_ && soc_sensor_->has_state()) ? soc_sensor_->state : 100.0f;
  }
  float get_temp() {
    return (temp_sensor_ && temp_sensor_->has_state()) ? temp_sensor_->state : 25.0f;
  }

  bool charge_enabled_{true};
  bool discharge_enabled_{true};

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
    if (!is_tcan_direct_available()) return 0;
    uint16_t max_mv = 0;
    for (int p = 0; p < 8; p++) {
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

  void update_protection_states() {
    if (!is_bms_data_fresh()) {
      charge_enabled_ = true;       // ALWAYS allow charging so solar/mains can wake up battery!
      discharge_enabled_ = false;   // Disallow discharge when BMS telemetry is unavailable
      return;
    }
    float soc = get_soc();
    float v = get_voltage();
    uint16_t max_cell = get_max_cell_voltage_mv();

    // 1. Overcharge Protection with Hysteresis (Max 53.6V, Float 53.0V for 15S, or Cell >= 3.62V)
    if (v >= 53.6f || (soc >= 100.0f && v >= 53.3f) || (max_cell >= 3620)) {
      charge_enabled_ = false;
    } else if (!charge_enabled_ && v <= 53.0f && soc <= 98.0f && (max_cell == 0 || max_cell <= 3450)) {
      charge_enabled_ = true;
    }

    // 2. Low-Voltage / Low-SOC Cut-off matching Safe Zone (25% SOC / 48.0V)
    // 48.0V = 3.20V/cell (Knee of LiFePO4). Cuts off before Huawei BMS enters sleep!
    if (soc <= 25.0f || v <= 48.0f) {
      discharge_enabled_ = false;  // Cut-off discharge gracefully so BMS never sleeps!
    } else if (!discharge_enabled_ && soc >= 60.0f && v >= 49.0f) {
      discharge_enabled_ = true;   // Re-enable discharge once charged safely to 60% and 49.0V
    }
  }

  // Charge current limit (in 0.1A units)
  uint16_t get_dynamic_charge_limit_100ma() {
    update_protection_states();
    if (!is_bms_data_fresh() || !charge_enabled_) {
      return 0;    // 0.0A when full or BMS stale
    }
    float soc = get_soc();
    float v = get_voltage();
    uint16_t limit = 1200;  // 120.0A (Matches Table Maximum Charging Current = 120.0A for 7.5kW Solar)

    if (soc >= 98.0f || v >= 53.4f) {
      limit = 150;  // 15.0A (Float/Balance stage ~2A/pack for 7-8 packs)
    } else if (soc >= 90.0f || v >= 53.0f) {
      limit = 400;  // 40.0A (Absorption stage ~5A/pack for 7-8 packs)
    }

    // Dynamic Cell-Spike Protection:
    // If any single cell across all active packs spikes during charging,
    // immediately throttle down current to give passive balancers time and prevent BMS OVP cut-off!
    uint16_t max_cell = get_max_cell_voltage_mv();
    if (max_cell >= 3600) {
      limit = 0;    // 0.0A (Cell at 3.60V+: stop charge to prevent Huawei BMS 3.65V OVP trip)
      ESP_LOGW(TAG, "CELL SPIKE CRITICAL: Max cell %u mV >= 3600 mV -> Charge stopped (0.0A)", max_cell);
    } else if (max_cell >= 3550) {
      limit = std::min(limit, (uint16_t)100);  // Max 10.0A (Cell at 3.55V+)
      ESP_LOGW(TAG, "CELL SPIKE HIGH: Max cell %u mV >= 3550 mV -> Charge throttled to 10.0A", max_cell);
    } else if (max_cell >= 3500) {
      limit = std::min(limit, (uint16_t)200);  // Max 20.0A (Cell at 3.50V+)
      ESP_LOGI(TAG, "CELL SPIKE DETECTED: Max cell %u mV >= 3500 mV -> Charge throttled to 20.0A", max_cell);
    }

    return limit;
  }

  // Discharge current limit (in 0.1A units)
  uint16_t get_dynamic_discharge_limit_100ma() {
    update_protection_states();
    if (!is_bms_data_fresh() || !discharge_enabled_) {
      return 0;    // 0.0A (Cut-off to Mains Bypass at SOC <= 25% or V <= 48.0V)
    }
    float soc = get_soc();
    float v = get_voltage();
    if (soc <= 30.0f || v <= 48.5f) {
      return 500;  // 50.0A (Soft step-down before 48.0V cut-off to prevent voltage sag)
    }
    return 3000;   // 300.0A (Matches Table Maximum Discharge Current = 300A)
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

    uint16_t cell_v_mv = (uint16_t)(pack_voltage_mv / 15);

    std::string info = "";
    info += "01";  // Command Group ID / Pack Index

    // 15 Cell Voltages (in mV) - Huawei ESM 15S
    info += "0F";  // 15 cells (0x0F)
    for (int c = 0; c < 15; c++) {
      info += to_hex_4(cell_v_mv);
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
    std::string info = "";
    info += "01";  // Pack Index
    info += "0F";  // 15 cells alarm flags (00 = normal)
    for (int c = 0; c < 15; c++) {
      info += "00";
    }
    info += "05";  // 5 temperature alarm flags (00 = normal)
    for (int t = 0; t < 5; t++) {
      info += "00";
    }
    info += "00";  // Charge current alarm (00 = normal)
    info += "00";  // Total voltage alarm (00 = normal)
    info += "00";  // Discharge current alarm (00 = normal)
    info += "00";  // Status 1: Normal
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
    uint16_t max_cell_v = cell_avg_mv + 10;
    uint16_t min_cell_v = cell_avg_mv - 10;
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

  // ---- CID2 0x63 / 0x92: Get Charge/Discharge Management Info ----
  std::string build_charge_mgmt_info_63() {
    uint16_t chg_limit = get_dynamic_charge_limit_100ma();
    uint16_t dis_limit = get_dynamic_discharge_limit_100ma();

    std::string info = "";
    info += to_hex_4(53800);     // Charge Voltage Limit: 53.800V (Matches Working Proven Config)
    info += to_hex_4(46500);     // Discharge Voltage Cut-off Limit: 46.500V (Matches Working Proven Config)
    info += to_hex_4(chg_limit); // Dynamic Charge Current Limit (0.1A)
    info += to_hex_4(dis_limit); // Dynamic Discharge Current Limit (0.1A)
    uint8_t flags = 0x80;        // Bit 7: Charge enable
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

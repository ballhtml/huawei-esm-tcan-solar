// pylontech_emulator.h — Pylontech BMS Protocol Emulator for ESPHome
// Version 5.0.0 — Comprehensive Maxsky EM1100-48L / EM11000 & Voltronic Inverters
// Full CID2 command set: 0x42, 0x44, 0x47, 0x4F, 0x51, 0x61, 0x62, 0x63, 0x92, 0x93, 0x94, 0x95, 0x96
// Multi-address support: 02 (Master/Pack 1), 12 (Pack 2), 22 (Pack 3), 32 (Pack 4), 42 (Pack 5), etc.
// Features: Dynamic Current Throttling (Absorption/Float), Stale Data Watchdog, Inverter Query Counter
#pragma once

#include "esphome/core/component.h"
#include "esphome/components/uart/uart.h"
#include "esphome/components/sensor/sensor.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"

namespace esphome {
namespace pylontech_emulator {

static const char *const TAG = "pylontech_emulator";

class PylontechEmulator : public Component, public uart::UARTDevice {
 public:
  // Sensor bindings
  void set_soc_sensor(sensor::Sensor *s) { soc_sensor_ = s; }
  void set_voltage_sensor(sensor::Sensor *s) { voltage_sensor_ = s; }
  void set_current_sensor(sensor::Sensor *s) { current_sensor_ = s; }
  void set_temp_sensor(sensor::Sensor *s) { temp_sensor_ = s; }
  void set_query_count_sensor(sensor::Sensor *s) { query_count_sensor_ = s; }
  void set_flow_control_pin(int pin) { tx_enable_pin_ = pin; }

  float get_setup_priority() const override { return setup_priority::LATE; }

  void setup() override {
    if (tx_enable_pin_ >= 0) {
      gpio_reset_pin((gpio_num_t)tx_enable_pin_);
      gpio_set_direction((gpio_num_t)tx_enable_pin_, GPIO_MODE_OUTPUT);
      gpio_set_level((gpio_num_t)tx_enable_pin_, 0);  // RX mode default
    }
    ESP_LOGI(TAG, "Pylontech Emulator v5.0.0 (Enterprise) initialized (flow_ctrl_pin=%d)", tx_enable_pin_);
  }

  void loop() override {
    // Read serial bytes until carriage return (\r)
    while (available()) {
      uint8_t byte;
      read_byte(&byte);
      ESP_LOGI(TAG, "Inverter raw RX: 0x%02X ('%c')", byte, (byte >= 32 && byte <= 126) ? (char)byte : '.');

      if (byte == '~') {
        // SOI: Start new frame
        rx_buffer_.clear();
        rx_buffer_ += (char)byte;
        receiving_ = true;
        rx_start_ms_ = millis();
      } else if (receiving_) {
        // Reject non-printable noise bytes (EMI noise is typically 0x80-0xFF)
        // Valid Pylontech ASCII frame contains only: 0x0D (\r), 0x20-0x7E
        if (byte != '\r' && (byte < 0x20 || byte > 0x7E)) {
          rx_buffer_.clear();
          receiving_ = false;
          continue;
        }
        rx_buffer_ += (char)byte;
        if (byte == '\r') {
          process_frame(rx_buffer_);
          rx_buffer_.clear();
          receiving_ = false;
        } else if (rx_buffer_.length() > 200) {
          rx_buffer_.clear();
          receiving_ = false;
        }
      }
    }
    // Generous frame receive timeout: 500ms
    if (receiving_ && (millis() - rx_start_ms_ > 500)) {
      ESP_LOGD(TAG, "Frame receive timeout — discarding %d bytes of partial/corrupt data", rx_buffer_.length());
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

  bool is_bms_data_fresh() {
    return (voltage_sensor_ && voltage_sensor_->has_state()) || (soc_sensor_ && soc_sensor_->has_state());
  }

  // Calculate dynamic charge current limit based on SOC & data freshness
  uint16_t get_dynamic_charge_limit_100ma() {
    if (!is_bms_data_fresh()) {
      return 0;  // 0.0A fail-safe when BMS is offline
    }
    float soc = get_soc();
    if (soc >= 98.0f) {
      return 100;  // 10.0A (Float/Balance stage)
    } else if (soc >= 90.0f) {
      return 300;  // 30.0A (Absorption stage - fast & battery friendly)
    }
    return 1000;   // 100.0A (Matches User Inverter Maximum Charging Current)
  }

  // Calculate dynamic discharge current limit based on SOC & data freshness
  uint16_t get_dynamic_discharge_limit_100ma() {
    if (!is_bms_data_fresh()) {
      return 0;  // 0.0A fail-safe when BMS is offline
    }
    float soc = get_soc();
    float v = get_voltage();
    if (soc <= 20.0f || v <= 46.5f) {
      return 0;    // 0.0A (Safe Cut-off reached: Stop discharging to protect BMS from sleeping)
    } else if (soc <= 25.0f || v <= 47.0f) {
      return 100;  // 10.0A (Critical buffer stage)
    } else if (soc <= 30.0f || v <= 47.5f) {
      return 500;  // 50.0A (Low voltage sag protection)
    }
    return 2000;   // 200.0A (Normal high discharge for 4x ESM packs)
  }

  // Pylontech Checksum: Sum of ASCII characters negated + 1
  uint16_t calculate_checksum(const std::string &data) {
    uint32_t sum = 0;
    for (char c : data) {
      sum += (uint8_t)c;
    }
    uint16_t checksum = (uint16_t)(~sum + 1);
    return checksum;
  }

  // Pylontech Length Encoding: 12-bit length with 4-bit LCHKSUM prefix
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

  void process_frame(const std::string &frame) {
    if (frame.length() < 13 || frame.front() != '~' || frame.back() != '\r') {
      return;  // Silent reject — too short or wrong delimiters
    }

    // EMI Filter: Validate all characters between ~ and \r are valid hex (0-9, A-F, a-f)
    for (size_t i = 1; i < frame.length() - 1; i++) {
      char c = frame[i];
      if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f'))) {
        ESP_LOGD(TAG, "Frame rejected: non-hex char 0x%02X at pos %d", (uint8_t)c, (int)i);
        return;
      }
    }

    // Validate incoming checksum (last 4 hex chars before \r)
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
    ESP_LOGD(TAG, "Valid RX Frame (%d bytes): %s", frame.length(), frame.c_str());

    std::string ver = frame.substr(1, 2);
    std::string adr = frame.substr(3, 2);
    std::string cid1 = frame.substr(5, 2);
    std::string cid2_str = frame.substr(7, 2);

    uint8_t cid2_val = (uint8_t)strtol(cid2_str.c_str(), nullptr, 16);
    std::string info = "";
    std::string rtn = "00";  // Return Code: 00 = Normal / OK

    switch (cid2_val) {
      case 0x42:  // Get Analog Data (Cell voltages, Temps, Current, Total V, Capacities)
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

      case 0x51:  // Get Manufacturer Info (ASCII)
        info = build_manufacturer_info();
        break;

      case 0x61:  // Get System Analog Data (V3.5 System-level)
        info = build_system_analog_data_61(adr);
        break;

      case 0x62:  // Get System Alarm Info (V3.5 System-level)
        info = build_system_alarm_62();
        break;

      case 0x63:  // Get System Charge / Discharge Management Info (V3.5 System-level)
        info = build_charge_mgmt_info_63();
        break;

      case 0x92:  // Get Charge / Discharge Management Info (Voltronic / Maxsky Inverters)
        info = build_charge_mgmt_info_63();
        break;

      case 0x93:  // Get Module Serial Number
        info = build_serial_number(adr);
        break;

      case 0x94:  // Get Software / Hardware Version
        info = build_version_info();
        break;

      case 0x95:  // Get Manufacturer / Model Name (Hex string)
        info = build_model_name_95();
        break;

      case 0x96:  // Get Protocol Version (e.g. V2.8 / V3.3)
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
             cid2_val, adr.c_str(), info.length(), (unsigned long)query_count_);
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

    // 15 Cell Voltages (in mV) - Standard Pylontech US2000 & Huawei ESM 15S
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
    uint32_t total_cap_10mah = 40000;  // 400.0 Ah (4x 100Ah ESM packs)
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

    if (!is_bms_data_fresh()) {
      info += "02";  // Status 1: BMS Communication Lost Alarm
    } else {
      info += "00";  // Status 1: Normal
    }
    info += "00";    // Status 2
    info += "00";    // Status 3
    info += "00";    // Status 4
    info += "00";    // Status 5
    return info;
  }

  // ---- CID2 0x47 / 0x62: Get System Parameters ----
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
    info += to_hex_4(55000);  // Module High Voltage Limit: 55.000V (Matches User Inverter Overvoltage Protection)
    info += to_hex_4(47000);  // Module Low Voltage Limit: 47.000V (Safe Alarm / Buffer threshold)
    info += to_hex_4(46000);  // Module Under Voltage Limit: 46.000V (Under-voltage threshold)
    info += to_hex_4(3331);   // Discharge High Temp Limit: 60°C
    info += to_hex_4(2631);   // Discharge Low Temp Limit: -10°C
    info += to_hex_4(dis_limit); // Dynamic Max Discharge Current Limit (0.1A)
    return info;
  }

  // ---- CID2 0x61: Get System Analog Data (Pylontech V3.5 Specification - 49 bytes / 98 hex chars) ----
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

    // Huawei ESM 15S cell voltages
    uint16_t cell_avg_mv = (uint16_t)(voltage_mv / 15);
    uint16_t max_cell_v = cell_avg_mv + 10;
    uint16_t min_cell_v = cell_avg_mv - 10;

    // Temperatures in 0.1 Kelvin (offset: T_C * 10 + 2731.5)
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

  // ---- CID2 0x62: Get System Alarm Info (Pylontech V3.5 Specification - 4 bytes / 8 hex chars) ----
  std::string build_system_alarm_62() {
    return "00000000";  // 4 bytes: all normal
  }

  // ---- CID2 0x63 / 0x92: Get Charge/Discharge Management Info (9 bytes / 18 hex chars) ----
  std::string build_charge_mgmt_info_63() {
    uint16_t chg_limit = get_dynamic_charge_limit_100ma();
    uint16_t dis_limit = get_dynamic_discharge_limit_100ma();
    bool allow_discharge = is_bms_data_fresh() && (get_soc() > 20.0f) && (get_voltage() > 46.5f);

    std::string info = "";
    info += to_hex_4(53800);     // Charge Voltage Limit: 53.800V (Matches User Inverter Maximum Charging Voltage)
    info += to_hex_4(46500);     // Discharge Voltage Cut-off Limit: 46.500V (Safe Cut-off, matches Mains mode 46.5V)
    info += to_hex_4(chg_limit); // Dynamic Charge Current Limit (0.1A)
    info += to_hex_4(dis_limit); // Dynamic Discharge Current Limit (0.1A)
    uint8_t flags = is_bms_data_fresh() ? 0x80 : 0x00; // Bit 7: Charge enable
    if (allow_discharge) flags |= 0x40;                 // Bit 6: Discharge enable
    info += to_hex_2(flags);
    return info;
  }

  // ---- CID2 0x93: Get Serial Number ----
  std::string build_serial_number(const std::string &adr) {
    return "PPT0010020030040";
  }

  // ---- CID2 0x94: Software / Hardware Version ----
  std::string build_version_info() {
    return "V1.0";
  }

  // ---- CID2 0x95 / 0x51: Manufacturer / Model Name ----
  std::string build_model_name_95() {
    return "US2000";
  }

  std::string build_manufacturer_info() {
    return "PYLON   ";
  }

  // ---- CID2 0x4F / 0x96: Protocol Version ----
  std::string build_protocol_info() {
    return "20";
  }
};

}  // namespace pylontech_emulator
}  // namespace esphome

#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <lwip/sockets.h>
#include <fcntl.h>
#include "esphome/core/hal.h"
#if defined(ESP32) || defined(USE_ESP32)
#include <esp_now.h>
#include <esp_wifi.h>
#endif

#define TCAN_TELEMETRY_PORT 5005
#define TCAN_MAGIC 0x5443

#define BRIDGE_TELEMETRY_PORT 5006
#define BRIDGE_MAGIC 0x4C49  // 'LI' for Li2 Inverter Bridge

#pragma pack(push, 1)
struct PackTelemetryData {
  uint8_t is_online;       // 1 if active (>20V or valid SOC), 0 if offline
  int16_t voltage_x100;    // e.g. 53.25V -> 5325
  int16_t current_x10;     // e.g. +12.5A -> 125, -20.0A -> -200
  int16_t soc_x10;         // e.g. 85.0% -> 850
  int16_t temp_x10;        // e.g. 27.5C -> 275
  int16_t delta_mv;        // e.g. 15 mV -> 15
  uint16_t cells_mv[15];   // e.g. 3280 mV each
};

struct TcanTelemetryPacket {
  uint16_t magic;          // 0x5443 ('TC')
  uint8_t seq;             // Rolling sequence counter
  int16_t sys_soc_x10;     // Total SOC x10
  int16_t sys_v_x100;      // Total Voltage x100
  int16_t sys_i_x10;       // Total Current x10
  int16_t max_temp_x10;    // Max Temp x10
  PackTelemetryData packs[8];
};

struct BridgeTelemetryPacket {
  uint16_t magic;          // 0x4C49 ('LI')
  uint8_t seq;             // Rolling sequence counter
  uint32_t queries_count;  // Pylontech Li2 queries count from Inverter
  int16_t sys_soc;         // SOC sent to Inverter (%)
  int16_t sys_v_x100;      // Voltage sent to Inverter (x100 V)
  int16_t sys_i_x10;       // Current sent to Inverter (x10 A)
  int16_t max_temp_x10;    // Max Temp sent to Inverter (x10 C)
};
#pragma pack(pop)

// -----------------------------------------------------------------------------
// Board 108 (BMS Gateway) Broadcast Sender Function -> CYD (192.168.8.110) & Subnet
// -----------------------------------------------------------------------------
inline void tcan_broadcast_telemetry(const TcanTelemetryPacket &pkt) {
  static int tx_sock = -1;
  static struct sockaddr_in cyd_addr;
  static struct sockaddr_in bridge_addr;
  static struct sockaddr_in bc_addr;
  if (tx_sock < 0) {
    tx_sock = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (tx_sock < 0) return;
    int opt = 1;
    ::setsockopt(tx_sock, SOL_SOCKET, SO_BROADCAST, &opt, sizeof(opt));
    memset(&cyd_addr, 0, sizeof(cyd_addr));
    cyd_addr.sin_family = AF_INET;
    cyd_addr.sin_port = htons(TCAN_TELEMETRY_PORT);
    cyd_addr.sin_addr.s_addr = inet_addr("192.168.8.110");

    memset(&bridge_addr, 0, sizeof(bridge_addr));
    bridge_addr.sin_family = AF_INET;
    bridge_addr.sin_port = htons(TCAN_TELEMETRY_PORT);
    bridge_addr.sin_addr.s_addr = inet_addr("192.168.8.109");

    memset(&bc_addr, 0, sizeof(bc_addr));
    bc_addr.sin_family = AF_INET;
    bc_addr.sin_port = htons(TCAN_TELEMETRY_PORT);
    bc_addr.sin_addr.s_addr = inet_addr("192.168.8.255");
  }
  ::sendto(tx_sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&cyd_addr, sizeof(cyd_addr));
  ::sendto(tx_sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&bridge_addr, sizeof(bridge_addr));
  ::sendto(tx_sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&bc_addr, sizeof(bc_addr));
}

// -----------------------------------------------------------------------------
// Board 109 (Li2 Inverter Bridge) Broadcast Sender Function -> CYD (192.168.8.110)
// -----------------------------------------------------------------------------
inline void bridge_broadcast_telemetry(const BridgeTelemetryPacket &pkt) {
  static int b_sock = -1;
  static struct sockaddr_in cyd_addr;
  static struct sockaddr_in bc_addr;
  if (b_sock < 0) {
    b_sock = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (b_sock < 0) return;
    int opt = 1;
    ::setsockopt(b_sock, SOL_SOCKET, SO_BROADCAST, &opt, sizeof(opt));
    memset(&cyd_addr, 0, sizeof(cyd_addr));
    cyd_addr.sin_family = AF_INET;
    cyd_addr.sin_port = htons(BRIDGE_TELEMETRY_PORT);
    cyd_addr.sin_addr.s_addr = inet_addr("192.168.8.110");

    memset(&bc_addr, 0, sizeof(bc_addr));
    bc_addr.sin_family = AF_INET;
    bc_addr.sin_port = htons(BRIDGE_TELEMETRY_PORT);
    bc_addr.sin_addr.s_addr = inet_addr("192.168.8.255");
  }
  ::sendto(b_sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&cyd_addr, sizeof(cyd_addr));
  ::sendto(b_sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&bc_addr, sizeof(bc_addr));
}

// -----------------------------------------------------------------------------
// CYD Display Receiver Functions & Cache
// -----------------------------------------------------------------------------
inline TcanTelemetryPacket g_tcan_direct_pkt;
inline uint32_t g_tcan_last_recv_ms = 0;
inline int g_cyd_udp_rx_sock = -1;

inline BridgeTelemetryPacket g_bridge_direct_pkt;
inline uint32_t g_bridge_last_recv_ms = 0;
inline int g_cyd_bridge_rx_sock = -1;

inline void poll_tcan_bms_receiver() {
  // Poll Board 108 (BMS 8-Pack Data on Port 5005)
  if (g_cyd_udp_rx_sock < 0) {
    g_cyd_udp_rx_sock = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (g_cyd_udp_rx_sock >= 0) {
      int flags = fcntl(g_cyd_udp_rx_sock, F_GETFL, 0);
      fcntl(g_cyd_udp_rx_sock, F_SETFL, flags | O_NONBLOCK);
      int opt = 1;
      setsockopt(g_cyd_udp_rx_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
      struct sockaddr_in bind_addr;
      memset(&bind_addr, 0, sizeof(bind_addr));
      bind_addr.sin_family = AF_INET;
      bind_addr.sin_port = htons(TCAN_TELEMETRY_PORT);
      bind_addr.sin_addr.s_addr = htonl(INADDR_ANY);
      if (::bind(g_cyd_udp_rx_sock, (struct sockaddr *)&bind_addr, sizeof(bind_addr)) < 0) {
        ::close(g_cyd_udp_rx_sock);
        g_cyd_udp_rx_sock = -1;
      }
    }
  }
  if (g_cyd_udp_rx_sock >= 0) {
    TcanTelemetryPacket temp_pkt;
    struct sockaddr_in src_addr;
    socklen_t addr_len = sizeof(src_addr);
    while (true) {
      int len = ::recvfrom(g_cyd_udp_rx_sock, &temp_pkt, sizeof(temp_pkt), 0, (struct sockaddr *)&src_addr, &addr_len);
      if (len <= 0) break;
      if (len == sizeof(TcanTelemetryPacket) && temp_pkt.magic == TCAN_MAGIC) {
        g_tcan_direct_pkt = temp_pkt;
        g_tcan_last_recv_ms = esphome::millis();
      }
    }
  }
}

inline void poll_cyd_udp_receiver() {
  // 1. Poll Board 108 (BMS 8-Pack Data on Port 5005)
  poll_tcan_bms_receiver();

  // 2. Poll Board 109 (Li2 Inverter Bridge Data on Port 5006)
  if (g_cyd_bridge_rx_sock < 0) {
    g_cyd_bridge_rx_sock = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (g_cyd_bridge_rx_sock >= 0) {
      int flags = fcntl(g_cyd_bridge_rx_sock, F_GETFL, 0);
      fcntl(g_cyd_bridge_rx_sock, F_SETFL, flags | O_NONBLOCK);
      struct sockaddr_in bind_addr;
      memset(&bind_addr, 0, sizeof(bind_addr));
      bind_addr.sin_family = AF_INET;
      bind_addr.sin_port = htons(BRIDGE_TELEMETRY_PORT);
      bind_addr.sin_addr.s_addr = htonl(INADDR_ANY);
      if (::bind(g_cyd_bridge_rx_sock, (struct sockaddr *)&bind_addr, sizeof(bind_addr)) < 0) {
        ::close(g_cyd_bridge_rx_sock);
        g_cyd_bridge_rx_sock = -1;
      }
    }
  }
  if (g_cyd_bridge_rx_sock >= 0) {
    BridgeTelemetryPacket b_pkt;
    struct sockaddr_in src_addr;
    socklen_t addr_len = sizeof(src_addr);
    while (true) {
      int len = ::recvfrom(g_cyd_bridge_rx_sock, &b_pkt, sizeof(b_pkt), 0, (struct sockaddr *)&src_addr, &addr_len);
      if (len <= 0) break;
      if (len == sizeof(BridgeTelemetryPacket) && b_pkt.magic == BRIDGE_MAGIC) {
        g_bridge_direct_pkt = b_pkt;
        g_bridge_last_recv_ms = esphome::millis();
      }
    }
  }
}

inline bool is_tcan_direct_available() {
  return (g_tcan_last_recv_ms > 0 && (esphome::millis() - g_tcan_last_recv_ms) < 6000);
}

inline bool is_bridge_direct_available() {
  return (g_bridge_last_recv_ms > 0 && (esphome::millis() - g_bridge_last_recv_ms) < 6000);
}

// -----------------------------------------------------------------------------
// Per-Pack Live Communication Freshness Watchdog & Safety Floor Cache
// Prevents "Zombie Pack" bug where disconnected/sleeping BMS retains stale state
// -----------------------------------------------------------------------------
inline uint32_t g_pack_last_rx_ms[8] = {0, 0, 0, 0, 0, 0, 0, 0};
inline float g_reported_min_pack_v = 0.0f;
inline uint16_t g_reported_min_cell_mv = 0;
inline uint16_t g_reported_max_cell_mv = 0;

inline void mark_pack_rx_fresh(int idx) {
  if (idx >= 0 && idx < 8) {
    g_pack_last_rx_ms[idx] = esphome::millis();
  }
}

inline bool is_pack_fresh(int idx, uint32_t max_age_ms = 90000) {
  if (idx < 0 || idx >= 8) return false;
  uint32_t last = g_pack_last_rx_ms[idx];
  return (last > 0 && (esphome::millis() - last) <= max_age_ms);
}

// -----------------------------------------------------------------------------
// Live Li2 Pylontech Emulator Command & Safety State (Shared with Web UI & HA)
// -----------------------------------------------------------------------------
inline bool g_li2_charge_enabled = true;
inline bool g_li2_discharge_enabled = true;
inline bool g_li2_low_cutoff_latched = false;
inline bool g_li2_bms_fresh = false;
inline float g_li2_charge_limit_a = 120.0f;
inline float g_li2_discharge_limit_a = 120.0f;
inline uint16_t g_li2_min_cell_mv = 0;
inline uint16_t g_li2_max_cell_mv = 0;
inline float g_li2_min_pack_v = 0.0f;

// -----------------------------------------------------------------------------
// ESP-NOW Zero-Latency Direct Wireless Link (Tri-Redundant Failover)
// -----------------------------------------------------------------------------
#define ESPNOW_BMS_MAGIC 0x454E // 'EN' (BMS Summary Packet)
#define ESPNOW_P8_MAGIC  0x5038 // 'P8' (Pack 8 Telemetry Packet)

#pragma pack(push, 1)
struct EspNowBmsPacket {
  uint16_t magic;           // 0x454E
  uint8_t  seq;             // rolling sequence
  uint8_t  online_mask;     // Bit 0..7 for Pack 1..8
  int16_t  sys_soc_x10;     // Total SOC x10 (e.g. 850 = 85.0%)
  int16_t  sys_soh_x10;     // Total SOH x10 (e.g. 1000 = 100.0%)
  int16_t  sys_v_x100;      // Total Voltage x100 (e.g. 5325 = 53.25V)
  int16_t  sys_i_x10;       // Total Current x10 (e.g. -200 = -20.0A)
  int16_t  max_temp_x10;    // Max Temp x10 (e.g. 285 = 28.5C)
  uint16_t min_cell_mv;     // Weakest cell mV (e.g. 3320)
  uint16_t max_cell_mv;     // Strongest cell mV (e.g. 3345)
  uint16_t min_pack_v_x100; // Weakest pack V x100 (e.g. 5310 = 53.10V)
  uint16_t checksum;        // Sum of all previous bytes
};

struct EspNowPack8Packet {
  uint16_t magic;           // 0x5038
  uint8_t  seq;
  uint8_t  is_online;
  int16_t  voltage_x100;
  int16_t  busbar_v_x100;
  int16_t  current_x10;
  int16_t  soc_x10;
  int16_t  temp_x10;
  uint16_t min_cell_mv;
  uint16_t max_cell_mv;
  uint8_t  op_mode;
  uint16_t checksum;
};
#pragma pack(pop)

inline uint16_t calc_bms_checksum(const EspNowBmsPacket &pkt) {
  const uint8_t *p = (const uint8_t *)&pkt;
  uint16_t sum = 0;
  for (size_t i = 0; i < sizeof(EspNowBmsPacket) - 2; i++) {
    sum += p[i];
  }
  return sum;
}

inline uint16_t calc_p8_checksum(const EspNowPack8Packet &pkt) {
  const uint8_t *p = (const uint8_t *)&pkt;
  uint16_t sum = 0;
  for (size_t i = 0; i < sizeof(EspNowPack8Packet) - 2; i++) {
    sum += p[i];
  }
  return sum;
}

#if defined(ESP32) || defined(USE_ESP32)
inline uint32_t g_last_espnow_bms_rx_ms = 0;
inline EspNowBmsPacket g_espnow_bms_rx = {};

inline uint32_t g_last_espnow_p8_rx_ms = 0;
inline EspNowPack8Packet g_espnow_p8_rx = {};

inline void on_espnow_shared_recv(const esp_now_recv_info_t *recv_info, const uint8_t *data, int len) {
  if (data == nullptr || len <= 0) return;
  if (len == sizeof(EspNowBmsPacket)) {
    const EspNowBmsPacket *pkt = (const EspNowBmsPacket *)data;
    if (pkt->magic == ESPNOW_BMS_MAGIC) {
      if (pkt->checksum == calc_bms_checksum(*pkt)) {
        g_espnow_bms_rx = *pkt;
        g_last_espnow_bms_rx_ms = esphome::millis();
      }
    }
  } else if (len == sizeof(EspNowPack8Packet)) {
    const EspNowPack8Packet *pkt = (const EspNowPack8Packet *)data;
    if (pkt->magic == ESPNOW_P8_MAGIC) {
      if (pkt->checksum == calc_p8_checksum(*pkt)) {
        g_espnow_p8_rx = *pkt;
        g_last_espnow_p8_rx_ms = esphome::millis();
      }
    }
  }
}

inline bool init_espnow_shared_link() {
  static bool s_espnow_ready = false;
  if (s_espnow_ready) return true;

  esp_err_t err = esp_now_init();
  if (err != ESP_OK) {
    return false;
  }

  esp_now_register_recv_cb(on_espnow_shared_recv);

  static const uint8_t bc_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, bc_mac, 6);
  peer.channel = 0;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = false;
  esp_now_add_peer(&peer);

  s_espnow_ready = true;
  return true;
}

inline void espnow_broadcast_bms_summary(EspNowBmsPacket &pkt) {
  if (!init_espnow_shared_link()) return;
  pkt.checksum = calc_bms_checksum(pkt);
  static const uint8_t bc_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bc_mac, (const uint8_t *)&pkt, sizeof(pkt));
}

inline void espnow_broadcast_pack8_summary(EspNowPack8Packet &pkt) {
  if (!init_espnow_shared_link()) return;
  pkt.checksum = calc_p8_checksum(pkt);
  static const uint8_t bc_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bc_mac, (const uint8_t *)&pkt, sizeof(pkt));
}
#endif

// -----------------------------------------------------------------------------
// Active Current Equalizer & Mode-3 Synchronizer (Huawei ESM-48100B1)
// Official Huawei Registers (from MaintenanceTool.exe & ModbusModule.dll):
//   0x100B: Discharge Limit Coef (RAM, prec=3, unit=C, 1000 = 1.000C = 100A, 25 = 0.025C = 2.5A)
//   0x100D: Charge Limit Coef    (RAM, prec=3, unit=C, 1000 = 1.000C = 100A)
//   0x000E: Module Mode          (2 = Charge, 3 = Discharge)
//   0xB798: Intelligent Hybrid Constant-Voltage Mode (0 = Disable, 1 = Enable)
// -----------------------------------------------------------------------------
inline uint16_t g_eq_disch_coef[8] = {1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000};
inline uint16_t g_eq_chg_coef[8]   = {1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000};
inline uint8_t  g_eq_force_mode3[8] = {0, 0, 0, 0, 0, 0, 0, 0};
inline bool     g_eq_cmd_pending[8] = {false, false, false, false, false, false, false, false};
inline uint16_t g_eq_last_disch_coef[8] = {1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000};

template <typename TCtrl, typename TCmdItem>
inline void exec_huawei_bms_equalizer_slot(int idx, TCtrl *ctrl) {
  if (idx < 0 || idx >= 8 || ctrl == nullptr) return;
  if (!g_eq_cmd_pending[idx]) return;
  g_eq_cmd_pending[idx] = false;

  ctrl->set_allow_duplicate_commands(true);
  uint16_t dis_coef = g_eq_disch_coef[idx];
  uint16_t chg_coef = g_eq_chg_coef[idx];
  uint8_t force_m3 = g_eq_force_mode3[idx];
  g_eq_last_disch_coef[idx] = dis_coef;

  // 1. Official Huawei Function Code 0x10 (Write Multiple Registers) to 0x100B (Discharge Limit Coef in RAM)
  std::vector<uint16_t> v_dis = {dis_coef};
  auto cmd_dis10 = TCmdItem::create_write_multiple_command(ctrl, 0x100B, 1, v_dis);
  ctrl->queue_command(cmd_dis10);

  // 2. Function Code 0x06 fallback for 0x100B
  auto cmd_dis06 = TCmdItem::create_write_single_command(ctrl, 0x100B, dis_coef);
  ctrl->queue_command(cmd_dis06);

  if (force_m3) {
    // Ensure Charge Limit Coef (0x100D) = 1000 (100A), Hybrid Constant-Voltage Boost (0xB798) = 0, and Module Mode (0x000E) = 3
    std::vector<uint16_t> v_chg = {chg_coef};
    auto cmd_chg10 = TCmdItem::create_write_multiple_command(ctrl, 0x100D, 1, v_chg);
    ctrl->queue_command(cmd_chg10);

    std::vector<uint16_t> v_hyb = {0};
    auto cmd_hyb = TCmdItem::create_write_multiple_command(ctrl, 0xB798, 1, v_hyb);
    ctrl->queue_command(cmd_hyb);

    std::vector<uint16_t> v_m3 = {3};
    auto cmd_m3 = TCmdItem::create_write_multiple_command(ctrl, 0x000E, 1, v_m3);
    ctrl->queue_command(cmd_m3);
  }
}




#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <lwip/sockets.h>
#include <fcntl.h>
#include "esphome/core/hal.h"

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

    memset(&bc_addr, 0, sizeof(bc_addr));
    bc_addr.sin_family = AF_INET;
    bc_addr.sin_port = htons(TCAN_TELEMETRY_PORT);
    bc_addr.sin_addr.s_addr = inet_addr("192.168.8.255");
  }
  ::sendto(tx_sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&cyd_addr, sizeof(cyd_addr));
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



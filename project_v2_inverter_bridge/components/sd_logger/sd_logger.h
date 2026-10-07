// sd_logger.h — ESP32 SD Card Data Logger & Wi-Fi Download Server for LilyGO T-CAN485
// Features: Daily log rotation (bms_YYYY-MM-DD.csv), Automatic 3-day retention cleanup, Multi-file HTTP server
#pragma once

#include "esphome/core/component.h"
#include "esphome/core/log.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/time/real_time_clock.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <sys/unistd.h>
#include <time.h>

#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdspi_host.h"
#include "driver/spi_master.h"

#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace esphome {
namespace sd_logger {

static const char *const TAG = "sd_logger";
static const char *const MOUNT_POINT = "/sdcard";

class SDLogger : public PollingComponent {
 public:
  void set_pins(int cs, int mosi, int miso, int clk) {
    cs_pin_ = cs;
    mosi_pin_ = mosi;
    miso_pin_ = miso;
    clk_pin_ = clk;
  }

  void set_http_port(int port) { http_port_ = port; }
  void set_time(time::RealTimeClock *t) { time_ = t; }

  void set_voltage_sensor(sensor::Sensor *s) { voltage_sensor_ = s; }
  void set_current_sensor(sensor::Sensor *s) { current_sensor_ = s; }
  void set_power_sensor(sensor::Sensor *s) { power_sensor_ = s; }
  void set_soc_sensor(sensor::Sensor *s) { soc_sensor_ = s; }
  void set_temp_sensor(sensor::Sensor *s) { temp_sensor_ = s; }

  void set_pack1_soc(sensor::Sensor *s) { p1_soc_ = s; }
  void set_pack1_v(sensor::Sensor *s) { p1_v_ = s; }
  void set_pack1_i(sensor::Sensor *s) { p1_i_ = s; }

  void set_pack2_soc(sensor::Sensor *s) { p2_soc_ = s; }
  void set_pack2_v(sensor::Sensor *s) { p2_v_ = s; }
  void set_pack2_i(sensor::Sensor *s) { p2_i_ = s; }

  void set_pack3_soc(sensor::Sensor *s) { p3_soc_ = s; }
  void set_pack3_v(sensor::Sensor *s) { p3_v_ = s; }
  void set_pack3_i(sensor::Sensor *s) { p3_i_ = s; }

  void set_pack4_soc(sensor::Sensor *s) { p4_soc_ = s; }
  void set_pack4_v(sensor::Sensor *s) { p4_v_ = s; }
  void set_pack4_i(sensor::Sensor *s) { p4_i_ = s; }

  void set_inverter_queries(sensor::Sensor *s) { inq_sensor_ = s; }

  float get_setup_priority() const override { return setup_priority::LATE; }

  void setup() override {
    ESP_LOGI(TAG, "Starting SD Card Logger & Web Server setup...");
    // Always start HTTP download server task on port 8080
    xTaskCreatePinnedToCore(http_server_task_entry, "sd_http_server", 6144, this, 2, nullptr, 1);

    // Initial mount attempt
    try_mount();
  }

  void dump_config() override {
    ESP_LOGCONFIG(TAG, "SD Card Data Logger (Daily Rotation & 3-Day Retention):");
    ESP_LOGCONFIG(TAG, "  Pins: CS=%d, MOSI=%d, MISO=%d, CLK=%d", cs_pin_, mosi_pin_, miso_pin_, clk_pin_);
    ESP_LOGCONFIG(TAG, "  Mount Status: %s (error: %s)", mounted_ ? "MOUNTED (OK)" : "FAILED / NOT MOUNTED", last_error_.c_str());
    ESP_LOGCONFIG(TAG, "  HTTP Download Port: %d", http_port_);
    if (mounted_) {
      ESP_LOGCONFIG(TAG, "  Active Today's Log: %s", get_today_log_path().c_str());
    }
  }

  bool try_mount(bool force_format = true) {
    if (mounted_) return true;

    ESP_LOGI(TAG, "Configuring SPI pins (CS=%d, MOSI=%d, MISO=%d, CLK=%d) with pull-ups...",
             cs_pin_, mosi_pin_, miso_pin_, clk_pin_);

    gpio_set_pull_mode((gpio_num_t)cs_pin_, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode((gpio_num_t)miso_pin_, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode((gpio_num_t)mosi_pin_, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode((gpio_num_t)clk_pin_, GPIO_PULLUP_ONLY);

    esp_vfs_fat_mount_config_t mount_config = {
        .format_if_mount_failed = force_format,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024,
        .disk_status_check_enable = false,
        .use_one_fat = false
    };

    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.max_freq_khz = SDMMC_FREQ_DEFAULT;

    if (!spi_initialized_) {
      spi_bus_config_t bus_cfg = {
          .mosi_io_num = (gpio_num_t)mosi_pin_,
          .miso_io_num = (gpio_num_t)miso_pin_,
          .sclk_io_num = (gpio_num_t)clk_pin_,
          .quadwp_io_num = -1,
          .quadhd_io_num = -1,
          .max_transfer_sz = 4000,
      };

      esp_err_t ret = spi_bus_initialize((spi_host_device_t)host.slot, &bus_cfg, SDSPI_DEFAULT_DMA);
      if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        last_error_ = "SPI Init Failed: " + std::string(esp_err_to_name(ret));
        ESP_LOGE(TAG, "%s", last_error_.c_str());
        return false;
      }
      spi_initialized_ = true;
    }

    sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_config.gpio_cs = (gpio_num_t)cs_pin_;
    slot_config.host_id = (spi_host_device_t)host.slot;

    esp_err_t ret = esp_vfs_fat_sdspi_mount(MOUNT_POINT, &host, &slot_config, &mount_config, &card_);
    if (ret != ESP_OK) {
      last_error_ = "Mount Failed: " + std::string(esp_err_to_name(ret));
      ESP_LOGW(TAG, "SD Card mount failed (%s)", esp_err_to_name(ret));
      return false;
    }

    mounted_ = true;
    last_error_ = "Active (FAT32 Mounted)";
    uint64_t capacity_mb = ((uint64_t)card_->csd.capacity) * card_->csd.sector_size / (1024 * 1024);
    ESP_LOGI(TAG, "SD Card mounted successfully at %s! Capacity: %llu MB", MOUNT_POINT, capacity_mb);

    // Initial check of today's file and retention cleanup if time is already valid
    if ((time_ != nullptr && time_->now().is_valid()) || ::time(nullptr) >= 1700000000) {
      std::string today_path = get_today_log_path();
      if (!today_path.empty()) {
        FILE *check = fopen(today_path.c_str(), "r");
        if (!check) {
          write_csv_header(today_path);
        } else {
          fclose(check);
        }
      }
      clean_old_logs();
    }
    return true;
  }

  void update() override {
    if (!mounted_) {
      static uint32_t retry_count = 0;
      if (++retry_count % 3 == 0) {  // retry mount every 30s
        ESP_LOGW(TAG, "SD Card not yet mounted (%s). Retrying mount...", last_error_.c_str());
        try_mount();
      }
      return;
    }

    // Wait for valid NTP time before writing daily log
    if ((time_ != nullptr && !time_->now().is_valid()) && ::time(nullptr) < 1700000000) {
      ESP_LOGD(TAG, "Waiting for NTP time sync before opening daily log file...");
      return;
    }

    std::string today_path = get_today_log_path();
    if (today_path.empty()) return;

    // Check if daily file needs header (only if file does not exist or is 0 bytes)
    FILE *check = fopen(today_path.c_str(), "r");
    if (!check) {
      write_csv_header(today_path);
    } else {
      fseek(check, 0, SEEK_END);
      if (ftell(check) == 0) {
        fclose(check);
        write_csv_header(today_path);
      } else {
        fclose(check);
      }
    }

    FILE *f = fopen(today_path.c_str(), "a");
    if (!f) {
      ESP_LOGW(TAG, "Failed to open %s for appending", today_path.c_str());
      return;
    }

    std::string dt = get_datetime_str();
    uint32_t sec = millis() / 1000;
    fprintf(f, "%s,%lu,%.2f,%.2f,%.1f,%.1f,%.1f,%.1f,%.2f,%.2f,%.1f,%.2f,%.2f,%.1f,%.2f,%.2f,%.1f,%.2f,%.2f,%lu\n",
            dt.c_str(),
            (unsigned long)sec,
            get_val(voltage_sensor_),
            get_val(current_sensor_),
            get_val(power_sensor_),
            get_val(soc_sensor_),
            get_val(temp_sensor_),
            get_val(p1_soc_), get_val(p1_v_), get_val(p1_i_),
            get_val(p2_soc_), get_val(p2_v_), get_val(p2_i_),
            get_val(p3_soc_), get_val(p3_v_), get_val(p3_i_),
            get_val(p4_soc_), get_val(p4_v_), get_val(p4_i_),
            (unsigned long)get_val(inq_sensor_));

    fclose(f);

    // Run 3-day retention cleanup every 60 updates (~10 minutes)
    static uint32_t update_cycles = 0;
    if (++update_cycles % 60 == 0) {
      clean_old_logs();
    }
  }

  void write_csv_header(const std::string &path) {
    FILE *f = fopen(path.c_str(), "w");
    if (f) {
      fprintf(f, "datetime,uptime_sec,total_v,total_a,total_w,total_soc,max_temp,"
                 "p1_soc,p1_v,p1_a,p2_soc,p2_v,p2_a,p3_soc,p3_v,p3_a,p4_soc,p4_v,p4_a,inverter_queries\n");
      fclose(f);
      ESP_LOGI(TAG, "Created fresh CSV daily log header at %s", path.c_str());
    }
  }

  // Deletes any daily log files older than 3 days (scans days 4 to 30)
  void clean_old_logs() {
    if (!mounted_) return;

    time_t now_sec = ::time(nullptr);
    if (time_ != nullptr && time_->now().is_valid()) {
      now_sec = time_->now().timestamp;
    }
    // If system time has not synced yet (year < 2024), do not delete anything
    if (now_sec < 1700000000) return;

    for (int d = 4; d <= 30; d++) {
      time_t past_sec = now_sec - (d * 86400);
      struct tm past_tm;
      localtime_r(&past_sec, &past_tm);
      char past_file[32];
      snprintf(past_file, sizeof(past_file), "%s/%04d%02d%02d.csv",
               MOUNT_POINT, past_tm.tm_year + 1900, past_tm.tm_mon + 1, past_tm.tm_mday);
      if (remove(past_file) == 0) {
        ESP_LOGI(TAG, "Deleted expired log file: %s (%d days old)", past_file, d);
      }
    }
  }

  std::string get_today_log_path() {
    std::string date_str = get_date_str();
    if (date_str.empty()) return "";
    return std::string(MOUNT_POINT) + "/" + date_str + ".csv";
  }

  std::string get_date_str() {
    if (time_ != nullptr && time_->now().is_valid()) {
      auto now = time_->now();
      char buf[16];
      snprintf(buf, sizeof(buf), "%04d%02d%02d", now.year, now.month, now.day_of_month);
      return std::string(buf);
    }
    time_t now_sec = ::time(nullptr);
    if (now_sec >= 1700000000) {
      struct tm t;
      localtime_r(&now_sec, &t);
      char buf[16];
      snprintf(buf, sizeof(buf), "%04d%02d%02d", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday);
      return std::string(buf);
    }
    return "";
  }

  std::string get_datetime_str() {
    if (time_ != nullptr && time_->now().is_valid()) {
      auto now = time_->now();
      char buf[32];
      snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d",
               now.year, now.month, now.day_of_month, now.hour, now.minute, now.second);
      return std::string(buf);
    }
    time_t now_sec = ::time(nullptr);
    if (now_sec >= 1700000000) {
      struct tm t;
      localtime_r(&now_sec, &t);
      char buf[32];
      snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d",
               t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec);
      return std::string(buf);
    }
    return "0000-00-00 00:00:00";
  }

 private:
  int cs_pin_{13};
  int mosi_pin_{15};
  int miso_pin_{2};
  int clk_pin_{14};
  int http_port_{8080};

  bool mounted_{false};
  bool spi_initialized_{false};
  std::string last_error_{"Not initialized"};
  sdmmc_card_t *card_{nullptr};

  time::RealTimeClock *time_{nullptr};

  sensor::Sensor *voltage_sensor_{nullptr};
  sensor::Sensor *current_sensor_{nullptr};
  sensor::Sensor *power_sensor_{nullptr};
  sensor::Sensor *soc_sensor_{nullptr};
  sensor::Sensor *temp_sensor_{nullptr};

  sensor::Sensor *p1_soc_{nullptr};
  sensor::Sensor *p1_v_{nullptr};
  sensor::Sensor *p1_i_{nullptr};

  sensor::Sensor *p2_soc_{nullptr};
  sensor::Sensor *p2_v_{nullptr};
  sensor::Sensor *p2_i_{nullptr};

  sensor::Sensor *p3_soc_{nullptr};
  sensor::Sensor *p3_v_{nullptr};
  sensor::Sensor *p3_i_{nullptr};

  sensor::Sensor *p4_soc_{nullptr};
  sensor::Sensor *p4_v_{nullptr};
  sensor::Sensor *p4_i_{nullptr};

  sensor::Sensor *inq_sensor_{nullptr};

  float get_val(sensor::Sensor *s) {
    return (s && s->has_state()) ? s->state : 0.0f;
  }

  static void http_server_task_entry(void *arg) {
    static_cast<SDLogger *>(arg)->http_server_task();
  }

  void http_server_task() {
    vTaskDelay(pdMS_TO_TICKS(4000));  // Wait 4s for network stack and Wi-Fi to stabilize

    while (true) {
      int server_fd = lwip_socket(AF_INET, SOCK_STREAM, 0);
      if (server_fd < 0) {
        ESP_LOGW(TAG, "HTTP Server socket creation failed, retrying in 2s...");
        vTaskDelay(pdMS_TO_TICKS(2000));
        continue;
      }

      int opt = 1;
      lwip_setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

      struct sockaddr_in server_addr{};
      server_addr.sin_family = AF_INET;
      server_addr.sin_addr.s_addr = htonl(INADDR_ANY);
      server_addr.sin_port = htons(http_port_);

      if (lwip_bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        ESP_LOGW(TAG, "HTTP Server bind failed on port %d, retrying in 2s...", http_port_);
        lwip_close(server_fd);
        vTaskDelay(pdMS_TO_TICKS(2000));
        continue;
      }

      lwip_listen(server_fd, 4);
      ESP_LOGI(TAG, "Wi-Fi SD Log Download Server active on port %d", http_port_);

      char rx_buf[512];
      char tx_buf[2048];

      while (true) {
        struct sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);
        int client_fd = lwip_accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
          vTaskDelay(pdMS_TO_TICKS(50));
          continue;
        }

        int len = lwip_recv(client_fd, rx_buf, sizeof(rx_buf) - 1, 0);
        if (len > 0) {
          rx_buf[len] = '\0';

          // Determine requested file path
          // Determine requested file path
          std::string target_file = "";
          std::string download_filename = "log.csv";

          if (strstr(rx_buf, "GET /log.csv") != nullptr || strstr(rx_buf, "GET /download") != nullptr) {
            target_file = get_today_log_path();
            download_filename = get_date_str() + ".csv";
          } else if (strstr(rx_buf, "GET /20") != nullptr) {
            // Specific daily file requested, e.g. GET /20260930.csv HTTP/1.1
            const char *start = strstr(rx_buf, "GET /20");
            if (start) {
              start += 5; // skip "GET /"
              const char *end = strstr(start, " ");
              if (end) {
                std::string fname(start, end - start);
                target_file = std::string(MOUNT_POINT) + "/" + fname;
                download_filename = fname;
              }
            }
          } else if (strstr(rx_buf, "GET /bms_log.csv") != nullptr) {
            target_file = "/sdcard/bms_log.csv";
            download_filename = "bms_log.csv";
          }

          if (!target_file.empty()) {
            FILE *f = fopen(target_file.c_str(), "r");
            if (f) {
              fseek(f, 0, SEEK_END);
              long fsize = ftell(f);
              fseek(f, 0, SEEK_SET);

              int hdr_len = snprintf(tx_buf, sizeof(tx_buf),
                                     "HTTP/1.1 200 OK\r\n"
                                     "Content-Type: text/csv\r\n"
                                     "Content-Disposition: attachment; filename=\"%s\"\r\n"
                                     "Content-Length: %ld\r\n"
                                     "Connection: close\r\n\r\n",
                                     download_filename.c_str(),
                                     fsize);
              lwip_send(client_fd, tx_buf, hdr_len, 0);

              size_t bytes_read;
              while ((bytes_read = fread(tx_buf, 1, sizeof(tx_buf), f)) > 0) {
                lwip_send(client_fd, tx_buf, bytes_read, 0);
              }
              fclose(f);
            } else {
              const char *not_found = "HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\nLog file not found.";
              lwip_send(client_fd, not_found, strlen(not_found), 0);
            }
          } else if (strstr(rx_buf, "GET /clear") != nullptr) {
            write_csv_header(get_today_log_path());
            const char *redirect = "HTTP/1.1 302 Found\r\nLocation: /\r\nConnection: close\r\n\r\n";
            lwip_send(client_fd, redirect, strlen(redirect), 0);
          } else if (strstr(rx_buf, "GET /format") != nullptr) {
            ESP_LOGW(TAG, "Format requested via HTTP. Formatting SD Card to FAT32...");
            if (mounted_) {
              esp_vfs_fat_sdcard_unmount(MOUNT_POINT, card_);
              mounted_ = false;
            }
            try_mount(true);
            const char *redirect = "HTTP/1.1 302 Found\r\nLocation: /\r\nConnection: close\r\n\r\n";
            lwip_send(client_fd, redirect, strlen(redirect), 0);
          } else {
            // Status landing page — check files for last 4 days directly
            std::string file_list_html = "";
            time_t now_sec = ::time(nullptr);
            if (time_ != nullptr && time_->now().is_valid()) {
              now_sec = time_->now().timestamp;
            }
            if (now_sec >= 1700000000) {
              for (int d = 0; d < 4; d++) {
                time_t t_sec = now_sec - (d * 86400);
                struct tm t_tm;
                localtime_r(&t_sec, &t_tm);
                char fname[16];
                snprintf(fname, sizeof(fname), "%04d%02d%02d.csv",
                         t_tm.tm_year + 1900, t_tm.tm_mon + 1, t_tm.tm_mday);
                char fpath[32];
                snprintf(fpath, sizeof(fpath), "%s/%s", MOUNT_POINT, fname);
                FILE *check_f = fopen(fpath, "r");
                if (check_f != nullptr) {
                  fseek(check_f, 0, SEEK_END);
                  long fsize = ftell(check_f);
                  fclose(check_f);
                  char item[256];
                  snprintf(item, sizeof(item),
                           "<li><a href='/%s' style='font-weight:bold;'>📄 %s</a> &nbsp;(%.2f KB) %s</li>",
                           fname, fname, fsize / 1024.0f,
                           d == 0 ? "<span style='color:#28a745;'><b>[Today]</b></span>" : "");
                  file_list_html += item;
                }
              }
            }
            FILE *f_leg = fopen("/sdcard/bms_log.csv", "r");
            if (f_leg != nullptr) {
              fseek(f_leg, 0, SEEK_END);
              long fsize = ftell(f_leg);
              fclose(f_leg);
              char item[256];
              snprintf(item, sizeof(item),
                       "<li><a href='/bms_log.csv'>📄 bms_log.csv (Legacy)</a> &nbsp;(%.2f KB)</li>",
                       fsize / 1024.0f);
              file_list_html += item;
            }
            if (file_list_html.empty()) {
              file_list_html = "<li>No log files recorded yet.</li>";
            }

            int html_len = snprintf(tx_buf, sizeof(tx_buf),
                                    "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
                                    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Huawei ESM SD Logger</title></head>"
                                    "<body style='font-family:sans-serif;padding:20px;max-width:650px;margin:auto;'>"
                                    "<h2>🔋 Huawei ESM-48100B1 SD Logger</h2>"
                                    "<p><b>Status:</b> %s</p>"
                                    "<p><b>Detail:</b> %s</p>"
                                    "<p><b>Current Time:</b> %s</p>"
                                    "<p><b>Policy:</b> Daily file rotation + Automatic 3-day retention cleanup</p>"
                                    "<hr>"
                                    "<h3>📁 Available Daily Logs (Last 3 Days)</h3>"
                                    "<ul>%s</ul>"
                                    "<hr>"
                                    "<h3>📊 Live Telemetry</h3>"
                                    "<ul>"
                                    "<li><b>Total Voltage:</b> %.2f V</li>"
                                    "<li><b>Total Current:</b> %.2f A</li>"
                                    "<li><b>Total Power:</b> %.1f W</li>"
                                    "<li><b>Total SOC:</b> %.0f %%</li>"
                                    "<li><b>Max Cell Temp:</b> %.0f &deg;C</li>"
                                    "<li><b>Inverter Queries:</b> %lu</li>"
                                    "</ul>"
                                    "<hr>"
                                    "<p><a href='/log.csv' style='display:inline-block;padding:10px 20px;background:#28a745;color:white;text-decoration:none;border-radius:5px;'>⬇️ Download Today's Log</a></p>"
                                    "<p><a href='/clear' onclick='return confirm(\"Reset today log?\");' style='color:#dc3545;'>Reset Today's Log</a> &nbsp;|&nbsp; "
                                    "<a href='/format' onclick='return confirm(\"Re-format MicroSD Card to FAT32? All data will be deleted.\");' style='color:#e0a800;'>Re-format SD to FAT32</a></p>"
                                    "</body></html>",
                                    mounted_ ? "✅ Mounted (FAT32 Active)" : "❌ Not Mounted",
                                    last_error_.c_str(),
                                    get_datetime_str().c_str(),
                                    file_list_html.c_str(),
                                    get_val(voltage_sensor_),
                                    get_val(current_sensor_),
                                    get_val(power_sensor_),
                                    get_val(soc_sensor_),
                                    get_val(temp_sensor_),
                                    (unsigned long)get_val(inq_sensor_));
            lwip_send(client_fd, tx_buf, html_len, 0);
          }
        }

        lwip_close(client_fd);
      }
    }
  }
};

}  // namespace sd_logger
}  // namespace esphome

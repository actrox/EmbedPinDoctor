window.WorkbenchExamples = {
  all: {
    esp32_iot_node: {
      project_name: "esp32_iot_node",
      notes: "ESP32 Wi-Fi IoT node with OLED, LoRa telemetry and status LEDs.",
      chip_id: "esp32-wroom-32",
      module_ids: ["oled_i2c", "analog_sensor", "lorawan_uart", "ws2812"],
    },
    stm32_sensor_board: {
      project_name: "stm32_sensor_board",
      notes:
        "STM32 sensor acquisition board with IMU, local display and SD logging.",
      chip_id: "stm32f103c8t6",
      module_ids: ["oled_i2c", "mpu6050", "button", "buzzer", "sd_card"],
    },
    rp2040_control_panel: {
      project_name: "rp2040_control_panel",
      notes:
        "RP2040 operator panel with rotary encoder, keys, buzzer and OLED.",
      chip_id: "rp2040",
      module_ids: ["rotary_encoder", "button", "buzzer", "oled_i2c"],
    },
  },
  get(id) {
    return this.all[id];
  },
};

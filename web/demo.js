const demoChips = [
  { id: "stm32f103c8t6", name: "STM32F103C8T6", voltage: "3.3V" },
  { id: "esp32-wroom-32", name: "ESP32-WROOM-32", voltage: "3.3V" },
  { id: "rp2040", name: "RP2040", voltage: "3.3V" },
];

const demoModules = [
  { id: "oled_i2c", name: "OLED SSD1306", description: "I2C display" },
  { id: "mpu6050", name: "MPU-6050", description: "Six-axis IMU" },
  { id: "button", name: "Push button", description: "Active-low GPIO input" },
  { id: "buzzer", name: "Passive buzzer", description: "PWM output" },
  { id: "sd_card", name: "SD card", description: "SPI storage" },
  { id: "ws2812", name: "WS2812 strip", description: "Single-wire LED" },
  {
    id: "rotary_encoder",
    name: "Rotary encoder",
    description: "Quadrature user input",
  },
  {
    id: "analog_sensor",
    name: "Analog sensor",
    description: "ADC measurement",
  },
  { id: "lorawan_uart", name: "LoRaWAN module", description: "UART telemetry" },
];

const demoAllocation = [
  ["oled_i2c", "OLED SSD1306", "SCL", "PB6", "I2C1_SCL", 94],
  ["oled_i2c", "OLED SSD1306", "SDA", "PB7", "I2C1_SDA", 94],
  ["mpu6050", "MPU-6050", "SCL", "PB6", "I2C1_SCL", 92],
  ["mpu6050", "MPU-6050", "SDA", "PB7", "I2C1_SDA", 92],
  ["button", "Push button", "KEY", "PA1", "GPIO", 88],
  ["buzzer", "Passive buzzer", "PWM", "PA8", "PWM", 86],
  ["rotary_encoder", "Rotary encoder", "A", "PA0", "GPIO", 88],
  ["rotary_encoder", "Rotary encoder", "B", "PA1", "GPIO", 88],
  ["analog_sensor", "Analog sensor", "AO", "PA0", "ADC", 90],
  ["lorawan_uart", "LoRaWAN module", "TX", "PA10", "UART_RX", 87],
  ["lorawan_uart", "LoRaWAN module", "RX", "PA9", "UART_TX", 87],
  ["ws2812", "WS2812 strip", "DIN", "PB0", "GPIO", 84],
].map(([module_id, module_name, module_pin, chip_pin, func, score]) => ({
  module_id,
  module_name,
  module_pin,
  chip_pin,
  function: func,
  score,
  note: "Low-risk assignment",
  direction: "bidirectional",
}));

const demoRisks = [
  {
    level: "警告",
    code: "data_unverified",
    message: "主控数据仍需完成最终人工手册复核。",
    suggestion: "打样前请根据官方数据手册核对所选引脚。",
    weight: 7.5,
  },
  {
    level: "提示",
    code: "pullup_required",
    message: "请确认 I2C 总线配有合适的上拉电阻。",
    suggestion: "检查板载电阻，并根据总线速率和长度计算等效上拉。",
    weight: 2,
  },
];

async function demoApi(path, options = {}) {
  if (
    options.method &&
    options.method !== "GET" &&
    !path.startsWith("/api/allocate")
  )
    throw new Error(window.I18N.t("readOnly"));
  if (path.startsWith("/api/chips")) return { chips: demoChips };
  if (path.startsWith("/api/modules")) return { modules: demoModules };
  if (path === "/api/projects") return { projects: [] };
  if (path === "/api/ecosystem") return { packages: [], plugins: [] };
  if (path === "/api/version") return { version: "0.2.0-alpha.1-demo" };
  if (path === "/api/allocate") {
    const request = options.body ? JSON.parse(options.body) : {};
    const selectedChip =
      demoChips.find((chip) => chip.id === request.chip_id) || demoChips[0];
    const requestedModules =
      request.module_ids || demoModules.slice(0, 4).map((item) => item.id);
    const selectedAllocation = demoAllocation.filter((item) =>
      requestedModules.includes(item.module_id),
    );
    return {
      chip: selectedChip,
      modules: demoModules.filter((item) => requestedModules.includes(item.id)),
      allocation: selectedAllocation,
      risks: demoRisks,
      alternatives: [
        {
          name: "Balanced low-risk plan",
          score: 91,
          change_count: 0,
          allocation: selectedAllocation,
        },
        {
          name: "Debug-port preserving plan",
          score: 88,
          change_count: 2,
          allocation: selectedAllocation.map((item) => ({ ...item })),
        },
      ],
      solver: {
        status: "optimal",
        nodes_searched: 128,
        limit_reached: false,
        assigned_count: selectedAllocation.length,
        total_count: selectedAllocation.length,
      },
      data_trust: {
        verified: selectedChip.id === "stm32f103c8t6",
        status:
          selectedChip.id === "stm32f103c8t6" ? "verified" : "review_required",
        source: "https://www.st.com/",
      },
    };
  }
  throw new Error(`Unsupported demo endpoint: ${path}`);
}

window.DemoAPI = { request: demoApi };

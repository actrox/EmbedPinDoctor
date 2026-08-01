from pathlib import Path


def generate_platformio_project(output_dir, chip, allocation):
    output_dir = Path(output_dir)
    src_dir = output_dir / "src"
    include_dir = output_dir / "include"
    src_dir.mkdir(parents=True, exist_ok=True)
    include_dir.mkdir(parents=True, exist_ok=True)
    platform = "espressif32" if "ESP32" in chip["name"].upper() else "ststm32"
    board = "esp32dev" if platform == "espressif32" else "genericSTM32F103C8"
    framework = "arduino"
    (output_dir / "platformio.ini").write_text(f"[env:{board}]\nplatform = {platform}\nboard = {board}\nframework = {framework}\n", encoding="utf-8")
    (src_dir / "main.cpp").write_text("#include <Arduino.h>\n#include \"pins.h\"\n\nvoid setup() {\n}\n\nvoid loop() {\n}\n", encoding="utf-8")
    lines = ["#pragma once", "// EmbedPinDoctor PlatformIO 模板引脚定义"]
    for item in allocation:
        if item["chip_pin"] != "未分配":
            name = (item["module_id"] + "_" + item["module_pin"]).upper().replace("-", "_")
            lines.append(f"#define {name} {item['chip_pin']}")
    (include_dir / "pins.h").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"path": str(output_dir), "platform": platform, "board": board}

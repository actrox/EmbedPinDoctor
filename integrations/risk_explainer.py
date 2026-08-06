DEFAULT_EXPLANATIONS = {
    "debug_pin": "调试引脚被外设占用后，下载器可能无法连接芯片，调试断点和在线烧录也会受影响。",
    "boot_pin": "启动脚在上电瞬间决定启动模式，外部上拉、下拉或模块输出可能让芯片进入错误启动状态。",
    "voltage_mismatch": "模块电压和芯片 IO 电压不一致时，可能出现识别失败、长期不稳定，严重时会损坏 IO。",
    "pin_duplicate": "多个非共享信号连接到同一个引脚会造成逻辑冲突，软件无法同时正确控制这些设备。",
    "unassigned": "未分配说明当前芯片数据中找不到满足该模块需求的可用引脚，需要调整方案。",
    "pullup_required": "I2C 是开漏总线，缺少上拉会导致 SDA/SCL 无法稳定回到高电平。",
    "data_unverified": "该芯片条目已通过格式和机器规则检查，但尚未由硬件工程师依据指定版本数据手册签字确认。",
    "output_on_input_only": "输入专用引脚没有输出驱动结构，无法产生控制外设所需的电平。",
    "input_overvoltage": "输入电压超过引脚允许范围时，可能触发保护二极管导通、造成误动作或永久损坏。",
    "drive_current_exceeded": "GPIO 适合传输逻辑信号，不应直接为超过建议电流的负载供电。",
    "five_v_tolerance_required": "只有数据手册明确标注为 5V 容忍的输入，才可在规定条件下接收高于 VDD 的电平。",
    "open_drain_unsupported": "I2C 等线与总线要求开漏输出，由外部上拉产生高电平。",
    "scan_unknown_pin": "项目文件中的引脚名与当前选择的主控不一致，常见原因是主控选择错误、旧配置残留或命名格式不同。",
    "scan_symbol_conflict": "同一个信号名称在不同文件中指向不同引脚，会让代码配置与原理图接线产生偏差。",
    "scan_pin_reused": "一个物理引脚出现多个信号名称可能是别名，也可能是真实复用冲突，需要结合来源文件确认。",
    "doctor_scan_mismatch": "医生推荐方案与项目现状不同；这不是自动修改指令，应先确认原理图和固件是否需要同步迁移。",
    "locked_pin_conflict": "锁定条件是强约束；被锁引脚不支持信号功能、已被占用或违反电气方向时，求解器不会静默改用其他引脚。",
    "i2c_address_conflict": "同一 I2C 总线上两个从设备地址相同，主控无法仅凭地址区分目标设备。",
    "spi_mode_mixed": "共享 SPI 总线可以连接不同模式设备，但驱动必须在切换片选时正确重配时钟极性和相位。",
    "spi_frequency_limit": "共享总线的默认频率不能超过最慢设备的额定上限。",
    "uart_flow_control_missing": "要求硬件流控的 UART 链路需要 CTS 和 RTS；缺失时可能在高负载下丢失数据。",
    "pwm_timer_frequency_conflict": "同一定时器的多个通道通常共享计数周期，因此不能独立设置互不兼容的 PWM 基频。",
}


def explain_risks(risks):
    explained = []
    for risk in risks:
        item = dict(risk)
        item["explanation"] = DEFAULT_EXPLANATIONS.get(risk.get("code"), "该风险来自规则检查结果，建议结合芯片手册和模块资料确认。")
        explained.append(item)
    return explained

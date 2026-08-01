DEFAULT_EXPLANATIONS = {
    "debug_pin": "调试引脚被外设占用后，下载器可能无法连接芯片，调试断点和在线烧录也会受影响。",
    "boot_pin": "启动脚在上电瞬间决定启动模式，外部上拉、下拉或模块输出可能让芯片进入错误启动状态。",
    "voltage_mismatch": "模块电压和芯片 IO 电压不一致时，可能出现识别失败、长期不稳定，严重时会损坏 IO。",
    "pin_duplicate": "多个非共享信号连接到同一个引脚会造成逻辑冲突，软件无法同时正确控制这些设备。",
    "unassigned": "未分配说明当前芯片数据中找不到满足该模块需求的可用引脚，需要调整方案。",
    "pullup_required": "I2C 是开漏总线，缺少上拉会导致 SDA/SCL 无法稳定回到高电平。",
}


def explain_risks(risks):
    explained = []
    for risk in risks:
        item = dict(risk)
        item["explanation"] = DEFAULT_EXPLANATIONS.get(risk.get("code"), "该风险来自规则检查结果，建议结合芯片手册和模块资料确认。")
        explained.append(item)
    return explained

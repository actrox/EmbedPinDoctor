#!/usr/bin/env python3
"""KiCad .kicad_sym 符号文件 → EmbedPinDoctor 模块数据 JSON"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple


def parse_sexp(text: str) -> list:
    """简易 S 表达式解析器。(a (b c) d) -> ['a', ['b', 'c'], 'd']，字符串保留引号形式或 token."""
    tokens = _tokenize(text)
    result, _ = _parse_list(tokens, 0)
    return result

def _tokenize(text: str) -> List[str]:
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            tokens.append(c); i += 1
        elif c == '"':
            j = i + 1
            buf = ['"']
            while j < n:
                if text[j] == '\\' and j + 1 < n:
                    buf.append(text[j]); buf.append(text[j+1]); j += 2
                elif text[j] == '"':
                    buf.append('"'); j += 1; break
                else:
                    buf.append(text[j]); j += 1
            tokens.append("".join(buf))
            i = j
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens

def _parse_list(tokens, pos):
    """从 tokens[pos]=='(' 开始解析，返回 (list, next_pos)"""
    if tokens[pos] != "(":
        raise ValueError(f"Expected '(' at {pos}, got {tokens[pos]!r}")
    pos += 1
    result = []
    while pos < len(tokens):
        t = tokens[pos]
        if t == ")":
            return result, pos + 1
        elif t == "(":
            sub, pos = _parse_list(tokens, pos)
            result.append(sub)
        else:
            if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
                result.append(t[1:-1])
            else:
                try:
                    if "." in t: result.append(float(t))
                    else: result.append(int(t))
                except ValueError:
                    result.append(t)
            pos += 1
    raise ValueError("Unterminated list")


def find_symbols(sexp) -> List[Dict]:
    """从最外层 (kicad_symbol_lib ...) 提取 symbol 列表。"""
    if not sexp or sexp[0] != "kicad_symbol_lib":
        return []
    result = []
    for node in sexp[1:]:
        if isinstance(node, list) and node and node[0] == "symbol":
            result.append(node)
    return result


def parse_symbol(sym_sexp: list) -> Dict:
    """从 (symbol "NAME" ...) 提取 name, properties, pins"""
    name = sym_sexp[1] if len(sym_sexp) > 1 else "UNKNOWN"
    if isinstance(name, list): name = "SYMBOL"
    properties: Dict[str, str] = {}
    pins: List[Dict] = []
    for node in sym_sexp[2:]:
        if not isinstance(node, list):
            continue
        tag = node[0]
        if tag == "property" and len(node) >= 3:
            key = node[1]; val = node[2]
            if isinstance(key, list): key = "".join(str(x) for x in key)
            if isinstance(val, list): val = "".join(str(x) for x in val)
            properties[str(key)] = str(val)
        elif tag == "pin":
            pins.append(_parse_pin(node))
        elif tag == "symbol":
            for sub in node[2:]:
                if isinstance(sub, list) and sub and sub[0] == "pin":
                    pins.append(_parse_pin(sub))
    return {"name": name, "properties": properties, "pins": pins}


def _parse_pin(pin_sexp) -> Dict:
    """(pin "name" (num 1) (type input) ...)"""
    pin = {"name": pin_sexp[1] if len(pin_sexp) > 1 else "",
           "num": None, "type": "passive"}
    for item in pin_sexp[2:]:
        if not isinstance(item, list) or not item:
            continue
        k = item[0]
        if k == "num" and len(item) > 1: pin["num"] = str(item[1])
        elif k == "type" and len(item) > 1: pin["type"] = str(item[1])
    return pin


def pin_type_to_direction(pin_type: str) -> str:
    pin_type = pin_type.lower()
    if pin_type in {"input", "power_input"}: return "input"
    if pin_type in {"output", "power_output"}: return "output"
    return "bidirectional"


def symbol_to_module_data(symbol: Dict) -> Dict:
    properties = symbol.get("properties", {})
    requirements = []
    for p in symbol.get("pins", []):
        ptype = (p.get("type") or "passive").lower()
        pname = (p.get("name") or "").upper()
        if ptype == "power_input":
            continue
        requirements.append({
            "module_pin": p.get("name") or f"PIN_{p.get('num', 'X')}",
            "function": "GPIO",
            "direction": pin_type_to_direction(ptype),
            "preferred_functions": ["GPIO"],
            "note": f"Pin {p.get('num')}, KiCad type: {p.get('type')}"
        })
    return {
        "schema_version": 1,
        "id": str(symbol["name"]).lower().replace(" ", "_").replace("-", "_"),
        "name": f"{symbol['name']} (KiCad 导入)",
        "description": properties.get("Description", properties.get("Datasheet", "")),
        "voltage": "3.3V",
        "logic_voltage": 3.3,
        "source": f"KiCad .kicad_sym import; Value={properties.get('Value', '')}; Footprint={properties.get('Footprint', '')}",
        "requirements": requirements,
    }


def parse_kicad_sym(path) -> List[Dict]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    sexp = parse_sexp(text)
    return [parse_symbol(s) for s in find_symbols(sexp)]


def import_kicad_symbols(kicad_sym_path, output_dir) -> List[str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sym in parse_kicad_sym(kicad_sym_path):
        data = symbol_to_module_data(sym)
        p = output_dir / f"{data['id']}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(p))
    return written


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tools/kicad_symbol_to_module.py <input.kicad_sym> [output_dir]")
        sys.exit(1)
    inp = sys.argv[1]
    default_out = Path(__file__).resolve().parents[1] / "data" / "modules"
    outp = sys.argv[2] if len(sys.argv) > 2 else str(default_out)
    result = import_kicad_symbols(inp, outp)
    for p in result:
        print(f"写入: {p}")
    print(f"共导入 {len(result)} 个模块")

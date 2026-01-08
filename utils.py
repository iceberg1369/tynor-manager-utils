# utils.py
import re

def parse_params(s: str):
    """
    Parse "100:200;101:300;" into dict {100: "200", 101: "300"}
    """
    out = {}
    if not s:
        return out
    s = s.strip().strip(";")
    if not s:
        return out
    for part in s.split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        if k.isdigit():
            out[int(k)] = v
    return out



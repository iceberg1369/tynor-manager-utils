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


def is_imei(s: str) -> bool:
    """
    Check if string looks like an IMEI (15 digits).
    """
    if not s:
        return False
    return s.isdigit() and len(s) < 16 and len(s) > 13


def get_balance_ussd(imsi: str) -> str:
    """
    Generate USSD code for balance retrieval based on IMSI using operator codes.
    """
    if not imsi or len(imsi) < 5:
        return ""

    mcc = imsi[:3]
    mnc = imsi[3:5]

    if mcc == "432": # IRAN
        if mnc == "35":        # Irancell
            return "*555*1*2#"
        if mnc == "20":        # Rightel
            return "*140#"
        if mnc == "11":        # Hamrahe Aval
            return "*140*11#"

    return ""

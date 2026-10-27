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
        # setparam replies put a space after each ';' ("New value 11600:1; 21600:1;")
        k = k.strip()
        if k.isdigit():
            out[int(k)] = v.strip()
    return out


def model_from_sn(sn) -> str | None:
    """The model the serial number on the box stands for: S/N 95... is a T950."""
    if sn and str(sn).strip().startswith("95"):
        return "TYNOR-T950"
    return None


T950_MODELS = {"T950", "TYNOR-T950"}


def is_t950(dev: dict) -> bool:
    """A T950, by either spelling of its model: older devices have "T950",
    registration writes "TYNOR-T950" (from the dm or the S/N)."""
    return dev.get("model") in T950_MODELS or dev.get("attributes", {}).get("model") in T950_MODELS


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

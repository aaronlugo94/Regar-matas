"""
tuya_control.py — Control del Insoma Smart Dual Water Timer vía Tuya Cloud API
════════════════════════════════════════════════════════════════════════════
Usa tinytuya.Cloud (maneja firma HMAC-SHA256 automáticamente).

DP Codes del dispositivo (confirmados en Tuya IoT Platform):
  switch_1       Boolean   Zona 1 (tierra)   on/off
  switch_2       Boolean   Zona 2 (macetas)  on/off
  countdown_1    Integer   0-1440 min — minutos de riego Zona 1
  countdown_2    Integer   0-1440 min — minutos de riego Zona 2
  battery_percentage  Integer 0-100

Variables de entorno requeridas (agregar en Railway):
  TUYA_ACCESS_ID
  TUYA_ACCESS_SECRET
  TUYA_DEVICE_ID
  TUYA_REGION        (default "us" — Western America Data Center)
════════════════════════════════════════════════════════════════════════════
"""

import os
import logging
import tinytuya

ACCESS_ID     = os.environ.get("TUYA_ACCESS_ID", "")
ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET", "")
DEVICE_ID     = os.environ.get("TUYA_DEVICE_ID", "")
REGION        = os.environ.get("TUYA_REGION", "us")  # us = Western America

TUYA_ENABLED = bool(ACCESS_ID and ACCESS_SECRET and DEVICE_ID)

_cloud = None

def _get_cloud():
    """Lazy-init the Tuya Cloud connection (handles auth token internally)."""
    global _cloud
    if _cloud is None:
        _cloud = tinytuya.Cloud(
            apiRegion=REGION,
            apiKey=ACCESS_ID,
            apiSecret=ACCESS_SECRET,
            apiDeviceID=DEVICE_ID,
        )
    return _cloud


def get_status() -> dict:
    """
    Returns a clean dict:
      {
        "ok": True,
        "switch_1": bool, "switch_2": bool,
        "countdown_1": int, "countdown_2": int,
        "battery": int,
      }
    or {"ok": False, "error": "..."} on failure.
    """
    if not TUYA_ENABLED:
        return {"ok": False, "error": "Tuya no configurado (faltan env vars)"}
    try:
        cloud = _get_cloud()
        raw = cloud.getstatus(DEVICE_ID)
        if "result" not in raw:
            return {"ok": False, "error": f"Respuesta inesperada: {raw}"}
        dps = {item["code"]: item["value"] for item in raw["result"]}
        return {
            "ok": True,
            "switch_1": dps.get("switch_1", False),
            "switch_2": dps.get("switch_2", False),
            "countdown_1": dps.get("countdown_1", 0),
            "countdown_2": dps.get("countdown_2", 0),
            "battery": dps.get("battery_percentage", None),
        }
    except Exception as e:
        logging.error(f"Tuya get_status error: {e}")
        return {"ok": False, "error": str(e)}


def send_commands(commands: list) -> dict:
    """
    commands: list of {"code": "...", "value": ...}
    Returns {"ok": True} or {"ok": False, "error": "..."}
    """
    if not TUYA_ENABLED:
        return {"ok": False, "error": "Tuya no configurado (faltan env vars)"}
    try:
        cloud = _get_cloud()
        result = cloud.sendcommand(DEVICE_ID, {"commands": commands})
        if result.get("success"):
            return {"ok": True}
        return {"ok": False, "error": str(result)}
    except Exception as e:
        logging.error(f"Tuya send_commands error: {e}")
        return {"ok": False, "error": str(e)}


def set_zone(zone: int, on: bool, minutes: int | None = None) -> dict:
    """
    zone: 1 (tierra) or 2 (macetas)
    on: True to open, False to close
    minutes: if provided and on=True, sets countdown before opening (0-1440)
    """
    if zone not in (1, 2):
        return {"ok": False, "error": "zone must be 1 or 2"}

    switch_code = f"switch_{zone}"
    countdown_code = f"countdown_{zone}"
    commands = []

    if on and minutes is not None:
        commands.append({"code": countdown_code, "value": max(0, min(1440, minutes))})

    commands.append({"code": switch_code, "value": on})

    return send_commands(commands)


def get_device_online() -> bool | None:
    """Returns True/False si el dispositivo está conectado a Tuya, None si no se pudo saber."""
    if not TUYA_ENABLED:
        return None
    try:
        cloud = _get_cloud()
        result = cloud.cloudrequest(f"/v1.0/devices/{DEVICE_ID}")
        if result.get("success"):
            return result["result"].get("online")
        return None
    except Exception as e:
        logging.error(f"Tuya get_device_online error: {e}")
        return None


def get_battery() -> int | None:
    """Returns battery percentage (0-100) or None if unavailable."""
    status = get_status()
    if status.get("ok"):
        return status.get("battery")
    return None

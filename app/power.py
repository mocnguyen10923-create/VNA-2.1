"""Quan ly nang luong: biet may dang dung pin hay cam sac, nguoi dung co dang ranh khong.
VNA dung thong tin nay de chon muc lam viec:
  - "tiet_kiem" (dung pin): mo hinh nho, it luong CPU, hoan viec nang (hoc tap, sang kien) den khi cam sac.
  - "hieu_nang" (cam sac): mo hinh chinh cho viec can chat luong, viec nen chay khi may ranh.
"""
import os
import sys
import time

IS_WIN = sys.platform.startswith("win")
_last_activity = time.time()


def touch():
    """Ghi nhan nguoi dung vua thao tac (hoi dap, bam nut)."""
    global _last_activity
    _last_activity = time.time()


def idle_seconds() -> float:
    return time.time() - _last_activity


def battery() -> dict:
    """{'plugged': bool, 'percent': int|None}"""
    if IS_WIN:
        try:
            import ctypes

            class SPS(ctypes.Structure):
                _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                            ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                            ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
            s = SPS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
                pct = s.BatteryLifePercent if 0 <= s.BatteryLifePercent <= 100 else None
                no_battery = (s.BatteryFlag & 128) != 0
                return {"plugged": s.ACLineStatus == 1 or no_battery, "percent": pct}
        except Exception:
            pass
    else:
        base = "/sys/class/power_supply"
        try:
            for n in os.listdir(base):
                if n.startswith(("AC", "ADP")):
                    with open(f"{base}/{n}/online") as f:
                        return {"plugged": f.read().strip() == "1", "percent": None}
        except Exception:
            pass
    return {"plugged": True, "percent": None}  # may ban / khong doc duoc: coi nhu cam sac


def profile(cfg) -> str:
    """'tiet_kiem' | 'hieu_nang' theo cai dat power_mode: tu_dong | tiet_kiem | hieu_nang."""
    mode = cfg.get("power_mode", "tu_dong")
    if mode in ("tiet_kiem", "hieu_nang"):
        return mode
    b = battery()
    if not b["plugged"]:
        return "tiet_kiem"
    return "hieu_nang"


def can_run_heavy(cfg, idle_needed=120) -> bool:
    """Viec nen nang (hoc tap, sang kien, AI phan bien bo sung) chi chay khi cam sac va nguoi dung dang ranh."""
    return profile(cfg) == "hieu_nang" and idle_seconds() >= idle_needed


def cpu_threads(cfg) -> int:
    n = os.cpu_count() or 4
    phys = max(2, n // 2)  # uoc so nhan vat ly
    if profile(cfg) == "tiet_kiem":
        return max(2, phys // 2)  # it nhan hon -> CPU chay xung thap, it hao pin
    return phys


def lower_own_priority():
    """VNA chay o muc uu tien thap de khong tranh CPU voi Word/Excel cua nguoi dung."""
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL
        except Exception:
            pass
    else:
        try:
            os.nice(5)
        except Exception:
            pass

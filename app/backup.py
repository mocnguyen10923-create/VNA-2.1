"""Sao luu hang tuan du lieu he thong VNA + so theo doi; giu 8 ban gan nhat. Phuc hoi bang mot nut."""
import datetime as dt
import logging
import threading
import time
import zipfile
from pathlib import Path

from . import config as cfgmod

KEEP = 8
FILES = ["cau_hinh.json", "cong_viec.json", "so_van_ban_den.json", "so_van_ban_di.json", "dinh_duong.json"]


def backup_dir(cfg) -> Path:
    p = Path(cfg.get("backup_dir") or (cfgmod.data_dir() / "_sao_luu"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def make(cfg) -> Path:
    d = cfgmod.data_dir()
    out = backup_dir(cfg) / f"VNA_saoluu_{dt.datetime.now():%Y%m%d_%H%M}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            if (d / f).exists():
                z.write(d / f, f)
        for f in cfgmod.system_dir().rglob("*"):
            if f.is_file():
                z.write(f, str(Path("_he_thong") / f.relative_to(cfgmod.system_dir())))
        track = cfgmod.workspace(cfg) / cfgmod.WS_THEO_DOI
        for f in track.rglob("*"):
            if f.is_file() and f.stat().st_size < 50 * 2**20:
                z.write(f, str(Path("05_THEO_DOI") / f.relative_to(track)))
    olds = sorted(backup_dir(cfg).glob("VNA_saoluu_*.zip"))
    for o in olds[:-KEEP]:
        o.unlink(missing_ok=True)
    logging.info("Da sao luu: %s", out)
    return out


def listing(cfg):
    return [{"name": p.name, "size": p.stat().st_size, "path": str(p)} for p in sorted(backup_dir(cfg).glob("VNA_saoluu_*.zip"), reverse=True)]


def restore(cfg, name: str):
    """Phuc hoi du lieu he thong (cong viec, so, hoc tap, cau hinh) tu ban sao luu. Truoc do tu sao luu hien trang."""
    src = backup_dir(cfg) / Path(name).name
    if not src.exists():
        raise ValueError("Không tìm thấy bản sao lưu.")
    make(cfg)
    d = cfgmod.data_dir()
    with zipfile.ZipFile(src) as z:
        for n in z.namelist():
            if n.startswith("05_THEO_DOI/") or ".." in n:
                continue
            target = d / n
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(n))


class BackupThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app

    def run(self):
        time.sleep(60)
        while True:
            try:
                items = sorted(backup_dir(self.app.cfg).glob("VNA_saoluu_*.zip"))
                last = items[-1].stat().st_mtime if items else 0
                if time.time() - last > 7 * 86400:
                    make(self.app.cfg)
            except Exception:
                logging.exception("Loi sao luu")
            time.sleep(6 * 3600)

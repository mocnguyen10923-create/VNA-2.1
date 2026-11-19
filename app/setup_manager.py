"""TU DONG CAI DAT & TU SUA: nguoi dung chi can cai VNA, phan con lai VNA tu lam.

Moi lan khoi dong, VNA kiem tra va tu hoan tat:
  1. Bo nao AI Ollama: chua co -> tu cai im lang (dung ban kem trong bo cai, hoac tai tu ollama.com).
  2. Ollama chua chay -> tu khoi dong ngam.
  3. Chon mo hinh theo RAM may (>=16GB: qwen2.5:7b, nho hon: qwen2.5:3b) -> tu tai ve, hien % tien do.
  4. Macro Word/Excel: chua cai -> tu cai (lan dau).
  5. Giong doc tieng Viet: kiem tra va bao trang thai (bo cai da xin quyen cai goi giong).
Ket noi Internet o buoc nay chi toi ollama.com / registry.ollama.ai (nha phat hanh Ollama) de tai bo nao AI mot lan.
"""
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from . import config as cfgmod
from . import llm

IS_WIN = sys.platform.startswith("win")
NO_WINDOW = 0x08000000 if IS_WIN else 0
OLLAMA_URL = "https://ollama.com/download/OllamaSetup.exe"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def ram_gb() -> float:
    try:
        if IS_WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except Exception:
        return 8.0


def find_ollama() -> str:
    cands = []
    if IS_WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        cands += [Path(la) / "Programs" / "Ollama" / "ollama.exe", Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe"]
    w = shutil.which("ollama")
    if w:
        cands.insert(0, Path(w))
    for c in cands:
        if c and Path(c).exists():
            return str(c)
    return ""


class SetupManager(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.state = {"stage": "start", "message": "Đang kiểm tra cài đặt…", "percent": None, "done": False, "error": ""}
        self.retry = threading.Event()

    def _set(self, stage, message, percent=None, error=""):
        self.state.update(stage=stage, message=message, percent=percent, error=error)
        logging.info("Cai dat tu dong [%s] %s %s", stage, message, f"{percent}%" if percent is not None else "")

    def run(self):
        while True:
            try:
                self.state["done"] = False
                self.step_office_macros()
                if self.app.cfg.get("backend", "ollama") == "ollama":
                    self.step_ollama()
                self._set("ok", "VNA đã sẵn sàng.", 100)
                self.state["done"] = True
            except Exception as e:
                logging.exception("Cai dat tu dong loi")
                self._set("error", "Chưa hoàn tất cài đặt tự động. VNA sẽ tự thử lại sau 5 phút.", None, str(e))
            # cho lan kiem tra sau (hoac nguoi dung bam 'Thu lai')
            self.retry.wait(300 if not self.state["done"] else 3600)
            self.retry.clear()

    # ---------------------------------------------------------------
    def step_ollama(self):
        cfg = self.app.cfg
        base = cfg.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
        if not self._alive(base):
            exe = find_ollama()
            if not exe and IS_WIN:
                exe = self._install_ollama()
            if not exe:
                raise RuntimeError("Không tìm thấy Ollama trên máy.")
            self._set("ollama_start", "Đang khởi động bộ não AI…")
            # Ung dung Ollama (khay he thong) neu co, neu khong thi chay 'ollama serve' an
            app_exe = Path(exe).with_name("ollama app.exe")
            if app_exe.exists():
                subprocess.Popen([str(app_exe)], creationflags=NO_WINDOW)
            else:
                subprocess.Popen([exe, "serve"], creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(60):
                if self._alive(base):
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Bộ não AI (Ollama) không khởi động được.")

        # Toi uu Ollama mot lan (giam RAM, tang toc, it ton pin)
        if IS_WIN:
            self._tune_ollama_env(base)
        # Chon mo hinh theo RAM (chi khi nguoi dung chua tu chon):
        #   >=15GB: chinh qwen2.5:7b + nhanh qwen2.5:3b ; nho hon: ca hai la qwen2.5:3b
        if cfg.get("model_auto", True):
            gb = ram_gb()
            want = "qwen2.5:7b" if gb >= 15 else "qwen2.5:3b"
            if cfg.get("ollama_model") != want or cfg.get("ollama_model_fast") != "qwen2.5:3b":
                cfg["ollama_model"] = want
                cfg["ollama_model_fast"] = "qwen2.5:3b"
                cfgmod.save(cfg)
                logging.info("RAM %.1f GB -> mo hinh chinh %s, nhanh qwen2.5:3b", gb, want)
        tags = llm._request(base + "/api/tags", timeout=10)
        names = [m.get("name", "") for m in tags.get("models", [])]
        for model in dict.fromkeys([cfg.get("ollama_model_fast"), cfg.get("ollama_model")]):  # mo hinh nho truoc: dung duoc som
            if model and not any(n == model or n == model + ":latest" for n in names):
                self._pull(base, model)

    def _tune_ollama_env(self, base):
        """Dat bien moi truong cho Ollama: 1 luong song song (giam 4 lan bo nho dem), flash attention,
        nen bo nho dem KV, gioi han so mo hinh nap cung luc. Khoi dong lai Ollama 1 lan de ap dung."""
        want = {"OLLAMA_NUM_PARALLEL": "1", "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0",
                "OLLAMA_MAX_LOADED_MODELS": "2" if ram_gb() >= 15 else "1"}
        try:
            import winreg
            changed = False
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                for name, val in want.items():
                    try:
                        cur = winreg.QueryValueEx(k, name)[0]
                    except OSError:
                        cur = None
                    if cur != val:
                        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
                        changed = True
            os.environ.update(want)
            if changed:
                logging.info("Da toi uu bien moi truong Ollama, khoi dong lai Ollama")
                self._set("ollama_tune", "Đang tối ưu bộ não AI cho tiết kiệm pin…")
                subprocess.run(["taskkill", "/IM", "ollama app.exe", "/F"], creationflags=NO_WINDOW, capture_output=True)
                subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], creationflags=NO_WINDOW, capture_output=True)
                time.sleep(2)
                exe = find_ollama()
                if exe:
                    app_exe = Path(exe).with_name("ollama app.exe")
                    env = dict(os.environ, **want)
                    if app_exe.exists():
                        subprocess.Popen([str(app_exe)], creationflags=NO_WINDOW, env=env)
                    else:
                        subprocess.Popen([exe, "serve"], creationflags=NO_WINDOW, env=env,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    for _ in range(40):
                        if self._alive(base):
                            break
                        time.sleep(1)
        except Exception as e:
            logging.warning("Khong toi uu duoc Ollama: %s", e)

    def _alive(self, base) -> bool:
        try:
            llm._request(base + "/api/tags", timeout=3)
            return True
        except Exception:
            return False

    def _install_ollama(self) -> str:
        bundled = app_dir() / "redist" / "OllamaSetup.exe"
        setup = bundled if bundled.exists() else Path(tempfile.gettempdir()) / "OllamaSetup.exe"
        if not bundled.exists():
            if IS_WIN and shutil.which("winget"):
                # Cach 1: winget (kho ung dung chinh thuc cua Microsoft)
                self._set("ollama_install", "Đang cài bộ não AI (Ollama) qua Microsoft winget… vui lòng chờ vài phút.")
                try:
                    subprocess.run(["winget", "install", "-e", "--id", "Ollama.Ollama", "--silent",
                                    "--accept-package-agreements", "--accept-source-agreements"],
                                   creationflags=NO_WINDOW, timeout=3600)
                    for _ in range(15):
                        exe = find_ollama()
                        if exe:
                            return exe
                        time.sleep(2)
                except Exception as e:
                    logging.warning("winget loi: %s", e)
            # Cach 2: tai truc tiep tu ollama.com
            self._download(OLLAMA_URL, setup, "Đang tải bộ cài bộ não AI (Ollama)")
        self._set("ollama_install", "Đang cài bộ não AI (Ollama)… vui lòng chờ vài phút.")
        r = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], timeout=1800)
        if r.returncode != 0:
            raise RuntimeError(f"Cài Ollama không thành công (mã {r.returncode}).")
        for _ in range(30):
            exe = find_ollama()
            if exe:
                return exe
            time.sleep(2)
        return ""

    def _download(self, url, dest: Path, label):
        self._set("download", label + "…", 0)
        if IS_WIN and self._download_windows(url, dest, label):
            return
        self._download_python(url, dest, label)

    def _download_windows(self, url, dest: Path, label) -> bool:
        """Tai bang curl.exe co san trong Windows 10/11 (dung kho chung chi Windows), co hien tien do."""
        curl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
        if not curl.exists():
            return False
        tmp = dest.with_suffix(".part")
        total = 0
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "VNA-Setup/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                total = int(r.headers.get("Content-Length") or 0)
        except Exception:
            pass
        p = subprocess.Popen([str(curl), "-L", "--fail", "--retry", "3", "-o", str(tmp), url],
                             creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while p.poll() is None:
            time.sleep(1)
            size = tmp.stat().st_size if tmp.exists() else 0
            self.state["message"] = f"{label}… {size // 2**20} MB" + (f" / {total // 2**20} MB" if total else "")
            if total:
                self.state["percent"] = int(size * 100 / total)
        if p.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1_000_000:
            os.replace(tmp, dest)
            return True
        logging.warning("curl.exe tai that bai (ma %s), thu cach khac", p.returncode)
        return False

    def _download_python(self, url, dest: Path, label):
        tmp = dest.with_suffix(".part")
        req = urllib.request.Request(url, headers={"User-Agent": "VNA-Setup/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                done += len(b)
                if total:
                    self.state["percent"] = int(done * 100 / total)
                    self.state["message"] = f"{label}… {done // 2**20} / {total // 2**20} MB"
        os.replace(tmp, dest)

    def _pull(self, base, model):
        self._set("model", f"Đang tải bộ não AI '{model}' (một lần duy nhất, cần Internet)…", 0)
        req = urllib.request.Request(base + "/api/pull", data=json.dumps({"name": model, "stream": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=7200) as r:
            for line in r:
                try:
                    ev = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if ev.get("error"):
                    raise RuntimeError("Tải mô hình lỗi: " + ev["error"])
                total, comp = ev.get("total"), ev.get("completed")
                if total and comp:
                    pct = int(comp * 100 / total)
                    self.state["percent"] = pct
                    self.state["message"] = (f"Đang tải bộ não AI '{model}': {comp / 1024 ** 3:.2f} / {total / 1024 ** 3:.2f} GB "
                                             "(một lần duy nhất)")
                if ev.get("status") == "success":
                    break

    # ---------------------------------------------------------------
    def step_office_macros(self):
        if not IS_WIN:
            return
        flag = cfgmod.data_dir() / ".macro_da_cai"
        ps1 = app_dir() / "office" / "cai_dat_office.ps1"
        if flag.exists() or not ps1.exists():
            return
        self._set("office", "Đang cài macro VNA vào Word và Excel…")
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), "-Silent"],
                           creationflags=NO_WINDOW, timeout=300)
            flag.write_text("ok", encoding="utf-8")
        except Exception as e:
            logging.warning("Khong cai duoc macro Office: %s", e)

"""Doc van ban thanh giong noi tieng Viet.
- windows: giong Viet cua Windows 10/11 (Microsoft An) - offline. Can cai goi giong noi tieng Viet:
           Settings > Time & Language > Language & region > Add language > Tieng Viet (chon Speech).
- edge   : giong tu nhien vi-VN-HoaiMyNeural / vi-VN-NamMinhNeural - can Internet va goi edge-tts.
- macOS  : lenh 'say' (giong Linh). Linux: espeak-ng.
"""
import asyncio
import datetime
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import docio

SCRIPTS = Path(__file__).parent / "scripts"
_proc = None
_lock = threading.Lock()
IS_WIN = sys.platform.startswith("win")
NO_WINDOW = 0x08000000 if IS_WIN else 0


class TTSError(Exception):
    pass


def clean_for_speech(text: str) -> str:
    t = docio.strip_markdown(text)
    t = re.sub(r"\[(Trang \d+)\]", r"\1.", t)
    t = t.replace("\t", ", ").replace("|", ", ")
    t = re.sub(r"[#*_`>]+", " ", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[  ]{2,}", " ", t)
    return t.strip()


def stop():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            try:
                _proc.kill()
            except Exception:
                pass
        _proc = None


def _powershell(args):
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + args


def _edge_save(text, out_path, voice, rate):
    try:
        import edge_tts
    except ImportError:
        raise TTSError("Chưa có gói edge-tts. Chọn giọng 'Windows (offline)' trong Cài đặt, hoặc cài: pip install edge-tts")
    pct = int(round((rate - 1.0) * 100))
    rate_s = f"{'+' if pct >= 0 else ''}{pct}%"

    async def run():
        await edge_tts.Communicate(text, voice, rate=rate_s).save(str(out_path))

    try:
        asyncio.run(run())
    except Exception as e:
        raise TTSError(f"Giọng Edge cần Internet. Lỗi: {e}")


def speak(text: str, cfg: dict, save_to: Path = None):
    """Doc to (save_to=None) hoac luu thanh file am thanh. Tra ve duong dan file (neu luu)."""
    global _proc
    text = clean_for_speech(text)
    if not text:
        raise TTSError("Không có nội dung để đọc.")
    stop()
    engine = cfg.get("tts_engine", "windows")
    rate = float(cfg.get("tts_rate", 1.0))
    tmpdir = Path(tempfile.gettempdir()) / "VNA_tts"
    tmpdir.mkdir(exist_ok=True)

    if engine == "edge" and cfg.get("offline_only", True):
        engine = "windows"  # che do ngoai tuyen: dung giong cua Windows, khong ket noi Internet
    if engine == "edge":
        out = save_to or (tmpdir / f"doc_{datetime.datetime.now():%H%M%S}.mp3")
        out = out.with_suffix(".mp3")
        _edge_save(text, out, cfg.get("edge_voice", "vi-VN-HoaiMyNeural"), rate)
        if save_to:
            return str(out)
        if IS_WIN:
            cmd = _powershell([str(SCRIPTS / "play_audio.ps1"), "-File", str(out)])
        elif sys.platform == "darwin":
            cmd = ["afplay", str(out)]
        else:
            cmd = ["mpg123", "-q", str(out)]
        with _lock:
            _proc = subprocess.Popen(cmd, creationflags=NO_WINDOW)
        return None

    # Giong cua he dieu hanh (offline)
    if IS_WIN:
        txt = tmpdir / "input.txt"
        txt.write_text(text, encoding="utf-8")
        out = (save_to.with_suffix(".wav") if save_to else tmpdir / f"doc_{datetime.datetime.now():%H%M%S%f}.wav")
        args = [str(SCRIPTS / "tts_windows.ps1"), "-InFile", str(txt), "-OutWav", str(out), "-Rate", str(rate)]
        if not save_to:
            args.append("-Play")
        if save_to:
            r = subprocess.run(_powershell(args), capture_output=True, text=True, creationflags=NO_WINDOW, timeout=600)
            if r.returncode != 0:
                raise TTSError("Không tạo được file giọng nói: " + (r.stderr or r.stdout)[-400:])
            return str(out)
        with _lock:
            _proc = subprocess.Popen(_powershell(args), creationflags=NO_WINDOW)
        return None
    if sys.platform == "darwin":
        cmd = ["say", "-v", "Linh", "-r", str(int(180 * rate))]
        if save_to:
            out = save_to.with_suffix(".aiff")
            subprocess.run(cmd + ["-o", str(out), text], check=False)
            return str(out)
        with _lock:
            _proc = subprocess.Popen(cmd + [text])
        return None
    cmd = ["espeak-ng", "-v", "vi", "-s", str(int(160 * rate))]
    try:
        if save_to:
            out = save_to.with_suffix(".wav")
            subprocess.run(cmd + ["-w", str(out), text], check=False)
            return str(out)
        with _lock:
            _proc = subprocess.Popen(cmd + [text])
    except FileNotFoundError:
        raise TTSError("Chưa cài espeak-ng trên máy này.")
    return None


def speak_async(text, cfg):
    """Chay nen de khong chan giao dien (edge-tts can tai am thanh truoc)."""
    def run():
        try:
            speak(text, cfg)
        except Exception as e:
            logging.warning("TTS loi: %s", e)
    threading.Thread(target=run, daemon=True).start()


def list_windows_voices():
    if not IS_WIN:
        return []
    try:
        r = subprocess.run(_powershell([str(SCRIPTS / "tts_windows.ps1"), "-ListVoices"]),
                           capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW, encoding="utf-8")
        return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []

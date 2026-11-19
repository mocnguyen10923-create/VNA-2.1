"""Cau hinh VNA: luu tai Documents/VNA/cau_hinh.json (thu muc nguoi dung, ghi duoc)."""
import json
import os
import sys
import threading
from pathlib import Path

_LOCK = threading.Lock()

DEFAULTS = {
    # ---- Mien phi & rieng tu ----
    # True: CHAN MOI KET NOI RA INTERNET. VNA chi lam viec tren chinh may tinh nay (mien phi hoan toan).
    "offline_only": True,
    # Cho phep tra cuu CHI cac trang chinh thong cua Nha nuoc (.gov.vn, chinhphu.vn, vbpl.vn...) khi can thong tin hien hanh.
    # Chi gui tu khoa tim kiem, khong gui tai lieu. Duoc phep ca khi dang o che do ngoai tuyen.
    "official_web": True,
    "web_auto": True,            # tu tra cuu khi cau hoi co tu "moi nhat", "hien hanh", "con hieu luc"...
    "official_extra_domains": "",  # them ten mien chinh thong khac, cach nhau dau phay
    # ---- Bo nao AI ----
    # "ollama"  : chay mo hinh ngay tren laptop (khong can Internet, bao mat du lieu)
    # "claude"  : dung Claude API cua Anthropic (TRA PHI theo luot dung, can Internet + API key) - tuy chon
    # "openai"  : may chu tuong thich OpenAI (LM Studio, vLLM, may chu noi bo...)
    "backend": "ollama",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5:7b",
    "model_auto": True,          # VNA tu chon mo hinh theo RAM; tat khi nguoi dung tu chon mo hinh
    "ollama_model_fast": "qwen2.5:3b",  # mo hinh nho: trich xuat, JSON, tu khoa; dung pin thi dung cho moi viec
    "ollama_ctx_main": 8192,    # co dinh (doi gia tri lam Ollama nap lai mo hinh)
    "ollama_ctx_fast": 4096,
    "ai_cache": True,           # nho ket qua AI cho viec lap lai
    # ---- Nang luong ----
    "power_mode": "tu_dong",    # tu_dong (theo pin/sac) | tiet_kiem | hieu_nang
    "phan_bien_khi_dung_pin": False,  # lop AI phan bien khi dang dung pin (tat de tiet kiem)
    "claude_api_key": "",
    "claude_model": "claude-sonnet-5-5",
    "openai_base_url": "http://127.0.0.1:1234/v1",
    "openai_api_key": "",
    "openai_model": "",
    "temperature": 0.3,
    "max_output_tokens": 8000,
    # So ky tu tai lieu toi da dua vao mot lan hoi (mo hinh tren may nho hon -> it hon)
    "context_chars_local": 10000,
    "context_chars_cloud": 200000,
    "history_messages": 12,
    "library_top_k": 6,
    # ---- Thu vien tai lieu (luat, nghi dinh, quy che, tai lieu nghien cuu) ----
    "library_dir": "",  # de trong = Documents/VNA/thu_vien
    # ---- Giong noi ----
    # "windows": giong Viet co san cua Windows (offline, can cai goi giong tieng Viet)
    # "edge"   : giong doc tu nhien cua Microsoft Edge (can Internet, can goi edge-tts)
    "tts_engine": "windows",
    "tts_rate": 1.0,
    "edge_voice": "vi-VN-HoaiMyNeural",
    # ---- The thuc van ban mac dinh (Nghi dinh 30/2020/ND-CP) ----
    "co_quan_chu_quan": "",
    "co_quan": "TÊN CƠ QUAN, TỔ CHỨC",
    "ky_hieu_co_quan": "",
    "dia_danh": "Hà Nội",
    "chuc_vu_ky": "THỦ TRƯỞNG CƠ QUAN",
    "nguoi_ky": "",
    # ---- Nha truong ----
    "ten_truong": "TRƯỜNG THCS VÀ THPT ...",
    "nam_hoc": "2026-2027",
    # ---- Nguoi dung & loi chao ----
    "ten_nguoi_dung": "",      # VD: "Nguyễn Văn A"
    "danh_xung": "",           # cach xung ho (khong bat buoc): thầy / cô / anh / chị ...
    "greet_speak": True,       # doc loi chao khi mo chuong trinh
    # ---- Van ban den tu dong ----
    "inbox_dir": "",           # de trong = Documents/VNA/Van_ban_den
    "inbox_auto": True,        # tu dong xu ly van ban moi
    "inbox_trien_khai": False, # True: tu tao bo trien khai; False (mac dinh): chi de xuat, ban bam moi tao
    "dat_ten_chuan": True,     # dat ten file chuan: NgayBanHanh_SoKyHieu_TrichYeu
    # ---- Tu kiem tra (Dac ta muc 11) ----
    "tu_kiem_tra": True,       # lop 1: kiem tra tu dong
    "phan_bien_ai": True,      # lop 2: AI phan bien doc lai (cham hon, chinh xac hon)
    # ---- Sao luu ----
    "backup_dir": "",          # de trong = Documents/VNA/_sao_luu
    # ---- Nhac viec ----
    "remind_speak": True,
    # ---- Thu muc duoc phep quan ly (chi do nguoi dung them) ----
    "managed_folders": [],
    # ---- Thu muc VNA quan ly (3 thu muc con) ----
    "workspace_dir": "",       # de trong = Documents/VNA/Thư mục VNA quản lý
    "port": 8765,
}

# ---- 5 thu muc quan ly (Dac ta muc 3) ----
WS_ROOT_NAME = "Quản lý công việc"
WS_DEN = "01_VAN_BAN_DEN"            # cong van den: nguoi dung chep vao goc thu muc
WS_NGUON = "02_NGUON_CAN_CU"         # can cu phap ly, huong dan hien hanh
WS_THAM_KHAO = "03_TAI_LIEU_THAM_KHAO"
WS_SAN_PHAM = "04_SAN_PHAM"          # Du_thao (VNA soan) / Da_ban_hanh (ban chinh thuc da ky)
WS_THEO_DOI = "05_THEO_DOI"          # so sach VNA tu cap nhat
WS_CHI_DAO = WS_DEN                  # ten cu, giu cho tuong thich
DA_XU_LY = "Da_xu_ly"
DU_THAO = "Du_thao"
DA_BAN_HANH = "Da_ban_hanh"
HET_HIEU_LUC = "Het_hieu_luc"
NGUON_SUB = ["Van_ban_phap_luat", "Huong_dan_chuyen_mon", "Chuong_trinh_GDPT_2018", "Quy_che_noi_bo", HET_HIEU_LUC]
_ACTIVE = {}


def _documents_folder() -> Path:
    """Thu muc Documents that cua Windows (ke ca khi duoc OneDrive chuyen huong)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes
            from uuid import UUID

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

            u = UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")  # FOLDERID_Documents
            g = GUID(u.fields[0], u.fields[1], u.fields[2], (wintypes.BYTE * 8).from_buffer_copy(u.bytes[8:]))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(buf)) == 0:
                path = Path(buf.value)
                ctypes.windll.ole32.CoTaskMemFree(buf)
                return path
        except Exception:
            pass
    return Path.home() / "Documents"


def data_dir() -> Path:
    env = os.environ.get("VNA_DATA")
    if env:
        p = Path(env)
    else:
        docs = _documents_folder()
        p = (docs if docs.exists() else Path.home()) / "VNA"
    p.mkdir(parents=True, exist_ok=True)
    return p


_OWNER = None
_GENERIC = {"admin", "administrator", "user", "users", "pc", "laptop", "owner", "guest", "default", "root"}


def owner_name() -> str:
    """Ten chu may (ten hien thi cua tai khoan Windows), dung cho loi chao mac dinh."""
    global _OWNER
    if _OWNER is not None:
        return _OWNER
    name = ""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            size = ctypes.c_ulong(0)
            ctypes.windll.secur32.GetUserNameExW(3, None, ctypes.byref(size))  # 3 = NameDisplay
            buf = ctypes.create_unicode_buffer(size.value or 256)
            if ctypes.windll.secur32.GetUserNameExW(3, buf, ctypes.byref(size)):
                name = buf.value.strip()
        except Exception:
            pass
        if not name:
            try:
                import subprocess
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;(Get-LocalUser -Name $env:USERNAME).FullName"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=10, creationflags=0x08000000)
                name = r.stdout.strip()
            except Exception:
                pass
    if not name:
        try:
            import getpass
            name = getpass.getuser()
        except Exception:
            name = ""
    if "@" in name:
        name = name.split("@")[0]
    if name.lower() in _GENERIC:
        name = ""
    _OWNER = name
    return name


def config_path() -> Path:
    return data_dir() / "cau_hinh.json"


def library_dir(cfg) -> Path:
    p = Path(cfg.get("library_dir") or (data_dir() / "thu_vien"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def workspace(cfg=None) -> Path:
    cfg = cfg or _ACTIVE
    root = Path(cfg.get("workspace_dir") or (data_dir() / WS_ROOT_NAME))
    for sub in (WS_DEN, WS_THAM_KHAO, WS_THEO_DOI):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / WS_DEN / DA_XU_LY).mkdir(parents=True, exist_ok=True)
    for sub in NGUON_SUB:
        (root / WS_NGUON / sub).mkdir(parents=True, exist_ok=True)
    for sub in (DU_THAO, DA_BAN_HANH):
        (root / WS_SAN_PHAM / sub).mkdir(parents=True, exist_ok=True)
    return root


def output_dir(kind: str = "Van ban soan thao") -> Path:
    """San pham VNA soan: 04_SAN_PHAM/Du_thao/<nam>/Thang_<mm>/<loai>"""
    import datetime
    now = datetime.date.today()
    p = workspace() / WS_SAN_PHAM / DU_THAO / str(now.year) / f"Thang_{now.month:02d}" / kind
    p.mkdir(parents=True, exist_ok=True)
    return p


def system_dir() -> Path:
    """Du lieu noi bo cua VNA (hoc tap, so loi, nhat ky thao tac...)."""
    p = data_dir() / "_he_thong"
    p.mkdir(parents=True, exist_ok=True)
    return p


def migrate_old_workspace(cfg):
    """Chuyen thu muc kieu cu ('Thư mục VNA quản lý' 3 thu muc) sang cau truc 5 thu muc. Khong xoa file."""
    import shutil
    old = data_dir() / "Thư mục VNA quản lý"
    if not old.exists():
        return
    ws = workspace(cfg)
    moves = {"1. Văn bản chỉ đạo cấp trên": ws / WS_DEN / DA_XU_LY / "_chuyen_tu_ban_cu",
             "2. Văn bản - sản phẩm đã làm": ws / WS_SAN_PHAM / DU_THAO / "_chuyen_tu_ban_cu",
             "3. Theo dõi công việc": ws / WS_THEO_DOI / "_chuyen_tu_ban_cu"}
    for name, dest in moves.items():
        src = old / name
        if src.exists() and any(src.iterdir()):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.move(str(src), str(dest))
    try:
        for sub in old.iterdir():
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        old.rmdir()
    except OSError:
        pass
    cfg["managed_folders"] = [x for x in cfg.get("managed_folders", []) if Path(x).exists()]
    save(cfg)


def tracking_dir() -> Path:
    return workspace() / WS_THEO_DOI


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    else:
        save(cfg)
    _ACTIVE.clear()
    _ACTIVE.update(cfg)
    return cfg


def save(cfg: dict) -> None:
    with _LOCK:
        tmp = config_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, config_path())


def public_view(cfg: dict) -> dict:
    """Cau hinh tra ve giao dien: an API key."""
    v = dict(cfg)
    for k in ("claude_api_key", "openai_api_key"):
        key = v.get(k) or ""
        v[k] = ("••••" + key[-4:]) if key else ""
        v[k + "_set"] = bool(key)
    v["data_dir"] = str(data_dir())
    v["owner_name"] = owner_name()
    v["library_path"] = str(library_dir(cfg))
    v["workspace_path"] = str(workspace(cfg))
    v["inbox_path"] = str(Path(cfg.get("inbox_dir") or (workspace(cfg) / WS_CHI_DAO)))
    v["is_windows"] = sys.platform.startswith("win")
    return v


def update(cfg: dict, changes: dict) -> dict:
    _ACTIVE.update(cfg)
    if changes.get("ollama_model") and changes["ollama_model"] != cfg.get("ollama_model"):
        cfg["model_auto"] = False  # nguoi dung tu chon mo hinh
    for k, val in changes.items():
        if k not in DEFAULTS or k == "managed_folders":
            continue
        if k in ("claude_api_key", "openai_api_key") and isinstance(val, str) and val.startswith("••••"):
            continue  # nguoi dung khong doi key
        default = DEFAULTS[k]
        try:
            if isinstance(default, bool):
                val = val if isinstance(val, bool) else str(val).lower() in ("1", "true", "on", "yes")
            elif isinstance(default, int):
                val = int(val)
            elif isinstance(default, float):
                val = float(val)
            else:
                val = str(val)
        except (TypeError, ValueError):
            continue
        cfg[k] = val
    save(cfg)
    _ACTIVE.clear()
    _ACTIVE.update(cfg)
    return cfg

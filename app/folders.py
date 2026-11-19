"""Quan ly thu muc do nguoi dung chi dinh: ra soat, sap xep, xu ly tai lieu trung noi dung.

NGUYEN TAC AN TOAN (bat buoc, khong the tat):
  1. Chi lam viec ben trong cac thu muc nguoi dung da dang ky. Moi duong dan deu duoc kiem tra.
  2. KHONG BAO GIO XOA file. Tai lieu trung chi duoc chuyen vao thu muc "_TRUNG_LAP" de nguoi dung tu quyet dinh.
  3. Moi thao tac deu: xem truoc ke hoach -> nguoi dung xac nhan -> thuc hien -> ghi nhat ky -> co the hoan tac.
  4. Khong quan ly o dia goc, thu muc he thong, thu muc chuong trinh.
  5. Khong gui noi dung file ra Internet (ra soat chay hoan toan tren may).
"""
import datetime
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import threading
from pathlib import Path

from . import config as cfgmod
from . import docio

DUP_DIR = "_TRUNG_LAP"
SKIP_DIRS = {DUP_DIR, "$RECYCLE.BIN", "System Volume Information", ".git", "node_modules", "__pycache__"}
_LOCK = threading.Lock()

# Nhom tai lieu: (ten thu muc, mau tim trong DONG DAU noi dung (chu in hoa), mau tim trong ten file/noi dung)
CATEGORIES = [
    ("01_Van ban phap luat", r"^\s*(LUẬT|NGHỊ ĐỊNH|THÔNG TƯ|NGHỊ QUYẾT|PHÁP LỆNH)\b",
     r"(^luật\b|nghị định|thông tư|nghị quyết|/nđ-cp|/tt-|/qh\d+)"),
    ("02_Quyet dinh", r"^\s*QUYẾT ĐỊNH\b", r"(quyết định|\bqđ\b|\bqd[-_ ])"),
    ("03_Cong van", r"^\s*V/v\b", r"(công văn|\bv/v\b|\bcv[-_ ])"),
    ("04_Ke hoach", r"^\s*KẾ HOẠCH\b", r"(kế hoạch(?! bài dạy)|\bkh[-_ ])"),
    ("05_Bao cao", r"^\s*BÁO CÁO\b", r"(báo cáo|\bbc[-_ ])"),
    ("06_To trinh", r"^\s*TỜ TRÌNH\b", r"(tờ trình)"),
    ("07_Thong bao", r"^\s*THÔNG BÁO\b", r"(thông báo|\btb[-_ ])"),
    ("08_Bien ban", r"^\s*BIÊN BẢN\b", r"(biên bản|\bbb[-_ ])"),
    ("09_Chuyen mon - Giang day", None,
     r"(giáo án|kế hoạch bài dạy|\bkhbd\b|đề kiểm tra|đề thi|ma trận|đáp án|chuyên đề|sáng kiến|tiết dạy|phân phối chương trình)"),
    ("10_Hoc sinh", None, r"(học sinh|học bạ|sổ điểm|bảng điểm|danh sách lớp|hạnh kiểm|tuyển sinh)"),
    ("11_Tai chinh - Tai san", None, r"(dự toán|quyết toán|thanh toán|kinh phí|bảng lương|hóa đơn|tài sản|mua sắm)"),
    ("12_To chuc - Can bo", None, r"(nhân sự|cán bộ|viên chức|bổ nhiệm|thi đua|khen thưởng|đánh giá xếp loại|hợp đồng lao động)"),
]
MEDIA = {
    "13_Hinh anh": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".heic", ".webp", ".tif", ".tiff"},
    "14_Am thanh - Video": {".mp3", ".wav", ".m4a", ".mp4", ".avi", ".mov", ".mkv", ".wmv"},
    "15_Trinh chieu": {".ppt", ".pptx"},
    "16_Nen - Cai dat": {".zip", ".rar", ".7z", ".exe", ".msi"},
}
OTHER = "17_Khac"


# ---------------------------------------------------------------------
# Dang ky thu muc & kiem tra an toan
# ---------------------------------------------------------------------
def _forbidden(p: Path) -> str:
    p = p.resolve()
    ws = cfgmod.workspace().resolve()
    if p != ws and ws in p.parents:
        return ""  # thu muc con trong "Thu muc VNA quan ly" luon duoc phep
    if p.parent == p:
        return "Không quản lý cả ổ đĩa. Hãy chọn một thư mục cụ thể."
    home = Path.home().resolve()
    if p == home:
        return "Không quản lý toàn bộ thư mục người dùng. Hãy chọn thư mục con cụ thể."
    bad = []
    if sys.platform.startswith("win"):
        for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "APPDATA", "LOCALAPPDATA"):
            if os.environ.get(env):
                bad.append(Path(os.environ[env]).resolve())
    else:
        bad += [Path(x) for x in ("/bin", "/etc", "/usr", "/var", "/sys", "/proc", "/boot", "/lib", "/opt", "/Applications", "/System", "/Library")]
    bad.append(cfgmod.data_dir().resolve())
    bad.append(Path(__file__).resolve().parent.parent)
    for b in bad:
        if p == b or b in p.parents or p in b.parents:
            return f"Thư mục hệ thống/chương trình được bảo vệ, VNA không can thiệp: {b}"
    return ""


def registered(cfg) -> list:
    return [str(x) for x in cfg.get("managed_folders", []) if Path(x).is_dir()]


def register(cfg, path: str) -> list:
    p = Path(path.strip().strip('"')).expanduser()
    if not p.is_dir():
        raise ValueError("Thư mục không tồn tại: " + str(p))
    why = _forbidden(p)
    if why:
        raise ValueError(why)
    lst = list(cfg.get("managed_folders", []))
    s = str(p.resolve())
    if s not in lst:
        lst.append(s)
    cfg["managed_folders"] = lst
    cfgmod.save(cfg)
    logging.info("Dang ky thu muc quan ly: %s", s)
    return lst


def unregister(cfg, path: str) -> list:
    cfg["managed_folders"] = [x for x in cfg.get("managed_folders", []) if x != path]
    cfgmod.save(cfg)
    return cfg["managed_folders"]


def _check_root(cfg, root: str) -> Path:
    if root not in cfg.get("managed_folders", []):
        raise ValueError("Thư mục này chưa được bạn cho phép quản lý.")
    return Path(root).resolve()


def _inside(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def pick_folder_dialog() -> str:
    """Hop thoai chon thu muc cua Windows (chay tren may nguoi dung)."""
    if not sys.platform.startswith("win"):
        return ""
    import subprocess
    ps = ("Add-Type -AssemblyName System.Windows.Forms;"
          "$f=New-Object System.Windows.Forms.FolderBrowserDialog;"
          "$f.Description='Chon thu muc cho VNA quan ly';$f.ShowNewFolderButton=$false;"
          "if($f.ShowDialog() -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;Write-Output $f.SelectedPath}")
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True,
                       text=True, encoding="utf-8", creationflags=0x08000000)
    return r.stdout.strip()


# ---------------------------------------------------------------------
# Ra soat
# ---------------------------------------------------------------------
def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _norm_text(t: str) -> str:
    t = t.lower()
    t = re.sub(r"\[trang \d+\]", " ", t)
    return re.sub(r"\W+", " ", t, flags=re.UNICODE).strip()


def _minhash(text: str, k=5, n=64):
    words = text.split()
    if len(words) < k + 5:
        return None
    sh = {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}
    hs = [int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "little") for s in sh]
    sig = []
    for seed in range(n):
        a, b = 6364136223846793005 * (seed + 1) | 1, 1442695040888963407 * (seed + 7)
        sig.append(min(((a * x + b) & 0xFFFFFFFFFFFFFFFF) for x in hs))
    return sig


def _category(name: str, text: str, ext: str) -> str:
    for cat, exts in MEDIA.items():
        if ext in exts:
            return cat
    head = "\n".join(text.splitlines()[:25]) if text else ""
    for cat, head_re, _ in CATEGORIES:
        if head_re and re.search(head_re, head, re.M):
            return cat
    low_name = name.lower()
    for cat, _, any_re in CATEGORIES:
        if re.search(any_re, low_name):
            return cat
    low_head = head.lower()
    for cat, _, any_re in CATEGORIES:
        if re.search(any_re, low_head):
            return cat
    if ext in (".xlsx", ".xls", ".xlsm", ".csv"):
        return "11_Tai chinh - Tai san" if re.search(r"(lương|kinh phí|dự toán)", low_head) else OTHER
    return OTHER


def _year(name: str, text: str, mtime: float) -> str:
    m = re.search(r"năm\s+(20\d{2})", text[:3000]) if text else None
    if m:
        return m.group(1)
    m = re.search(r"(?<!\d)(20\d{2})(?!\d)", name)
    if m and 2000 <= int(m.group(1)) <= datetime.date.today().year + 1:
        return m.group(1)
    return str(datetime.datetime.fromtimestamp(mtime).year)


def scan(cfg, root: str, by_category=True, by_year=True, handle_dups=True, near_dup=True, progress=None) -> dict:
    rootp = _check_root(cfg, root)
    files = []
    for dirpath, dirnames, filenames in os.walk(rootp):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("~$") or fn.startswith(".") or fn.lower() in ("desktop.ini", "thumbs.db"):
                continue
            p = Path(dirpath) / fn
            if p.is_symlink() or not _inside(rootp, p):
                continue
            files.append(p)
    items, errors = [], []
    for i, p in enumerate(files):
        if progress:
            progress(i + 1, len(files), p.name)
        try:
            st = p.stat()
            ext = p.suffix.lower()
            text = ""
            if ext in docio.DOC_EXT and st.st_size < 60 * 1024 * 1024:  # khong OCR anh khi ra soat (tiet kiem pin)
                try:
                    text = docio.extract_file(p)
                except Exception as e:
                    errors.append({"file": str(p.relative_to(rootp)), "error": str(e)[:200]})
            items.append({
                "path": p, "rel": str(p.relative_to(rootp)), "name": p.name, "ext": ext, "size": st.st_size,
                "mtime": st.st_mtime, "sha": _sha256(p),
                "cat": _category(p.name, text, ext), "year": _year(p.name, text, st.st_mtime),
                "norm": _norm_text(text) if text else "",
            })
        except Exception as e:
            errors.append({"file": str(p), "error": str(e)[:200]})

    # ---- Trung lap: giong het (cung ma bam) ----
    groups, by_sha = [], {}
    for it in items:
        by_sha.setdefault(it["sha"], []).append(it)
    in_group = set()
    for sha, lst in by_sha.items():
        if len(lst) > 1:
            groups.append({"type": "Giống hệt", "items": lst})
            in_group.update(id(x) for x in lst)
    # ---- Trung noi dung (khac dinh dang/sua nho): MinHash, Jaccard uoc luong >= 0.85 ----
    if near_dup:
        cands = [it for it in items if id(it) not in in_group and it["norm"]]
        for it in cands:
            it["sig"] = _minhash(it["norm"])
        cands = [c for c in cands if c["sig"]]
        buckets = {}
        for idx, it in enumerate(cands):
            for b in range(16):
                buckets.setdefault((b, tuple(it["sig"][b * 4:(b + 1) * 4])), []).append(idx)
        parent = list(range(len(cands)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        checked = set()
        for lst in buckets.values():
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    a, b = lst[i], lst[j]
                    if (a, b) in checked:
                        continue
                    checked.add((a, b))
                    sim = sum(x == y for x, y in zip(cands[a]["sig"], cands[b]["sig"])) / 64
                    if sim >= 0.85:
                        parent[find(a)] = find(b)
        comp = {}
        for i in range(len(cands)):
            comp.setdefault(find(i), []).append(cands[i])
        for lst in comp.values():
            if len(lst) > 1:
                groups.append({"type": "Trùng nội dung", "items": lst})

    # Ban giu lai: ban moi nhat (uu tien .docx/.xlsx hon .pdf vi con sua duoc), con lai chuyen vao _TRUNG_LAP
    pref = {".docx": 3, ".xlsx": 3, ".pdf": 2, ".doc": 1, ".xls": 1}
    dup_of = {}
    for g in groups:
        copy_re = re.compile(r"(copy|bản sao|ban sao|\(\d+\)$)", re.I)
        g["items"].sort(key=lambda x: (not copy_re.search(Path(x["name"]).stem), pref.get(x["ext"], 0),
                                       -x["rel"].count(os.sep), x["mtime"], x["size"]), reverse=True)
        keep = g["items"][0]
        for other in g["items"][1:]:
            dup_of[id(other)] = keep

    # ---- Ke hoach di chuyen ----
    moves = []
    for it in items:
        if handle_dups and id(it) in dup_of:
            keep = dup_of[id(it)]
            dest = rootp / DUP_DIR / Path(keep["name"]).stem[:60] / it["name"]
            reason = f"Trùng với: {keep['rel']}"
        else:
            sub = rootp
            if by_category:
                sub = sub / it["cat"]
            if by_year:
                sub = sub / it["year"]
            dest = sub / it["name"]
            reason = it["cat"] + (f" / {it['year']}" if by_year else "")
        if dest.resolve() != it["path"].resolve() and (by_category or by_year or id(it) in dup_of):
            moves.append({"from": it["rel"], "to": str(dest.relative_to(rootp)), "reason": reason})

    stats = {}
    for it in items:
        stats[it["cat"]] = stats.get(it["cat"], 0) + 1
    report = {
        "root": str(rootp), "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "total": len(items), "total_size": sum(i["size"] for i in items),
        "by_category": dict(sorted(stats.items())),
        "duplicates": [{"type": g["type"], "keep": g["items"][0]["rel"], "others": [x["rel"] for x in g["items"][1:]]}
                       for g in groups],
        "moves": moves, "errors": errors,
        "options": {"by_category": by_category, "by_year": by_year, "handle_dups": handle_dups},
    }
    plan_path = cfgmod.data_dir() / "ke_hoach_sap_xep.json"
    plan_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    logging.info("Ra soat %s: %d file, %d nhom trung, %d de xuat di chuyen", rootp, len(items), len(groups), len(moves))
    return report


# ---------------------------------------------------------------------
# Thuc hien & hoan tac (chi DI CHUYEN, khong xoa)
# ---------------------------------------------------------------------
def _unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    i = 2
    while True:
        cand = dest.with_name(f"{dest.stem} ({i}){dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _logs_dir() -> Path:
    p = cfgmod.data_dir() / "nhat_ky_thu_muc"
    p.mkdir(exist_ok=True)
    return p


def apply_plan(cfg, root: str) -> dict:
    with _LOCK:
        rootp = _check_root(cfg, root)
        plan = json.loads((cfgmod.data_dir() / "ke_hoach_sap_xep.json").read_text(encoding="utf-8"))
        if Path(plan["root"]).resolve() != rootp:
            raise ValueError("Kế hoạch sắp xếp không khớp thư mục. Hãy rà soát lại.")
        done, failed = [], []
        for m in plan["moves"]:
            src, dst = rootp / m["from"], rootp / m["to"]
            if not (_inside(rootp, src) and _inside(rootp, dst)):
                failed.append({**m, "error": "Ngoài phạm vi thư mục được phép"})
                continue
            if not src.exists():
                failed.append({**m, "error": "File không còn tồn tại"})
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst = _unique(dst)
                shutil.move(str(src), str(dst))
                done.append({"from": m["from"], "to": str(dst.relative_to(rootp))})
            except Exception as e:
                failed.append({**m, "error": str(e)[:200]})
        # don thu muc rong (chi thu muc rong, khong xoa file)
        for dirpath, _, _ in sorted(os.walk(rootp), key=lambda x: -len(x[0])):
            d = Path(dirpath)
            if d != rootp and _inside(rootp, d) and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass
        log = {"root": str(rootp), "time": datetime.datetime.now().isoformat(timespec="seconds"), "moves": done, "failed": failed}
        lp = _logs_dir() / f"sap_xep_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
        lp.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        logging.info("Sap xep %s: %d da chuyen, %d loi. Nhat ky: %s", rootp, len(done), len(failed), lp)
        return {"moved": len(done), "failed": failed, "log": str(lp)}


def undo_last(cfg, root: str) -> dict:
    with _LOCK:
        rootp = _check_root(cfg, root)
        logs = sorted(_logs_dir().glob("sap_xep_*.json"), reverse=True)
        for lp in logs:
            log = json.loads(lp.read_text(encoding="utf-8"))
            if Path(log["root"]).resolve() != rootp or log.get("undone"):
                continue
            back, failed = 0, []
            for m in reversed(log["moves"]):
                src, dst = rootp / m["to"], rootp / m["from"]
                if not (_inside(rootp, src) and _inside(rootp, dst)) or not src.exists():
                    failed.append(m["to"])
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(_unique(dst)))
                back += 1
            for dirpath, _, _ in sorted(os.walk(rootp), key=lambda x: -len(x[0])):
                d = Path(dirpath)
                if d != rootp and not any(d.iterdir()):
                    try:
                        d.rmdir()
                    except OSError:
                        pass
            log["undone"] = datetime.datetime.now().isoformat(timespec="seconds")
            lp.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
            logging.info("Hoan tac %s: %d file", lp, back)
            return {"restored": back, "failed": failed}
        raise ValueError("Không có lần sắp xếp nào để hoàn tác cho thư mục này.")


def report_markdown(rep: dict) -> str:
    mb = rep["total_size"] / 1024 / 1024
    out = [f"# BÁO CÁO RÀ SOÁT THƯ MỤC", f"**Thư mục:** {rep['root']}  ",
           f"**Thời điểm:** {rep['time']}  ", f"**Tổng số tài liệu:** {rep['total']} ({mb:.1f} MB)", "",
           "## 1. Phân loại tài liệu", "| Nhóm | Số lượng |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rep["by_category"].items()]
    out += ["", f"## 2. Tài liệu trùng lặp ({len(rep['duplicates'])} nhóm)"]
    if rep["duplicates"]:
        out += ["| STT | Loại trùng | Bản giữ lại | Bản trùng (chuyển vào _TRUNG_LAP) |", "|---|---|---|---|"]
        for i, d in enumerate(rep["duplicates"], 1):
            out.append(f"| {i} | {d['type']} | {d['keep']} | {'<br>'.join(d['others'])} |")
    else:
        out.append("Không phát hiện tài liệu trùng.")
    out += ["", f"## 3. Đề xuất sắp xếp ({len(rep['moves'])} tài liệu sẽ được di chuyển, không xóa tài liệu nào)"]
    if rep["moves"]:
        out += ["| Từ | Đến | Lý do |", "|---|---|---|"]
        out += [f"| {m['from']} | {m['to']} | {m['reason']} |" for m in rep["moves"][:300]]
        if len(rep["moves"]) > 300:
            out.append(f"\n... và {len(rep['moves']) - 300} tài liệu khác.")
    if rep["errors"]:
        out += ["", f"## 4. Tài liệu không đọc được nội dung ({len(rep['errors'])})", "| Tài liệu | Lý do |", "|---|---|"]
        out += [f"| {e['file']} | {e['error']} |" for e in rep["errors"][:100]]
    return "\n".join(out)

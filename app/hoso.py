"""Tien ich ho so: dat ten file chuan, gan ma an vao file Word, so sanh do giong nhau."""
import datetime as dt
import hashlib
import io
import re
import unicodedata
import uuid
from pathlib import Path


def bo_dau(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slug(s: str, maxlen=60) -> str:
    s = bo_dau(s or "")
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"[\s_]+", "-", s.strip())
    return s[:maxlen].strip("-") or "Van-ban"


def parse_date(s):
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s or "")
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def std_name(ngay, so_ky_hieu: str, trich_yeu: str, ext: str) -> str:
    """2026-11-10_1234-SGDDT-GDTrH_Trien-khai-chuyen-doi-so.docx"""
    d = ngay if isinstance(ngay, dt.date) else (parse_date(ngay) or dt.date.today())
    so = slug(so_ky_hieu.replace("/", "-"), 30) if so_ky_hieu else ""
    parts = [d.isoformat()] + ([so] if so else []) + [slug(trich_yeu, 60)]
    return "_".join(parts) + ext.lower()


def new_id() -> str:
    return "VNA-" + uuid.uuid4().hex[:12]


def tag_docx_bytes(blob: bytes, vna_id: str) -> bytes:
    """Ghi ma an vao thuoc tinh file Word (File > Info > Properties). Khong anh huong noi dung."""
    try:
        import docx
        d = docx.Document(io.BytesIO(blob))
        d.core_properties.identifier = vna_id
        d.core_properties.comments = "Dự thảo do VNA soạn"
        buf = io.BytesIO()
        d.save(buf)
        return buf.getvalue()
    except Exception:
        return blob


def read_tag(path: Path) -> str:
    if Path(path).suffix.lower() != ".docx":
        return ""
    try:
        import docx
        return docx.Document(str(path)).core_properties.identifier or ""
    except Exception:
        return ""


def _shingles(text: str, k=4):
    w = re.findall(r"\w+", (text or "").lower())
    return {" ".join(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


def similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def working_days_after(d: dt.date, n: int) -> dt.date:
    while n > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def short_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode()).hexdigest()[:10]

"""Doc chu trong anh (anh chup cong van, PDF scan) bang OCR co san cua Windows - offline, mien phi, nhe.
- Anh: jpg, jpeg, png, bmp, tif, tiff, gif, webp (heic neu Windows co codec).
- PDF scan: tach anh tung trang (pypdf) roi doc chu.
- Ket qua duoc nho (cache) theo ma bam, khong doc lai cung mot anh.
"""
import hashlib
import io
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config as cfgmod

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp", ".heic"}
IS_WIN = sys.platform.startswith("win")
SCRIPT = Path(__file__).parent / "scripts" / "ocr_windows.ps1"
MAX_SIDE = 2400  # OCR cua Windows gioi han kich thuoc anh; thu nho anh lon (cung nhanh hon)


class OCRError(ValueError):
    pass


def _cache(key):
    p = cfgmod.system_dir() / "cache" / f"ocr_{key}.txt"
    p.parent.mkdir(exist_ok=True)
    return p


def _prepare(data: bytes, out: Path):
    """Chuan hoa anh: xoay theo EXIF, thu nho, chuyen PNG den trang (OCR doc tot hon, nhanh hon)."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("L", "RGB"):
            im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, MAX_SIDE / max(w, h))
        if scale < 1.0:
            im = im.resize((int(w * scale), int(h * scale)))
        elif max(w, h) < 1000:  # anh qua nho: phong to de doc ro chu
            im = im.resize((w * 2, h * 2))
        im.convert("RGB").save(out, "PNG")
    except Exception:
        out.write_bytes(data)  # khong co Pillow: dua nguyen anh


def ocr_images(images: list) -> list:
    """images: list[bytes] -> list[str] (moi anh mot doan)."""
    if not images:
        return []
    keys = [hashlib.sha256(b).hexdigest()[:24] for b in images]
    out = [None] * len(images)
    todo = []
    for i, k in enumerate(keys):
        c = _cache(k)
        if c.exists():
            out[i] = c.read_text(encoding="utf-8")
        else:
            todo.append(i)
    if todo:
        if not IS_WIN:
            raise OCRError("Đọc chữ trong ảnh cần Windows 10/11 (bộ OCR có sẵn của Windows).")
        tmp = Path(tempfile.mkdtemp(prefix="VNA_ocr_"))
        paths = []
        for i in todo:
            p = tmp / f"{i:04d}.png"
            _prepare(images[i], p)
            paths.append(str(p))
        lst, res = tmp / "list.txt", tmp / "out.txt"
        lst.write_text("\n".join(paths), encoding="utf-8")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
                            "-ListFile", str(lst), "-OutFile", str(res)],
                           capture_output=True, text=True, timeout=600, creationflags=0x08000000)
        if not res.exists():
            raise OCRError("Không đọc được chữ trong ảnh: " + (r.stderr or r.stdout)[-300:])
        pages = res.read_text(encoding="utf-8-sig").split("<<<HET_TRANG>>>")
        for j, i in enumerate(todo):
            txt = pages[j].strip() if j < len(pages) else ""
            out[i] = txt
            if txt and not txt.startswith("(Khong doc duoc"):
                _cache(keys[i]).write_text(txt, encoding="utf-8")
        for f in tmp.iterdir():
            f.unlink(missing_ok=True)
        tmp.rmdir()
    return [o or "" for o in out]


def image_text(data: bytes) -> str:
    txt = ocr_images([data])[0]
    if not txt.strip():
        return "(Ảnh không có chữ đọc được. Hãy chụp thẳng, đủ sáng, rõ nét.)"
    return "[Văn bản đọc từ ảnh bằng OCR – có thể sai chính tả, cần đối chiếu bản gốc]\n" + txt


def scanned_pdf_text(reader, max_pages=40) -> str:
    """PDF scan: lay anh lon nhat moi trang roi OCR."""
    imgs, idx = [], []
    for n, page in enumerate(reader.pages[:max_pages], 1):
        try:
            pics = list(page.images)
        except Exception as e:
            logging.info("Khong tach duoc anh trang %s: %s", n, e)
            continue
        if not pics:
            continue
        best = max(pics, key=lambda im: len(im.data))
        data = best.data
        try:  # chuan hoa dinh dang la (CCITT, JBIG2...) sang PNG qua Pillow neu co
            buf = io.BytesIO()
            best.image.save(buf, "PNG")
            data = buf.getvalue()
        except Exception:
            pass
        imgs.append(data)
        idx.append(n)
    if not imgs:
        return ""
    texts = ocr_images(imgs)
    body = "\n\n".join(f"[Trang {n}]\n{t}" for n, t in zip(idx, texts) if t.strip())
    return ("[PDF scan – văn bản đọc bằng OCR, có thể sai chính tả, cần đối chiếu bản gốc]\n" + body) if body else ""

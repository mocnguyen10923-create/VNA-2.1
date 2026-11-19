"""HOC TAP VA TU HOAN THIEN (Dac ta muc 10).

VNA hoc tu cap (du thao cua VNA -> ban nguoi dung da sua, ky, ban hanh):
  - Dinh dang (phong, co chu, le, gian dong, thut dau dong): doc chinh xac tu file Word da duyet.
  - Van phong, cau truc: AI doc cac doan bi sua -> quy tac ngan -> So tay phong cach.
  - Loi da sua -> So loi (kiem tra moi lan, khong tai pham).
  - Van ban da ban hanh -> van ban mau theo loai.
  - Phan hoi truc tiep (nut 👍/👎 + "lan sau hay...").
Moi thu luu tren may (_he_thong/hoc_tap.json); nguoi dung xem, sua, tat, xoa tung muc.
Gioi han: VNA khong doi bo nao AI, khong tu sua ma nguon; "hoc" = tich luy quy tac, mau, vi du.
"""
import datetime as dt
import difflib
import json
import logging
import re
import threading
import uuid
from pathlib import Path

from . import config as cfgmod
from . import docio, hoso, llm, power

_LOCK = threading.Lock()
DOC_TYPES = ["Công văn", "Quyết định", "Tờ trình", "Báo cáo", "Kế hoạch", "Thông báo", "Biên bản", "Giấy mời",
             "Giáo án", "Đề kiểm tra", "Nhận xét", "Khác"]

LEARN_PROMPT = """Dưới đây là các đoạn trong DỰ THẢO do trợ lý AI soạn (TRƯỚC) và bản đã được lãnh đạo SỬA, DUYỆT (SAU) của cùng một văn bản loại "{loai}".
Hãy rút ra những QUY TẮC CHUNG về phong cách, văn phong, từ ngữ, cấu trúc mà người duyệt mong muốn, để lần sau soạn đúng ngay.
- Chỉ ghi quy tắc có thể áp dụng cho văn bản khác (không ghi chi tiết riêng của văn bản này như tên người, ngày cụ thể, số liệu).
- Mỗi quy tắc một câu ngắn, mệnh lệnh, cụ thể (VD: "Gọi giáo viên là 'các thầy cô giáo', không dùng 'các đồng chí'").
- Nếu là lỗi cụ thể về từ ngữ có thể thay tự động, điền cum_tu_sai và cum_tu_dung.
Trả về DUY NHẤT JSON:
{{"quy_tac": [{{"noi_dung": "...", "nhom": "van_phong|cau_truc|tu_ngu"}}],
  "loi": [{{"noi_dung": "mô tả lỗi cần tránh", "cum_tu_sai": "", "cum_tu_dung": ""}}]}}
Không có gì đáng rút ra thì trả về danh sách rỗng.

{pairs}"""


def _path() -> Path:
    return cfgmod.system_dir() / "hoc_tap.json"


def load() -> dict:
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        d = {}
    for k, v in (("rules", []), ("errors", []), ("formats", {}), ("examples", {}), ("stats", []), ("cho_hoc", [])):
        d.setdefault(k, v)
    return d


def save(d):
    with _LOCK:
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(_path())


def _norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def _merge(items: list, new: dict, approve_after=2):
    for it in items:
        if difflib.SequenceMatcher(None, _norm(it["noi_dung"]), _norm(new["noi_dung"])).ratio() > 0.8:
            it["dem"] = it.get("dem", 1) + 1
            it["lan_cuoi"] = dt.date.today().isoformat()
            if it.get("trang_thai") == "cho" and it["dem"] >= approve_after:
                it["trang_thai"] = "ap_dung"
            return it
    new.setdefault("id", uuid.uuid4().hex[:8])
    new.setdefault("dem", 1)
    new.setdefault("tao", dt.date.today().isoformat())
    items.append(new)
    return new


# ---------------------------------------------------------------------
# Dinh dang (chinh xac, khong can AI)
# ---------------------------------------------------------------------
def format_from_docx(path: Path) -> dict:
    import docx
    from collections import Counter
    d = docx.Document(str(path))
    sec = d.sections[0]
    cm = lambda v: round(v / 360000, 2) if v else None  # EMU -> cm
    fonts, sizes, spacing, indent, after = Counter(), Counter(), Counter(), Counter(), Counter()
    for p in d.paragraphs:
        if len(p.text.strip()) < 40:   # bo dong ngan (tieu de, quoc hieu)
            continue
        pf = p.paragraph_format
        if pf.line_spacing and isinstance(pf.line_spacing, float):
            spacing[round(pf.line_spacing, 2)] += 1
        if pf.first_line_indent is not None:
            indent[cm(pf.first_line_indent)] += 1
        if pf.space_after is not None:
            after[round(pf.space_after.pt)] += 1
        for r in p.runs:
            if r.font.name:
                fonts[r.font.name] += len(r.text)
            if r.font.size:
                sizes[r.font.size.pt] += len(r.text)
    st = d.styles["Normal"].font
    fmt = {
        "font": (fonts.most_common(1)[0][0] if fonts else st.name) or "Times New Roman",
        "size": (sizes.most_common(1)[0][0] if sizes else (st.size.pt if st.size else 14)),
        "top": cm(sec.top_margin), "bottom": cm(sec.bottom_margin), "left": cm(sec.left_margin), "right": cm(sec.right_margin),
        "line_spacing": spacing.most_common(1)[0][0] if spacing else None,
        "first_indent": indent.most_common(1)[0][0] if indent else None,
        "space_after": after.most_common(1)[0][0] if after else None,
        "hoc_tu": Path(path).name, "ngay": dt.date.today().isoformat(),
    }
    return fmt


def format_for(doc_type: str) -> dict:
    f = load()["formats"]
    return f.get(doc_type) or f.get("_chung") or {}


# ---------------------------------------------------------------------
# Hoc tu cap du thao -> ban da ban hanh
# ---------------------------------------------------------------------
def _paras(path: Path):
    text = docio.extract_file(path)
    return [l.strip() for l in text.split("\n") if len(l.strip()) > 3]


def learn_pair(cfg, draft_path: Path, final_path: Path, doc_type: str = "Khác") -> dict:
    a, b = _paras(draft_path), _paras(final_path)
    sm = difflib.SequenceMatcher(None, a, b)
    ratio = round(1 - sm.ratio(), 3)  # ty le phai sua (0 = giu nguyen)
    pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        before, after = "\n".join(a[i1:i2])[:600], "\n".join(b[j1:j2])[:600]
        if before or after:
            pairs.append((before, after))
    d = load()
    d["stats"].append({"ngay": dt.date.today().isoformat(), "loai": doc_type, "ty_le_sua": ratio, "file": Path(final_path).name})
    d["stats"] = d["stats"][-500:]
    if Path(final_path).suffix.lower() == ".docx":
        try:
            fmt = format_from_docx(final_path)
            d["formats"][doc_type] = fmt
            d["formats"].setdefault("_chung", fmt)
        except Exception as e:
            logging.warning("Khong doc duoc dinh dang %s: %s", final_path, e)
    ex = d["examples"].setdefault(doc_type, [])
    if str(final_path) not in ex:
        ex.append(str(final_path))
        d["examples"][doc_type] = ex[-5:]
    learned = {"ty_le_sua": ratio, "quy_tac_moi": 0, "loi_moi": 0, "hoan": False}
    if pairs and ratio > 0.01 and not power.can_run_heavy(cfg, idle_needed=0):
        # Dang dung pin: chi hoc dinh dang ngay (khong can AI); phan van phong de danh khi cam sac, may ranh
        d["cho_hoc"].append({"draft": str(draft_path), "final": str(final_path), "loai": doc_type})
        learned["hoan"] = True
        save(d)
        return learned
    if pairs and ratio > 0.01:
        txt = "\n\n".join(f"--- ĐOẠN {i} ---\nTRƯỚC: {x or '(không có)'}\nSAU: {y or '(đã xóa)'}" for i, (x, y) in enumerate(pairs[:15], 1))
        try:
            raw = llm.chat(cfg, "Bạn là chuyên gia biên tập văn bản hành chính, giáo dục.",
                           [{"role": "user", "content": LEARN_PROMPT.format(loai=doc_type, pairs=txt)}], json_mode=True)
            res = _json(raw)
            for q in res.get("quy_tac", [])[:8]:
                if isinstance(q, dict) and q.get("noi_dung"):
                    _merge(d["rules"], {"noi_dung": q["noi_dung"].strip(), "nhom": q.get("nhom", "van_phong"), "loai_vb": doc_type,
                                        "nguon": f"Học từ {Path(final_path).name}", "trang_thai": "cho"})
                    learned["quy_tac_moi"] += 1
            for e in res.get("loi", [])[:8]:
                if isinstance(e, dict) and e.get("noi_dung"):
                    _merge(d["errors"], {"noi_dung": e["noi_dung"].strip(), "cum_tu_sai": e.get("cum_tu_sai", "").strip(),
                                         "cum_tu_dung": e.get("cum_tu_dung", "").strip(), "nguon": f"Sửa trong {Path(final_path).name}",
                                         "trang_thai": "ap_dung"}, approve_after=1)
                    learned["loi_moi"] += 1
        except Exception as e:
            logging.warning("Hoc van phong loi: %s", e)
    save(d)
    logging.info("Hoc tu %s: %s", final_path, learned)
    return learned


def process_pending(cfg) -> bool:
    """Chay 1 viec hoc da hoan (goi boi tien trinh nen khi cam sac + may ranh)."""
    d = load()
    if not d["cho_hoc"]:
        return False
    job = d["cho_hoc"].pop(0)
    save(d)
    dp, fp = Path(job["draft"]), Path(job["final"])
    if dp.exists() and fp.exists():
        d2 = load()
        d2["stats"] = [s for s in d2["stats"] if s.get("file") != fp.name]  # tranh dem trung
        save(d2)
        learn_pair(cfg, dp, fp, job.get("loai") or "Khác")
    return True


def _json(text):
    t = re.sub(r"^```(json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        return json.loads(m.group(0)) if m else {}


# ---------------------------------------------------------------------
# Phan hoi truc tiep, quan ly so tay
# ---------------------------------------------------------------------
def feedback(rating: str, note: str, sample: str = "") -> dict:
    d = load()
    out = {}
    if note.strip():
        r = _merge(d["rules"], {"noi_dung": note.strip(), "nhom": "phan_hoi", "loai_vb": "",
                                "nguon": "Bạn dặn trực tiếp", "trang_thai": "ap_dung"}, approve_after=1)
        r["trang_thai"] = "ap_dung"
        out["rule"] = r
    d["stats"].append({"ngay": dt.date.today().isoformat(), "loai": "Phản hồi", "danh_gia": rating})
    save(d)
    return out


def set_item(kind: str, item_id: str, changes: dict):
    d = load()
    lst = d["rules" if kind == "rule" else "errors"]
    for it in lst:
        if it["id"] == item_id:
            if changes.get("xoa"):
                lst.remove(it)
            else:
                for k in ("noi_dung", "trang_thai", "cum_tu_sai", "cum_tu_dung", "loai_vb"):
                    if k in changes:
                        it[k] = changes[k]
            save(d)
            return True
    return False


def add_item(kind: str, noi_dung: str, **kw):
    d = load()
    item = {"noi_dung": noi_dung.strip(), "nguon": "Bạn thêm", "trang_thai": "ap_dung", **kw}
    _merge(d["rules" if kind == "rule" else "errors"], item, approve_after=1)
    save(d)


# ---------------------------------------------------------------------
# Dua vao loi dan cho AI
# ---------------------------------------------------------------------
def guess_type(text: str) -> str:
    t = (text or "").lower()
    for k in ["công văn", "quyết định", "tờ trình", "báo cáo", "kế hoạch", "thông báo", "biên bản", "giấy mời"]:
        if k in t:
            return k.capitalize()
    if "giáo án" in t or "kế hoạch bài dạy" in t:
        return "Giáo án"
    if "đề kiểm tra" in t or "ma trận" in t:
        return "Đề kiểm tra"
    if "nhận xét" in t:
        return "Nhận xét"
    return ""


def prompt_addon(question: str = "") -> str:
    d = load()
    doc_type = guess_type(question)
    rules = [r for r in d["rules"] if r.get("trang_thai") == "ap_dung" and (not r.get("loai_vb") or r.get("loai_vb") == doc_type)]
    errs = [e for e in d["errors"] if e.get("trang_thai") == "ap_dung"]
    parts = []
    if rules:
        parts.append("SỔ TAY PHONG CÁCH CỦA NGƯỜI DÙNG (bắt buộc tuân theo, học từ các bản họ đã sửa, duyệt):\n"
                     + "\n".join(f"- {r['noi_dung']}" for r in rules[-40:]))
    if errs:
        parts.append("SỔ LỖI – KHÔNG ĐƯỢC TÁI PHẠM:\n" + "\n".join(f"- {e['noi_dung']}" for e in errs[-40:]))
    ex = d["examples"].get(doc_type) if doc_type else None
    if ex and re.search(r"\b(soạn|viết|lập|dự thảo)\b", (question or "").lower()):
        p = Path(ex[-1])
        if p.exists():
            try:
                sample = docio.extract_file(p)[:2500]
                parts.append(f"VĂN BẢN MẪU ĐÃ ĐƯỢC DUYỆT (cùng loại {doc_type}) – bám theo cách trình bày, giọng văn, cấu trúc; "
                             f"KHÔNG chép nội dung riêng:\n{sample}")
            except Exception:
                pass
    return "\n\n".join(parts)


def monthly_stats():
    d = load()
    out = {}
    for s in d["stats"]:
        if "ty_le_sua" not in s:
            continue
        m = s["ngay"][:7]
        out.setdefault(m, []).append(s["ty_le_sua"])
    return [{"thang": m, "so_van_ban": len(v), "ty_le_sua_tb": round(sum(v) / len(v) * 100, 1)} for m, v in sorted(out.items())]

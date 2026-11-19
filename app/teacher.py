"""Cong cu giao vien: cham bai hang loat, nhan xet danh gia hoc sinh theo quy che."""
import datetime as dt
import io
import json
import logging
import re

from . import config as cfgmod
from . import docio, llm, prompts

GRADE_PROMPT = """Bạn là giáo viên giỏi, chấm bài công tâm, chính xác theo ĐÁP ÁN – HƯỚNG DẪN CHẤM.
Môn: {mon}. Thang điểm: {thang}. {yeu_cau}
Quy tắc: chấm theo ý, cho điểm thành phần đúng như hướng dẫn chấm; học sinh làm cách khác đúng vẫn cho đủ điểm;
không suy đoán phần bài làm không có; điểm làm tròn đến 0,25. Nhận xét ngắn gọn, động viên, chỉ rõ lỗi sai và cách khắc phục.

=== ĐỀ BÀI ===
{de}

=== ĐÁP ÁN – HƯỚNG DẪN CHẤM ===
{dap_an}

=== BÀI LÀM CỦA HỌC SINH (file: {file}) ===
{bai}

Trả về DUY NHẤT JSON:
{{"ho_ten": "họ tên học sinh nếu có trong bài, nếu không thì để trống",
  "lop": "",
  "cac_cau": [{{"cau": "1", "diem": 0.0, "toi_da": 0.0, "nhan_xet": "..."}}],
  "tong_diem": 0.0,
  "nhan_xet_chung": "2-3 câu nhận xét chung, động viên",
  "can_xem_lai": "ghi lý do nếu bài khó đọc/không chắc chắn, nếu không để trống"}}"""

COMMENT_PROMPT = """Viết lời nhận xét cho từng học sinh theo Thông tư 22/2021/TT-BGDĐT (đánh giá học sinh THCS, THPT){loai}.
Môn/nội dung: {mon}. Yêu cầu: mỗi nhận xét 1–2 câu (15–35 từ), cụ thể theo số liệu của học sinh đó, nêu điểm mạnh và điều cần cố gắng,
ngôn ngữ sư phạm, tôn trọng, động viên; không dùng lời lẽ xúc phạm, không so sánh với bạn khác; không lặp y nguyên giữa các học sinh.
{them}
Dữ liệu (dòng đầu là tiêu đề cột):
{data}

Trả về DUY NHẤT JSON: {{"nhan_xet": ["nhận xét học sinh thứ 1", "nhận xét học sinh thứ 2", ...]}} — đúng {n} phần tử, đúng thứ tự."""


def _json(text):
    t = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            return json.loads(m.group(0))
        raise ValueError("AI không trả về đúng định dạng.")


def _num(v):
    try:
        return round(float(str(v).replace(",", ".")), 2)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------
# CHAM BAI
# ---------------------------------------------------------------------
def grade(app, dap_an: dict, bai_lam: list, de: dict = None, mon="", thang=10, yeu_cau=""):
    if not dap_an or not dap_an.get("text"):
        raise ValueError("Cần có file ĐÁP ÁN – HƯỚNG DẪN CHẤM.")
    if not bai_lam:
        raise ValueError("Chưa có bài làm của học sinh.")
    cfg = app.cfg
    system = prompts.build_system("giao_vien", cfg)
    results = []
    for b in bai_lam:
        text = (b.get("text") or "").strip()
        if len(text) < 5 or text.startswith("(PDF này là bản scan"):
            results.append({"file": b["name"], "ho_ten": "", "cac_cau": [], "tong_diem": None,
                            "nhan_xet_chung": "", "can_xem_lai": "Không đọc được chữ trong bài (bài viết tay/scan) – cần chấm tay."})
            continue
        msg = GRADE_PROMPT.format(mon=mon or "(theo đề)", thang=thang, yeu_cau=yeu_cau, de=(de or {}).get("text", "(xem trong đáp án)")[:15000],
                                  dap_an=dap_an["text"][:20000], file=b["name"], bai=text[:20000])
        try:
            r = _json(llm.chat(cfg, system, [{"role": "user", "content": msg}], json_mode=True))
            r["file"] = b["name"]
            r["tong_diem"] = _num(r.get("tong_diem"))
            cau = [c for c in r.get("cac_cau", []) if isinstance(c, dict)]
            s = round(sum(_num(c.get("diem")) for c in cau), 2)
            if cau and abs(s - r["tong_diem"]) > 0.01:  # tu kiem tra cong diem
                r["tong_diem"] = s
            r["tong_diem"] = min(max(r["tong_diem"], 0), float(thang))
            results.append(r)
        except llm.LLMError:
            raise
        except Exception as e:
            results.append({"file": b["name"], "tong_diem": None, "cac_cau": [], "can_xem_lai": f"Lỗi chấm: {e}"})
        logging.info("Cham bai %s: %s", b["name"], results[-1].get("tong_diem"))
    return _export_grades(results, mon, thang)


def _export_grades(results, mon, thang):
    safe_mon = re.sub(r"[^\w\- ]+", "", mon)[:30]
    folder = cfgmod.output_dir("Chấm bài") / f"{dt.datetime.now():%Y%m%d_%H%M} {safe_mon}".strip()
    folder.mkdir(parents=True, exist_ok=True)
    # Bang diem Excel
    md = ["| STT | Họ và tên | File bài làm | Điểm | Nhận xét chung | Cần GV xem lại |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        diem = "" if r.get("tong_diem") is None else r["tong_diem"]
        md.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in
                                     [i, r.get("ho_ten", ""), r["file"], diem, r.get("nhan_xet_chung", ""), r.get("can_xem_lai", "")]) + " |")
    xlsx = folder / "Bang_diem.xlsx"
    xlsx.write_bytes(docio.export_xlsx(f"# BẢNG ĐIỂM – {mon} (thang điểm {thang})\n\n" + "\n".join(md)))
    # Chi tiet tung bai (Word)
    lines = [f"# KẾT QUẢ CHẤM BÀI – {mon.upper()}", f"Thang điểm {thang}. VNA chấm theo đáp án; giáo viên kiểm tra lại trước khi công bố.", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. {r.get('ho_ten') or r['file']} — Điểm: {'' if r.get('tong_diem') is None else r['tong_diem']}")
        cau = r.get("cac_cau") or []
        if cau:
            lines += ["| Câu | Điểm | Tối đa | Nhận xét |", "|---|---|---|---|"]
            lines += [f"| {c.get('cau', '')} | {c.get('diem', '')} | {c.get('toi_da', '')} | {str(c.get('nhan_xet', '')).replace('|', '/')} |" for c in cau]
        if r.get("nhan_xet_chung"):
            lines.append(f"**Nhận xét:** {r['nhan_xet_chung']}")
        if r.get("can_xem_lai"):
            lines.append(f"**⚠ Cần giáo viên xem lại:** {r['can_xem_lai']}")
        lines.append("")
    docx = folder / "Chi_tiet_cham_bai.docx"
    docx.write_bytes(docio.export_docx("\n".join(lines), {"the_thuc": False}))
    graded = [r["tong_diem"] for r in results if r.get("tong_diem") is not None]
    summary = (f"Đã chấm {len(graded)}/{len(results)} bài"
               + (f"; điểm trung bình {sum(graded) / len(graded):.2f}; cao nhất {max(graded)}; thấp nhất {min(graded)}" if graded else ""))
    return {"folder": str(folder), "excel": str(xlsx), "word": str(docx), "summary": summary, "markdown": "\n".join(md)}


# ---------------------------------------------------------------------
# NHAN XET HOC SINH
# ---------------------------------------------------------------------
def comments_for_rows(cfg, header: list, rows: list, mon="", loai="mon_hoc", them="") -> list:
    """Tra ve danh sach nhan xet, dung so luong va thu tu cac dong."""
    loai_txt = {"mon_hoc": " — nhận xét kết quả học tập môn học",
                "ren_luyen": " — nhận xét kết quả rèn luyện (phẩm chất), mức Tốt/Khá/Đạt/Chưa đạt",
                "gvcn": " — nhận xét của giáo viên chủ nhiệm về học tập và rèn luyện cả năm"}.get(loai, "")
    system = prompts.build_system("giao_vien", cfg)
    out = []
    for i in range(0, len(rows), 12):  # moi lan 12 hoc sinh cho on dinh
        part = rows[i:i + 12]
        data = "\n".join(["\t".join(map(str, header))] + ["\t".join("" if v is None else str(v) for v in r) for r in part])
        msg = COMMENT_PROMPT.format(loai=loai_txt, mon=mon or "(theo bảng)", them=them, data=data, n=len(part))
        res = []
        for _ in range(2):
            try:
                res = _json(llm.chat(cfg, system, [{"role": "user", "content": msg}], json_mode=True)).get("nhan_xet", [])
                if len(res) == len(part):
                    break
            except llm.LLMError:
                raise
            except Exception:
                res = []
        res = [str(x).strip() for x in res][: len(part)]
        res += ["(VNA chưa tạo được nhận xét – giáo viên bổ sung)"] * (len(part) - len(res))
        out += res
    return out


def comments_xlsx(app, data: bytes, mon="", loai="mon_hoc", them=""):
    import openpyxl
    from openpyxl.styles import Alignment, Font

    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb.active
    # tim dong tieu de: dong dau tien co tu 2 o chu tro len, trong do co "tên"
    hdr_row = 1
    for r in range(1, min(ws.max_row, 15) + 1):
        vals = [str(c.value or "").lower() for c in ws[r]]
        if any("tên" in v for v in vals):
            hdr_row = r
            break
    max_col = ws.max_column
    header = [ws.cell(hdr_row, c).value or f"Cột {c}" for c in range(1, max_col + 1)]
    name_col = next((i for i, h in enumerate(header) if "tên" in str(h).lower()), 1)
    rows, row_idx = [], []
    for r in range(hdr_row + 1, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, max_col + 1)]
        if vals[name_col] in (None, ""):
            continue
        rows.append(vals)
        row_idx.append(r)
    if not rows:
        raise ValueError("Không tìm thấy danh sách học sinh (cần cột có chữ 'Tên' ở dòng tiêu đề).")
    cmts = comments_for_rows(app.cfg, header, rows, mon, loai, them)
    col = max_col + 1
    ws.cell(hdr_row, col, "Nhận xét (VNA)").font = Font(bold=True)
    for r, c in zip(row_idx, cmts):
        cell = ws.cell(r, col, c)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 60
    folder = cfgmod.output_dir("Nhận xét học sinh")
    safe_mon = re.sub(r"[^\w\- ]+", "", mon)[:30]
    path = folder / f"NhanXet_{safe_mon}_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
    buf = io.BytesIO()
    wb.save(buf)
    path.write_bytes(buf.getvalue())
    return {"path": str(path), "count": len(rows)}

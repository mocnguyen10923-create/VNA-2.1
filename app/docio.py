"""Doc tai lieu (Word, Excel, PDF, van ban) va xuat ra Word theo the thuc ND 30/2020, xuat Excel."""
import datetime
import io
import re
from pathlib import Path

DOC_EXT = {".docx", ".xlsx", ".xlsm", ".pdf", ".txt", ".md", ".csv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp", ".heic"}
SUPPORTED = DOC_EXT | IMAGE_EXT  # anh: doc chu bang OCR cua Windows


# =====================================================================
# DOC TAI LIEU
# =====================================================================
def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1258", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _docx_text(data: bytes) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(io.BytesIO(data))
    out = []
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(el, d).text.strip()
            if t:
                out.append(t)
        elif tag == "tbl":
            for row in Table(el, d).rows:
                cells = []
                for c in row.cells:
                    txt = c.text.strip().replace("\n", " ")
                    if not cells or cells[-1] != txt:  # bo o gop trung lap
                        cells.append(txt)
                out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _xlsx_text(data: bytes, max_rows=3000) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"### Trang tính: {ws.title}")
        n = 0
        for row in ws.iter_rows(values_only=True):
            if row is None or all(v is None or str(v).strip() == "" for v in row):
                continue
            out.append("\t".join("" if v is None else str(v) for v in row).rstrip())
            n += 1
            if n >= max_rows:
                out.append(f"... (đã cắt bớt, chỉ đọc {max_rows} dòng đầu)")
                break
    wb.close()
    return "\n".join(out)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    r = PdfReader(io.BytesIO(data))
    pages = []
    for i, p in enumerate(r.pages, 1):
        t = (p.extract_text() or "").strip()
        if t:
            pages.append(f"[Trang {i}]\n{t}")
    if not pages:
        # PDF scan: doc chu bang OCR cua Windows
        try:
            from . import ocr
            t = ocr.scanned_pdf_text(r)
            if t:
                return t
        except Exception as e:
            return f"(PDF scan dạng ảnh – chưa đọc được chữ: {e})"
        return "(PDF scan dạng ảnh, không đọc được chữ. Hãy quét lại rõ nét hơn.)"
    return "\n\n".join(pages)


def extract_text(name: str, data: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext == ".docx":
        return _docx_text(data)
    if ext in (".xlsx", ".xlsm"):
        return _xlsx_text(data)
    if ext == ".pdf":
        return _pdf_text(data)
    if ext in (".txt", ".md", ".csv"):
        return _decode(data)
    if ext in IMAGE_EXT:
        from . import ocr
        return ocr.image_text(data)
    if ext in (".doc", ".xls"):
        raise ValueError(f"Định dạng cũ {ext}: hãy mở bằng Word/Excel và 'Lưu thành' .docx/.xlsx rồi đưa lại.")
    raise ValueError(f"Chưa hỗ trợ định dạng {ext}. Hỗ trợ: docx, xlsx, pdf (kể cả bản scan), txt, md, csv, ảnh jpg/png/tif.")


def extract_file(path: Path) -> str:
    return extract_text(path.name, Path(path).read_bytes())


# =====================================================================
# PHAN TICH MARKDOWN DON GIAN
# =====================================================================
_TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _split_row(line: str):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_blocks(md: str):
    """Tra ve list block: ('h', level, text) ('p', text) ('li', text, marker) ('table', rows) ('blank',)"""
    lines = md.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                blocks.append(("p", lines[i]))
                i += 1
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            rows = [_split_row(s)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            blocks.append(("table", rows))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
        elif re.match(r"^[-*+•]\s+", s):
            blocks.append(("li", re.sub(r"^[-*+•]\s+", "", s), "-"))
        elif s in ("---", "***", "___"):
            blocks.append(("blank",))
        elif s == "":
            blocks.append(("blank",))
        else:
            blocks.append(("p", s))
        i += 1
    return blocks


def strip_markdown(md: str) -> str:
    """Bo ky hieu markdown de chen vao Word hoac doc thanh giong noi."""
    out = []
    for b in parse_blocks(md):
        if b[0] == "h":
            out.append(_plain_inline(b[2]))
        elif b[0] == "p":
            out.append(_plain_inline(b[1]))
        elif b[0] == "li":
            out.append("- " + _plain_inline(b[1]))
        elif b[0] == "table":
            for r in b[1]:
                out.append("\t".join(_plain_inline(c) for c in r))
        else:
            if out and out[-1] != "":
                out.append("")
    return "\n".join(out).strip()


def _plain_inline(t: str) -> str:
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"__(.+?)__", r"\1", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = t.replace("<br>", " ").replace("<br/>", " ")
    return t


def _runs(t: str):
    """Tach doan thanh cac run (text, bold, italic)."""
    parts = re.split(r"(\*\*.+?\*\*|(?<!\*)\*(?!\s).+?(?<!\s)\*(?!\*))", t)
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            yield p[2:-2], True, False
        elif p.startswith("*") and p.endswith("*") and len(p) > 2:
            yield p[1:-1], False, True
        else:
            yield p.replace("`", ""), False, False


# =====================================================================
# KHUON VAN BAN DO AI SOAN (LOAI / TRICH YEU / --- / NOI NHAN / CHUC VU)
# =====================================================================
def parse_draft(text: str) -> dict:
    res = {"loai": "", "trich_yeu": "", "kinh_gui": "", "noi_dung": text.strip(), "noi_nhan": "", "chuc_vu": "", "ghi_chu": ""}
    if not re.search(r"^\s*\**LOẠI\**\s*:", text, re.M | re.I):
        return res
    t = text.replace("\r\n", "\n")
    lines = t.split("\n")
    body, mode = [], "head"
    nn_lines = []
    for line in lines:
        s = line.strip().replace("**", "")
        up = s.upper()
        if mode in ("head", "body", "after") and up.startswith("NƠI NHẬN"):
            mode = "nn"
            rest = s.split(":", 1)[1].strip() if ":" in s else ""
            if rest:
                nn_lines.append(rest)
            continue
        if up.startswith("CHỨC VỤ") and ":" in s:
            res["chuc_vu"] = s.split(":", 1)[1].strip()
            mode = "after"
            continue
        if up.startswith("GHI CHÚ") and ":" in s:
            res["ghi_chu"] = s.split(":", 1)[1].strip()
            mode = "note"
            continue
        if mode == "head":
            if up.startswith("LOẠI") and ":" in s:
                res["loai"] = s.split(":", 1)[1].strip()
            elif up.startswith("TRÍCH YẾU") and ":" in s:
                res["trich_yeu"] = re.sub(r"^V/v\s*", "", s.split(":", 1)[1].strip(), flags=re.I)
            elif up.startswith("KÍNH GỬI") and ":" in s:
                res["kinh_gui"] = s.split(":", 1)[1].strip()
            elif s == "---":
                mode = "body"
            elif s:
                mode = "body"
                body.append(line)
        elif mode == "body":
            if s == "---":
                mode = "after"
            else:
                body.append(line)
        elif mode == "nn":
            if s and s != "---":
                nn_lines.append(s)
        elif mode == "note":
            if s:
                res["ghi_chu"] += " " + s
    res["noi_dung"] = "\n".join(body).strip()
    res["noi_nhan"] = "\n".join(nn_lines).strip()
    return res


# =====================================================================
# XUAT WORD
# =====================================================================
def _ngay_thang(dia_danh: str) -> str:
    d = datetime.date.today()
    ngay = f"{d.day:02d}" if d.day < 10 else str(d.day)  # ND30: ngay < 10 ghi so 0 phia truoc
    thang = f"{d.month:02d}" if d.month < 3 else str(d.month)  # thang 1, 2 ghi so 0 phia truoc
    return f"{dia_danh}, ngày {ngay} tháng {thang} năm {d.year}"


def export_docx(content: str, opts: dict) -> bytes:
    import docx
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    the_thuc = bool(opts.get("the_thuc", True))
    draft = parse_draft(content)
    loai = (opts.get("loai") or draft["loai"] or "").strip()
    if loai.lower() in ("văn bản khác", "khác"):
        loai = ""
    trich_yeu = (opts.get("trich_yeu") or draft["trich_yeu"]).strip()
    kinh_gui = (opts.get("kinh_gui") or draft["kinh_gui"]).strip()
    noi_nhan = (opts.get("noi_nhan") or draft["noi_nhan"]).strip()
    chuc_vu = (opts.get("chuc_vu") or draft["chuc_vu"] or "").strip()
    body = draft["noi_dung"]
    fmt = opts.get("dinh_dang") or {}   # dinh dang VNA da hoc tu van ban nguoi dung duyet (learning.format_for)
    font_name = fmt.get("font") or "Times New Roman"
    font_size = Pt(float(opts.get("co_chu") or fmt.get("size") or 14))

    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name = font_name
    st.font.size = font_size
    st.element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    pf = st.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(fmt["space_after"] if fmt.get("space_after") is not None else 6)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = fmt.get("line_spacing") or 1.15
    first_indent = Cm(fmt["first_indent"]) if fmt.get("first_indent") else Cm(1.0)

    sec = d.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin, sec.bottom_margin = Cm(fmt.get("top") or 2.0), Cm(fmt.get("bottom") or 2.0)
    sec.left_margin, sec.right_margin = Cm(fmt.get("left") or 3.0), Cm(fmt.get("right") or 1.5)

    def para(container, text="", bold=False, italic=False, size=None, align=None, upper=False,
             indent=False, after=None, before=None, keep=False):
        p = container.add_paragraph()
        if align is not None:
            p.alignment = align
        if indent:
            p.paragraph_format.first_line_indent = first_indent
        if after is not None:
            p.paragraph_format.space_after = Pt(after)
        if before is not None:
            p.paragraph_format.space_before = Pt(before)
        if keep:
            p.paragraph_format.line_spacing = 1.0
        if text:
            for t, b, it in _runs(text):
                r = p.add_run(t.upper() if upper else t)
                r.bold = bold or b
                r.italic = italic or it
                r.font.name = font_name
                if size:
                    r.font.size = Pt(size)
        return p

    def no_borders(tbl):
        tblPr = tbl._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "nil")
            borders.append(el)
        tblPr.append(borders)

    def set_widths(tbl, widths):
        tbl.autofit = False
        tblW = tbl._tbl.tblPr.find(qn("w:tblW"))
        if tblW is None:
            tblW = OxmlElement("w:tblW")
            tbl._tbl.tblPr.append(tblW)
        tblW.set(qn("w:type"), "dxa")
        tblW.set(qn("w:w"), str(int(sum(w for w in widths) / 635)))
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tbl._tbl.tblPr.append(layout)
        for gc, w in zip(tbl._tbl.tblGrid.findall(qn("w:gridCol")), widths):
            gc.set(qn("w:w"), str(int(w / 635)))
        for idx, w in enumerate(widths):
            tbl.columns[idx].width = w
        for row in tbl.rows:
            for idx, w in enumerate(widths):
                row.cells[idx].width = w

    def short_line(cell, width_chars=14):
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 0.8
        r = p.add_run("─" * width_chars)
        r.font.size = Pt(8)

    C = WD_ALIGN_PARAGRAPH.CENTER
    is_cong_van = (loai.lower() in ("công văn", "cong van")) if loai else False

    if the_thuc:
        tbl = d.add_table(rows=1, cols=2)
        no_borders(tbl)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_widths(tbl, [Cm(6.3), Cm(10.2)])
        L, R = tbl.rows[0].cells
        L.paragraphs[0].text = ""
        cq_cq = opts.get("co_quan_chu_quan", "").strip()
        first = L.paragraphs[0]
        first.alignment = C
        first.paragraph_format.space_after = Pt(0)
        if cq_cq:
            r = first.add_run(cq_cq.upper())
            r.font.size = Pt(12)
            p = para(L, opts.get("co_quan", ""), bold=True, size=12, align=C, upper=True, after=0, keep=True)
        else:
            r = first.add_run((opts.get("co_quan") or "").upper())
            r.bold = True
            r.font.size = Pt(12)
        short_line(L, 10)
        ky_hieu = opts.get("so_ky_hieu") or (f"Số:      /{opts.get('ky_hieu_co_quan')}" if opts.get("ky_hieu_co_quan") else "Số:      /")
        para(L, ky_hieu, size=13, align=C, after=0, keep=True)
        if is_cong_van and trich_yeu:
            para(L, "V/v " + trich_yeu, size=12, align=C, after=0, keep=True)

        R.paragraphs[0].alignment = C
        R.paragraphs[0].paragraph_format.space_after = Pt(0)
        r = R.paragraphs[0].add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        r.bold = True
        r.font.size = Pt(12)
        para(R, "Độc lập - Tự do - Hạnh phúc", bold=True, size=13, align=C, after=0, keep=True)
        short_line(R, 16)
        para(R, _ngay_thang(opts.get("dia_danh") or "Hà Nội"), italic=True, size=13, align=C, after=0, before=4, keep=True)

        para(d, "", after=0)
        if loai and not is_cong_van:
            para(d, loai, bold=True, size=14, align=C, upper=True, after=0, keep=True)
            if trich_yeu:
                para(d, trich_yeu, bold=True, size=14, align=C, after=0, keep=True)
            p = d.add_paragraph()
            p.alignment = C
            r = p.add_run("─" * 12)
            r.font.size = Pt(8)
        if kinh_gui:
            noi = [x.strip() for x in re.split(r"[;\n]", kinh_gui) if x.strip()]
            if len(noi) == 1:
                para(d, "Kính gửi: " + noi[0].rstrip("."), align=C, before=6)
            else:
                para(d, "Kính gửi:", align=C, before=6, after=0)
                for k, n in enumerate(noi):
                    p = para(d, "- " + n.rstrip(";.") + ("." if k == len(noi) - 1 else ";"), after=6 if k == len(noi) - 1 else 0)
                    p.paragraph_format.left_indent = Cm(4.5)
    elif opts.get("tieu_de"):
        para(d, opts["tieu_de"], bold=True, size=16, align=C, after=12)

    # ---- Noi dung ----
    J = WD_ALIGN_PARAGRAPH.JUSTIFY
    for b in parse_blocks(body):
        kind = b[0]
        if kind == "h":
            para(d, _plain_inline(b[2]), bold=True, align=J if b[1] > 1 or the_thuc else C, before=6,
                 upper=(b[1] == 1 and the_thuc))
        elif kind == "p":
            txt = b[1]
            heading_like = re.match(r"^(PHẦN|CHƯƠNG|[IVXLC]+\.)\s", txt) is not None
            p = para(d, txt, bold=heading_like, align=J, indent=not heading_like)
        elif kind == "li":
            p = para(d, "- " + b[1], align=J, indent=True)
        elif kind == "table":
            rows = b[1]
            ncol = max(len(r) for r in rows)
            t = d.add_table(rows=len(rows), cols=ncol)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for ri, row in enumerate(rows):
                for ci in range(ncol):
                    cell = t.cell(ri, ci)
                    cell.text = ""
                    cp = cell.paragraphs[0]
                    cp.paragraph_format.space_after = Pt(2)
                    cp.paragraph_format.first_line_indent = Cm(0)
                    val = row[ci] if ci < len(row) else ""
                    for tx, bo, it in _runs(val.replace("<br>", "\n")):
                        rr = cp.add_run(tx)
                        rr.bold = bo or ri == 0
                        rr.italic = it
                        rr.font.size = Pt(12)
                    if ri == 0:
                        cp.alignment = C
            para(d, "", after=0)

    # ---- Noi nhan & chu ky ----
    if the_thuc:
        para(d, "", after=0)
        tbl = d.add_table(rows=1, cols=2)
        no_borders(tbl)
        set_widths(tbl, [Cm(8.0), Cm(8.5)])
        L, R = tbl.rows[0].cells
        p0 = L.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r = p0.add_run("Nơi nhận:")
        r.bold, r.italic = True, True
        r.font.size = Pt(12)
        items = [x.strip() for x in (noi_nhan or "- Như trên;\n- Lưu: VT.").split("\n") if x.strip()]
        for it in items:
            if not it.startswith("-"):
                it = "- " + it
            para(L, it, size=11, after=0, keep=True)
        R.paragraphs[0].alignment = C
        R.paragraphs[0].paragraph_format.space_after = Pt(0)
        for k, line in enumerate((chuc_vu or opts.get("chuc_vu_ky") or "").split("/")):
            line = line.strip()
            if not line:
                continue
            if k == 0:
                rr = R.paragraphs[0].add_run(line.upper())
                rr.bold = True
                rr.font.size = Pt(13)
            else:
                para(R, line, bold=True, size=13, align=C, upper=True, after=0, keep=True)
        for _ in range(4):
            para(R, "", after=0)
        if opts.get("nguoi_ky"):
            para(R, opts["nguoi_ky"], bold=True, size=13, align=C, after=0)

    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# =====================================================================
# XUAT EXCEL
# =====================================================================
def _to_number(s: str):
    t = s.strip().replace(" ", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t) if "." in t else int(t)
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):  # 1,234,567.8
        t2 = t.replace(",", "")
        return float(t2) if "." in t2 else int(t2)
    if re.fullmatch(r"-?\d+(\.\d+)?%", t):
        return float(t[:-1]) / 100
    return None


def export_xlsx(content: str, title: str = "VNA") -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    blocks = parse_blocks(content)
    tables = [b[1] for b in blocks if b[0] == "table"]
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="DCE6F1")
    font = "Times New Roman"

    def write_table(ws, rows, start_row):
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                v = _plain_inline(val)
                num = _to_number(v) if ri > 0 else None
                c = ws.cell(row=start_row + ri, column=ci + 1, value=num if num is not None else v)
                c.border = border
                c.font = Font(name=font, bold=(ri == 0), size=12)
                c.alignment = Alignment(wrap_text=True, vertical="top", horizontal="center" if ri == 0 else None)
                if ri == 0:
                    c.fill = head_fill
                if isinstance(num, float) and v.strip().endswith("%"):
                    c.number_format = "0.0%"
                elif isinstance(num, (int, float)):
                    c.number_format = "#,##0.##" if isinstance(num, float) else "#,##0"
        return start_row + len(rows)

    if tables:
        for idx, rows in enumerate(tables, 1):
            ws = wb.create_sheet(f"Bang {idx}")
            write_table(ws, rows, 1)
            ws.freeze_panes = "A2"
            for ci in range(1, max(len(r) for r in rows) + 1):
                width = max(len(_plain_inline(r[ci - 1])) if ci - 1 < len(r) else 0 for r in rows)
                ws.column_dimensions[get_column_letter(ci)].width = min(max(10, width + 2), 60)
    ws = wb.create_sheet("Noi dung", 0 if not tables else None)
    ws.column_dimensions["A"].width = 120
    r = 1
    for line in strip_markdown(content).split("\n"):
        c = ws.cell(row=r, column=1, value=line)
        c.font = Font(name=font, size=12)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

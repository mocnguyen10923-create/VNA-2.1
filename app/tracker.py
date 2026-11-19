"""Thu muc '3. Theo doi cong viec': VNA tu dong cap nhat
  - Bang theo doi cong viec.xlsx  (co cot danh dau hoan thanh)
  - So van ban den.xlsx
  - Nhat ky cong viec.docx
Ghi lai sau moi thay doi (gom nhieu thay doi trong vai giay thanh mot lan ghi).
Neu file dang mo trong Excel/Word (bi khoa), VNA thu lai sau."""
import datetime as dt
import io
import logging
import threading

from . import config as cfgmod
from . import docio, inbox, planner

BANG_CV = "Bang_theo_doi_nhiem_vu.xlsx"
SO_VB = "So_van_ban_den.xlsx"
SO_DI = "So_van_ban_di.xlsx"
NHAT_KY = "Nhat_ky_cong_viec.docx"
_timer = None
_lock = threading.Lock()


def schedule(delay: float = 4):
    global _timer
    with _lock:
        if _timer:
            _timer.cancel()
        _timer = threading.Timer(delay, _run)
        _timer.daemon = True
        _timer.start()


def _run():
    pending = write_all()
    if pending:
        schedule(60)  # co file dang mo -> thu lai sau 1 phut


def _write(path, blob) -> bool:
    try:
        path.write_bytes(blob)
        return True
    except PermissionError:
        logging.info("File dang mo, se cap nhat sau: %s", path)
        return False


def tasks_xlsx() -> bytes:
    import openpyxl
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    d = planner.load()
    now = dt.datetime.now()
    wb = openpyxl.Workbook()
    thin = Side(style="thin", color="A6A6A6")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    F = "Times New Roman"
    pri_order = planner.PRIORITY

    def sheet(ws, title, rows):
        ws.merge_cells("A1:J1")
        ws["A1"] = title
        ws["A1"].font = Font(name=F, bold=True, size=14, color="B3161B")
        ws["A2"] = f"Cập nhật lúc {now:%H:%M ngày %d/%m/%Y} – VNA tự động cập nhật, đánh dấu hoàn thành trong phần mềm VNA."
        ws["A2"].font = Font(name=F, italic=True, size=10, color="666666")
        head = ["STT", "Hoàn thành", "Công việc", "Người thực hiện", "Ưu tiên", "Hạn", "Tình trạng", "Ngày xong", "Nguồn", "Ghi chú"]
        widths = [6, 11, 55, 20, 12, 17, 14, 17, 26, 34]
        for i, (h, w) in enumerate(zip(head, widths), 1):
            c = ws.cell(row=4, column=i, value=h)
            c.font = Font(name=F, bold=True, size=12)
            c.fill = PatternFill("solid", fgColor="DCE6F1")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = border
            ws.column_dimensions[c.column_letter].width = w
        for r, t in enumerate(rows, 5):
            due = planner._parse(t.get("due"))
            done = t["status"] == "xong"
            tinh_trang = "Đã xong" if done else ("Quá hạn" if due and due < now else (t["status"] if t["status"] in ("đang làm", "chờ kết quả") else "Chưa làm"))
            vals = [r - 4, "☑" if done else "☐", t["title"], t.get("nguoi", "") or ("(tôi)" if t.get("loai", "toi") == "toi" else ""),
                    t.get("priority", ""), due.strftime("%d/%m/%Y %H:%M") if due else "", tinh_trang,
                    (t.get("done_at") or "")[:16].replace("T", " "), t.get("nguon", ""), t.get("note", "")]
            for i, v in enumerate(vals, 1):
                c = ws.cell(row=r, column=i, value=v)
                c.font = Font(name=F, size=12, strike=done and i == 3, color="808080" if done else None)
                c.border = border
                c.alignment = Alignment(wrap_text=True, vertical="top", horizontal="center" if i in (1, 2, 5, 7) else None)
            if tinh_trang == "Quá hạn":
                ws.cell(row=r, column=7).font = Font(name=F, size=12, bold=True, color="C00000")
        ws.freeze_panes = "A5"
        if rows:
            ws.auto_filter.ref = f"A4:J{4 + len(rows)}"

    tasks = [t for t in d["tasks"] if t["status"] != "đề xuất"]
    key = lambda t: (t.get("due") or "9999", pri_order.get(t.get("priority"), 1))
    open_t = sorted([t for t in tasks if t["status"] != "xong"],
                    key=lambda t: (not (planner._parse(t.get("due")) and planner._parse(t.get("due")) < now),
                                   pri_order.get(t.get("priority"), 1), t.get("due") or "9999"))
    done_t = sorted([t for t in tasks if t["status"] == "xong"], key=lambda t: t.get("done_at", ""), reverse=True)
    ws = wb.active
    ws.title = "Việc tôi phải làm"
    sheet(ws, "VIỆC TÔI PHẢI LÀM (ưu tiên nhất ở trên)", [t for t in open_t if t.get("loai", "toi") == "toi"])
    sheet(wb.create_sheet("Việc đã giao - đôn đốc"), "VIỆC ĐÃ GIAO – CẦN CHỈ ĐẠO, ĐÔN ĐỐC", [t for t in open_t if t.get("loai") == "giao"])
    sheet(wb.create_sheet("Đã hoàn thành"), "CÔNG VIỆC ĐÃ HOÀN THÀNH", done_t)
    sheet(wb.create_sheet("Tất cả"), "TẤT CẢ CÔNG VIỆC", sorted(tasks, key=key))
    # Thong ke
    st = wb.create_sheet("Thống kê")
    total = len(tasks)
    n_done = len(done_t)
    n_over = sum(1 for t in open_t if planner._parse(t.get("due")) and planner._parse(t.get("due")) < now)
    rows = [("Tổng số công việc", total), ("Đã hoàn thành", n_done), ("Đang làm", len(open_t) - n_over),
            ("Quá hạn", n_over), ("Tỷ lệ hoàn thành", (n_done / total) if total else 0)]
    st["A1"] = "THỐNG KÊ CÔNG VIỆC"
    st["A1"].font = Font(name=F, bold=True, size=14, color="B3161B")
    for i, (k, v) in enumerate(rows, 3):
        st.cell(row=i, column=1, value=k).font = Font(name=F, size=12)
        c = st.cell(row=i, column=2, value=v)
        c.font = Font(name=F, size=12, bold=True)
        if k.startswith("Tỷ lệ"):
            c.number_format = "0%"
    st.column_dimensions["A"].width = 28
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def journal_docx() -> bytes:
    d = planner.load()
    lines = ["# NHẬT KÝ CÔNG VIỆC", f"*Cập nhật: {dt.datetime.now():%H:%M ngày %d/%m/%Y}*", ""]
    thu = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]
    for day in sorted(d["journal"], reverse=True):
        dd = dt.date.fromisoformat(day)
        lines.append(f"## {thu[dd.weekday()]}, ngày {dd:%d/%m/%Y}")
        for e in d["journal"][day]:
            lines.append(f"- **{e['time']}** – {e['text']}")
        done = [t for t in d["tasks"] if (t.get("done_at") or "")[:10] == day]
        if done:
            lines.append("")
            lines.append("**Việc đã hoàn thành trong ngày:**")
            lines += [f"- ☑ {t['title']}" for t in done]
        lines.append("")
    return docio.export_docx("\n".join(lines), {"the_thuc": False})


def write_all() -> bool:
    """Ghi 3 file theo doi. Tra ve True neu con file chua ghi duoc (dang mo)."""
    pending = False
    try:
        folder = cfgmod.tracking_dir()
        pending |= not _write(folder / BANG_CV, tasks_xlsx())
        if inbox.load_register():
            pending |= not _write(folder / SO_VB, inbox.register_xlsx())
        from . import outbox
        if outbox.load_register():
            pending |= not _write(folder / SO_DI, outbox_xlsx(outbox.load_register()))
        if planner.load()["journal"]:
            pending |= not _write(folder / NHAT_KY, journal_docx())
    except Exception as e:
        logging.exception("Loi cap nhat thu muc theo doi: %s", e)
    return pending


def outbox_xlsx(reg) -> bytes:
    md = ["| Số TT | Ngày ghi | Số, ký hiệu | Ngày ban hành | Loại | Trích yếu | Nơi nhận | Trả lời VB đến số | Việc đã giao | Học tập | File |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reg:
        cells = [r.get("stt"), r.get("ngay_ghi"), r.get("so_ky_hieu"), r.get("ngay_ban_hanh"), r.get("loai"), r.get("trich_yeu"),
                 r.get("noi_nhan"), ", ".join(map(str, r.get("tra_loi", []))), r.get("nhiem_vu_giao", ""), r.get("hoc_tap", ""), r.get("file")]
        md.append("| " + " | ".join(str(c or "").replace("|", "/").replace("\n", " ") for c in cells) + " |")
    return docio.export_xlsx("# SỔ VĂN BẢN ĐI / SẢN PHẨM ĐÃ BAN HÀNH\n\n" + "\n".join(md))

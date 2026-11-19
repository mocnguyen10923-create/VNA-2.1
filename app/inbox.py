"""VAN BAN DEN TU DONG.

Nguoi dung chi can chep van ban vao thu muc "Van ban den". VNA tu dong:
  1. Doc noi dung; kiem tra trung lap voi kho (giong het / trung noi dung).
  2. AI trich thong tin: co quan ban hanh, so ky hieu, ngay, trich yeu, do khan, tom tat, nhiem vu + han.
  3. Tao cong viec co nhac han cho tung nhiem vu.
  4. Lap "Phieu xu ly van ban den" (Word).
  5. Neu can trien khai trong nha truong -> tao bo tai lieu trien khai (4 file Word).
  6. Luu van ban vao kho (thu vien) theo loai/nam -> dung cho tra cuu ve sau.
  7. Ghi So van ban den, nhat ky, thong bao cho nguoi dung.
Khong xoa file nao. Neu AI chua san sang (VD Ollama chua chay) thi giu nguyen van ban va thu lai sau.
"""
import datetime as dt
import hashlib
import json
import logging
import re
import shutil
import threading
import time
from pathlib import Path

from . import config as cfgmod
from . import docio, folders, hoso, llm, planner, prompts, tracker

ANALYZE_PROMPT = """Phân tích văn bản đến dưới đây. Trả về DUY NHẤT một đối tượng JSON hợp lệ (không thêm chữ nào khác) theo mẫu:
{
 "co_quan_ban_hanh": "tên cơ quan ban hành, đúng như trong văn bản",
 "so_ky_hieu": "số, ký hiệu, VD 1234/SGDĐT-GDTrH; để trống nếu không có",
 "ngay_ban_hanh": "dd/mm/yyyy hoặc để trống",
 "loai": "Công văn | Quyết định | Kế hoạch | Thông báo | Báo cáo | Tờ trình | Giấy mời | Hướng dẫn | Luật | Nghị định | Thông tư | Khác",
 "trich_yeu": "trích yếu nội dung",
 "do_khan": "Thường | Khẩn | Thượng khẩn | Hỏa tốc",
 "tom_tat": "tóm tắt 3-6 câu: văn bản yêu cầu gì, đối với ai",
 "nhiem_vu": [
   {"noi_dung": "việc đơn vị nhận văn bản phải làm (cụ thể, bắt đầu bằng động từ)",
    "han": "dd/mm/yyyy nếu văn bản nêu thời hạn, hoặc để trống",
    "uu_tien": "cao | trung bình | thấp",
    "bo_phan": "bộ phận đề xuất chủ trì"}
 ],
 "han_tra_loi": "dd/mm/yyyy nếu văn bản yêu cầu báo cáo/trả lời trước một ngày, hoặc để trống",
 "can_trien_khai": true,
 "y_kien_de_xuat": "đề xuất hướng xử lý ngắn gọn cho lãnh đạo (giao ai, làm gì)"
}
Quy tắc: chỉ ghi thông tin có trong văn bản, không bịa. Nhiệm vụ có hạn gấp hoặc văn bản khẩn thì ưu tiên "cao".
"can_trien_khai" = true khi văn bản yêu cầu đơn vị tổ chức thực hiện/triển khai; false khi chỉ để biết, giấy mời, văn bản QPPL tham khảo."""


_SO = re.compile(r"Số\s*[:.]?\s*([0-9]{1,6}\s*/\s*[A-ZĐa-zđ0-9\-–&/]{2,40})")
_NGAY = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I)
_VV = re.compile(r"^\s*V/v[:.]?\s*(.+)$", re.I | re.M)
_KHAN = re.compile(r"\b(HỎA TỐC|THƯỢNG KHẨN|KHẨN)\b")


def quick_extract(text: str) -> dict:
    """Trich thong tin hanh chinh bang quy tac (khong can AI): so ky hieu, ngay ban hanh, trich yeu V/v, do khan, co quan."""
    head = (text or "")[:2500]
    out = {}
    m = _SO.search(head)
    if m:
        out["so_ky_hieu"] = re.sub(r"\s+", "", m.group(1)).strip("-–/")
    m = _NGAY.search(head)
    if m:
        out["ngay_ban_hanh"] = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    m = _VV.search(head)
    if m:
        out["trich_yeu"] = m.group(1).strip()[:200]
    m = _KHAN.search(head)
    out["do_khan"] = {"HỎA TỐC": "Hỏa tốc", "THƯỢNG KHẨN": "Thượng khẩn", "KHẨN": "Khẩn"}[m.group(1)] if m else ""
    for line in head.splitlines()[:6]:
        l = line.strip()
        if len(l) > 6 and l.isupper() and "CỘNG HÒA" not in l and "ĐỘC LẬP" not in l:
            out["co_quan_ban_hanh"] = l.title() if len(l) > 60 else l
            break
    return out


def short_tip(rec: dict, tasks: list = None) -> str:
    """Tom tat that ngan de hien khi tro chuot: viec can lam + thoi han."""
    items = rec.get("viec_can_lam") or [{"noi_dung": t["title"].split(" (theo VB")[0], "han": (t.get("due") or "")[:10]}
                                        for t in (tasks or [])]
    lines = []
    for v in items[:4]:
        han = v.get("han") or ""
        if len(han) == 10 and han[4] == "-":
            han = f"{han[8:10]}/{han[5:7]}"
        lines.append(f"• {v['noi_dung'][:90]}" + (f" — hạn {han}" if han else ""))
    if not lines and rec.get("tom_tat"):
        lines.append(rec["tom_tat"][:200])
    head = f"⏰ Hạn trả lời: {rec.get('han_tra_loi', '')}" + (" (ước tính)" if rec.get("han_uoc_tinh") else "")
    if rec.get("da_tra_loi"):
        head = f"✔ Đã trả lời: {rec['da_tra_loi']}"
    return head + ("\n" + "\n".join(lines) if lines else "")


def inbox_dir(cfg) -> Path:
    """Thu muc '1. Van ban chi dao cap tren': nguoi dung tha van ban vao day."""
    p = Path(cfg.get("inbox_dir") or (cfgmod.workspace(cfg) / cfgmod.WS_CHI_DAO))
    p.mkdir(parents=True, exist_ok=True)
    return p


def archive_dir(cfg) -> Path:
    """Van ban da xu ly: 01_VAN_BAN_DEN/Da_xu_ly"""
    p = inbox_dir(cfg) / cfgmod.DA_XU_LY
    p.mkdir(parents=True, exist_ok=True)
    return p


def _register_path() -> Path:
    return cfgmod.data_dir() / "so_van_ban_den.json"


def load_register() -> list:
    try:
        return json.loads(_register_path().read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_register(reg):
    tmp = _register_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_register_path())


def _parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(json)?|```$", "", t, flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            return json.loads(m.group(0))
    raise ValueError("AI không trả về đúng định dạng JSON")


def _date(s: str):
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _norm_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\W+", "", text.lower()).encode()).hexdigest() if text else ""


def _unique(dest: Path) -> Path:
    i = 2
    while dest.exists():
        dest = dest.with_name(f"{dest.stem.rsplit(' (', 1)[0]} ({i}){dest.suffix}")
        i += 1
    return dest


class InboxWatcher(threading.Thread):
    """Theo doi thu muc Van ban den, xu ly tung van ban mot (tuan tu, an toan)."""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.seen_size = {}
        self.fail = {}
        self.new_items = []     # van ban moi xu ly, de hien len giao dien
        self.status = "chờ"
        self.lock = threading.Lock()

    def run(self):
        time.sleep(5)
        while True:
            try:
                self.scan_once()
            except Exception as e:
                logging.exception("Loi van ban den: %s", e)
            from . import power
            time.sleep(20 if power.profile(self.app.cfg) == "hieu_nang" else 45)  # dung pin: quet thua hon

    def scan_once(self):
        cfg = self.app.cfg
        if not cfg.get("inbox_auto", True):
            return
        box = inbox_dir(cfg)
        for p in sorted(box.iterdir(), key=lambda x: x.stat().st_mtime):
            if not p.is_file() or p.name.startswith(("~$", ".")) or p.name.lower() in ("desktop.ini", "thumbs.db"):
                continue
            size = p.stat().st_size
            # chi xu ly khi file da chep xong (kich thuoc khong doi giua 2 lan quet)
            if self.seen_size.get(p.name) != size:
                self.seen_size[p.name] = size
                continue
            if self.fail.get(p.name, (0, 0))[1] > time.time():
                continue
            with self.lock:
                self.process(p)

    # ------------------------------------------------------------------
    def process(self, p: Path):
        cfg = self.app.cfg
        self.status = f"đang xử lý: {p.name}"
        logging.info("Tiep nhan van ban den: %s", p)
        ext = p.suffix.lower()
        reg = load_register()
        sha = folders._sha256(p)
        rec = {"stt": len(reg) + 1, "file": p.name, "ngay_den": dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "sha": sha}

        text = ""
        if ext in docio.SUPPORTED:
            try:
                text = docio.extract_file(p)
            except Exception as e:
                rec["ghi_chu"] = f"Không đọc được nội dung: {e}"
        else:
            rec["ghi_chu"] = "Định dạng không đọc được nội dung (chỉ lưu kho)."
        nh = _norm_hash(text)
        rec["norm"] = nh

        # ---- Trung lap ----
        dup = next((r for r in reg if r.get("sha") == sha or (nh and r.get("norm") == nh)), None)
        if dup:
            dest = _unique(archive_dir(cfg) / folders.DUP_DIR / p.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
            rec.update({"trich_yeu": dup.get("trich_yeu", ""), "trang_thai": f"Trùng với văn bản số TT {dup['stt']} – đã chuyển vào _TRUNG_LAP",
                        "luu_tai": str(dest)})
            reg.append(rec)
            _save_register(reg)
            planner.add_journal(f"Văn bản đến '{p.name}' trùng với văn bản đã nhận (STT {dup['stt']}), không tạo việc mới.")
            self._notify(rec, "Văn bản trùng")
            tracker.schedule()
            return

        # ---- AI phan tich ----
        info = {}
        if text.strip():
            try:
                budget = min(self.app.budget(), 9000)
                body = text if len(text) <= budget else (text[: int(budget * 0.7)] + "\n...\n" + text[-int(budget * 0.25):])
                # Trich xuat co cau truc: dung mo hinh nho (nhanh, it ton pin); thong tin hanh chinh lay bang quy tac
                raw = llm.chat(cfg, "Bạn là chuyên viên văn thư, trích thông tin chính xác, không bịa.",
                               [{"role": "user", "content": ANALYZE_PROMPT + "\n\n=== VĂN BẢN ===\n" + body}],
                               json_mode=True, tier="fast", max_tokens=1200)
                info = _parse_json(raw)
            except llm.LLMError as e:
                n = self.fail.get(p.name, (0, 0))[0] + 1
                self.fail[p.name] = (n, time.time() + min(1800, 60 * n))
                self.status = f"chờ AI sẵn sàng ({e})"
                logging.warning("Van ban den %s: AI chua san sang, thu lai sau: %s", p.name, e)
                return
            except Exception as e:
                rec["ghi_chu"] = f"AI phân tích chưa đầy đủ: {e}"

        rx = quick_extract(text)  # quy tac: chinh xac cho so hieu, ngay, trich yeu, do khan
        for k, v in rx.items():
            if v and (k in ("so_ky_hieu", "ngay_ban_hanh", "do_khan") or not info.get(k)):
                info[k] = v
        rec.update({k: info.get(k, "") for k in ("co_quan_ban_hanh", "so_ky_hieu", "ngay_ban_hanh", "loai", "trich_yeu",
                                                  "do_khan", "tom_tat", "y_kien_de_xuat")})
        rec["trich_yeu"] = rec["trich_yeu"] or p.stem
        rec["ten_goc"] = p.name
        rec["de_xuat_trien_khai"] = bool(info.get("can_trien_khai"))
        nguon = f"VB đến số {rec['stt']}" + (f" ({rec['so_ky_hieu']})" if rec.get("so_ky_hieu") else "")

        # ---- Tao cong viec ----
        tasks = []
        khan = (info.get("do_khan") or "").lower() not in ("", "thường")
        for nv in (info.get("nhiem_vu") or [])[:15]:
            if not isinstance(nv, dict) or not nv.get("noi_dung"):
                continue
            d = _date(nv.get("han", ""))
            title = nv["noi_dung"].strip()
            if rec.get("so_ky_hieu"):
                title += f" (theo VB {rec['so_ky_hieu']})"
            pri = "cao" if khan else (nv.get("uu_tien") or "trung bình")
            if pri not in planner.PRIORITY:
                pri = "trung bình"
            uoc = not d
            if not d:  # khong ghi han: uoc tinh 3 ngay lam viec (danh dau "uoc tinh")
                d = hoso.working_days_after(dt.date.today(), 2 if khan else 3)
            t = planner.add_task({"title": title, "note": f"Chủ trì đề xuất: {nv.get('bo_phan', '')}".strip(": ") + (" · hạn do VNA ước tính" if uoc else ""),
                                  "due": d.isoformat() + "T08:00", "priority": pri, "remind_before": 1440,
                                  "loai": "toi", "nguon": nguon, "nguon_den": rec["stt"], "han_uoc_tinh": uoc, "de_xuat": True})
            tasks.append(t)
        if not tasks:  # luon co viec "xem va cho y kien" de khong bo sot
            planner.add_task({"title": f"Xem, cho ý kiến xử lý văn bản: {rec['trich_yeu'][:120]}",
                              "due": hoso.working_days_after(dt.date.today(), 1).isoformat() + "T08:00",
                              "priority": "cao" if khan else "trung bình", "remind_before": 60,
                              "nguon": nguon, "nguon_den": rec["stt"]})
        rec["so_viec"] = max(1, len(tasks))
        rec["viec_can_lam"] = [{"noi_dung": t["title"].split(" (theo VB")[0], "han": (t.get("due") or "")[:10]} for t in tasks][:6]
        # Han tra loi: van ban ghi -> dung; khong ghi -> han som nhat cua nhiem vu, hoac 3 ngay lam viec (uoc tinh)
        htl = _date(info.get("han_tra_loi", ""))
        if not htl and tasks:
            htl = min(planner._parse(t["due"]).date() for t in tasks)
        rec["han_tra_loi"] = (htl or hoso.working_days_after(dt.date.today(), 3)).strftime("%d/%m/%Y")
        rec["han_uoc_tinh"] = not _date(info.get("han_tra_loi", ""))

        # ---- Luu kho theo loai / nam ----
        nb = _date(rec.get("ngay_ban_hanh", ""))
        today = dt.date.today()
        new_name = hoso.std_name(nb or today, rec.get("so_ky_hieu", ""), rec["trich_yeu"], ext) if cfg.get("dat_ten_chuan", True) else p.name
        dest = _unique(archive_dir(cfg) / str(today.year) / f"Thang_{today.month:02d}" / new_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))
        rec["luu_tai"] = str(dest)

        # ---- Phieu xu ly van ban den ----
        out = cfgmod.output_dir("Phieu_xu_ly")
        rec["phieu"] = str(self._phieu(rec, info, out))

        # ---- Bo tai lieu trien khai: chi tao tu dong khi nguoi dung bat (mac dinh: de xuat, ban bam moi tao) ----
        if info.get("can_trien_khai") and cfg.get("inbox_trien_khai", False) and text.strip():
            try:
                res = self.app.trien_khai([{"name": dest.name, "text": text}],
                                          f"Văn bản {rec.get('so_ky_hieu', '')} – {rec['trich_yeu']}")
                rec["trien_khai"] = res["folder"]
            except Exception as e:
                rec["ghi_chu"] = (rec.get("ghi_chu", "") + f" Chưa tạo được bộ triển khai: {e}").strip()

        rec["trang_thai"] = "Đã xử lý"
        reg.append(rec)
        _save_register(reg)
        threading.Thread(target=self.app.library.refresh, daemon=True).start()
        planner.add_journal(f"Tiếp nhận văn bản {rec.get('so_ky_hieu') or ''} \"{rec['trich_yeu']}\" "
                            f"({rec.get('co_quan_ban_hanh', '')}); đề xuất {rec['so_viec']} việc chờ duyệt"
                            + ("; đã soạn bộ tài liệu triển khai." if rec.get("trien_khai") else "."))
        self.fail.pop(p.name, None)
        self._notify(rec, "Văn bản mới")
        self.status = "chờ"
        tracker.schedule()

    def _notify(self, rec, kind):
        item = {k: rec.get(k, "") for k in ("stt", "file", "trich_yeu", "so_ky_hieu", "do_khan", "trang_thai", "so_viec")}
        item["tip"] = short_tip(rec)
        self.new_items.append(item)
        planner.notify_windows(f"VNA – {kind}", f"{rec.get('so_ky_hieu', '')} {rec.get('trich_yeu', rec['file'])}"[:200])

    def _phieu(self, rec, info, out: Path) -> Path:
        lines = [
            "# PHIẾU XỬ LÝ VĂN BẢN ĐẾN", "",
            "| Mục | Nội dung |", "|---|---|",
            f"| Số đến (STT) | {rec['stt']} |", f"| Ngày đến | {rec['ngay_den']} |",
            f"| Cơ quan ban hành | {rec.get('co_quan_ban_hanh', '')} |", f"| Số, ký hiệu | {rec.get('so_ky_hieu', '')} |",
            f"| Ngày ban hành | {rec.get('ngay_ban_hanh', '')} |", f"| Loại văn bản | {rec.get('loai', '')} |",
            f"| Trích yếu | {rec.get('trich_yeu', '')} |", f"| Độ khẩn | {rec.get('do_khan', '') or 'Thường'} |",
            f"| Hạn trả lời | {rec.get('han_tra_loi', '')}{' (VNA ước tính)' if rec.get('han_uoc_tinh') else ''} |",
            f"| Lưu tại | {rec.get('luu_tai', '')} |", "",
            "## Tóm tắt nội dung", rec.get("tom_tat", "") or "(không có)", "",
            "## Nhiệm vụ phải thực hiện",
        ]
        nvs = [n for n in (info.get("nhiem_vu") or []) if isinstance(n, dict)]
        if nvs:
            lines += ["| STT | Nhiệm vụ | Thời hạn | Đề xuất chủ trì |", "|---|---|---|---|"]
            lines += [f"| {i} | {n.get('noi_dung', '')} | {n.get('han', '')} | {n.get('bo_phan', '')} |" for i, n in enumerate(nvs, 1)]
        else:
            lines.append("Không xác định được nhiệm vụ cụ thể – đề nghị lãnh đạo xem xét.")
        lines += ["", "## Đề xuất hướng xử lý (VNA tham mưu)", rec.get("y_kien_de_xuat", "") or "(không có)", "",
                  "## Ý kiến chỉ đạo của lãnh đạo", "", "........................................................................", "",
                  "........................................................................"]
        blob = docio.export_docx("\n".join(lines), {"the_thuc": False})
        path = _unique(out / hoso.std_name(dt.date.today(), f"PXL-{rec['stt']:04d}", rec.get("trich_yeu", "Van ban"), ".docx"))
        path.write_bytes(blob)
        return path


def register_xlsx() -> bytes:
    reg = load_register()
    md = ["| Số đến | Ngày đến | Cơ quan ban hành | Số, ký hiệu | Ngày VB | Loại | Trích yếu | Độ khẩn | Hạn trả lời | Đã trả lời bằng | Số việc | Trạng thái | Tên gốc | Lưu tại |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reg:
        cells = [r.get(k, "") for k in ("stt", "ngay_den", "co_quan_ban_hanh", "so_ky_hieu", "ngay_ban_hanh", "loai",
                                        "trich_yeu", "do_khan", "han_tra_loi", "da_tra_loi", "so_viec", "trang_thai", "ten_goc", "luu_tai")]
        md.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |")
    return docio.export_xlsx("# SỔ ĐĂNG KÝ VĂN BẢN ĐẾN\n\n" + "\n".join(md))


def sap_het_han(days=3) -> list:
    """Cong van chua co van ban tra loi, han tra loi trong `days` ngay toi hoac da qua."""
    out = []
    lim = dt.date.today() + dt.timedelta(days=days)
    for r in load_register():
        d = _date(r.get("han_tra_loi", ""))
        if d and not r.get("da_tra_loi") and "Trùng" not in (r.get("trang_thai") or "") and d <= lim:
            out.append({"stt": r["stt"], "so_ky_hieu": r.get("so_ky_hieu", ""), "trich_yeu": r.get("trich_yeu", ""),
                        "han_tra_loi": r["han_tra_loi"], "qua_han": d < dt.date.today(), "uoc_tinh": r.get("han_uoc_tinh", False)})
    return sorted(out, key=lambda x: _date(x["han_tra_loi"]))

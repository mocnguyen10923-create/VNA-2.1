"""SANG KIEN CAI TIEN CACH LAM VIEC (Dac ta muc 12).
Moi thang (hoac khi nguoi dung bam): tinh so lieu lam viec that -> AI de xuat sang kien
co thuc trang, nguyen nhan, giai phap, loi ich do duoc, ke hoach, huong dan tung buoc, tieu chi danh gia.
Nguoi dung: Trien khai (cac buoc thanh nhiem vu) hoac Bo qua (VNA ghi nho, khong de xuat lai)."""
import collections
import datetime as dt
import json
import logging
import threading
import time
import uuid

from . import config as cfgmod
from . import docio, hoso, inbox, learning, llm, outbox, planner, prompts

PROMPT = """Bạn là chuyên gia quản trị trường học và cải tiến quy trình. Dưới đây là SỐ LIỆU LÀM VIỆC THẬT của tôi
(lãnh đạo trường THCS & THPT) trong {days} ngày qua. Hãy phát hiện cách làm lỗi thời, kém hiệu quả, lặp lại, chậm trễ,
và đề xuất TỐI ĐA 3 SÁNG KIẾN có tác động lớn nhất. Chỉ đề xuất khi có số liệu làm căn cứ; không đề xuất chung chung.
Tránh các sáng kiến tôi đã bỏ qua: {bo_qua}

SỐ LIỆU:
{data}

Trả về DUY NHẤT JSON:
{{"sang_kien": [{{
  "ten": "tên ngắn",
  "thuc_trang": "vấn đề + số liệu dẫn chứng",
  "nguyen_nhan": "",
  "giai_phap": "quy trình/dự án mới, cụ thể",
  "loi_ich": "lợi ích đo được (VD: giảm 50% việc quá hạn)",
  "cac_buoc": [{{"viec": "bước triển khai", "nguoi": "người/bộ phận", "so_ngay": 7}}],
  "huong_dan": ["hướng dẫn tôi thực hiện từng bước, cụ thể, kể cả cách làm trên VNA/Word/Excel nếu có"],
  "danh_gia_sau_1_thang": "tiêu chí và số liệu để so sánh trước/sau"}}]}}"""


def _path():
    return cfgmod.system_dir() / "sang_kien.json"


def load():
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("items", [])
    d.setdefault("lan_cuoi", "")
    return d


def save(d):
    _path().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def metrics(days=60) -> dict:
    now = dt.datetime.now()
    since = now - dt.timedelta(days=days)
    tasks = planner.load()["tasks"]
    recent = [t for t in tasks if (t.get("created") or "") >= since.isoformat()]
    def due(t):
        return planner._parse(t.get("due"))
    overdue_now = [t for t in tasks if t["status"] not in ("xong", "đề xuất") and due(t) and due(t) < now]
    late_done = [t for t in recent if t["status"] == "xong" and due(t) and t.get("done_at") and t["done_at"] > t["due"]]
    by_person = collections.Counter(t.get("nguoi") or "(tôi)" for t in overdue_now + late_done)
    words = collections.Counter()
    for t in recent:
        for w in t["title"].lower().split()[:3]:
            if len(w) > 3:
                words[w] += 1
    inreg = [r for r in inbox.load_register() if hoso.parse_date(r.get("ngay_den", "")) and
             hoso.parse_date(r["ngay_den"]) >= since.date()]
    answered = [r for r in inreg if r.get("da_tra_loi")]
    outreg = outbox.load_register()
    types = collections.Counter(r.get("loai") or "Khác" for r in outreg)
    edit = learning.monthly_stats()
    return {
        "so_nhiem_vu_moi": len(recent), "dang_qua_han": len(overdue_now), "xong_tre_han": len(late_done),
        "tre_theo_nguoi": dict(by_person.most_common(6)), "cum_tu_lap_lai_trong_ten_viec": dict(words.most_common(8)),
        "cong_van_den": len(inreg), "cong_van_da_tra_loi": len(answered),
        "cong_van_khan": sum(1 for r in inreg if (r.get("do_khan") or "Thường") != "Thường"),
        "van_ban_di_theo_loai": dict(types), "ty_le_phai_sua_du_thao_theo_thang": edit[-3:],
        "viec_qua_han_tieu_bieu": [t["title"] for t in overdue_now[:8]],
    }


def generate(app, days=60) -> list:
    d = load()
    m = metrics(days)
    bo_qua = [i["ten"] for i in d["items"] if i.get("trang_thai") == "bo_qua"][-20:]
    raw = llm.chat(app.cfg, prompts.build_system("lanh_dao", app.cfg),
                   [{"role": "user", "content": PROMPT.format(days=days, bo_qua=bo_qua or "không có",
                                                              data=json.dumps(m, ensure_ascii=False, indent=1))}], json_mode=True)
    res = learning._json(raw).get("sang_kien", [])
    out = []
    for s in res[:3]:
        if not isinstance(s, dict) or not s.get("ten"):
            continue
        s.update(id=uuid.uuid4().hex[:8], ngay=dt.date.today().isoformat(), trang_thai="moi", so_lieu_truoc=m)
        s["file"] = str(_export(s))
        d["items"].append(s)
        out.append(s)
    d["lan_cuoi"] = dt.date.today().isoformat()
    save(d)
    return out


def _export(s) -> "Path":
    md = [f"# ĐỀ XUẤT SÁNG KIẾN: {s['ten'].upper()}", f"*VNA đề xuất ngày {dt.date.today():%d/%m/%Y}, dựa trên số liệu làm việc thực tế.*", "",
          "## 1. Thực trạng", s.get("thuc_trang", ""), "", "## 2. Nguyên nhân", s.get("nguyen_nhan", ""), "",
          "## 3. Giải pháp", s.get("giai_phap", ""), "", "## 4. Lợi ích dự kiến", s.get("loi_ich", ""), "",
          "## 5. Kế hoạch triển khai", "| STT | Việc | Người/bộ phận | Số ngày |", "|---|---|---|---|"]
    md += [f"| {i} | {b.get('viec', '')} | {b.get('nguoi', '')} | {b.get('so_ngay', '')} |" for i, b in enumerate(s.get("cac_buoc", []), 1)]
    md += ["", "## 6. Hướng dẫn thực hiện từng bước"] + [f"{i}. {h}" for i, h in enumerate(s.get("huong_dan", []), 1)]
    md += ["", "## 7. Đánh giá sau 1 tháng", s.get("danh_gia_sau_1_thang", "")]
    p = cfgmod.output_dir("Sang_kien") / hoso.std_name(dt.date.today(), "", "Sang kien " + s["ten"], ".docx")
    p.write_bytes(docio.export_docx("\n".join(md), {"the_thuc": False}))
    return p


def decide(item_id: str, action: str) -> dict:
    d = load()
    for s in d["items"]:
        if s["id"] != item_id:
            continue
        if action == "trien_khai":
            start = dt.date.today()
            for b in s.get("cac_buoc", []):
                start = start + dt.timedelta(days=max(1, int(b.get("so_ngay") or 7)))
                planner.add_task({"title": f"[Sáng kiến] {b.get('viec', '')}", "loai": "giao" if b.get("nguoi") else "toi",
                                  "nguoi": b.get("nguoi", ""), "nguon": f"Sáng kiến: {s['ten']}",
                                  "due": start.isoformat() + "T08:00", "priority": "trung bình", "remind_before": 1440})
            planner.add_task({"title": f"Đánh giá hiệu quả sáng kiến: {s['ten']}", "nguon": "Sáng kiến",
                              "due": (dt.date.today() + dt.timedelta(days=30)).isoformat() + "T08:00", "remind_before": 1440})
            s["trang_thai"] = "trien_khai"
        elif action == "bo_qua":
            s["trang_thai"] = "bo_qua"
        save(d)
        return s
    raise ValueError("Không tìm thấy sáng kiến.")


class InitiativeThread(threading.Thread):
    """Moi thang tu de xuat sang kien mot lan (khi da co du so lieu)."""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app

    def run(self):
        time.sleep(300)
        while True:
            try:
                d = load()
                last = hoso.parse_date(d["lan_cuoi"]) if d["lan_cuoi"] else None
                from . import power
                if (not last or (dt.date.today() - last).days >= 30) and len(planner.load()["tasks"]) >= 10 \
                        and power.can_run_heavy(self.app.cfg, idle_needed=300):  # chi khi cam sac, may ranh
                    generate(self.app)
            except Exception as e:
                logging.warning("Sang kien: %s", e)
            time.sleep(3600)

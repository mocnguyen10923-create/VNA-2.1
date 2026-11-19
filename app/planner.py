"""Cong viec, ke hoach hang ngay, nhat ky va nhac viec. Du lieu luu tren may tai Documents/VNA/cong_viec.json."""
import datetime as dt
import json
import logging
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import config as cfgmod

_LOCK = threading.Lock()
PRIORITY = {"cao": 0, "trung bình": 1, "thấp": 2}
SCRIPTS = Path(__file__).parent / "scripts"


def _path() -> Path:
    return cfgmod.data_dir() / "cong_viec.json"


def load() -> dict:
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("tasks", [])
    d.setdefault("journal", {})
    return d


def save(d: dict):
    tmp = _path().with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_path())


def _now():
    return dt.datetime.now().replace(microsecond=0)


def _parse(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


# ---------------- Cong viec ----------------
def add_task(data: dict) -> dict:
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Chưa nhập tên công việc.")
    due = data.get("due") or ""          # 'YYYY-MM-DDTHH:MM' hoac 'YYYY-MM-DD'
    if due and len(due) == 10:
        due += "T08:00"
    remind_before = int(data.get("remind_before", 15) or 0)
    remind_at = ""
    if due and data.get("remind", True):
        remind_at = (_parse(due) - dt.timedelta(minutes=remind_before)).isoformat()
    t = {
        "id": uuid.uuid4().hex[:10], "title": title, "note": data.get("note", ""), "due": due,
        "remind_at": remind_at, "remind_before": remind_before, "priority": data.get("priority", "trung bình"),
        "repeat": data.get("repeat", "không"), "status": "đề xuất" if data.get("de_xuat") else "chưa", "notified": False,
        "created": _now().isoformat(), "done_at": "",
        # Hai loai nhiem vu (Dac ta muc 4): "toi" = viec toi phai lam; "giao" = viec da giao, can chi dao/don doc
        "loai": data.get("loai") if data.get("loai") in ("toi", "giao") else "toi",
        "nguoi": data.get("nguoi", ""), "nguon": data.get("nguon", ""), "nguon_den": data.get("nguon_den"),
        "han_uoc_tinh": bool(data.get("han_uoc_tinh")),
    }
    with _LOCK:
        d = load()
        d["tasks"].append(t)
        save(d)
    return t


def update_task(tid: str, changes: dict) -> dict:
    with _LOCK:
        d = load()
        for t in d["tasks"]:
            if t["id"] == tid:
                for k in ("title", "note", "due", "priority", "repeat", "status", "loai", "nguoi"):
                    if k in changes:
                        t[k] = changes[k]
                if t["status"] == "xong" and not t.get("done_at"):
                    t["done_at"] = _now().isoformat()
                    if t.get("repeat") in ("hằng ngày", "hằng tuần") and t.get("due"):
                        _spawn_next(d, t)
                if "due" in changes and t["due"]:
                    t["remind_at"] = (_parse(t["due"]) - dt.timedelta(minutes=int(t.get("remind_before", 15)))).isoformat()
                    t["notified"] = False
                save(d)
                return t
    raise ValueError("Không tìm thấy công việc.")


def _spawn_next(d, t):
    step = dt.timedelta(days=1 if t["repeat"] == "hằng ngày" else 7)
    nxt = dict(t, id=uuid.uuid4().hex[:10], status="chưa", done_at="", notified=False)
    due = _parse(t["due"]) + step
    while due < _now():
        due += step
    nxt["due"] = due.isoformat(timespec="minutes")
    nxt["remind_at"] = (due - dt.timedelta(minutes=int(t.get("remind_before", 15)))).isoformat()
    d["tasks"].append(nxt)


def approve(tid: str, ok: bool):
    """Duyet nhiem vu de xuat: ok -> vao danh sach (nhac han); khong -> bo."""
    with _LOCK:
        d = load()
        for t in d["tasks"]:
            if t["id"] == tid and t["status"] == "đề xuất":
                if ok:
                    t["status"] = "chưa"
                else:
                    d["tasks"].remove(t)
                save(d)
                return True
    return False


def approve_all(ok=True):
    with _LOCK:
        d = load()
        if ok:
            for t in d["tasks"]:
                if t["status"] == "đề xuất":
                    t["status"] = "chưa"
        else:
            d["tasks"] = [t for t in d["tasks"] if t["status"] != "đề xuất"]
        save(d)


def complete_by_source(inbox_stts: set, note: str) -> int:
    """Dong cac nhiem vu sinh ra tu cong van den da co van ban tra loi."""
    n = 0
    with _LOCK:
        d = load()
        for t in d["tasks"]:
            if t.get("nguon_den") is not None and int(t["nguon_den"]) in inbox_stts and t["status"] not in ("xong",):
                t["status"] = "xong"
                t["done_at"] = _now().isoformat()
                t["note"] = (t.get("note", "") + f" · {note}").strip(" ·")
                n += 1
        save(d)
    return n


def delete_task(tid: str):
    with _LOCK:
        d = load()
        d["tasks"] = [t for t in d["tasks"] if t["id"] != tid]
        save(d)


def list_tasks() -> dict:
    d = load()
    now = _now()
    today = now.date()
    groups = {"de_xuat": [], "qua_han": [], "hom_nay": [], "sap_toi": [], "chua_hen": [], "da_xong": []}
    for t in d["tasks"]:
        due = _parse(t.get("due"))
        if t["status"] == "đề xuất":
            groups["de_xuat"].append(t)
        elif t["status"] == "xong":
            if t.get("done_at", "")[:10] >= (today - dt.timedelta(days=7)).isoformat():
                groups["da_xong"].append(t)
        elif not due:
            groups["chua_hen"].append(t)
        elif due.date() < today:
            groups["qua_han"].append(t)
        elif due.date() == today:
            groups["hom_nay"].append(t)
        else:
            groups["sap_toi"].append(t)
    for k in groups:
        groups[k].sort(key=lambda t: (t.get("due") or "9999", PRIORITY.get(t.get("priority"), 1)))
    return groups


# ---------------- Nhat ky ----------------
def add_journal(text: str, day: str = None) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Nhật ký trống.")
    day = day or dt.date.today().isoformat()
    with _LOCK:
        d = load()
        d["journal"].setdefault(day, []).append({"time": _now().strftime("%H:%M"), "text": text})
        save(d)
    return {"day": day, "entries": d["journal"][day]}


def get_journal(day: str = None, days: int = 1) -> dict:
    d = load()
    end = dt.date.fromisoformat(day) if day else dt.date.today()
    out = {}
    for i in range(days):
        k = (end - dt.timedelta(days=i)).isoformat()
        if k in d["journal"]:
            out[k] = d["journal"][k]
    return out


def context_for_ai(kind: str) -> str:
    """Du lieu cong viec/nhat ky dua cho AI lap ke hoach hoac tong ket."""
    g = list_tasks()
    today = dt.date.today()
    thu = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"][today.weekday()]
    def fmt(t):
        due = t.get("due", "").replace("T", " ") or "chưa hẹn"
        who = f" — giao: {t['nguoi']}" if t.get("loai") == "giao" and t.get("nguoi") else ""
        return f"- [{t.get('priority')}] {t['title']} (hạn: {due}){who}{' — ' + t['note'] if t.get('note') else ''}"
    parts = [f"Hôm nay: {thu}, ngày {today:%d/%m/%Y}."]
    for key, label in (("qua_han", "VIỆC QUÁ HẠN"), ("hom_nay", "VIỆC HÔM NAY"), ("sap_toi", "VIỆC SẮP TỚI"),
                       ("chua_hen", "VIỆC CHƯA HẸN NGÀY"), ("da_xong", "VIỆC ĐÃ XONG (7 NGÀY QUA)")):
        if g[key]:
            parts.append(label + ":\n" + "\n".join(fmt(t) for t in g[key][:40]))
    j = get_journal(days=7 if kind == "tuan" else (1 if kind == "tong_ket" else 3))
    if j:
        parts.append("NHẬT KÝ:\n" + "\n".join(f"{day} {e['time']}: {e['text']}" for day, es in sorted(j.items()) for e in es))
    return "\n\n".join(parts)


# ---------------- Nhac viec ----------------
def due_reminders() -> list:
    """Cac viec den gio nhac va chua nhac. Danh dau da nhac."""
    now = _now()
    out = []
    with _LOCK:
        d = load()
        for t in d["tasks"]:
            ra = _parse(t.get("remind_at"))
            if t["status"] not in ("xong", "đề xuất") and ra and ra <= now and not t.get("notified"):
                if now - ra < dt.timedelta(hours=12):  # khong nhac cac viec da qua lau (may tat)
                    out.append(t)
                t["notified"] = True
        if out:
            save(d)
    return out


def notify_windows(title: str, body: str):
    if not sys.platform.startswith("win"):
        return
    f = Path(tempfile.gettempdir()) / f"VNA_toast_{uuid.uuid4().hex[:6]}.txt"
    f.write_text(title + "\n" + body, encoding="utf-8")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(SCRIPTS / "toast.ps1"), "-InFile", str(f)], creationflags=0x08000000)
    except Exception as e:
        logging.warning("Khong hien duoc thong bao: %s", e)


class ReminderThread(threading.Thread):
    def __init__(self, get_cfg, speak):
        super().__init__(daemon=True)
        self.get_cfg, self.speak = get_cfg, speak
        self.pending_ui = []  # giao dien lay ve de hien thong bao

    def run(self):
        while True:
            try:
                for t in due_reminders():
                    due = (t.get("due") or "").replace("T", " lúc ")
                    body = f"{t['title']}" + (f" — hạn {due}" if due else "")
                    notify_windows("VNA nhắc việc", body)
                    self.pending_ui.append(t)
                    if self.get_cfg().get("remind_speak", True):
                        self.speak(f"VNA nhắc việc: {t['title']}.")
                    logging.info("Nhac viec: %s", t["title"])
            except Exception as e:
                logging.warning("Loi nhac viec: %s", e)
            time.sleep(30)


# ---------------- Loi chao & bang kiem soat 3 ngay toi ----------------
LOI_CHUC = [
    "Chúc {x} một ngày làm việc nhiều năng lượng và thật hiệu quả!",
    "Chúc {x} luôn mạnh khỏe, bình an và mọi việc hanh thông!",
    "Chúc {x} một ngày thật nhiều niềm vui bên đồng nghiệp và học trò!",
    "Mỗi việc nhỏ hoàn thành là một bước tiến lớn. Chúc {x} làm việc thật suôn sẻ!",
    "Chúc {x} giữ trọn nhiệt huyết và có thêm nhiều thành công mới!",
    "Hãy nhớ nghỉ ngơi và uống đủ nước nhé. Chúc {x} một ngày thật trọn vẹn!",
    "Chúc {x} sáng suốt trong mọi quyết định và vui vẻ suốt cả ngày!",
]


def upcoming(days: int = 3, loai: str = None) -> list:
    """Viec qua han + viec den han trong `days` ngay toi (ke ca viec da xong trong khoang do, de tich kiem soat).
    Sap xep: chua xong truoc; qua han truoc; muc uu tien cao truoc; han som truoc."""
    d = load()
    today = dt.date.today()
    last = today + dt.timedelta(days=days - 1)
    out = []
    for t in d["tasks"]:
        if t["status"] == "đề xuất" or (loai and t.get("loai", "toi") != loai):
            continue
        due = _parse(t.get("due"))
        done = t["status"] == "xong"
        if due:
            if due.date() > last:
                continue
            if due.date() < today and done:
                continue
        elif done:
            continue
        item = dict(t)
        item["overdue"] = bool(due and due.date() < today and not done)
        item["day_label"] = ("Quá hạn" if item["overdue"] else
                             "Hôm nay" if due and due.date() == today else
                             "Ngày mai" if due and due.date() == today + dt.timedelta(days=1) else
                             (due.strftime("%d/%m") if due else "Chưa hẹn"))
        out.append(item)
    out.sort(key=lambda t: (t["status"] == "xong", not t["overdue"], PRIORITY.get(t.get("priority"), 1),
                            t.get("due") or "9999"))
    return out


def greeting(cfg: dict) -> dict:
    import random
    now = _now()
    h = now.hour
    buoi = ("Chào buổi sáng" if 4 <= h < 11 else "Chào buổi trưa" if h < 13 else
            "Chào buổi chiều" if h < 18 else "Chào buổi tối")
    x = (cfg.get("danh_xung") or "").strip()
    ten = (cfg.get("ten_nguoi_dung") or "").strip() or cfgmod.owner_name()  # mac dinh: ten chu may
    if x:
        goi = f"{x} {ten.split()[-1]}".strip() if ten else x   # VD: "thầy An"
    else:
        goi = ten or "bạn"                                      # VD: "Nguyễn Văn An"
    thu = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"][now.weekday()]
    items = upcoming(3, "toi")
    giao = upcoming(3, "giao")
    todo = [t for t in items if t["status"] != "xong"]
    overdue = sum(1 for t in todo if t["overdue"])
    today_n = sum(1 for t in todo if t["day_label"] == "Hôm nay")
    random.seed(now.toordinal())  # moi ngay mot loi chuc
    wish = random.choice(LOI_CHUC).format(x=x or "bạn")
    hello = f"{buoi} {goi}! Hôm nay là {thu}, ngày {now:%d/%m/%Y}."
    if not todo:
        summary = "3 ngày tới chưa có việc nào cần làm. Bấm “＋ Thêm việc” để lập kế hoạch nhé."
    else:
        summary = f"Trong 3 ngày tới {x or 'bạn'} có {len(todo)} việc cần làm"
        extra = []
        if overdue:
            extra.append(f"{overdue} việc đã quá hạn")
        if today_n:
            extra.append(f"{today_n} việc hôm nay")
        summary += (" (" + ", ".join(extra) + ")" if extra else "") + ". Việc ưu tiên nhất được xếp lên đầu."
    speak = f"{hello} {wish} {summary}"
    if todo:
        speak += " Việc quan trọng nhất là: " + todo[0]["title"] + "."
    dondoc = [t for t in giao if t["status"] != "xong"]
    if dondoc:
        speak += f" Có {len(dondoc)} việc đã giao cần chỉ đạo, đôn đốc."
    n_prop = sum(1 for t in load()["tasks"] if t["status"] == "đề xuất")
    if n_prop:
        speak += f" Có {n_prop} nhiệm vụ đề xuất đang chờ duyệt."
    return {"hello": hello, "wish": wish, "summary": summary, "items": items, "giao": giao, "de_xuat": n_prop, "speak": speak}

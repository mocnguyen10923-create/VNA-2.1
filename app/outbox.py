"""VAN BAN DI / SAN PHAM DA BAN HANH (Dac ta muc 4, buoc 5-6).
Theo doi 04_SAN_PHAM/Da_ban_hanh. Moi van ban moi:
  - Ghi So van ban di.
  - Ghep voi du thao VNA da soan (ma an trong file Word, hoac noi dung giong) -> HOC phong cach.
  - Neu tra loi/thuc hien cong van den nao -> danh dau cong van do da tra loi, dong nhiem vu lien quan.
  - Trich cac nhiem vu DA GIAO cho nguoi khac -> de xuat vao danh sach can don doc.
"""
import datetime as dt
import json
import logging
import threading
import time
from pathlib import Path

from . import config as cfgmod
from . import docio, hoso, inbox, learning, llm, planner, prompts, tracker

ANALYZE = """Đây là văn bản ĐÃ BAN HÀNH của nhà trường/cơ quan. Trả về DUY NHẤT JSON:
{"so_ky_hieu": "", "ngay_ban_hanh": "dd/mm/yyyy", "loai": "Công văn|Quyết định|Kế hoạch|Thông báo|Báo cáo|Tờ trình|Giấy mời|Biên bản|Khác",
 "trich_yeu": "", "noi_nhan": "tóm tắt nơi nhận",
 "tra_loi_van_ban": ["số ký hiệu các văn bản cấp trên mà văn bản này thực hiện/trả lời (từ phần căn cứ, 'thực hiện công văn số...')"],
 "nhiem_vu_giao": [{"noi_dung": "việc giao cho người/bộ phận khác (bắt đầu bằng động từ)", "nguoi_thuc_hien": "", "han": "dd/mm/yyyy hoặc trống"}]}
Chỉ ghi thông tin có trong văn bản."""


def _drafts_path():
    return cfgmod.system_dir() / "du_thao.json"


def _out_path():
    return cfgmod.data_dir() / "so_van_ban_di.json"


def _load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(p, d):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _sig(text):
    from . import folders
    return folders._minhash(folders._norm_text(text or ""))


def _sim(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a) if a and b else 0.0


def register_draft(vna_id: str, path: Path, doc_type: str, inbox_stt=None, text: str = None):
    d = _load(_drafts_path(), {})
    if text is None:
        try:
            text = docio.extract_file(Path(path))
        except Exception:
            text = ""
    # Luu "dau van tay" noi dung (64 so) de ghep cap nhanh, khong phai doc lai hang tram file
    d[vna_id] = {"path": str(path), "loai": doc_type or "Khác", "inbox_stt": inbox_stt, "ngay": dt.date.today().isoformat(),
                 "sig": _sig(text)}
    # giu 1000 du thao gan nhat
    if len(d) > 1000:
        for k in sorted(d, key=lambda k: d[k]["ngay"])[: len(d) - 1000]:
            d.pop(k)
    _save(_drafts_path(), d)


def load_register():
    return _load(_out_path(), [])


def ban_hanh_dir(cfg) -> Path:
    return cfgmod.workspace(cfg) / cfgmod.WS_SAN_PHAM / cfgmod.DA_BAN_HANH


class OutboxWatcher(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.lock = threading.Lock()

    def run(self):
        time.sleep(8)
        while True:
            try:
                self.scan_once()
            except Exception:
                logging.exception("Loi theo doi van ban di")
            from . import power
            time.sleep(30 if power.profile(self.app.cfg) == "hieu_nang" else 90)

    def scan_once(self):
        root = ban_hanh_dir(self.app.cfg)
        reg = load_register()
        seen = {r["path"]: r.get("mtime") for r in reg}
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.name.startswith(("~$", ".")) or p.suffix.lower() not in docio.SUPPORTED:
                continue
            st = p.stat()
            if str(p) in seen or time.time() - st.st_mtime < 20:  # cho chep xong
                continue
            with self.lock:
                self.process(p, st.st_mtime)

    def process(self, p: Path, mtime: float):
        cfg = self.app.cfg
        reg = load_register()
        text = ""
        try:
            text = docio.extract_file(p)
        except Exception as e:
            logging.warning("Khong doc duoc %s: %s", p, e)
        info = {}
        if text.strip():
            try:
                info = learning._json(llm.chat(cfg, "Bạn là chuyên viên văn thư, trích thông tin chính xác, không bịa.",
                                               [{"role": "user", "content": ANALYZE + "\n\n=== VĂN BẢN ===\n" + text[:9000]}],
                                               json_mode=True, tier="fast", max_tokens=1000))
            except llm.LLMError as e:
                logging.warning("Van ban di %s: AI chua san sang (%s), thu lai sau", p.name, e)
                return
            except Exception:
                info = {}
        rec = {"stt": len(reg) + 1, "path": str(p), "mtime": mtime, "file": p.name,
               "ngay_ghi": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
               **{k: info.get(k, "") for k in ("so_ky_hieu", "ngay_ban_hanh", "loai", "trich_yeu", "noi_nhan")}}
        rec["trich_yeu"] = rec["trich_yeu"] or p.stem

        # ---- Ghep voi du thao -> hoc ----
        drafts = _load(_drafts_path(), {})
        vid = hoso.read_tag(p)
        match = drafts.get(vid) if vid else None
        if not match and text:
            sig = _sig(text)
            best, best_s = None, 0.0
            for k, dr in list(drafts.items())[-300:]:
                s = _sim(sig, dr.get("sig"))
                if s > best_s:
                    best, best_s = dr, s
            if best_s >= 0.3 and Path(best["path"]).exists():
                match = best
        if match and Path(match["path"]).exists():
            try:
                res = learning.learn_pair(cfg, Path(match["path"]), p, match.get("loai") or rec.get("loai") or "Khác")
                rec["hoc_tap"] = f"Đã học: sửa {res['ty_le_sua'] * 100:.0f}% · {res['quy_tac_moi']} quy tắc · {res['loi_moi']} lỗi"
            except Exception as e:
                logging.warning("Hoc tu %s loi: %s", p, e)

        # ---- Dong cong van den da tra loi ----
        inreg = inbox.load_register()
        linked = set()
        if match and match.get("inbox_stt"):
            linked.add(int(match["inbox_stt"]))
        for so in info.get("tra_loi_van_ban") or []:
            key = hoso.slug(str(so)).lower()
            for r in inreg:
                if r.get("so_ky_hieu") and hoso.slug(r["so_ky_hieu"]).lower() == key:
                    linked.add(int(r["stt"]))
        if linked:
            for r in inreg:
                if int(r["stt"]) in linked and not r.get("da_tra_loi"):
                    r["da_tra_loi"] = f"VB đi số {rec['stt']} ({rec.get('so_ky_hieu') or p.name})"
            inbox._save_register(inreg)
            n = planner.complete_by_source(linked, f"Đã có văn bản {rec.get('so_ky_hieu') or p.name}")
            rec["tra_loi"] = sorted(linked)
            rec["dong_nhiem_vu"] = n

        # ---- Nhiem vu da giao -> de xuat don doc ----
        giao = 0
        for nv in (info.get("nhiem_vu_giao") or [])[:20]:
            if not isinstance(nv, dict) or not nv.get("noi_dung"):
                continue
            d = hoso.parse_date(nv.get("han", ""))
            planner.add_task({"title": nv["noi_dung"].strip(), "loai": "giao", "nguoi": nv.get("nguoi_thuc_hien", ""),
                              "nguon": f"VB đi {rec.get('so_ky_hieu') or p.name}", "due": d.isoformat() + "T08:00" if d else "",
                              "remind_before": 1440, "de_xuat": True})
            giao += 1
        rec["nhiem_vu_giao"] = giao
        reg.append(rec)
        _save(_out_path(), reg)
        planner.add_journal(f"Ghi sổ văn bản đi: {rec.get('so_ky_hieu') or ''} {rec['trich_yeu']}"
                            + (f"; đã trả lời {len(linked)} công văn đến" if linked else "")
                            + (f"; đề xuất {giao} việc cần đôn đốc" if giao else "") + ".")
        threading.Thread(target=self.app.library.refresh, daemon=True).start()
        tracker.schedule()
        logging.info("Van ban di: %s", rec)

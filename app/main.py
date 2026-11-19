"""VNA - may chu cuc bo (chi chay tren 127.0.0.1) phuc vu giao dien va macro Word/Excel."""
import base64
import datetime
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import APP_NAME, __version__
from . import config as cfgmod
from . import (backup, docio, power, folders, hoso, inbox, knowledge, learning, llm, nutrition, outbox, planner, prompts, sangkien,
               selfcheck, setup_manager, teacher, tracker, tts, websearch)

STATIC = Path(__file__).parent / "static"


# =====================================================================
# LOI XU LY CHINH
# =====================================================================
class VNA:
    def __init__(self):
        self.cfg = cfgmod.load()
        try:
            cfgmod.migrate_old_workspace(self.cfg)
        except Exception as e:
            logging.warning("Chuyen cau truc thu muc cu loi: %s", e)
        ws = cfgmod.workspace(self.cfg)
        # Thu vien tra cuu: 01 (van ban den), 02 (can cu), 03 (tham khao), 04/Da_ban_hanh, thu_vien cu
        self.library = knowledge.Library(lambda: [cfgmod.library_dir(self.cfg), ws / cfgmod.WS_DEN, ws / cfgmod.WS_NGUON,
                                                  ws / cfgmod.WS_THAM_KHAO, ws / cfgmod.WS_SAN_PHAM / cfgmod.DA_BAN_HANH],
                                         cfgmod.data_dir() / "chi_muc.json")
        tracker.schedule(delay=3)
        threading.Thread(target=self.library.refresh, daemon=True).start()
        self.reminders = planner.ReminderThread(lambda: self.cfg, lambda t: tts.speak_async(t, self.cfg))
        self.reminders.start()
        self.inbox = inbox.InboxWatcher(self)
        self.inbox.start()
        self.setup = setup_manager.SetupManager(self)
        self.setup.start()
        self.outbox = outbox.OutboxWatcher(self)
        self.outbox.start()
        backup.BackupThread(self).start()
        sangkien.InitiativeThread(self).start()
        threading.Thread(target=self._idle_worker, daemon=True).start()

    def _idle_worker(self):
        """Viec nen nang chi chay khi cam sac va nguoi dung khong thao tac >= 2 phut (khong tranh may voi ban)."""
        time.sleep(90)
        while True:
            try:
                if power.can_run_heavy(self.cfg, idle_needed=120):
                    if learning.process_pending(self.cfg):
                        continue
                    if time.time() - getattr(self, "_last_lib", 0) > 900:  # OCR anh con cho, 15 phut/lan
                        self._last_lib = time.time()
                        threading.Thread(target=self.library.refresh, daemon=True).start()
            except Exception:
                logging.exception("Viec nen loi")
            time.sleep(60)

    def budget(self):
        local = self.cfg.get("backend") == "ollama"
        return int(self.cfg.get("context_chars_local" if local else "context_chars_cloud", 12000))

    def _trim_history(self, messages):
        n = int(self.cfg.get("history_messages", 12))
        msgs = [m for m in messages if m.get("role") in ("user", "assistant") and m.get("content")]
        msgs = msgs[-n:]
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        # rut gon cac cau tra loi cu qua dai
        out = []
        for i, m in enumerate(msgs):
            c = m["content"]
            if i < len(msgs) - 2 and len(c) > 4000:
                c = c[:4000] + "\n...(đã rút gọn)"
            out.append({"role": m["role"], "content": c})
        return out

    def _map_reduce(self, mode, question, attachments, budget):
        """Tai lieu qua dai so voi mo hinh: doc tung phan, ghi chep y lien quan, roi tong hop."""
        parts = []
        for a in attachments:
            text = a["text"]
            step = max(4000, int(budget * 0.8))
            for i in range(0, len(text), step):
                parts.append((a["name"], i // step + 1, text[i:i + step]))
        parts = parts[:24]
        notes = []
        sys_map = prompts.build_system("nghien_cuu", self.cfg)
        for name, idx, chunk in parts:
            msg = (f"Đây là PHẦN {idx} của tài liệu '{name}'.\n\n{chunk}\n\n"
                   f"YÊU CẦU CỦA NGƯỜI DÙNG: {question}\n\n"
                   "Hãy ghi chép NGẮN GỌN những nội dung, số liệu, quy định trong phần này phục vụ yêu cầu trên "
                   "(ghi rõ Điều/Mục nếu có). Nếu phần này không liên quan, trả lời: KHÔNG LIÊN QUAN.")
            note = llm.chat(self.cfg, sys_map, [{"role": "user", "content": msg}], tier="fast", max_tokens=600)
            if "KHÔNG LIÊN QUAN" not in note.upper()[:40]:
                notes.append(f"--- Ghi chép từ '{name}' phần {idx} ---\n{note}")
        joined = "\n\n".join(notes)
        return joined[: int(budget * 1.2)]

    def web_context(self, question, budget):
        """Tra cuu nguon chinh thong. Tra ve (doan_ngu_canh, nguon, loi)."""
        if not self.cfg.get("official_web", True):
            return "", [], "Chức năng tra cứu nguồn chính thống đang tắt (bật trong Cài đặt)."
        try:
            kw = llm.chat(self.cfg, "Bạn tạo từ khóa tìm kiếm tiếng Việt.",
                          [{"role": "user", "content": "Viết MỘT dòng từ khóa tìm kiếm (tối đa 10 từ, không giải thích, không dấu ngoặc) "
                                                      f"để tra cứu trên cổng thông tin chính thống của Nhà nước cho câu hỏi: {question[:600]}"}],
                          tier="fast", max_tokens=40)
            kw = kw.strip().splitlines()[0].strip(' "\'') if kw.strip() else question[:150]
        except Exception:
            kw = question[:150]
        extra = [x for x in self.cfg.get("official_extra_domains", "").split(",") if x.strip()]
        pages = websearch.search(kw, extra)
        if not pages:
            return "", [], f"Không tìm được thông tin từ nguồn chính thống cho: “{kw}” (kiểm tra kết nối Internet)."
        hits = websearch.best_passages(pages, question, budget=min(10000, int(budget * 0.5)))
        today = datetime.date.today().strftime("%d/%m/%Y")
        parts = [f"[{h['source']} – {h['url']}]\n{h['text']}" for h in hits]
        src = [{"source": h["source"], "loc": "", "url": h["url"]} for h in hits]
        return (f"=== THÔNG TIN TỪ NGUỒN CHÍNH THỐNG (tra cứu ngày {today}, từ khóa: {kw}) ===\n"
                "Khi dùng thông tin này, ghi rõ nguồn kèm đường link.\n\n" + "\n\n".join(parts)), src, ""

    def answer(self, mode, messages, attachments=None, use_library=True, web=False, check=True,
               on_token=None, on_phase=None):
        messages = self._trim_history(messages)
        if not messages:
            raise llm.LLMError("Chưa có câu hỏi.")
        question = messages[-1]["content"]
        mode = prompts.resolve_mode(mode, question)
        budget = self.budget()
        ctx, sources = [], []

        attachments = [a for a in (attachments or []) if a.get("text")]
        if attachments:
            total = sum(len(a["text"]) for a in attachments)
            if total <= budget * 0.75:
                for a in attachments:
                    ctx.append(f"=== TÀI LIỆU ĐÍNH KÈM: {a['name']} ===\n{a['text']}")
            else:
                ctx.append("=== GHI CHÉP TỪ TÀI LIỆU ĐÍNH KÈM (tài liệu dài, đã đọc từng phần) ===\n"
                           + self._map_reduce(mode, question, attachments, budget))
            sources += [{"source": a["name"], "loc": "đính kèm"} for a in attachments]

        if use_library:
            remain = max(3000, budget - sum(len(c) for c in ctx))
            hits = self.library.search(question, k=int(self.cfg.get("library_top_k", 6)))
            lib_parts, used = [], 0
            for h in hits:
                piece = f"[{self.library.kind_of(h['path'])}] [{h['source']}{' – ' + h['loc'] if h['loc'] else ''}]\n{h['text']}"
                if used + len(piece) > remain:
                    break
                lib_parts.append(piece)
                used += len(piece)
                sources.append({"source": h["source"], "loc": h["loc"], "score": h["score"]})
            if lib_parts:
                ctx.append("=== TRÍCH ĐOẠN TỪ THƯ VIỆN TÀI LIỆU ===\n" + "\n\n".join(lib_parts))

        web_note = ""
        if web == "auto":
            web = bool(self.cfg.get("web_auto", True) and websearch.AUTO_HINTS.search(question))
        if web:
            if on_phase:
                on_phase("tra_cuu")
            wctx, wsrc, web_note = self.web_context(question, budget)
            if wctx:
                ctx.append(wctx)
                sources += wsrc
        if ctx:
            messages[-1] = {"role": "user", "content": "TÀI LIỆU THAM KHẢO:\n\n" + "\n\n".join(ctx)
                            + f"\n\n=====\nYÊU CẦU:\n{question}"}
        system = prompts.build_system(mode, self.cfg)
        addon = learning.prompt_addon(question)
        if addon:
            system += "\n\n" + addon
        if on_phase:
            on_phase("viet")
        reply = llm.chat(self.cfg, system, messages, on_token=on_token)
        if check:
            if on_phase and mode in selfcheck.DOC_MODES and len(reply) >= 400:
                on_phase("kiem_tra")
            reply = selfcheck.run(self.cfg, mode, question, reply, self.library)
        if web_note:
            reply += f"\n\n> ℹ {web_note}"
        return reply, sources

    def trien_khai(self, attachments, extra="", inbox_stt=None):
        """Bo tai lieu trien khai van ban trong nha truong: nhieu buoc AI, moi buoc mot file Word."""
        if not attachments:
            raise ValueError("Hãy đính kèm văn bản cần triển khai (Word/PDF).")
        title = re.sub(r"[^\w\- ]+", "", extra or "", flags=re.UNICODE).strip()[:50]
        folder = cfgmod.output_dir("Bo_trien_khai") / hoso.std_name(datetime.date.today(), "", title or "Trien khai", "")
        folder.mkdir(parents=True, exist_ok=True)
        base_opts = {k: self.cfg.get(k, "") for k in ("co_quan_chu_quan", "co_quan", "ky_hieu_co_quan", "dia_danh", "nguoi_ky")}
        if self.cfg.get("ten_truong") and "..." not in self.cfg["ten_truong"]:
            base_opts["co_quan"] = self.cfg["ten_truong"]
        base_opts["chuc_vu_ky"] = "HIỆU TRƯỞNG"
        files, combined = [], []
        for name, mode, instr in prompts.TRIEN_KHAI_STEPS:
            q = instr + (f"\n\nYêu cầu bổ sung của Hiệu trưởng: {extra}" if extra else "")
            reply, _ = self.answer(mode, [{"role": "user", "content": q}], attachments, use_library=True)
            clean = selfcheck.strip_report(reply)
            draft = docio.parse_draft(clean)
            loai = draft["loai"] or "Khác"
            opts = dict(base_opts, the_thuc=bool(draft["loai"]), tieu_de=name[3:].replace("_", " ").upper(),
                        dinh_dang=learning.format_for(loai))
            vid = hoso.new_id()
            blob = hoso.tag_docx_bytes(docio.export_docx(clean, opts), vid)
            path = folder / f"{name}.docx"
            path.write_bytes(blob)
            outbox.register_draft(vid, path, loai, inbox_stt)
            files.append({"name": path.name, "path": str(path)})
            combined.append(f"## {name[3:].replace('_', ' ')}\n\n{reply}")
        logging.info("Trien khai van ban: %s", folder)
        return {"folder": str(folder), "files": files, "markdown": "\n\n---\n\n".join(combined)}

    def save_output(self, data: bytes, base: str, ext: str, kind: str = None) -> Path:
        folder = cfgmod.output_dir(kind or ("Bang_tinh" if ext == ".xlsx" else "Van_ban"))
        path = folder / hoso.std_name(datetime.date.today(), "", base or "VNA", ext)
        if path.exists():
            path = path.with_name(f"{path.stem}_{datetime.datetime.now():%H%M%S}{ext}")
        path.write_bytes(data)
        return path


APP: VNA = None
SHUTDOWN = threading.Event()


def open_file(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # mo bang Word/Excel
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
    except Exception as e:
        logging.warning("Khong mo duoc %s: %s", path, e)


EXT = {"python": ".py", "py": ".py", "javascript": ".js", "js": ".js", "typescript": ".ts", "ts": ".ts", "html": ".html",
       "css": ".css", "sql": ".sql", "vba": ".bas", "vb": ".bas", "powershell": ".ps1", "ps1": ".ps1", "bat": ".bat",
       "cmd": ".bat", "batch": ".bat", "csharp": ".cs", "cs": ".cs", "java": ".java", "json": ".json", "xml": ".xml",
       "bash": ".sh", "sh": ".sh", "yaml": ".yml", "yml": ".yml", "markdown": ".md", "md": ".md", "php": ".php", "c": ".c", "cpp": ".cpp"}


def save_code_blocks(content: str) -> list:
    """Luu cac khoi ma ``` trong cau tra loi thanh file trong '2. Van ban - san pham da lam/.../Ma nguon/<thoi diem>'."""
    blocks = re.findall(r"```([\w#+-]*)[^\n]*\n(.*?)```", content, re.S)
    if not blocks:
        raise ValueError("Không có khối mã nguồn nào trong câu trả lời.")
    folder = cfgmod.output_dir("Ma_nguon") / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, (lang, code) in enumerate(blocks, 1):
        first = code.strip().splitlines()[0] if code.strip() else ""
        m = re.search(r"(?:file|tệp|tep)\s*:\s*([\w.\-/\\ ]+\.\w+)", first, re.I)
        name = Path(m.group(1).strip()).name if m else f"ma_nguon_{i}{EXT.get(lang.lower(), '.txt')}"
        path = folder / name
        if path.exists():
            path = folder / f"{path.stem}_{i}{path.suffix}"
        path.write_text(code, encoding="utf-8-sig" if path.suffix in (".ps1",) else "utf-8")
        saved.append(str(path))
    return saved


def no_accent(s: str) -> str:
    """Thong bao loi cho macro VBA (MsgBox khong hien dau tieng Viet)."""
    import unicodedata
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# =====================================================================
# HTTP
# =====================================================================
class Handler(BaseHTTPRequestHandler):
    server_version = f"VNA/{__version__}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        logging.info("%s %s", self.address_string(), fmt % args)

    # ---- bao mat: chi nhan yeu cau tu chinh may nay & tu giao dien VNA ----
    def _allowed(self):
        port = APP.cfg.get("port", 8765)
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in hosts}:
            return False
        return True

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _jbody(self):
        raw = self._body()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self):
        if not self._allowed():
            return self._send(403, b'{"error":"forbidden"}')
        u = urlparse(self.path)
        p = u.path
        try:
            if p in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if p == "/api/ping":
                return self._json({"app": APP_NAME, "version": __version__})
            if p == "/api/status":
                return self._json(llm.status(APP.cfg))
            if p == "/api/config":
                return self._json(cfgmod.public_view(APP.cfg))
            if p == "/api/modes":
                return self._json(prompts.modes_public())
            if p == "/api/library":
                return self._json(APP.library.listing())
            if p == "/api/folders":
                return self._json({"folders": folders.registered(APP.cfg)})
            if p == "/api/greeting":
                g = planner.greeting(APP.cfg)
                g["inbox"] = list(APP.inbox.new_items)
                g["sap_het_han"] = inbox.sap_het_han(3)
                g["sang_kien"] = [{"id": x["id"], "ten": x["ten"], "loi_ich": x.get("loi_ich", "")}
                                  for x in sangkien.load()["items"] if x.get("trang_thai") == "moi"][-3:]
                if g["sap_het_han"]:
                    g["speak"] += f" Có {len(g['sap_het_han'])} công văn sắp đến hạn trả lời."
                if g["inbox"]:
                    g["speak"] += f" Có {len(g['inbox'])} văn bản mới đã được tiếp nhận và xử lý."
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                if q.get("speak") == "1" and APP.cfg.get("greet_speak", True):
                    tts.speak_async(g["speak"], APP.cfg)
                return self._json(g)
            if p == "/api/nutrition":
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                day = q.get("day") or datetime.date.today().isoformat()
                d = nutrition.load()
                a = nutrition.analyze(7)
                return self._json({"groups": nutrition.GROUPS, "profile": d["profile"], "day": day,
                                   "items": d["log"].get(day, []), "analysis": nutrition.analysis_markdown(a),
                                   "logged_days": a["so_ngay_ghi"]})
            if p == "/api/outbox":
                reg = outbox.load_register()
                return self._json({"dir": str(outbox.ban_hanh_dir(APP.cfg)), "register": list(reversed(reg[-200:]))})
            if p == "/api/learning":
                d = learning.load()
                return self._json({"rules": d["rules"], "errors": d["errors"], "formats": d["formats"],
                                   "examples": {k: [Path(x).name for x in v] for k, v in d["examples"].items()},
                                   "stats": learning.monthly_stats()})
            if p == "/api/backup":
                return self._json({"dir": str(backup.backup_dir(APP.cfg)), "items": backup.listing(APP.cfg)})
            if p == "/api/sangkien":
                return self._json({"items": list(reversed(sangkien.load()["items"][-30:]))})
            if p == "/api/setup_status":
                return self._json(APP.setup.state)
            if p == "/api/upcoming":
                return self._json({"items": planner.upcoming(3)})
            if p == "/api/tasks":
                return self._json(planner.list_tasks())
            if p == "/api/journal":
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                return self._json(planner.get_journal(q.get("day"), int(q.get("days", 1))))
            if p == "/api/reminders":
                items, APP.reminders.pending_ui = APP.reminders.pending_ui, []
                return self._json({"items": items})
            if p == "/api/inbox":
                reg = inbox.load_register()
                by_src = {}
                for t in planner.load()["tasks"]:
                    if t.get("nguon_den") is not None and t["status"] != "xong":
                        by_src.setdefault(int(t["nguon_den"]), []).append(t)
                for r in reg:
                    r["tip"] = inbox.short_tip(r, by_src.get(int(r["stt"]), []))
                return self._json({"dir": str(inbox.inbox_dir(APP.cfg)), "archive": str(inbox.archive_dir(APP.cfg)),
                                   "status": APP.inbox.status, "new": APP.inbox.new_items,
                                   "register": [{k: v for k, v in r.items() if k not in ("sha", "norm")} for r in reversed(reg[-200:])]})
            if p == "/api/voices":
                return self._json({"voices": tts.list_windows_voices()})
            return self._send(404, b'{"error":"not found"}')
        except Exception as e:
            logging.exception("GET %s", p)
            return self._json({"error": str(e)}, 500)

    def do_POST(self):
        if not self._allowed():
            return self._send(403, b'{"error":"forbidden"}')
        u = urlparse(self.path)
        p = u.path
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        power.touch()  # nguoi dung dang thao tac -> hoan viec nen nang
        try:
            if p == "/api/chat_stream":
                return self._chat_stream(self._jbody())
            if p == "/api/office":
                return self._office(q)
            data = self._jbody()
            if p == "/api/chat":
                msgs = data.get("messages", [])
                used = prompts.resolve_mode(data.get("mode", "tu_dong"), (msgs[-1]["content"] if msgs else ""))
                reply, sources = APP.answer(used, msgs,
                                            data.get("attachments"), bool(data.get("use_library", True)),
                                            web=data.get("web", "auto"))
                return self._json({"reply": reply, "sources": sources, "mode": used,
                                   "mode_name": prompts.MODES.get(used, {}).get("ten", "")})
            if p == "/api/extract":
                raw = base64.b64decode(data["data"])
                text = docio.extract_text(data["name"], raw)
                return self._json({"name": data["name"], "text": text, "chars": len(text)})
            if p == "/api/parse_draft":
                return self._json(docio.parse_draft(data.get("content", "")))
            if p == "/api/export_docx":
                opts = {k: APP.cfg.get(k, "") for k in ("co_quan_chu_quan", "co_quan", "ky_hieu_co_quan",
                                                        "dia_danh", "chuc_vu_ky", "nguoi_ky")}
                opts.update({k: v for k, v in (data.get("opts") or {}).items() if v is not None})
                content = selfcheck.strip_report(data.get("content", ""))
                dr = docio.parse_draft(content)
                loai = (opts.get("loai") or dr["loai"] or "Khác") if opts.get("the_thuc", True) else (opts.get("loai_hoc") or learning.guess_type(content) or "Khác")
                opts["dinh_dang"] = learning.format_for(loai)
                vid = hoso.new_id()
                blob = hoso.tag_docx_bytes(docio.export_docx(content, opts), vid)
                name = opts.get("trich_yeu") or dr["trich_yeu"] or opts.get("tieu_de") or "VanBan"
                if (opts.get("loai") or dr["loai"]) and opts.get("the_thuc", True):
                    name = f"{opts.get('loai') or dr['loai']} {name}"
                path = APP.save_output(blob, name, ".docx")
                outbox.register_draft(vid, path, loai, data.get("inbox_stt"))
                if data.get("open"):
                    open_file(path)
                return self._json({"path": str(path), "name": path.name, "data": base64.b64encode(blob).decode()})
            if p == "/api/export_xlsx":
                blob = docio.export_xlsx(selfcheck.strip_report(data.get("content", "")))
                path = APP.save_output(blob, data.get("name") or "BangTinh", ".xlsx")
                if data.get("open"):
                    open_file(path)
                return self._json({"path": str(path), "name": path.name, "data": base64.b64encode(blob).decode()})
            # ---- Cong cu giao vien ----
            if p == "/api/cham_bai":
                res = teacher.grade(APP, data.get("dap_an"), data.get("bai_lam") or [], data.get("de"),
                                    data.get("mon", ""), data.get("thang", 10), data.get("yeu_cau", ""))
                if data.get("open"):
                    open_file(Path(res["excel"]))
                return self._json(res)
            if p == "/api/nhan_xet":
                res = teacher.comments_xlsx(APP, base64.b64decode(data["data"]), data.get("mon", ""),
                                            data.get("loai", "mon_hoc"), data.get("them", ""))
                if data.get("open"):
                    open_file(Path(res["path"]))
                return self._json(res)
            if p == "/api/save_code":
                saved = save_code_blocks(data.get("content", ""))
                if saved:
                    open_file(Path(saved[0]).parent)
                return self._json({"files": saved})
            if p == "/api/tts":
                action = data.get("action", "speak")
                if action == "stop":
                    tts.stop()
                    return self._json({"ok": True})
                if action == "save":
                    path = tts.speak(data.get("text", ""), APP.cfg,
                                     save_to=cfgmod.output_dir("Giong_doc") / f"GiongDoc_{datetime.datetime.now():%Y%m%d_%H%M%S}")
                    return self._json({"ok": True, "path": path})
                tts.speak_async(data.get("text", ""), APP.cfg)
                return self._json({"ok": True})
            if p == "/api/config":
                cfgmod.update(APP.cfg, data)
                threading.Thread(target=APP.library.refresh, daemon=True).start()
                return self._json(cfgmod.public_view(APP.cfg))
            if p == "/api/library/refresh":
                threading.Thread(target=APP.library.refresh, daemon=True).start()
                return self._json({"ok": True})
            if p == "/api/library/add":
                dest = cfgmod.library_dir(APP.cfg) / Path(data["name"]).name
                dest.write_bytes(base64.b64decode(data["data"]))
                threading.Thread(target=APP.library.refresh, daemon=True).start()
                return self._json({"ok": True, "path": str(dest)})
            if p == "/api/open_folder":
                which = data.get("which", "library")
                ws = cfgmod.workspace(APP.cfg)
                open_file({"library": cfgmod.library_dir(APP.cfg), "workspace": ws, "tracking": cfgmod.tracking_dir(),
                           "den": ws / cfgmod.WS_DEN, "nguon": ws / cfgmod.WS_NGUON, "tham_khao": ws / cfgmod.WS_THAM_KHAO,
                           "du_thao": ws / cfgmod.WS_SAN_PHAM / cfgmod.DU_THAO, "ban_hanh": ws / cfgmod.WS_SAN_PHAM / cfgmod.DA_BAN_HANH,
                           "backup": backup.backup_dir(APP.cfg)}.get(which, ws))
                return self._json({"ok": True})
            # ---- Quan ly thu muc (chi thu muc nguoi dung cho phep) ----
            if p == "/api/folders/add":
                path = folders.pick_folder_dialog() if data.get("pick") else data.get("path", "")
                if not path:
                    return self._json({"folders": folders.registered(APP.cfg), "cancelled": True})
                return self._json({"folders": folders.register(APP.cfg, path)})
            if p == "/api/folders/remove":
                return self._json({"folders": folders.unregister(APP.cfg, data.get("path", ""))})
            if p == "/api/folders/scan":
                o = data.get("options") or {}
                rep = folders.scan(APP.cfg, data.get("root", ""), o.get("by_category", True), o.get("by_year", True),
                                   o.get("handle_dups", True), o.get("near_dup", True))
                md = folders.report_markdown(rep)
                return self._json({"total": rep["total"], "moves": len(rep["moves"]), "dups": len(rep["duplicates"]),
                                   "errors": len(rep["errors"]), "markdown": md})
            if p == "/api/folders/apply":
                return self._json(folders.apply_plan(APP.cfg, data.get("root", "")))
            if p == "/api/folders/undo":
                return self._json(folders.undo_last(APP.cfg, data.get("root", "")))
            if p == "/api/folders/open":
                root = data.get("root", "")
                if root in APP.cfg.get("managed_folders", []):
                    open_file(Path(root))
                return self._json({"ok": True})
            # ---- Cong viec, nhat ky ----
            if p == "/api/tasks/add":
                tracker.schedule()
                return self._json(planner.add_task(data))
            if p == "/api/tasks/update":
                tracker.schedule()
                return self._json(planner.update_task(data.get("id", ""), data))
            if p == "/api/tasks/approve":
                planner.approve(data.get("id", ""), bool(data.get("ok", True)))
                tracker.schedule()
                return self._json({"ok": True})
            if p == "/api/tasks/approve_all":
                planner.approve_all(bool(data.get("ok", True)))
                tracker.schedule()
                return self._json({"ok": True})
            if p == "/api/tasks/delete":
                planner.delete_task(data.get("id", ""))
                tracker.schedule()
                return self._json({"ok": True})
            if p == "/api/journal/add":
                tracker.schedule()
                return self._json(planner.add_journal(data.get("text", ""), data.get("day")))
            if p == "/api/planner/ai":
                kind = data.get("kind", "ke_hoach")
                instr = {
                    "ke_hoach": "Lập KẾ HOẠCH LÀM VIỆC HÔM NAY cho tôi từ danh sách công việc và nhật ký dưới đây: sắp xếp theo thứ tự ưu tiên "
                                "và khung giờ (bảng | Thời gian | Công việc | Mức ưu tiên | Ghi chú |), cảnh báo việc quá hạn, gợi ý việc có thể giao cho người khác.",
                    "tong_ket": "TỔNG KẾT NGÀY từ nhật ký và công việc dưới đây: việc đã làm, việc chưa xong và lý do có thể, việc cần chuyển sang ngày mai, nhận xét ngắn.",
                    "tuan": "Lập KẾ HOẠCH TUẦN từ công việc và nhật ký dưới đây: bảng theo từng ngày, việc trọng tâm, mốc hạn chót.",
                }.get(kind, "")
                mode = "hieu_truong" if APP.cfg.get("ten_truong") and "..." not in APP.cfg.get("ten_truong", "") else "lanh_dao"
                reply, _ = APP.answer(mode, [{"role": "user", "content": instr + "\n\n" + planner.context_for_ai(kind)}],
                                      use_library=False, check=False)
                return self._json({"reply": reply})
            # ---- Bo tai lieu trien khai trong nha truong ----
            if p == "/api/trien_khai":
                res = APP.trien_khai(data.get("attachments") or [], data.get("extra", ""))
                if data.get("open"):
                    open_file(Path(res["folder"]))
                return self._json(res)
            # ---- Van ban den ----
            if p == "/api/inbox/open":
                which = data.get("which", "inbox")
                target = {"inbox": inbox.inbox_dir(APP.cfg), "archive": inbox.archive_dir(APP.cfg)}.get(which)
                if which == "file":
                    f = Path(data.get("path", ""))
                    allowed = [cfgmod.data_dir().resolve(), cfgmod.library_dir(APP.cfg).resolve()]
                    if f.exists() and any(a == f.resolve() or a in f.resolve().parents for a in allowed):
                        target = f
                if target:
                    open_file(target)
                return self._json({"ok": True})
            if p == "/api/inbox/seen":
                APP.inbox.new_items = []
                return self._json({"ok": True})
            if p == "/api/inbox/scan_now":
                threading.Thread(target=APP.inbox.scan_once, daemon=True).start()
                return self._json({"ok": True})
            if p == "/api/inbox/register_xlsx":
                tracker.write_all()
                path = cfgmod.tracking_dir() / tracker.SO_VB
                open_file(path)
                return self._json({"path": str(path)})
            if p == "/api/nutrition/day":
                return self._json({"items": nutrition.set_day(data.get("day") or datetime.date.today().isoformat(), data.get("items", []))})
            if p == "/api/nutrition/profile":
                return self._json(nutrition.set_profile(data))
            if p == "/api/nutrition/ai":
                kind = data.get("kind", "khuyen_nghi")
                reply, _ = APP.answer("dinh_duong", [{"role": "user", "content": nutrition.ai_prompt(kind, data.get("extra", ""))}],
                                      use_library=False)
                if kind == "khuyen_nghi":
                    reply = nutrition.analysis_markdown(nutrition.analyze(7)) + "\n\n---\n\n" + reply
                return self._json({"reply": reply})
            if p == "/api/inbox/trien_khai":
                stt = int(data.get("stt", 0))
                rec = next((r for r in inbox.load_register() if int(r["stt"]) == stt), None)
                if not rec or not Path(rec.get("luu_tai", "")).exists():
                    raise ValueError("Không tìm thấy văn bản đến.")
                text = docio.extract_file(Path(rec["luu_tai"]))
                res = APP.trien_khai([{"name": Path(rec["luu_tai"]).name, "text": text}],
                                     f"Văn bản {rec.get('so_ky_hieu', '')} – {rec.get('trich_yeu', '')}", inbox_stt=stt)
                reg = inbox.load_register()
                for r in reg:
                    if int(r["stt"]) == stt:
                        r["trien_khai"] = res["folder"]
                inbox._save_register(reg)
                if data.get("open"):
                    open_file(Path(res["folder"]))
                return self._json(res)
            if p == "/api/feedback":
                return self._json(learning.feedback(data.get("rating", ""), data.get("note", ""), data.get("sample", "")[:500]))
            if p == "/api/learning/item":
                learning.set_item(data.get("kind", "rule"), data.get("id", ""), data.get("changes", {}))
                return self._json({"ok": True})
            if p == "/api/learning/add":
                learning.add_item(data.get("kind", "rule"), data.get("noi_dung", ""),
                                  **{k: data[k] for k in ("cum_tu_sai", "cum_tu_dung", "loai_vb") if data.get(k)})
                return self._json({"ok": True})
            if p == "/api/backup/now":
                return self._json({"path": str(backup.make(APP.cfg))})
            if p == "/api/backup/restore":
                backup.restore(APP.cfg, data.get("name", ""))
                self._json({"ok": True, "message": "Đã phục hồi. VNA sẽ tắt; hãy mở lại VNA."})
                SHUTDOWN.set()
                return
            if p == "/api/sangkien/generate":
                return self._json({"items": sangkien.generate(APP, int(data.get("days", 60)))})
            if p == "/api/sangkien/decide":
                return self._json(sangkien.decide(data.get("id", ""), data.get("action", "")))
            if p == "/api/setup/retry":
                APP.setup.retry.set()
                return self._json({"ok": True})
            if p == "/api/shutdown":
                self._json({"ok": True})
                SHUTDOWN.set()
                return
            return self._send(404, b'{"error":"not found"}')
        except (llm.LLMError, tts.TTSError, ValueError) as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            logging.exception("POST %s", p)
            return self._json({"error": f"Lỗi: {e}"}, 500)

    # ---- Tra loi truyen tung doan (hien chu ngay, cam giac nhanh hon nhieu) ----
    def _chat_stream(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def emit(obj):
            b = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
            try:
                self.wfile.write(f"{len(b):X}\r\n".encode() + b + b"\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        buf = []
        last = [time.time()]

        def on_token(t):
            buf.append(t)
            if time.time() - last[0] > 0.08:  # gom chu, gui 12 lan/giay
                emit({"t": "".join(buf)})
                buf.clear()
                last[0] = time.time()
        try:
            msgs = data.get("messages", [])
            used = prompts.resolve_mode(data.get("mode", "tu_dong"), (msgs[-1]["content"] if msgs else ""))
            emit({"mode": used, "mode_name": prompts.MODES.get(used, {}).get("ten", "")})
            reply, sources = APP.answer(used, msgs, data.get("attachments"), bool(data.get("use_library", True)),
                                        web=data.get("web", "auto"), on_token=on_token,
                                        on_phase=lambda ph: emit({"phase": ph}))
            if buf:
                emit({"t": "".join(buf)})
            emit({"done": True, "reply": reply, "sources": sources, "mode": used,
                  "mode_name": prompts.MODES.get(used, {}).get("ten", ""), "tps": llm.STATS.get("tps")})
        except Exception as e:
            logging.exception("chat_stream")
            emit({"error": str(e)})
        try:
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except Exception:
            pass

    # ---- Cong cho macro Word / Excel: van ban thuan UTF-8 ----
    def _office(self, q):
        text = self._body().decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n").replace("\x07", "\t")
        task = q.get("task", "thuc_hien")
        fmt = q.get("fmt", "plain")
        try:
            if task == "tts":
                tts.speak_async(text, APP.cfg)
                return self._send(200, b"OK", "text/plain; charset=utf-8")
            if task == "tts_stop":
                tts.stop()
                return self._send(200, b"OK", "text/plain; charset=utf-8")
            if task == "nhan_xet":  # Excel: vung chon co dong tieu de -> moi dong 1 nhan xet
                rows = [r.split("\t") for r in text.strip("\n").split("\n")]
                cm = teacher.comments_for_rows(APP.cfg, rows[0], rows[1:], q.get("mon", ""), q.get("loai", "mon_hoc"))
                return self._send(200, "\n".join(c.replace("\n", " ") for c in cm).encode("utf-8"), "text/plain; charset=utf-8")
            if task not in prompts.OFFICE_TASKS:
                return self._send(400, b"Nhiem vu khong hop le", "text/plain; charset=utf-8")
            mode, instr = prompts.OFFICE_TASKS[task]
            mode = q.get("mode", mode)
            msg = f"{instr}\n\n-----\n{text.strip()}"
            reply, _ = APP.answer(mode, [{"role": "user", "content": msg}],
                                  use_library=q.get("lib", "1") == "1" and task not in ("cong_thuc", "tao_bang", "chinh_sua"),
                                  web="auto", check=False)
            if task == "cong_thuc":
                m = re.search(r"=[^\n`]+", reply)
                reply = m.group(0).strip() if m else reply.strip()
            elif fmt == "plain":
                reply = docio.strip_markdown(reply)
            return self._send(200, reply.encode("utf-8"), "text/plain; charset=utf-8")
        except Exception as e:
            logging.exception("office")
            return self._send(500, no_accent(str(e)).encode("utf-8"), "text/plain; charset=utf-8")


# =====================================================================
# KHOI DONG
# =====================================================================
def already_running(port) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            return json.loads(r.read()).get("app") == APP_NAME
    except Exception:
        return False


def use_windows_certificates():
    """Dung kho chung chi cua Windows (tranh loi CERTIFICATE_VERIFY_FAILED khi may co
    phan mem diet virus/proxy kiem tra HTTPS)."""
    try:
        import truststore
        truststore.inject_into_ssl()
        logging.info("Dung kho chung chi he dieu hanh (truststore)")
    except Exception as e:
        logging.warning("Khong nap duoc truststore: %s", e)


def main():
    global APP
    logging.basicConfig(filename=str(cfgmod.data_dir() / "nhat_ky.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    use_windows_certificates()
    power.lower_own_priority()
    cfg = cfgmod.load()
    port = int(cfg.get("port", 8765))
    url = f"http://127.0.0.1:{port}/"
    no_browser = "--no-browser" in sys.argv
    if already_running(port):
        if not no_browser:
            webbrowser.open(url)
        return
    APP = VNA()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    logging.info("VNA %s dang chay tai %s", __version__, url)
    print(f"VNA dang chay tai {url}  (Ctrl+C de dung)")
    if not no_browser:
        webbrowser.open(url)
    try:
        while not SHUTDOWN.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    tts.stop()
    httpd.shutdown()


if __name__ == "__main__":
    main()

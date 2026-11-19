"""Ket noi mo hinh AI: Ollama (tren may), Claude API, hoac may chu tuong thich OpenAI."""
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse


class LLMError(Exception):
    pass


def _opener_for(url: str):
    host = (urlparse(url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "::1"):
        # Khong di qua proxy he thong khi goi may chu tren chinh laptop
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "::1"):
        return True
    # may chu trong mang noi bo (LAN) cua co quan cung duoc coi la noi bo
    return host.startswith(("10.", "192.168.")) or any(host.startswith(f"172.{i}.") for i in range(16, 32))


OFFLINE_MSG = ("Đang bật chế độ 'Hoàn toàn ngoại tuyến' nên VNA không kết nối Internet. "
               "Hãy dùng mô hình trên máy (Ollama – miễn phí), hoặc tắt chế độ này trong Cài đặt nếu thực sự cần.")


def guard(cfg: dict, url: str):
    if cfg.get("offline_only", True) and not _is_local(url):
        raise LLMError(OFFLINE_MSG)


def _request(url, payload=None, headers=None, timeout=900, method=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data else "GET"))
    try:
        with _opener_for(url).open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("error")
            if isinstance(msg, dict):
                msg = msg.get("message")
        except Exception:
            msg = body[:400]
        raise LLMError(f"Máy chủ AI báo lỗi {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise LLMError(f"Không kết nối được máy chủ AI ({url}): {e.reason}")
    except TimeoutError:
        raise LLMError("Máy chủ AI phản hồi quá lâu (hết thời gian chờ).")


# ---------------------------------------------------------------------
# TOI UU PIN & TOC DO
#  - 2 tang mo hinh: "fast" (nho, cho viec trich xuat/JSON/tu khoa) va "main" (cho soan thao, tra loi).
#    Dung pin -> moi viec dung mo hinh nho.
#  - num_ctx CO DINH theo tang (doi num_ctx lam Ollama nap lai mo hinh -> ton pin).
#  - So luong CPU giam khi dung pin; keep_alive ngan khi dung pin de giai phong RAM.
#  - Bo nho dem ket qua cho cac viec lap lai (JSON, tom tat cung noi dung).
#  - Truyen tung chu ve giao dien (stream) de thay ket qua ngay.
# ---------------------------------------------------------------------
import hashlib as _hashlib
import time as _time

STATS = {"tps": None, "model": "", "last_s": None}


def pick_model(cfg, tier="main") -> str:
    from . import power
    main = cfg.get("ollama_model") or "qwen2.5:7b"
    fast = cfg.get("ollama_model_fast") or main
    if tier == "fast" or power.profile(cfg) == "tiet_kiem":
        return fast
    return main


def _cache_get(key):
    from . import config as cfgmod
    p = cfgmod.system_dir() / "cache" / (key + ".json")
    try:
        return json.loads(p.read_text(encoding="utf-8"))["text"]
    except Exception:
        return None


def _cache_put(key, text):
    from . import config as cfgmod
    d = cfgmod.system_dir() / "cache"
    d.mkdir(exist_ok=True)
    try:
        (d / (key + ".json")).write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
        files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for f in files[:-800]:  # giu 800 ket qua gan nhat
            f.unlink(missing_ok=True)
    except Exception:
        pass


def chat(cfg: dict, system: str, messages: list, json_mode: bool = False, tier: str = "main",
         on_token=None, max_tokens: int = None, cache: bool = None) -> str:
    """messages: [{'role': 'user'|'assistant', 'content': str}]
    tier: "fast" cho trich xuat, phan loai, JSON; "main" cho soan thao, tra loi.
    on_token: ham nhan tung doan chu (hien ket qua ngay tren giao dien)."""
    backend = cfg.get("backend", "ollama")
    temp = 0.1 if json_mode else float(cfg.get("temperature", 0.3))
    max_out = int(max_tokens or cfg.get("max_output_tokens", 8000))
    use_cache = (json_mode or tier == "fast") if cache is None else cache
    key = None
    if use_cache and cfg.get("ai_cache", True):
        raw = json.dumps([backend, pick_model(cfg, tier) if backend == "ollama" else "", system, messages, json_mode], ensure_ascii=False)
        key = _hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        hit = _cache_get(key)
        if hit is not None:
            if on_token:
                on_token(hit)
            return hit
    text = _chat_backend(cfg, backend, system, messages, json_mode, tier, temp, max_out, on_token)
    if key and text:
        _cache_put(key, text)
    return text


def _chat_backend(cfg, backend, system, messages, json_mode, tier, temp, max_out, on_token):
    if backend == "claude":
        guard(cfg, "https://api.anthropic.com")
        key = cfg.get("claude_api_key", "").strip()
        if not key:
            raise LLMError("Chưa nhập Claude API key (vào Cài đặt).")
        res = _request(
            "https://api.anthropic.com/v1/messages",
            {"model": cfg.get("claude_model") or "claude-sonnet-5-5", "max_tokens": max_out, "temperature": temp,
             "system": system, "messages": messages},
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text").strip()
        if on_token:
            on_token(text)
        return text

    if backend == "openai":
        base = cfg.get("openai_base_url", "").rstrip("/")
        guard(cfg, base)
        headers = {}
        if cfg.get("openai_api_key"):
            headers["Authorization"] = "Bearer " + cfg["openai_api_key"]
        res = _request(base + "/chat/completions",
                       {"model": cfg.get("openai_model") or "local-model", "temperature": temp, "max_tokens": max_out,
                        "messages": [{"role": "system", "content": system}] + messages}, headers)
        text = res["choices"][0]["message"]["content"].strip()
        if on_token:
            on_token(text)
        return text

    # ---- Ollama tren laptop ----
    from . import power
    base = cfg.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
    guard(cfg, base)
    model = pick_model(cfg, tier)
    is_fast = model == (cfg.get("ollama_model_fast") or "")
    saving = power.profile(cfg) == "tiet_kiem"
    payload = {
        "model": model,
        "stream": bool(on_token),
        "messages": [{"role": "system", "content": system}] + messages,
        "keep_alive": "3m" if saving else "15m",
        "options": {"temperature": temp,
                    "num_ctx": int(cfg.get("ollama_ctx_fast" if is_fast else "ollama_ctx_main", 4096 if is_fast else 8192)),
                    "num_predict": max_out, "num_thread": power.cpu_threads(cfg)},
    }
    if json_mode:
        payload["format"] = "json"
    t0 = _time.time()
    if not on_token:
        res = _request(base + "/api/chat", payload)
        text = res.get("message", {}).get("content", "")
        _stats(res, model, t0)
    else:
        text = _stream_ollama(base, payload, on_token, model, t0)
    if "</think>" in text:  # mo hinh suy luan: bo phan nghi
        text = text.split("</think>", 1)[1]
    return text.strip()


def _stats(res, model, t0):
    try:
        ec, ed = res.get("eval_count"), res.get("eval_duration")
        if ec and ed:
            STATS["tps"] = round(ec / (ed / 1e9), 1)
        STATS["model"], STATS["last_s"] = model, round(_time.time() - t0, 1)
    except Exception:
        pass


def _stream_ollama(base, payload, on_token, model, t0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + "/api/chat", data=data, headers={"Content-Type": "application/json"})
    out = []
    try:
        with _opener_for(base).open(req, timeout=1800) as r:
            for line in r:
                try:
                    ev = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if ev.get("error"):
                    raise LLMError("Máy chủ AI báo lỗi: " + str(ev["error"]))
                piece = ev.get("message", {}).get("content", "")
                if piece:
                    out.append(piece)
                    on_token(piece)
                if ev.get("done"):
                    _stats(ev, model, t0)
                    break
    except urllib.error.HTTPError as e:
        raise LLMError(f"Máy chủ AI báo lỗi {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        raise LLMError(f"Không kết nối được máy chủ AI ({base}): {e.reason}")
    return "".join(out)


def status(cfg: dict) -> dict:
    backend = cfg.get("backend", "ollama")
    out = {"backend": backend, "ok": False, "message": "", "models": []}
    if backend == "ollama":
        base = cfg.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
        try:
            res = _request(base + "/api/tags", timeout=4)
            names = [m.get("name", "") for m in res.get("models", [])]
            out["models"] = names
            want = cfg.get("ollama_model", "")
            if any(n == want or n.split(":")[0] == want for n in names):
                out["ok"] = True
                from . import power
                b = power.battery()
                prof = power.profile(cfg)
                used = pick_model(cfg, "main")
                speed = f" · {STATS['tps']} từ/giây" if STATS.get("tps") else ""
                out["message"] = (f"{'🔋 Tiết kiệm pin' if prof == 'tiet_kiem' else '⚡ Hiệu năng'}: {used}{speed}"
                                  + (f" · pin {b['percent']}%" if b.get("percent") is not None else "")
                                  + (" · ngoại tuyến" if cfg.get("offline_only", True) else ""))
                out["power"] = {"profile": prof, **b, "tps": STATS.get("tps")}
            else:
                out["message"] = (f"Ollama đang chạy nhưng chưa có mô hình '{want}'. "
                                  f"Mở Command Prompt và chạy: ollama pull {want}")
        except LLMError:
            out["message"] = ("Chưa thấy Ollama. Hãy cài Ollama (https://ollama.com) rồi chạy: "
                              f"ollama pull {cfg.get('ollama_model')} — hoặc chuyển sang Claude API trong Cài đặt.")
    elif backend == "claude" and cfg.get("offline_only", True):
        out["message"] = "Chế độ ngoại tuyến đang bật: không dùng được Claude API. Chọn Ollama (miễn phí) hoặc tắt chế độ ngoại tuyến."
    elif backend == "claude":
        out["ok"] = bool(cfg.get("claude_api_key"))
        out["message"] = (f"Đang dùng Claude API ({cfg.get('claude_model')})" if out["ok"]
                          else "Chưa nhập Claude API key (vào Cài đặt).")
    else:
        out["ok"] = bool(cfg.get("openai_base_url"))
        out["message"] = f"Đang dùng máy chủ: {cfg.get('openai_base_url')}"
    return out

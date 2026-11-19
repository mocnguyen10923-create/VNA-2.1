"""Thu vien tai lieu: lap chi muc va tim kiem (BM25) cho van ban phap luat, quy che, tai lieu nghien cuu.
Chay hoan toan tren may, khong can Internet."""
import json
import logging
import math
import re
import threading
from collections import Counter
from pathlib import Path

from . import docio, power

TOKEN_RE = re.compile(r"\w+", re.UNICODE)
LOC_RE = re.compile(r"^\s*(Phần|Chương|Mục|Điều|Phụ lục)\s+[\w\.]+", re.I)


def tokenize(text: str):
    toks = TOKEN_RE.findall(text.lower())
    # them cap tu (bigram) vi tieng Viet la ngon ngu don am tiet
    return toks + [a + "_" + b for a, b in zip(toks, toks[1:])]


def chunk_text(text: str, size=1500, overlap=200):
    """Chia van ban thanh doan, giu ranh gioi doan van va ghi nho vi tri (Chuong/Dieu)."""
    paras = [p.strip() for p in text.replace("\r", "").split("\n") if p.strip()]
    chunks, cur, cur_len, loc, cur_loc = [], [], 0, "", ""
    for p in paras:
        m = LOC_RE.match(p)
        if m:
            loc = p[:80]
            # bat dau doan moi khi gap Dieu moi de trich dan chinh xac
            if cur and cur_len > size * 0.4:
                chunks.append({"text": "\n".join(cur), "loc": cur_loc})
                cur, cur_len = [], 0
        if not cur:
            cur_loc = loc
        while len(p) > size:  # doan qua dai
            head, p = p[:size], p[size - overlap:]
            if cur:
                chunks.append({"text": "\n".join(cur), "loc": cur_loc})
                cur, cur_len = [], 0
            chunks.append({"text": head, "loc": loc})
            cur_loc = loc
        if cur_len + len(p) > size and cur:
            chunks.append({"text": "\n".join(cur), "loc": cur_loc})
            tail = cur[-1] if len(cur[-1]) < overlap else ""
            cur = [tail] if tail else []
            cur_len = len(tail)
            cur_loc = loc
        cur.append(p)
        cur_len += len(p) + 1
    if cur:
        chunks.append({"text": "\n".join(cur), "loc": cur_loc})
    return chunks


class BM25:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tfs = [Counter(t) for t in docs_tokens]
        self.lens = [len(t) for t in docs_tokens]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(self.tfs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def scores(self, q_tokens):
        out = []
        q = Counter(q_tokens)
        for tf, ln in zip(self.tfs, self.lens):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / (self.avg or 1)))
            out.append(s)
        return out


def rank(chunks, query, k=6):
    if not chunks or not query.strip():
        return []
    bm = BM25([tokenize(c["text"]) for c in chunks])
    sc = bm.scores(tokenize(query))
    order = sorted(range(len(chunks)), key=lambda i: sc[i], reverse=True)
    return [dict(chunks[i], score=round(sc[i], 3)) for i in order[:k] if sc[i] > 0]


class Library:
    def _cfg(self):
        from . import config as cfgmod
        return cfgmod._ACTIVE

    def __init__(self, folders_fn, index_path: Path):
        """folders_fn: ham tra ve danh sach thu muc can lap chi muc."""
        self.folders_fn = folders_fn
        self.index_path = Path(index_path)
        self.lock = threading.Lock()
        self.files = {}  # rel_path -> {"mtime":..., "chunks":[...], "error":...}
        self.flat = []
        self.bm = None
        self.busy = False
        try:
            self.files = json.loads(self.index_path.read_text(encoding="utf-8")).get("files", {})
        except Exception:
            self.files = {}
        self._rebuild()

    def _rebuild(self):
        # Chi tach tu cac file moi/thay doi (bo nho dem theo file) -> lap chi muc lai rat nhanh, it ton CPU
        cache = getattr(self, "_tok", {})
        new_cache, flat, toks = {}, [], []
        for rel, info in self.files.items():
            key = (rel, info.get("mtime"))
            tl = cache.get(key) or [tokenize(c["text"]) for c in info.get("chunks", [])]
            new_cache[key] = tl
            for c, t in zip(info.get("chunks", []), tl):
                flat.append({"source": Path(rel).name, "path": rel, "loc": c.get("loc", ""), "text": c["text"]})
                toks.append(t)
        self._tok = new_cache
        bm = BM25(toks) if flat else None
        with self.lock:
            self.flat, self.bm = flat, bm

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        try:
            seen, changed = set(), False
            paths = []
            for folder in self.folders_fn():
                folder = Path(folder)
                if folder.is_dir():
                    paths += [p for p in folder.rglob("*") if "_TRUNG_LAP" not in p.parts]
            for p in sorted(set(paths)):
                if not p.is_file() or p.suffix.lower() not in docio.SUPPORTED or p.name.startswith("~$"):
                    continue
                rel = str(p)
                seen.add(rel)
                mtime = p.stat().st_mtime
                if rel in self.files and self.files[rel].get("mtime") == mtime:
                    continue
                if p.suffix.lower() in docio.IMAGE_EXT and rel not in self.files and power.profile(self._cfg()) != "hieu_nang":
                    seen.discard(rel)
                    continue  # anh: OCR khi cam sac (tiet kiem pin)
                try:
                    text = docio.extract_file(p)
                    self.files[rel] = {"mtime": mtime, "chunks": chunk_text(text), "chars": len(text)}
                except Exception as e:  # noqa
                    logging.warning("Khong doc duoc %s: %s", p, e)
                    self.files[rel] = {"mtime": mtime, "chunks": [], "error": str(e)}
                changed = True
            for rel in list(self.files):
                if rel not in seen:
                    del self.files[rel]
                    changed = True
            if changed:
                self.index_path.write_text(json.dumps({"files": self.files}, ensure_ascii=False), encoding="utf-8")
                self._rebuild()
        finally:
            self.busy = False

    def search(self, query: str, k=6):
        with self.lock:
            flat, bm = self.flat, self.bm
        if not bm or not query.strip():
            return []
        sc = bm.scores(tokenize(query))
        for i, c in enumerate(flat):
            if "Het_hieu_luc" in c["path"]:
                sc[i] = 0  # van ban het hieu luc: khong dung de tra loi
            elif "02_NGUON_CAN_CU" in c["path"]:
                sc[i] *= 1.3  # uu tien can cu
        order = sorted(range(len(flat)), key=lambda i: sc[i], reverse=True)
        best = sc[order[0]] if order else 0
        # bo ket qua qua yeu so voi ket qua tot nhat
        return [dict(flat[i], score=round(sc[i], 3)) for i in order[:k] if sc[i] > 0 and sc[i] >= best * 0.25]

    def kind_of(self, path: str) -> str:
        if "02_NGUON_CAN_CU" in path:
            return "CĂN CỨ"
        if "03_TAI_LIEU_THAM_KHAO" in path:
            return "THAM KHẢO"
        if "01_VAN_BAN_DEN" in path:
            return "VĂN BẢN ĐẾN"
        if "04_SAN_PHAM" in path:
            return "ĐÃ BAN HÀNH"
        return "THƯ VIỆN"

    def find_number(self, so: str):
        """Tim so hieu van ban trong thu vien. Tra ve 'het_hieu_luc' | 'co' | None."""
        key = so.lower()
        found = None
        for rel, info in self.files.items():
            if key in Path(rel).name.lower() or any(key in c["text"][:400].lower() for c in info.get("chunks", [])[:2]):
                if "Het_hieu_luc" in rel:
                    found = found or "het_hieu_luc"
                else:
                    return "co"
        return found

    def listing(self):
        return {
            "folder": " ; ".join(str(f) for f in self.folders_fn()),
            "busy": self.busy,
            "files": [
                {"name": rel, "chunks": len(i.get("chunks", [])), "chars": i.get("chars", 0), "error": i.get("error", "")}
                for rel, i in sorted(self.files.items())
            ],
        }

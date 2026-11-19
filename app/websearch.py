"""Tra cuu thong tin hien hanh tu CAC KENH CHINH THONG cua Nha nuoc.

An toan:
  - Chi mo trang thuoc danh sach ten mien chinh thong (OFFICIAL). Moi trang khac bi chan.
  - Chi gui TU KHOA tim kiem ra ngoai, khong gui tai lieu cua nguoi dung.
  - Nguoi dung bat/tat trong Cai dat ("Cho phep tra cuu nguon chinh thong").
  - Ket qua luon kem duong link nguon de nguoi dung kiem chung.
"""
import html
import io
import logging
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from . import knowledge

# Ten mien chinh thong (khop chinh xac hoac la ten mien con)
OFFICIAL = [
    "gov.vn",                # tat ca co quan nha nuoc: moet.gov.vn, *.gov.vn cua tinh, so GDDT...
    "chinhphu.vn",           # Cong TTDT Chinh phu, vanban.chinhphu.vn, congbao.chinhphu.vn
    "baochinhphu.vn",
    "vbpl.vn",               # Co so du lieu quoc gia ve van ban phap luat (Bo Tu phap)
    "quochoi.vn",
    "dangcongsan.vn",
    "nhandan.vn",
    "dichvucong.gov.vn",
]
SEARCH_URL = "https://html.duckduckgo.com/html/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VNA/1.0"
AUTO_HINTS = re.compile(r"(mới nhất|hiện hành|còn hiệu lực|hết hiệu lực|hiện nay|năm nay|vừa ban hành|mới ban hành|"
                        r"cập nhật|tra cứu|tìm trên mạng|tìm kiếm|hướng dẫn mới|năm học 20\d\d)", re.I)


def is_official(url: str, extra=()) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if not host or urllib.parse.urlparse(url).scheme not in ("https", "http"):
        return False
    for d in list(OFFICIAL) + [x.strip().lower() for x in extra if x.strip()]:
        if host == d or host.endswith("." + d):
            return True
    return False


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "form", "svg", "iframe"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "td", "section", "article"}

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def html_to_text(raw: str):
    p = _Text()
    p.feed(raw)
    text = re.sub(r"[ \t ]+", " ", "".join(p.out))
    text = re.sub(r"\n\s*\n+", "\n", text)
    return p.title.strip(), text.strip()


def _get(url, timeout=15, data=None, limit=4_000_000):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        final = r.geturl()
        ctype = r.headers.get("Content-Type", "")
        body = r.read(limit)
    return final, ctype, body


def parse_ddg(raw: str):
    links = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', raw, re.S):
        href = html.unescape(m.group(1))
        if "uddg=" in href:
            href = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [""])[0])
        if href.startswith("//"):
            href = "https:" + href
        title = re.sub(r"<[^>]+>", "", html.unescape(m.group(2))).strip()
        links.append((href, title))
    return links


def search(query: str, extra_domains=(), max_pages=4):
    """Tim tren cac trang chinh thong. Tra ve [{'url','title','text'}]."""
    sites = ["gov.vn", "chinhphu.vn", "vbpl.vn"]
    seen, results = set(), []
    for site in sites:
        q = f"{query} site:{site}"
        try:
            _, _, body = _get(SEARCH_URL, data=urllib.parse.urlencode({"q": q, "kl": "vn-vi"}).encode())
        except Exception as e:
            logging.warning("Tim kiem loi (%s): %s", site, e)
            continue
        for url, title in parse_ddg(body.decode("utf-8", "replace")):
            if url in seen or not is_official(url, extra_domains):
                continue
            seen.add(url)
            results.append({"url": url, "title": title})
        if len(results) >= max_pages * 2:
            break
    pages = []
    for r in results:
        if len(pages) >= max_pages:
            break
        try:
            final, ctype, body = _get(r["url"])
            if not is_official(final, extra_domains):  # chuyen huong ra ngoai -> bo
                continue
            if "pdf" in ctype.lower() or final.lower().endswith(".pdf"):
                from pypdf import PdfReader
                text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(body)).pages[:40])
                title = r["title"]
            else:
                enc = re.search(r"charset=([\w-]+)", ctype)
                title, text = html_to_text(body.decode(enc.group(1) if enc else "utf-8", "replace"))
                title = r["title"] or title
            if len(text) > 200:
                pages.append({"url": final, "title": title, "text": text})
        except Exception as e:
            logging.info("Bo qua %s: %s", r["url"], e)
    return pages


def best_passages(pages, question, budget=8000):
    chunks = []
    for p in pages:
        for c in knowledge.chunk_text(p["text"], size=1200):
            chunks.append({"text": c["text"], "loc": c["loc"], "source": p["title"][:120], "url": p["url"]})
    hits = knowledge.rank(chunks, question, k=12)
    out, used = [], 0
    for h in hits:
        if used + len(h["text"]) > budget:
            break
        out.append(h)
        used += len(h["text"])
    return out

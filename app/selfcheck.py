"""TU KIEM TRA LOI, KHONG TAI PHAM (Dac ta muc 11).
Lop 1: kiem tra tu dong bang chuong trinh (chinh xac, khong phu thuoc AI).
Lop 2: AI phan bien doc lai lan hai (vai tro khac voi vai tro da soan).
Ket qua: ban da tu sua + phieu tu kiem tra (da kiem tra gi, da sua gi, con gi can ban xac nhan)."""
import datetime as dt
import json
import logging
import re

from . import docio, learning, llm, power

DOC_MODES = {"van_ban", "lanh_dao", "giao_vien"}
LEGAL_RE = re.compile(r"\b(\d{1,5}/\d{4}/[A-ZĐ][A-ZĐa-z0-9\-]*)", re.U)
DATE_RE = re.compile(r"(trước ngày|hạn chót|hạn nộp|chậm nhất (?:là )?ngày|hoàn thành trước)\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", re.I)

CRITIC_PROMPT = """Bạn là NGƯỜI PHẢN BIỆN độc lập, nghiêm khắc (không phải người soạn). Đọc kỹ bản dưới đây được soạn cho yêu cầu:
"{q}"

Kiểm tra: mâu thuẫn nội dung; thiếu mục bắt buộc (với kế hoạch/thông báo: tổ chức thực hiện, phân công, thời hạn, chế độ báo cáo);
nhiệm vụ thiếu người phụ trách hoặc thiếu hạn; nhận định không có căn cứ; số liệu, phép tính sai; câu dài, lặp ý, rườm rà;
văn phong không phù hợp; vi phạm các quy tắc trong Sổ tay phong cách và Sổ lỗi (nếu có ở phần lời dặn).
Trả về DUY NHẤT JSON:
{{"van_de": [{{"muc": "vị trí ngắn", "mo_ta": "vấn đề"}}],
  "sua": [{{"tim": "đoạn NGUYÊN VĂN ngắn cần sửa (chép đúng từng chữ trong bản)", "thay": "đoạn thay thế"}}],
  "can_xac_nhan": ["điều cần người dùng cung cấp/xác nhận (số liệu thật, tên người...)"]}}
KHÔNG chép lại toàn bộ bản; chỉ liệt kê tối đa 8 chỗ sửa quan trọng nhất. Bản tốt thì để các danh sách rỗng.

=== BẢN CẦN KIỂM TRA ===
{text}"""


def rule_checks(text: str, library=None) -> tuple:
    """Tra ve (van_ban_da_sua, danh_sach_van_de)."""
    issues, fixed = [], text
    # 1. So loi: cum tu sai -> tu sua
    for e in learning.load()["errors"]:
        if e.get("trang_thai") != "ap_dung":
            continue
        bad, good = e.get("cum_tu_sai", ""), e.get("cum_tu_dung", "")
        if bad and bad in fixed:
            n = fixed.count(bad)
            if good:
                fixed = fixed.replace(bad, good)
                issues.append({"muc": "Sổ lỗi", "mo_ta": f"Thay “{bad}” → “{good}” ({n} chỗ)", "da_sua": True})
            else:
                issues.append({"muc": "Sổ lỗi", "mo_ta": f"Còn dùng “{bad}” ({n} chỗ) – {e['noi_dung']}", "da_sua": False})
    # 2. The thuc (khi la van ban theo khuon)
    d = docio.parse_draft(fixed)
    if d["loai"]:
        if not d["trich_yeu"]:
            issues.append({"muc": "Thể thức", "mo_ta": "Thiếu trích yếu nội dung", "da_sua": False})
        if not d["noi_nhan"]:
            issues.append({"muc": "Thể thức", "mo_ta": "Thiếu Nơi nhận", "da_sua": False})
        elif "lưu" not in d["noi_nhan"].lower():
            fixed = fixed.replace(d["noi_nhan"], d["noi_nhan"].rstrip() + "\n- Lưu: VT.", 1)
            issues.append({"muc": "Thể thức", "mo_ta": "Nơi nhận thiếu “Lưu: VT” – đã bổ sung", "da_sua": True})
        if not d["chuc_vu"]:
            issues.append({"muc": "Thể thức", "mo_ta": "Thiếu chức vụ người ký", "da_sua": False})
    # 3. Can cu phap ly: co trong thu muc 02 khong, co het hieu luc khong
    if library is not None:
        for so in sorted(set(LEGAL_RE.findall(fixed)))[:10]:
            where = library.find_number(so)
            if where == "het_hieu_luc":
                issues.append({"muc": "Căn cứ", "mo_ta": f"{so} nằm trong thư mục Het_hieu_luc – kiểm tra văn bản thay thế", "da_sua": False})
            elif where is None:
                issues.append({"muc": "Căn cứ", "mo_ta": f"{so} chưa có trong 02_NGUON_CAN_CU để đối chiếu – cần kiểm tra số hiệu, hiệu lực", "da_sua": False})
    # 4. Han: roi vao ngay nghi hoac da qua
    today = dt.date.today()
    for m in DATE_RE.finditer(fixed):
        try:
            day = dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        except ValueError:
            issues.append({"muc": "Thời hạn", "mo_ta": f"Ngày không hợp lệ: {m.group(0)}", "da_sua": False})
            continue
        if day < today:
            issues.append({"muc": "Thời hạn", "mo_ta": f"Hạn {day:%d/%m/%Y} đã qua", "da_sua": False})
        elif day.weekday() >= 5:
            issues.append({"muc": "Thời hạn", "mo_ta": f"Hạn {day:%d/%m/%Y} rơi vào {'Thứ Bảy' if day.weekday() == 5 else 'Chủ nhật'}", "da_sua": False})
    # 5. Cong tong trong bang
    for b in docio.parse_blocks(fixed):
        if b[0] != "table" or len(b[1]) < 3:
            continue
        rows = b[1]
        last = rows[-1]
        if not re.search(r"(tổng|cộng)", " ".join(last).lower()):
            continue
        for ci in range(1, len(last)):
            tot = docio._to_number(last[ci].replace("**", "")) if ci < len(last) else None
            vals = [docio._to_number(r[ci].replace("**", "")) for r in rows[1:-1] if ci < len(r)]
            if tot is None or not vals or any(v is None for v in vals):
                continue
            s = round(sum(vals), 2)
            if abs(s - tot) > 0.01:
                issues.append({"muc": "Số liệu", "mo_ta": f"Dòng tổng cột “{rows[0][ci]}” ghi {tot}, cộng lại được {s}", "da_sua": False})
    return fixed, issues


def ai_critic(cfg, question: str, text: str, system_addon: str = "") -> dict:
    try:
        raw = llm.chat(cfg, "Bạn là chuyên gia thẩm định văn bản, phản biện độc lập. " + system_addon,
                       [{"role": "user", "content": CRITIC_PROMPT.format(q=question[:500], text=text[:12000])}],
                       json_mode=True, max_tokens=900)
        return learning._json(raw)
    except llm.LLMError:
        raise
    except Exception as e:
        logging.warning("Phan bien AI loi: %s", e)
        return {}


def run(cfg, mode: str, question: str, reply: str, library=None) -> str:
    """Chay 2 lop kiem tra. Tra ve cau tra loi (da tu sua) + phieu tu kiem tra."""
    if not cfg.get("tu_kiem_tra", True) or mode not in DOC_MODES or len(reply) < 400:
        return reply
    text, issues = rule_checks(reply, library)
    confirm = []
    # Lop 2 (AI phan bien): khi dung pin chi chay neu nguoi dung bat "phan_bien_khi_dung_pin"
    run_ai = cfg.get("phan_bien_ai", True) and (power.profile(cfg) == "hieu_nang" or cfg.get("phan_bien_khi_dung_pin", False))
    if run_ai:
        res = ai_critic(cfg, question, text, learning.prompt_addon(question))
        applied = 0
        for fx in (res.get("sua") or [])[:8]:   # sua tung cho (khong viet lai ca ban -> nhanh, it ton pin)
            if isinstance(fx, dict) and fx.get("tim") and fx.get("thay") is not None and fx["tim"] in text and len(fx["tim"]) >= 4:
                text = text.replace(fx["tim"], fx["thay"], 1)
                applied += 1
                issues.append({"muc": "Phản biện", "mo_ta": f"“{fx['tim'][:60]}” → “{str(fx['thay'])[:60]}”", "da_sua": True})
        if applied:
            text, more = rule_checks(text, library)
            issues += [i for i in more if i["da_sua"]]
        for v in res.get("van_de", [])[:10]:
            if isinstance(v, dict) and v.get("mo_ta"):
                issues.append({"muc": v.get("muc", "Phản biện"), "mo_ta": v["mo_ta"], "da_sua": False})
        confirm = [c for c in res.get("can_xac_nhan", []) if isinstance(c, str) and c.strip()][:8]
    fixed = [i for i in issues if i["da_sua"]]
    pending = [i for i in issues if not i["da_sua"]]
    lines = ["", "---", "**🔎 Phiếu tự kiểm tra** " + ("(2 lớp: kiểm tra tự động + phản biện)" if run_ai else
                                                   "(kiểm tra tự động; lớp phản biện AI tạm tắt khi dùng pin)")]
    if not issues and not confirm:
        lines.append("- Không phát hiện vấn đề.")
    if fixed:
        lines.append("**Đã tự sửa:** " + "; ".join(f"{i['muc']}: {i['mo_ta']}" for i in fixed))
    if pending:
        lines.append("**Cần bạn xem:**")
        lines += [f"- ⚠ {i['muc']}: {i['mo_ta']}" for i in pending]
    if confirm:
        lines.append("**Cần bạn xác nhận/cung cấp:**")
        lines += [f"- {c}" for c in confirm]
    return text.rstrip() + "\n" + "\n".join(lines)


def strip_report(text: str) -> str:
    """Bo phieu tu kiem tra khi xuat Word/Excel."""
    return text.split("\n---\n**🔎 Phiếu tự kiểm tra**")[0].rstrip()

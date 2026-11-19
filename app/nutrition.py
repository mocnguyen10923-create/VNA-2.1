"""Dinh duong gia dinh: thuc don tuan/thang, bang tich chon mon da dung, phan tich & khuyen nghi bo sung.
Danh cho nguoi truong thanh va trung nien khoe manh. Khong thay the tu van cua bac si/chuyen gia dinh duong lam sang."""
import datetime as dt
import json
import threading

from . import config as cfgmod

_LOCK = threading.Lock()

# Nhom thuc pham & mon thuong dung trong bua com gia dinh Viet
GROUPS = [
    {"id": "ngu_coc", "ten": "Ngũ cốc, tinh bột", "items": ["Cơm trắng", "Cơm gạo lứt", "Bún / phở / miến", "Bánh mì", "Khoai lang / khoai tây", "Ngô", "Yến mạch / ngũ cốc nguyên hạt"]},
    {"id": "rau", "ten": "Rau xanh, củ", "items": ["Rau muống / rau cải", "Rau ngót / mồng tơi / rau dền", "Bông cải / bắp cải", "Cà rốt / bí đỏ", "Cà chua / dưa chuột", "Rau thơm, salad", "Canh rau"]},
    {"id": "trai_cay", "ten": "Trái cây", "items": ["Chuối", "Cam / quýt / bưởi", "Táo / lê", "Đu đủ / xoài", "Ổi / thanh long", "Dưa hấu / nho"]},
    {"id": "ca", "ten": "Cá, hải sản", "items": ["Cá biển (thu, ngừ, nục…)", "Cá đồng (rô, chép, trắm…)", "Tôm / cua / ốc", "Mực / nghêu / hến"]},
    {"id": "thit", "ten": "Thịt, trứng", "items": ["Thịt lợn nạc", "Thịt bò", "Thịt gà / vịt", "Trứng", "Nội tạng (gan, lòng…)"]},
    {"id": "dau_hat", "ten": "Đậu, đỗ, hạt", "items": ["Đậu phụ", "Đậu đỗ (đậu đen, xanh, đỏ)", "Lạc / vừng", "Hạt điều / óc chó / hạnh nhân", "Sữa đậu nành"]},
    {"id": "sua", "ten": "Sữa, chế phẩm sữa", "items": ["Sữa tươi (ít đường / không đường)", "Sữa chua", "Phô mai"]},
    {"id": "nuoc", "ten": "Nước", "items": ["Uống đủ 1,5–2 lít nước"]},
    {"id": "chien", "ten": "⚠ Đồ chiên rán, nhiều mỡ", "items": ["Đồ chiên rán", "Thịt mỡ / da", "Đồ ăn nhanh"], "han_che": True},
    {"id": "man", "ten": "⚠ Đồ mặn, chế biến sẵn", "items": ["Dưa muối / cà muối", "Giò chả / xúc xích / lạp xưởng", "Mì tôm / đồ hộp", "Nước chấm nhiều"], "han_che": True},
    {"id": "ngot", "ten": "⚠ Đồ ngọt", "items": ["Nước ngọt có ga / trà sữa", "Bánh kẹo / chè ngọt"], "han_che": True},
    {"id": "ruou", "ten": "⚠ Rượu, bia", "items": ["Rượu / bia"], "han_che": True},
]

# Muc tieu so ngay co mat trong 7 ngay (khuyen nghi chung cho nguoi lon khoe manh) va goi y bo sung
TARGETS = {
    "ngu_coc": (7, "Ăn đủ tinh bột mỗi bữa; thay một phần cơm trắng bằng gạo lứt, khoai lang, ngô, yến mạch để thêm chất xơ."),
    "rau": (7, "Ăn rau ở **mọi bữa chính** (khoảng nửa đĩa): rau lá xanh đậm như rau ngót, cải xanh, mồng tơi, bông cải; thêm cà rốt, bí đỏ."),
    "trai_cay": (7, "Ăn trái cây **mỗi ngày** (1–2 phần, sau bữa ăn): ổi, cam, bưởi, chuối, đu đủ – bổ sung vitamin C, kali, chất xơ."),
    "ca": (3, "Ăn cá **ít nhất 2–3 bữa/tuần**, ưu tiên cá biển (thu, ngừ, nục, hồi) – giàu omega-3 tốt cho tim mạch, trí não."),
    "thit": (4, "Duy trì đạm nạc vừa phải: thịt nạc, gà bỏ da, trứng (3–4 quả/tuần). Hạn chế nội tạng và thịt mỡ."),
    "dau_hat": (4, "Thêm đạm thực vật: đậu phụ, đậu đỗ, sữa đậu nành; một nắm nhỏ hạt (lạc, vừng, óc chó) vài lần/tuần."),
    "sua": (5, "Bổ sung canxi: 1–2 cốc sữa ít đường hoặc hộp sữa chua mỗi ngày; thêm tôm tép, cá nhỏ ăn cả xương, đậu phụ, rau lá xanh đậm. Đặc biệt quan trọng ở tuổi trung niên (phòng loãng xương)."),
    "nuoc": (7, "Uống đủ 1,5–2 lít nước/ngày, chia đều; ưu tiên nước lọc, nước rau luộc, trà không đường."),
}
LIMITS = {
    "chien": (2, "Giảm đồ chiên rán: chuyển sang luộc, hấp, kho nhạt, nướng; dùng dầu thực vật lượng vừa phải."),
    "man": (2, "Giảm muối: hạn chế dưa cà muối, giò chả, mì tôm, đồ hộp; chấm nhạt, nêm ít muối/nước mắm – tốt cho huyết áp."),
    "ngot": (1, "Hạn chế nước ngọt, trà sữa, bánh kẹo; thay bằng trái cây tươi, nước lọc, sữa chua không đường."),
    "ruou": (1, "Hạn chế rượu bia tối đa; không uống hằng ngày."),
}


def _path():
    return cfgmod.data_dir() / "dinh_duong.json"


def load():
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("profile", {"so_nguoi": 4, "thanh_vien": "2 người trưởng thành (30–49 tuổi), 2 người trung niên (50–64 tuổi)",
                             "suc_khoe": "", "vung_mien": "Miền Bắc", "ngan_sach": "trung bình", "so_thich": ""})
    d.setdefault("log", {})
    return d


def save(d):
    with _LOCK:
        _path().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def set_day(day: str, items: list):
    d = load()
    d["log"][day] = sorted(set(items))
    save(d)
    return d["log"][day]


def set_profile(p: dict):
    d = load()
    d["profile"].update({k: v for k, v in p.items() if k in d["profile"]})
    save(d)
    return d["profile"]


def _group_of(item: str):
    for g in GROUPS:
        if item in g["items"]:
            return g["id"]
    return None


def analyze(days: int = 7) -> dict:
    """Phan tich theo quy tac: nhom nao thieu, nhom nao qua nhieu trong `days` ngay qua."""
    d = load()
    today = dt.date.today()
    rng = [(today - dt.timedelta(days=i)).isoformat() for i in range(days)]
    logged = [k for k in rng if d["log"].get(k)]
    count = {g["id"]: 0 for g in GROUPS}
    item_freq = {}
    for k in logged:
        groups_today = set()
        for it in d["log"][k]:
            gid = _group_of(it)
            if gid:
                groups_today.add(gid)
                item_freq[it] = item_freq.get(it, 0) + 1
        for gid in groups_today:
            count[gid] += 1
    n = len(logged) or 1
    scale = n / 7  # quy doi muc tieu theo so ngay da ghi
    thieu, du, tot = [], [], []
    names = {g["id"]: g["ten"] for g in GROUPS}
    for gid, (target, tip) in TARGETS.items():
        need = max(1, round(target * scale))
        if count[gid] < need:
            thieu.append({"nhom": names[gid], "co": count[gid], "nen": need, "khuyen_nghi": tip})
        else:
            tot.append(names[gid])
    for gid, (limit, tip) in LIMITS.items():
        lim = max(1, round(limit * scale)) if limit else 0
        if count[gid] > lim:
            du.append({"nhom": names[gid], "co": count[gid], "toi_da": lim, "khuyen_nghi": tip})
    return {"so_ngay_ghi": len(logged), "tu_ngay": rng[-1], "den_ngay": rng[0], "dem": count, "thieu": thieu, "du": du, "tot": tot,
            "mon_hay_dung": sorted(item_freq.items(), key=lambda x: -x[1])[:10], "profile": d["profile"]}


def analysis_markdown(a: dict) -> str:
    out = [f"### Kết quả theo dõi {a['so_ngay_ghi']} ngày gần nhất"]
    if not a["so_ngay_ghi"]:
        return "Chưa có dữ liệu. Hãy tích chọn các món đã dùng trong ngày để VNA phân tích."
    if a["thieu"]:
        out += ["**Nhóm thực phẩm cần BỔ SUNG:**", "| Nhóm | Số ngày đã có | Nên có | Khuyến nghị |", "|---|---|---|---|"]
        out += [f"| {x['nhom']} | {x['co']} | ≥ {x['nen']} | {x['khuyen_nghi']} |" for x in a["thieu"]]
    if a["du"]:
        out += ["", "**Nhóm cần HẠN CHẾ:**", "| Nhóm | Số ngày đã dùng | Nên tối đa | Khuyến nghị |", "|---|---|---|---|"]
        out += [f"| {x['nhom']} | {x['co']} | {x['toi_da']} | {x['khuyen_nghi']} |" for x in a["du"]]
    if a["tot"]:
        out += ["", "**Đã đạt tốt:** " + ", ".join(a["tot"]) + "."]
    return "\n".join(out)


def ai_prompt(kind: str, extra: str = "") -> str:
    d = load()
    p = d["profile"]
    prof = (f"Gia đình {p['so_nguoi']} người: {p['thanh_vien']}. Vùng miền: {p['vung_mien']}. Ngân sách: {p['ngan_sach']}. "
            f"Lưu ý sức khỏe: {p['suc_khoe'] or 'không'}. Sở thích/kiêng: {p['so_thich'] or 'không'}.")
    if kind == "tuan":
        return (f"{prof}\nĐề xuất THỰC ĐƠN 1 TUẦN (Thứ Hai → Chủ nhật) cho gia đình. Trình bày bảng | Ngày | Bữa sáng | Bữa trưa | Bữa tối | Bữa phụ |, "
                "mỗi bữa trưa/tối gồm món mặn – món rau – món canh – tráng miệng trái cây; đa dạng, không lặp món trong 3 ngày liên tiếp, "
                "cân đối các nhóm chất, ít muối, ít đường, ít chiên rán. Sau bảng: 1) DANH SÁCH ĐI CHỢ cả tuần theo nhóm (ước lượng số lượng cho cả nhà); "
                "2) Gợi ý điều chỉnh riêng cho người trung niên và người có lưu ý sức khỏe; 3) Mẹo chế biến giữ dinh dưỡng. " + extra)
    if kind == "thang":
        return (f"{prof}\nĐề xuất KẾ HOẠCH THỰC ĐƠN 1 THÁNG (4 tuần) cho gia đình. Với mỗi tuần: bảng | Ngày | Bữa sáng | Bữa trưa | Bữa tối | "
                "(món ngắn gọn), xoay vòng nguồn đạm (cá ≥ 3 bữa/tuần, đậu phụ/đậu đỗ, thịt nạc, trứng), rau và trái cây theo mùa. "
                "Cuối cùng: nguyên tắc dinh dưỡng của tháng, danh sách thực phẩm khô dự trữ, gợi ý ngân sách. " + extra)
    a = analyze(7)
    return (f"{prof}\nĐây là kết quả theo dõi bữa ăn {a['so_ngay_ghi']} ngày gần nhất của tôi (số ngày có dùng mỗi nhóm): "
            f"{json.dumps(a['dem'], ensure_ascii=False)}. Món hay dùng: {a['mon_hay_dung']}.\n"
            f"Nhóm còn thiếu: {[x['nhom'] for x in a['thieu']]}. Nhóm dùng quá nhiều: {[x['nhom'] for x in a['du']]}.\n"
            "Với vai trò chuyên gia dinh dưỡng, hãy: 1) Nhận xét ngắn chế độ ăn hiện tại; 2) Liệt kê CỤ THỂ thực phẩm cần bổ sung "
            "(món Việt dễ mua, cách chế biến, tần suất trong tuần); 3) Thực phẩm cần giảm và món thay thế; "
            "4) Thực đơn mẫu 3 ngày tới đã điều chỉnh. " + extra)

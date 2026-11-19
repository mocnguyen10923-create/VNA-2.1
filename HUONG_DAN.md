# VNA – AI CHUYÊN GIA CỦA CÁC CHUYÊN GIA
### Hướng dẫn cài đặt và sử dụng (phiên bản 2.1)

VNA là phần mềm trợ lý AI cài trên laptop, chuyên sâu về: **khoa học giáo dục · giảng dạy (giáo án, tài liệu, đề kiểm tra, chấm bài, nhận xét học sinh) · nghiên cứu văn bản pháp luật · soạn thảo văn bản hành chính · lãnh đạo, quản lý trường THCS và THPT · lập trình, thiết kế phần mềm · dinh dưỡng gia đình**.

> **Việc của bạn:** chép công văn vào **01_VAN_BAN_DEN**, duyệt nhiệm vụ VNA đề xuất, sửa và ký dự thảo, đặt bản đã ký vào **04_SAN_PHAM\Da_ban_hanh**. VNA làm phần còn lại.

---

## 1. Cam kết miễn phí – bảo mật – tuân thủ pháp luật

- **Miễn phí hoàn toàn:** không tài khoản, không quảng cáo, không thu phí, không thu thập dữ liệu. Bộ não AI (Ollama + mô hình mở Qwen) đều miễn phí.
- **Chế độ “Hoàn toàn ngoại tuyến” bật sẵn:** VNA chặn mọi kết nối Internet, chỉ làm việc trên chính máy tính của bạn. Không có máy chủ trung gian nào điều khiển VNA.
- **Tra cứu nguồn chính thống (tùy chọn, bật sẵn):** khi cần thông tin hiện hành, VNA **chỉ** mở các trang chính thống của Nhà nước (.gov.vn, chinhphu.vn, vbpl.vn, quochoi.vn, baochinhphu.vn…). Trang ngoài danh sách bị chặn, kể cả khi chuyển hướng. VNA chỉ gửi **từ khóa tìm kiếm** (qua công cụ tìm kiếm DuckDuckGo), không gửi tài liệu của bạn. Có thể tắt trong Cài đặt.
- **Chỉ làm việc trong thư mục bạn cho phép.** Không bao giờ xóa tài liệu: tài liệu trùng được **chuyển** vào `_TRUNG_LAP`, mọi lần sắp xếp đều xem trước, ghi nhật ký và **hoàn tác được**.
- Không quản lý ổ đĩa gốc, thư mục Windows, Program Files hay thư mục hệ thống.
- Phần mềm chỉ nhận lệnh từ chính máy này (127.0.0.1) và chặn yêu cầu từ trang web lạ.
- VNA từ chối các yêu cầu vi phạm pháp luật Việt Nam (làm giả giấy tờ, gian lận, xâm phạm bí mật nhà nước, dữ liệu cá nhân, xâm nhập hệ thống, mã độc…).
- **Tài liệu mật:** chỉ dùng chế độ mô hình trên máy (mặc định). Không bật Claude API (dịch vụ trả phí, có gửi dữ liệu ra ngoài) cho tài liệu mật.
- VNA chỉ **tham mưu**. Mọi văn bản phải được người có thẩm quyền kiểm tra trước khi ký ban hành; luôn đối chiếu hiệu lực văn bản pháp luật.

---

## 2. Cấu hình máy khuyến nghị

| Thành phần | Tối thiểu | Khuyến nghị |
|---|---|---|
| Hệ điều hành | Windows 10 (64-bit) | Windows 11 |
| RAM | 8 GB (dùng mô hình `qwen2.5:3b`) | 16 GB trở lên (`qwen2.5:7b`) |
| Ổ cứng trống | 10 GB | 20 GB, ổ SSD |
| Microsoft Office | Word, Excel 2016 | Office 2019/2021/365 |

---

## 3. Cài đặt: chỉ một bước

**Bấm đúp `VNA_Setup.exe`, rồi bấm Install.** Mọi thứ còn lại VNA tự làm:

| VNA tự động làm | Ghi chú |
|---|---|
| Tạo biểu tượng VNA và “Thư mục VNA quản lý” trên Desktop, tạo đủ 3 thư mục con | |
| Đặt VNA tự chạy ngầm khi bật máy (để nhắc việc, xử lý văn bản đến) | |
| Cài macro VNA vào Word và Excel | Nên đóng Word và Excel trước khi cài |
| Cài giọng đọc tiếng Việt của Windows | Windows hỏi “Cho phép thay đổi?” **một lần**: bấm **Yes** |
| Mở VNA, VNA **tự cài bộ não AI (Ollama)** và **tự chọn, tự tải mô hình hợp với RAM của máy** (16 GB trở lên: `qwen2.5:7b`; nhỏ hơn: `qwen2.5:3b`) | Cần Internet **một lần**, khoảng 2–5 GB. Thanh tiến độ màu vàng hiện ở đầu cửa sổ. Bạn vẫn dùng các chức năng khác trong lúc chờ |

Nếu mất mạng hoặc tắt máy giữa chừng, VNA **tự làm tiếp** ở lần mở sau, hoặc bạn bấm **Thử lại** trên thanh tiến độ. Cuối cùng VNA báo “✅ VNA đã cài đặt xong”.

> Windows SmartScreen có thể hiện “Windows protected your PC” vì bộ cài chưa có chữ ký số. Bấm **More info → Run anyway**.

## 4. Năm thư mục quản lý (phiên bản 2.0)

Nằm tại `Documents\VNA\Quản lý công việc` (có lối tắt trên Desktop):

| Thư mục | Bạn làm | VNA làm |
|---|---|---|
| **01_VAN_BAN_DEN** | Chép công văn mới vào (Word, PDF có chữ, Excel) | Ghi sổ đến, tóm tắt, xác định hạn trả lời, **đề xuất nhiệm vụ** chờ bạn duyệt, lập phiếu xử lý, đặt tên chuẩn rồi xếp vào `Da_xu_ly\Năm\Tháng`. Bản trùng chuyển vào `_TRUNG_LAP` |
| **02_NGUON_CAN_CU** | Đặt luật, nghị định, thông tư, hướng dẫn của Bộ/Sở, chương trình GDPT 2018, quy chế trường. Văn bản hết hiệu lực chuyển vào `Het_hieu_luc` | Dùng làm **căn cứ**, trích dẫn Điều/Khoản; cảnh báo khi dự thảo viện dẫn văn bản hết hiệu lực hoặc chưa có để đối chiếu |
| **03_TAI_LIEU_THAM_KHAO** | Sách, chuyên đề, mẫu văn bản hay, giáo án và đề mẫu | Dùng để **tham khảo**, không dùng làm căn cứ pháp lý |
| **04_SAN_PHAM\Du_thao** | Mở, sửa dự thảo VNA soạn | Lưu mọi sản phẩm theo `Năm\Tháng\Loại` |
| **04_SAN_PHAM\Da_ban_hanh** | **Đặt bản chính thức đã ký** (Word hoặc PDF) | Ghi sổ đi; **đóng các nhiệm vụ** của công văn đã trả lời; **đề xuất việc cần đôn đốc** từ phần phân công; **học phong cách** từ phần bạn đã sửa |
| **05_THEO_DOI** | Xem, in | Tự cập nhật sổ văn bản đến, sổ văn bản đi, bảng nhiệm vụ (2 trang: việc tôi phải làm, việc đã giao) và nhật ký |

Thư mục cũ của phiên bản 1.x được VNA tự chuyển sang cấu trúc mới, không mất file.

**Một công văn đi trọn vòng:** chép vào 01 → VNA đề xuất nhiệm vụ → bạn duyệt → VNA soạn dự thảo → bạn sửa, ký, đặt vào Da_ban_hanh → VNA đóng nhiệm vụ, nhắc đôn đốc việc đã giao, học phong cách cho lần sau.

## 5. Mỗi ngày làm việc với VNA

Cột trái có **6 khu vực**: ☀ Hôm nay · 📄 Văn bản · ✅ Công việc · 🤖 Hỏi chuyên gia · 🧑‍🏫 Chuyên môn · 🏠 Cá nhân.

1. Mở VNA, màn hình **Hôm nay** hiện ra và VNA đọc to lời chào. Màn hình gồm:
    - văn bản mới đến (khẩn có dấu 🔴);
    - **nhiệm vụ đề xuất chờ duyệt**: bấm *Duyệt tất cả*, hoặc *Xem và duyệt* để duyệt từng việc;
    - **công văn sắp hết hạn trả lời** mà chưa có văn bản;
    - **việc tôi phải làm** trong 3 ngày tới, có ô tích *Xong*;
    - **việc cần chỉ đạo, đôn đốc** (việc đã giao), có cột người thực hiện và tình trạng;
    - **sáng kiến cải tiến** VNA đề xuất, nếu có.
2. Làm xong việc nào thì tích ô *Xong*. Bảng Excel trong 05_THEO_DOI tự cập nhật.
3. Đến giờ, VNA nhắc việc bằng thông báo Windows và đọc to.
4. Cuối ngày: **Công việc → Nhật ký → AI tổng kết ngày**.

## 6. Chuyên gia trả lời, tự kiểm tra, học tập

**6 chuyên gia:** Lãnh đạo nhà trường · Văn bản – pháp lý · Giáo viên – chuyên gia giáo dục · Nghiên cứu – số liệu · Lập trình – thiết kế phần mềm · Dinh dưỡng gia đình. Để **Tự động chọn chuyên gia** thì VNA chọn theo câu hỏi; tên chuyên gia đã trả lời hiện phía trên câu trả lời.

**Tôn chỉ làm việc** được cài vào mọi chuyên gia:
- tâm (vì học sinh, trung thực, nhân văn);
- tầm (tác động lâu dài);
- phương pháp khoa học (vấn đề → căn cứ → phân tích → phương án → kiến nghị);
- lý luận sắc bén;
- gọn gàng, kết luận trước;
- chủ động đề xuất sáng kiến.

**Phiếu tự kiểm tra:** cuối mỗi văn bản soạn ra có phiếu nêu những gì VNA đã tự sửa, những gì cần bạn xem, và những gì cần bạn cung cấp. VNA kiểm tra hai lớp:
- **Lớp 1 – chương trình kiểm tra:** thể thức, Nơi nhận, căn cứ có trong thư mục 02 không hoặc đã hết hiệu lực chưa, hạn rơi vào ngày nghỉ hoặc đã qua, cộng lại dòng tổng, Sổ lỗi.
- **Lớp 2 – AI phản biện đọc lại.**

Khi xuất Word, phiếu này được bỏ ra. Có thể tắt lớp 2 trong Cài đặt nếu muốn nhanh hơn.

**🧠 Học tập (nút trên thanh đầu):**
- **Sổ tay phong cách:** quy tắc VNA rút ra từ bản bạn đã sửa và từ nút 👍/👎. Quy tắc mới ở trạng thái *chờ*; gặp lại lần 2 hoặc bạn duyệt thì chuyển sang *áp dụng*.
- **Sổ lỗi:** lỗi đã sửa một lần sẽ được kiểm tra mãi về sau. Lỗi từ ngữ thì VNA tự thay.
- **Tiến bộ:** tỷ lệ nội dung bạn phải sửa theo tháng; định dạng (phông, cỡ chữ, lề, giãn dòng) VNA đã học theo từng loại văn bản. Lần xuất Word sau dùng đúng định dạng đó.
- **Sáng kiến:** VNA phân tích số liệu làm việc thật (việc quá hạn, việc lặp lại, tỷ lệ phải sửa…) và đề xuất sáng kiến kèm kế hoạch và hướng dẫn từng bước. Bấm *Triển khai* thì các bước thành nhiệm vụ; bấm *Bỏ qua* thì VNA không đề xuất lại.

Dưới mỗi câu trả lời có nút **👍 / 👎**. Bấm 👎 rồi gõ "lần sau hãy…", VNA ghi vào Sổ tay và làm theo từ lần sau.

**Giới hạn:** VNA "học" bằng cách tích lũy quy tắc, mẫu và ví dụ của riêng bạn. VNA không tự thay bộ não AI và không tự sửa mã nguồn. Bạn vẫn là người duyệt cuối.

**🌐 Nguồn chính thống:** tích ô này cạnh nút Gửi để VNA tra cứu thông tin hiện hành **chỉ** trên các trang của Nhà nước (.gov.vn, chinhphu.vn, vbpl.vn…) và ghi link nguồn. Câu hỏi có các từ "mới nhất", "hiện hành", "còn hiệu lực" thì VNA tự tra. Chức năng này cần Internet.

### 🧑‍🏫 Chuyên môn (khu vực bên trái)
- **Soạn giáo án** theo Công văn 5512, tài liệu, đề cương, phiếu học tập, ma trận, bản đặc tả, đề và đáp án: gõ yêu cầu vào ô chat.
- **✅ Chấm bài hàng loạt:** chọn file đáp án và nhiều file bài làm đánh máy. VNA chấm từng câu, xuất bảng điểm Excel và file Word chi tiết. Bài viết tay được đánh dấu để chấm tay.
- **💬 Nhận xét học sinh theo Thông tư 22:** chọn file Excel bảng điểm. VNA thêm cột nhận xét vào **bản sao**.
- Nên chép **Chương trình môn học GDPT 2018** vào `02_NGUON_CAN_CU\Chuong_trinh_GDPT_2018` để VNA bám đúng yêu cầu cần đạt.

Dưới mỗi câu trả lời có các nút: **Sao chép**, **Mở bằng Word** (tự trình bày Quốc hiệu, tiêu ngữ, số ký hiệu, nơi nhận, chữ ký), **Xuất Excel**, **Đọc to**, **Dừng đọc**, **Lưu file giọng đọc**.

**Cài đặt → Thể thức mặc định:** nhập một lần tên trường, cơ quan chủ quản, ký hiệu, địa danh, chức vụ, người ký. Ở mục **Người dùng & lời chào**, nhập họ tên và cách xưng hô (thầy, cô, anh, chị).

---

### 🍲 Dinh dưỡng gia đình (khu vực Cá nhân)
1. Nhập thông tin **Gia đình tôi**: số người, thành viên (trưởng thành, trung niên), vùng miền, ngân sách, lưu ý sức khỏe, sở thích.
2. Bấm **📅 Đề xuất thực đơn 1 tuần** hoặc **🗓 Thực đơn 1 tháng**. VNA lập bảng thực đơn theo từng bữa, kèm **danh sách đi chợ** và mẹo chế biến. Có thể **Mở bằng Word** hoặc **Xuất Excel** để in dán bếp.
3. Mỗi ngày, ở mục **“Hôm nay tôi đã dùng”**, **tích chọn** các món đã ăn. VNA tự lưu theo ngày.
4. Mục **Phân tích 7 ngày** cho biết ngay nhóm thực phẩm còn thiếu (rau, trái cây, cá, đậu, sữa, nước…) và nhóm dùng quá nhiều (chiên rán, mặn, ngọt, rượu bia).
5. Bấm **✨ Khuyến nghị thực phẩm cần bổ sung**: VNA nêu cụ thể món cần thêm, món nên giảm và gợi ý thực đơn 3 ngày tới đã điều chỉnh.

Đây là thông tin tham khảo cho người khỏe mạnh. Người có bệnh lý (tiểu đường, huyết áp, gút, thận…) nên hỏi ý kiến bác sĩ.

## 7. Dùng VNA ngay trong Word và Excel

VNA phải đang chạy. Trong Word/Excel bấm **Alt + F8**, chọn macro rồi bấm **Run**. Nên gắn macro lên Ribbon: File → Options → Customize Ribbon → *Choose commands from: Macros*.

**Word:**
| Macro | Chức năng |
|---|---|
| `VNA_ThucHienYeuCau` | Viết yêu cầu vào văn bản (VD: *Soạn công văn gửi các tổ về…*), bôi đen rồi chạy: kết quả chèn ngay bên dưới |
| `VNA_TomTat` | Tóm tắt phần bôi đen (hoặc cả tài liệu), kết quả ra tài liệu mới |
| `VNA_RaSoatVanBan` | Rà soát căn cứ, thể thức, chính tả, lập bảng đề xuất sửa |
| `VNA_BienTapVanPhong` | Biên tập đoạn văn theo văn phong hành chính |
| `VNA_ThamMuuLanhDao` | Phân tích, đề xuất phương án cho lãnh đạo |
| `VNA_NghienCuuChoNhaTruong` | Nhiệm vụ nhà trường phải làm theo văn bản |
| `VNA_PhanTichPhapLy` | Phân tích tình huống pháp lý |
| `VNA_SoanGiaoAn` | Viết yêu cầu (môn, lớp, bài, số tiết), bôi đen rồi chạy: giáo án ra tài liệu mới |
| `VNA_SoanDeKiemTra` | Viết yêu cầu đề, bôi đen rồi chạy: ma trận, đặc tả, đề, đáp án |
| `VNA_DocVanBan` / `VNA_DungDoc` | Đọc to / dừng đọc |

**Excel:** `VNA_NhanXetHocSinh` (chọn bảng gồm dòng tiêu đề, họ tên và điểm: nhận xét ghi vào cột bên phải), `VNA_PhanTichDuLieu` (chọn vùng số liệu), `VNA_TaoBang`, `VNA_VietCongThuc`, `VNA_DocVungChon`, `VNA_DungDoc`.

Nếu chưa cài macro: Start → VNA → **Cài lại macro Word - Excel**. Hoặc trong Word/Excel bấm Alt+F11 → File → Import File → chọn `VNA_Word.bas` / `VNA_Excel.bas` trong thư mục `office`.

---

## 7a. Tiết kiệm pin và tăng tốc (phiên bản 2.1)

Nguyên nhân chính làm tốn pin và chậm là **bộ não AI chạy trên CPU của laptop**. Bản 2.1 giảm việc AI phải làm, mà vẫn giữ đủ tính năng.

| VNA tự làm | Tác dụng |
|---|---|
| **Hai mô hình:** mô hình nhỏ (`qwen2.5:3b`) cho việc trích xuất, phân loại, tìm từ khóa; mô hình chính chỉ dùng khi soạn thảo, trả lời | Phần lớn việc nền nhanh hơn khoảng 2–3 lần |
| **Tự nhận biết dùng pin hay cắm sạc.** Khi dùng pin: mọi việc dùng mô hình nhỏ, giảm số nhân CPU, tắt lớp AI phản biện (lớp kiểm tra tự động vẫn chạy), quét thư mục thưa hơn | Đỡ hao pin rõ rệt |
| **Hoãn việc nặng:** học phong cách, đề xuất sáng kiến, đọc chữ ảnh trong thư viện chỉ chạy khi cắm sạc và bạn không thao tác 2 phút | Không tranh máy với bạn |
| **Tối ưu Ollama một lần:** 1 luồng xử lý, flash attention, nén bộ nhớ đệm, cố định độ dài ngữ cảnh | Giảm mạnh RAM, không phải nạp lại mô hình |
| **Thông tin hành chính lấy bằng quy tắc:** số ký hiệu, ngày ban hành, V/v, độ khẩn | Chính xác, tức thì |
| **AI phản biện chỉ trả về chỗ cần sửa**, không viết lại cả văn bản | Lớp kiểm tra nhanh hơn nhiều |
| **Nhớ kết quả** cho việc lặp lại; ghép dự thảo với bản ban hành bằng "dấu vân tay" | Không làm lại việc đã làm |
| **Hiện chữ ngay khi AI đang viết** | Không phải chờ đến khi xong |
| VNA và Ollama chạy ở mức ưu tiên thấp; giao diện ngừng hỏi máy chủ khi bạn chuyển sang cửa sổ khác | Word/Excel vẫn mượt |

Dòng trạng thái trên cùng cho biết chế độ hiện tại (⚡ Hiệu năng hoặc 🔋 Tiết kiệm pin), mô hình đang dùng, tốc độ (từ/giây) và % pin. Chỉnh trong **Cài đặt → Năng lượng & tốc độ**: Tự động, Luôn tiết kiệm, hoặc Luôn hiệu năng cao.

**Lời khuyên:** soạn văn bản dài khi cắm sạc. Nếu trường có một máy có card đồ họa rời, hãy dùng nó làm **máy chủ AI chung** (Đợt 3); laptop gần như không tốn pin cho AI nữa.

## 7b. Tài liệu dạng ảnh (ảnh chụp, PDF scan)

VNA nhận ảnh **jpg, png, tif, bmp, webp, heic** và **PDF scan** ở mọi nơi: thư mục 01–04, đính kèm, thư viện, chấm bài. VNA đọc chữ bằng **OCR có sẵn của Windows**: offline, miễn phí, rất nhẹ. Bộ cài tự cài gói OCR tiếng Việt cùng lúc với giọng đọc.

- Chụp thẳng, đủ sáng, không nghiêng, mỗi trang một ảnh; VNA tự xoay ảnh theo chiều chụp.
- Chữ đọc từ ảnh có thể sai chính tả, nên VNA ghi chú "đọc bằng OCR" để bạn đối chiếu bản gốc.
- Chữ viết tay thường đọc không tốt.
- Khi rà soát thư mục, VNA không đọc chữ trong ảnh để tiết kiệm pin.

## 8. Quản lý thư mục khác (🗂 Thư mục)

1. **＋ Chọn thư mục…**, chọn thư mục hồ sơ cần dọn (ví dụ `D:\HoSo2025`).
2. Chọn các tùy chọn (xếp theo loại, theo năm, gom tài liệu trùng), rồi bấm **🔎 Rà soát**. VNA lập báo cáo: phân loại, các nhóm trùng (giống hệt hoặc trùng nội dung, kể cả khác định dạng), danh sách đề xuất di chuyển. Bạn có thể **📝 Xuất báo cáo Word**.
3. Đồng ý thì bấm **✔ Thực hiện sắp xếp**. Không vừa ý thì bấm **↶ Hoàn tác**.

---

## 9. Tạo bộ cài VNA_Setup.exe (làm một lần, cho người phụ trách kỹ thuật)

**Cách 1 – không cần cài gì, dùng máy chủ GitHub (miễn phí):**
1. Tạo tài khoản GitHub, tạo kho (repository) mới, tải toàn bộ thư mục VNA lên.
2. Vào tab **Actions**, chọn **Dong goi VNA**, bấm **Run workflow**.
3. Khoảng 5–10 phút sau, tải **VNA_Setup.exe** ở mục **Artifacts**.

**Cách 2 – trên một máy Windows:** cài Python 3.10+ (tích Add to PATH) và Inno Setup 6, rồi bấm đúp **`build.bat`**. Kết quả nằm ở `Output\VNA_Setup.exe`, kèm mã SHA256.

**Cài cho máy không có Internet hoặc cài hàng loạt:**
- Đặt `OllamaSetup.exe` vào thư mục `redist\` (hoặc chạy `set BUNDLE_OLLAMA=1` trước khi chạy `build.bat`).
- Chép thư mục `%USERPROFILE%\.ollama\models` từ một máy đã tải mô hình vào `redist\models\`.
- Bộ cài khi đó kèm sẵn bộ não AI, không cần tải gì thêm.
- Cài im lặng hàng loạt: `VNA_Setup.exe /VERYSILENT`.

**Chống làm giả:** chỉ phát hành bộ cài từ nguồn tin cậy của đơn vị và đối chiếu mã SHA256 trước khi cài: `certutil -hashfile VNA_Setup.exe SHA256`.

## 10. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Thanh vàng “đang tự hoàn tất cài đặt” lâu | Kiểm tra Internet, rồi bấm **Thử lại**. Lần tải đầu mất 10–40 phút tùy tốc độ mạng |
| Trả lời chậm | Bình thường với máy không có card đồ họa rời. Dùng `qwen2.5:3b` cho nhanh hơn, và đóng bớt ứng dụng |
| Không đọc được tiếng Việt | Cài gói giọng nói Tiếng Việt (mục 3, bước 3) |
| Macro báo “Không kết nối được VNA” | Mở VNA trước. Bật “chạy ngầm khi bật máy” |
| PDF không đọc được chữ | Đó là PDF scan dạng ảnh: mở bằng Word để chuyển sang văn bản rồi chép vào lại |
| File .doc / .xls cũ | Mở bằng Word/Excel rồi *Lưu thành* .docx / .xlsx |
| Bảng theo dõi chưa cập nhật | Đóng file Excel đang mở; VNA tự ghi lại sau 1 phút |

Dữ liệu của VNA (cấu hình, công việc, nhật ký, học tập) nằm trong `Documents\VNA`. VNA **tự sao lưu hằng tuần** (giữ 8 bản) vào `Documents\VNA\_sao_luu`. Nên đổi thư mục sao lưu sang USB hoặc ổ khác trong **Cài đặt → Sao lưu**; phục hồi bằng một nút ở cùng chỗ.


---

## Phụ lục – Giấy phép các thành phần

VNA sử dụng các thành phần của bên thứ ba dưới đây. Mỗi thành phần thuộc quyền của chủ sở hữu và chịu giấy phép riêng của nó.

| Thành phần | Vai trò trong VNA | Giấy phép |
|---|---|---|
| Ollama | Chạy mô hình AI trên máy | MIT |
| Qwen2.5 7B, 1.5B (Alibaba) | Mô hình AI | Apache 2.0 |
| Qwen2.5 3B (Alibaba) | Mô hình AI nhỏ | Qwen Research License – hạn chế dùng cho mục đích thương mại |
| Python, python-docx, openpyxl, pypdf, Pillow, truststore, edge-tts | Ngôn ngữ và thư viện | Giấy phép mã nguồn mở của từng dự án (xem trang dự án) |
| PyInstaller, Inno Setup | Đóng gói bộ cài | Giấy phép của từng dự án, cho phép phát hành phần mềm được đóng gói |
| OCR, giọng đọc của Windows | Đọc chữ trong ảnh, đọc to | Thuộc Microsoft Windows trên máy người dùng |

VNA phát hành **miễn phí, phi thương mại**. Nếu sau này muốn dùng VNA vào mục đích thương mại, cần chuyển mô hình nhỏ sang loại có giấy phép Apache 2.0, và rà soát lại giấy phép của từng thành phần.

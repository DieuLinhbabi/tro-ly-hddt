# Hướng dẫn cài đặt "Trợ lý Hóa đơn điện tử"

Làm lần lượt 3 bước. Mỗi bước chỉ cần làm một lần.

## Bước 1. Gắn đoạn kết nối vào Google Sheet

Đoạn kết nối (Apps Script) cho phép trợ lý đọc kiến thức, lưu góp ý vào tab **GopY**, lưu tài khoản vào tab **TaiKhoan** (mật khẩu đã mã hóa) và cho người quản lý sửa bài ngay trên trang quản lý.

1. Mở file Google Sheet **Dữ liệu Trợ lý Hóa đơn điện tử** bằng tài khoản chủ sở hữu (dvkhnhanh.ai@gmail.com).
2. Bấm menu **Tiện ích mở rộng › Apps Script**.
3. Xóa hết code có sẵn, dán toàn bộ nội dung file `apps_script/Code.gs`, rồi bấm **Lưu** (biểu tượng đĩa mềm).
4. Đặt mã bí mật:
   - Bấm biểu tượng bánh răng **Cài đặt dự án** ở cột trái.
   - Kéo xuống mục **Thuộc tính tập lệnh**, bấm **Thêm thuộc tính tập lệnh**.
   - Thuộc tính: `TOKEN`. Giá trị: một chuỗi dài tự đặt, ví dụ `nhanh-hddt-8f3k29xq`. Bấm **Lưu**.
5. Triển khai:
   - Bấm **Triển khai › Tùy chọn triển khai mới**, chọn loại **Ứng dụng web**.
   - **Thực thi dưới dạng:** Tôi. **Người có quyền truy cập:** Bất kỳ ai.
   - Bấm **Triển khai**, rồi bấm **Cấp quyền truy cập** và chọn tài khoản. Nếu Google báo "ứng dụng chưa được xác minh", bấm **Nâng cao › Đi tới… (không an toàn)**. Đây là code của chính anh/chị nên an toàn.
   - Sao chép **URL ứng dụng web** (dạng `https://script.google.com/macros/s/…/exec`).

> Từ giờ Sheet **không cần** chia sẻ "Bất kỳ ai có đường liên kết" nữa. Nếu đã bật thì có thể tắt đi.
>
> Sau này nếu sửa code Apps Script, vào **Triển khai › Quản lý các bản triển khai › Sửa › Phiên bản mới** để cập nhật. Làm vậy thì URL giữ nguyên.

## Bước 2. Đưa code lên GitHub

1. Tạo repository mới, ví dụ `tro-ly-hddt`, chọn **Private**.
2. Tải lên tất cả file trong thư mục này: `app.py`, `hoi_dap.py`, `quan_ly.py`, `common.py`, `requirements.txt`, thư mục `.streamlit/`, `data/`, `images/` và `apps_script/`.

## Bước 3. Chạy trên Streamlit Community Cloud

1. Tạo app mới từ repository vừa tạo, **Main file path** là `app.py`.
2. Vào **Advanced settings › Secrets** và dán đoạn sau, thay bằng giá trị thật:

```toml
GROQ_API_KEY = "khóa Groq của anh/chị"
APPS_SCRIPT_URL = "URL ứng dụng web ở Bước 1"
APPS_SCRIPT_TOKEN = "đúng chuỗi TOKEN đã đặt ở Bước 1"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "mật khẩu tài khoản gốc"
```

3. Bấm **Deploy**.

## Sử dụng

| Ai | Vào đâu | Làm gì |
|---|---|---|
| Người dùng | Địa chỉ trang, ví dụ `https://ten-app.streamlit.app` | Hỏi đáp, không cần đăng nhập. Bấm 👍 / 👎 dưới câu trả lời để góp ý. Bấm 👎 thì có ô ghi lý do. |
| Người quản lý | Địa chỉ trang thêm `/quan-ly`, ví dụ `https://ten-app.streamlit.app/quan-ly` | Đăng nhập bằng tên + mật khẩu. Tài khoản gốc là `ADMIN_USERNAME` / `ADMIN_PASSWORD` trong Secrets, các tài khoản khác do Admin tạo ở mục **Quản lý tài khoản**. |

- Bài sửa trên trang quản lý được lưu thẳng vào Google Sheet, trợ lý dùng ngay.
- Bài sửa trực tiếp trong Sheet thì trợ lý tự nhận sau tối đa 5 phút. Muốn nhận ngay, bấm **Đồng bộ từ Sheet** trên trang quản lý.
- Bài nào chưa có nội dung sẽ chưa được trợ lý dùng để trả lời.

## Phân quyền

| Quyền | Kiến thức | Góp ý người dùng | Quản lý tài khoản |
|---|---|---|---|
| **Admin** | Thêm + sửa bài | Xem + đánh dấu đã xử lý | Thêm, xem, xóa tài khoản |
| **Giảng viên** | Thêm + sửa bài | Xem toàn bộ | – |
| **Thực tập** | Thêm (nạp) + sửa bài | – | – |

- Tài khoản gốc nằm trong Secrets nên không bị xóa nhầm. Muốn đổi mật khẩu gốc thì sửa `ADMIN_PASSWORD` trong Secrets.
- Mật khẩu các tài khoản khác chỉ lưu dạng đã mã hóa. Nếu ai quên mật khẩu, Admin xóa tài khoản đó rồi tạo lại.

## Ảnh minh họa

- Cột **E (Ảnh minh họa)** trong Sheet ghi ảnh của từng bài, mỗi dòng: `tên ảnh | chú thích`.
- Ảnh chụp sẵn nằm trong thư mục `images/` của code. Ảnh admin tải lên ở trang quản lý được lưu vào thư mục Google Drive **Ảnh Trợ lý Hóa đơn điện tử** (tự tạo) và ghi dạng `drive:<mã ảnh>`.
- Khi người dùng hỏi, trợ lý hiện ảnh của bài khớp nhất ngay dưới câu trả lời.
- Lần đầu dán Code.gs có phần tải ảnh, Google sẽ hỏi thêm quyền **Google Drive**: bấm Cho phép.

# Hướng Dẫn Kỹ Thuật: Sử Dụng Bộ Starter Kit Chung Kết Indoor M4E
**Mã tài liệu:** `261106-huong-dan-su-dung-starter-kit-indoor.md`  
**Ngày ban hành:** 06/11/2026  
**Áp dụng:** Sinh viên các đội thi Vòng Chung kết AI Drone Challenge FA26  
**Thư mục làm việc:** `starter-kit-indoor/`

---

## 1. Tổng Quan Bộ Starter Kit Indoor

Bộ kit được thiết kế để sinh viên chạy thử nghiệm hoàn toàn ngoại tuyến trên máy tính cá nhân trong suốt 24 giờ trước ngày thi đấu. 
Kit giải quyết bài toán phát hiện 10 mục tiêu rải rác từ Tầng 1 đến Tầng 5 trong giếng trời:
1. **Nhận diện đồ vật (`object_type`):** Ghế lục giác (Cam, Trắng, Xám), Balo thông thường (Backpack), Bình cứu hỏa.
2. **Đọc số trên vật (`number`):** Nhận diện chính xác nhãn số 2 chữ số (từ `01` đến `99`).
3. **Xác định Tầng (`floor`) & Hướng (`direction`):** Dựa trên phân vùng góc nhìn camera (`venue.json`), hoặc dựa trên giải pháp tính toán riêng của đội (tọa độ hình học ảnh, hoặc Telemetry bay thật).

---

## 2. Bản Đồ Tệp Tin: Sinh Viên Được Sửa Gì & Cấm Sửa Gì?

Để tránh việc sinh viên làm hỏng giao tiếp với máy chủ chấm thi hoặc mất thời gian mò mẫm, BTC phân định rõ vai trò từng tệp tin:

| Tệp tin / Thư mục | Quyền can thiệp | Mục đích sử dụng |
| :--- | :---: | :--- |
| **`solution.py`** (hoặc phát triển từ `baseline.py`) | 🟢 **ĐƯỢC PHÉP SỬA (TRỌNG TÂM)** | Script chính của đội. Nơi lập trình luồng đọc ảnh, gọi model nhận diện, đọc số, tính Tầng/Hướng và gọi API nộp bài. |
| **`models/`** | 🟢 **ĐƯỢC PHÉP THAY THẾ** | Chứa trọng số detector của đội (`.pt`, `.onnx` hoặc OpenVINO), tối đa 150 MB. Đội có thể nạp mô hình riêng đã huấn luyện thêm bình cứu hỏa hoặc ghế. |
| **`venue.json`** | 🟡 **TÙY CHỌN SỬA** | Dùng nếu đội chọn dùng giải pháp mẫu (baseline) của BTC: hiệu chuẩn dải màu HSV và vùng ROI. Nếu đội tự viết thuật toán riêng trong `solution.py` thì không cần dùng file này. |
| **`custom-classes.json`** | 🟡 **TÙY CHỌN SỬA** | File mapping class id $\to$ tên mục tiêu nếu model đội train có thứ tự nhãn khác COCO (ví dụ: `{"0": "fire_extinguisher"}`). |
| **`README.md`** | 🟢 **CẦN CẬP NHẬT** | Ghi rõ: Tên đội thi, danh sách mô hình sử dụng, câu lệnh chuẩn để chạy file code chính của đội. |
| **`indoor_client.py`** | 🔴 **TUYỆT ĐỐI KHÔNG ĐƯỢC SỬA** | Thư viện client chuẩn của BTC (xử lý chữ ký Base64, mã hóa gói tin JSON `submit_target`, cơ chế retry chống nghẽn mạng). Sửa file này sẽ khiến bài nộp bị máy chủ từ chối! |
| **`tools/tesseract/` & `models/tessdata/`** | ⚪ **KHÔNG CẦN CAN THIỆP** | Bộ nhị phân OCR Portable và dữ liệu ngôn ngữ BTC đã đóng gói sẵn để chạy trực tiếp trên Windows máy BTC. |
| **`sample_data/`** | ⚪ **CHỈ DÙNG ĐỂ TỰ LUYỆN TẬP** | Video và telemetry bay thật để test offline. **Bắt buộc phải xóa/bỏ ra ngoài trước khi nén zip nộp bài**. |

---

## 3. Lộ Trình 4 Bước: Sinh Viên Nên Bắt Đầu Từ Đâu?

Đối với 24 giờ nghiên cứu trước ngày thi, lộ trình tối ưu nhất cho các đội:

### Bước 1: Chạy thử kiểm chứng trên ảnh nhân tạo (Smoke Test — 5 phút)
Tạo ảnh giả lập ghế cam + nhãn số 17 và chạy thử để chắc chắn môi trường máy tính hoạt động trơn tru:
```powershell
uv run --no-project --python .venv-baseline/Scripts/python.exe python make_fixture.py --output fixtures
uv run --no-project --python .venv-baseline/Scripts/python.exe python baseline.py `
   --source fixtures/synthetic-chair-17.jpg `
   --weights models/yolov8n.pt `
   --calibration calibration.example.json `
   --allow-example `
   --outbox outbox/
```
👉 Kiểm tra thư mục `outbox/` thấy sinh ra file JSON phát hiện mục tiêu thành công.

### Bước 2: Quan sát và đánh giá trên Chuyến Bay Thật (30 phút)
Chạy phát video giếng trời thực tế `sample_data/sample_flight_atrium.mp4` kết hợp đồng bộ dữ liệu bay `sample_data/sample_telemetry.json`:
```powershell
uv run --no-project --python .venv-baseline/Scripts/python.exe python baseline.py `
   --source sample_data/sample_flight_atrium.mp4 `
   --telemetry sample_data/sample_telemetry.json `
   --max-frames 100
```
👉 Quan sát độ cao `alt_rel`, góc quay Gimbal `gimbal_pitch` và hướng la bàn `attitude_head` in ra terminal để hiểu hành trình trinh sát của drone.

### Bước 3: Nâng cấp thuật toán cốt lõi (Trọng tâm chính của Đội)
Tập trung vào 3 bài toán để ăn trọn 100 điểm:
1. **Phát hiện vật thể (`object_type`):** Đảm bảo phát hiện đúng Ghế lục giác (Cam, Trắng, Xám), Balo thông thường và Bình cứu hỏa.
2. **Đọc số (`number`):** Cắt vùng ảnh (crop) nhãn dán trên thân vật thể, đưa qua OCR (Tesseract portable có sẵn hoặc RapidOCR/PaddleOCR do đội tự tích hợp) để nhận diện chính xác 2 chữ số (từ 01 đến 99).
3. **Xác định Tầng (`floor`) & Hướng (`direction`):**
   - Kết hợp độ cao `alt_rel` từ telemetry hoặc tỷ lệ kích thước bbox để suy ra tầng 1 đến 5.
   - Kết hợp hướng mũi drone `attitude_head` + `gimbal_yaw` để quy về 4 mốc: **ĐÔNG (Trống đồng)**, **TÂY (Thư viện)**, **BẮC (Thang máy)**, **NAM (Nhà vệ sinh)**.

### Bước 4: Đóng gói và kiểm tra dung lượng trước khi nộp
- Xóa thư mục `sample_data/`.
- Kiểm tra toàn bộ thư mục `models/` $\le$ 150 MB.
- Nén file zip: `<ten_doi>_submission.zip` và upload lên đúng Folder Google Drive của đội mình.

---

## 4. Cài Đặt Môi Trường (Chỉ Chạy 1 Lần)

Yêu cầu máy tính cài đặt Python 3.12 và công cụ `uv`. Mở terminal tại thư mục `starter-kit-indoor`:

```powershell
# 1. Tạo môi trường ảo riêng biệt
uv venv .venv-baseline --python 3.12

# 2. Cài đặt các thư viện cần thiết (Ultralytics YOLO, OpenCV, aiohttp...)
uv pip install --python .venv-baseline/Scripts/python.exe -r requirements-baseline.txt --torch-backend cpu

# 3. Tải trọng số mô hình YOLO mặc định (COCO)
uv run --no-project --python .venv-baseline/Scripts/python.exe python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
New-Item -ItemType Directory -Force models
Move-Item -LiteralPath yolov8n.pt -Destination models/yolov8n.pt
```

*(Lưu ý: Thư viện OCR Tesseract CPU và tệp `eng.traineddata` đã được BTC kẹp sẵn trong thư mục `tools/tesseract/` và `models/tessdata/`).*

---

## 5. Chế Độ Tự Luyện Tập Ngoại Tuyến (Offline Testing — Không Cần Server)

Sinh viên không cần mạng Wi-Fi và không cần kết nối tới Server BTC trong quá trình nghiên cứu và tinh chỉnh code:

### Cách 3.1: Kiểm thử nhanh trên ảnh mẫu nhân tạo (`make_fixture.py`)
```powershell
# Tạo ảnh mẫu gồm ghế cam và nhãn số 17
uv run --no-project --python .venv-baseline/Scripts/python.exe python make_fixture.py --output fixtures

# Chạy thử nghiệm pipeline nhận diện
uv run --no-project --python .venv-baseline/Scripts/python.exe python baseline.py `
   --source fixtures/synthetic-chair-17.jpg `
   --weights models/yolov8n.pt `
   --calibration calibration.example.json `
   --allow-example `
   --outbox outbox/
```
👉 **Kiểm tra kết quả:** Mở thư mục `outbox/`, sinh viên sẽ thấy file JSON được tạo ra:
`object_type: chair_orange`, `number: 17`, `bbox: [160, 260, 480, 460]`.

---

### Cách 3.2: Kiểm thử trên Video Chuyến Bay Thật Kèm Telemetry M4E (Được Khuyên Dùng)
BTC cung cấp sẵn bộ dữ liệu ghi hình thực tế của drone M4E trong thư mục `sample_data/`:
- Tệp video quay giếng trời: `sample_data/sample_flight_atrium.mp4`
- Tệp dữ liệu bay đồng bộ: `sample_data/sample_telemetry.json`

Sinh viên chạy lệnh kiểm thử toàn diện:
```powershell
uv run --no-project --python .venv-baseline/Scripts/python.exe python baseline.py `
   --source sample_data/sample_flight_atrium.mp4 `
   --telemetry sample_data/sample_telemetry.json `
   --weights models/yolov8n.pt `
   --calibration venue.json `
   --outbox outbox/
```
- Chương trình sẽ tự động phát video theo thời gian thực (FPS gốc).
- Đồng bộ góc la bàn `attitude_head` và độ cao `alt_rel` tương ứng với từng frame hình ảnh.
- Xuất toàn bộ bằng chứng nhận diện vào thư mục `outbox/` để đội rà soát độ chính xác.

---

### Cách 3.3: Công cụ giải nén & ghép nối bản ghi chuyến bay (`unpack_recording.py`)
Khi BTC cung cấp thêm các bản ghi bay mới (thư mục `recordings/<tên_ban_ghi>/` chứa `manifest.json`, `telemetry.jsonl`, và các file cắt `video/*.ts`), đội thi có thể tự tái tạo thành video MP4 và telemetry JSON bằng công cụ kẹp sẵn trong kit:

```powershell
# Chuyển đổi toàn bộ video và trích xuất telemetry vào thư mục sample_data/
uv run --no-project --python .venv-baseline/Scripts/python.exe python unpack_recording.py `
   path/to/recordings/<ten_ban_ghi> `
   --output-dir sample_data/ `
   --name chuyen_bay_moi
```
- Lệnh trên sẽ tự động:
  1. Dùng FFmpeg ghép các tệp phân đoạn `.ts` thành `sample_data/chuyen_bay_moi.mp4`.
  2. Trích xuất và căn chỉnh timestamp các bản tin OSD của Matrice 4E thành `sample_data/chuyen_bay_moi_telemetry.json`.
  3. Đội thi có thể truyền ngay file mới vào `baseline.py --source ... --telemetry ...` để luyện tập tiếp!

---

## 6. Các Tham Số Cốt Lõi Đội Thi Cần Tinh Chỉnh

Để đạt điểm tối đa trên sân thi đấu thực tế, đội thi cần tập trung cải tiến 3 điểm:

1. **Hiệu chuẩn Màu Ghế trong `venue.json` (nếu dùng baseline của BTC):**
   - Dùng ảnh thực tế chụp tại sân, đo dải màu HSV (H: 0–179, S/V: 0–255) cho 3 màu: Cam (`chair_orange`), Trắng (`chair_white`), Xám (`chair_gray`).
   - Cập nhật các ngưỡng `ranges` trong `venue.json` để thuật toán không bị nhận diện nhầm dưới ánh đèn sảnh.
2. **Khai báo Bình Cứu Hỏa (`custom-classes.json`):**
   - Mô hình YOLO COCO mặc định không có lớp bình cứu hỏa. Đội thi có thể nạp mô hình đã train thêm của mình và khai báo tệp mapping:
     ```json
     {"0": "fire_extinguisher"}
     ```
3. **Phân Vùng ROI hoặc Tự Xây Dựng Giải Pháp Riêng (Tầng & Hướng):**
   - **Quy định 4 Hướng theo mốc thực địa tòa nhà giếng trời:**
     - `EAST` (Hướng ĐÔNG): Khu vực Trống đồng.
     - `WEST` (Hướng TÂY): Khu vực Thư viện.
     - `NORTH` (Hướng BẮC): Khu vực Thang máy.
     - `SOUTH` (Hướng NAM): Khu vực Nhà vệ sinh.
   - **Cách 1 (Dùng baseline BTC):** Căn cứ vào sơ đồ giếng trời BTC công bố, tinh chỉnh các vùng ROI trong `venue.json` tương ứng với độ cao/vị trí trên ảnh để thuật toán suy ra đúng Tầng (1–5) và Hướng (Bắc/Đông/Nam/Tây). Đổi `"example_only": false` trước khi nộp.
   - **Cách 2 (Đội tự làm giải pháp riêng):** Đội thi **hoàn toàn có quyền tự phát triển giải pháp riêng** trong file `solution.py` mà **không bắt buộc phải dùng `venue.json`**! Đội có thể tự tính Tầng và Hướng bằng bất kỳ thuật toán nào (ví dụ: mô hình hồi quy độ cao từ bbox, 3D projection, tracking camera trajectory, hoặc đọc trực tiếp telemetry). Miễn là gói tin JSON nộp lên API `submit_target` trả về đúng 5 trường chuẩn (`object_type`, `number`, `floor`, `direction`, `bbox`) là hệ thống BTC sẽ chấm điểm bình thường!

---

## 7. Quy Chuẩn Đóng Gói Khi Nộp Bài Cho BTC

Toàn bộ bài nộp của các đội sẽ **được nạp và chạy trực tiếp trên máy tính chấm thi của BTC** (Core i5-12450H / Iris Xe iGPU). Vì vậy đội thi cần tuân thủ nghiêm ngặt:

1. **Dùng đường dẫn tương đối:** Mọi đường dẫn model weights trong code phải là `models/<tên_model>.pt`, không hardcode đường dẫn tuyệt đối dạng `C:\Users\...`.
2. **Nén toàn bộ thư mục thành 1 file zip duy nhất theo Tên đội thi:**
   $$\mathbf{<ten\_doi>\_submission.zip}$$
   *(Mỗi đội thi trong Top 8 sẽ được BTC cấp riêng **1 folder Google Drive** theo đúng tên đội để tải file bài nộp lên. Ví dụ: `CaHaTa-DTH_submission.zip`, `Finn0.3no_submission.zip`, `TECH DRONE_submission.zip`)*

### Danh sách 8 Đội thi chính thức Vòng Chung kết:
1. **`CaHaTa-DTH`**
2. **`5ML`**
3. **`KTN`**
4. **`newbies`**
5. **`4BiA`**
6. **`Finn0.3no`**
7. **`Mimeo`**
8. **`TECH DRONE`**

   - Chứa đầy đủ bên trong: `models/`, `venue.json` (tùy chọn), `custom-classes.json`, `solution.py` (hoặc `baseline.py`), và `README.md`.
3. **LOẠI BỎ DỮ LIỆU MẪU (`sample_data/`) TRƯỚC KHI NÉN BÀI NỘP:**
   > [!WARNING]
   > Thư mục `sample_data/` (video `.mp4` và telemetry `.json`) có dung lượng rất lớn (~856 MB) chỉ dùng để đội tự luyện tập ngoại tuyến. **Bắt buộc phải xóa hoặc loại bỏ thư mục `sample_data/` ra khỏi file zip nộp bài**. Gói nộp vi phạm vượt dung lượng do chứa `sample_data/` sẽ bị hệ thống từ chối nhận!
4. **Dung lượng tối đa:** Toàn bộ thư mục `models/` nộp kèm không vượt quá **150 MB** (tổng dung lượng file `.zip` hoàn chỉnh thông thường chỉ từ 10 MB đến tối đa 160 MB).
5. **Không cần sửa URL hay IP Server:** Khi thi thật, kỹ thuật viên BTC sẽ tự động truyền cờ `--server http://127.0.0.1:20201` và `--source "rtsp://127.0.0.1:8554/m4e"` để bài thi của đội kết nối trực tiếp với drone và server chấm thi!

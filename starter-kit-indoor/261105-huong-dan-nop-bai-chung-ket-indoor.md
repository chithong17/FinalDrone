# HƯỚNG DẪN ĐÓNG GÓI VÀ NỘP BÀI THI CHUNG KẾT INDOOR M4E
## Cuộc thi: AI Drone Challenge FA26 — ĐH FPT Phân hiệu Quy Nhơn
**Mã tài liệu:** `261105-huong-dan-nop-bai-chung-ket-indoor.md`  
**Ngày ban hành:** 05/11/2026  
**Áp dụng cho:** Tất cả các đội lọt vào Vòng Chung kết (Trinh sát cứu hộ tòa nhà 5 tầng bằng DJI Matrice 4E)

---

## 1. Nguyên Tắc Tổ Chức & Vận Hành Bài Thi

> [!IMPORTANT]
> **QUY TẮC CÔNG BẰNG PHẦN CỨNG TUYỆT ĐỐI:**
> Để triệt tiêu sự chênh lệch cấu hình máy tính cá nhân giữa các đội sinh viên (máy có card GPU rời mạnh vs máy mỏng nhẹ không card), **toàn bộ bài nộp của các đội sẽ được nạp và chạy trực tiếp trên máy tính chấm thi của Ban Tổ chức (Laptop BTC)**:
> - **Cấu hình máy BTC:** Intel Core i5-12450H (8 Cores/12 Threads), 16GB RAM, đồ họa tích hợp **Intel Iris Xe Graphics (iGPU)**.
> - **Môi trường chạy:** Mỗi đội thi sẽ có một thư mục riêng biệt trên máy BTC, kết nối trực tiếp với Server chấm thi PA2 qua địa chỉ loopback nội bộ (`http://127.0.0.1:20201`), nhận luồng video RTSP trực tiếp từ camera drone M4E (`rtsp://127.0.0.1:8554/m4e`).
> - Laptop cá nhân của sinh viên chỉ dùng để nghiên cứu, lập trình, huấn luyện mô hình và hiệu chuẩn trước giờ thi.

---

## 2. Quy Cách Định Dạng Model Được Chấp Nhận

Đội thi được phép lựa chọn một trong các định dạng mô hình sau để nộp trong gói bài thi:

| Định dạng mô hình | Tên tệp / Cấu trúc | Khuyến nghị sử dụng |
| :--- | :--- | :--- |
| **PyTorch tiêu chuẩn (`.pt`)** *(Mặc định)* | `models/<tên_model>.pt`<br>*(Ví dụ: `models/yolo11n.pt`, `models/best.pt`)* | **Dễ nộp nhất:** Chạy trực tiếp qua Ultralytics trên CPU máy BTC. |
| **OpenVINO iGPU (`_openvino_model/`)** *(Tối ưu FPS cao)* | Thư mục chứa 2 file:<br>• `<tên_model>.xml`<br>• `<tên_model>.bin` (FP16) | 🚀 **Tối ưu nhất:** Tận dụng tối đa chip đồ họa Intel Iris Xe iGPU trên máy BTC, đạt **40 – 52 FPS** ở độ phân giải 640x640 (theo kết quả benchmark thực tế). |
| **ONNX Runtime (`.onnx`)** | `models/<tên_model>.onnx` | Tối ưu hóa suy luận đa luồng trên CPU. |
| **Model OCR (Đọc số)** | `models/tessdata/eng.traineddata`<br>hoặc model ONNX của RapidOCR | Dùng để nhận diện 2 chữ số (từ 01 đến 99) trên bảng mục tiêu. |

> [!CAUTION]
> **GIỚI HẠN DUNG LƯỢNG & LOẠI BỎ SAMPLE DATA:**
> 1. **BẮT BUỘC LOẠI BỎ THƯ MỤC `sample_data/`:** Tuyệt đối không nén kèm thư mục dữ liệu mẫu `sample_data/` (video `.mp4` và telemetry `.json` ~856 MB). Thư mục này chỉ phục vụ tự luyện tập offline. File zip nộp bài chứa `sample_data/` sẽ bị loại vì vi phạm giới hạn dung lượng.
> 2. **Dung lượng tối đa:** Toàn bộ thư mục `models/` nộp **không vượt quá 150 MB** (khuyến khích dùng các dòng mô hình Nano/Small như YOLOv8n, YOLO11n, YOLO26n). Tổng file `.zip` hoàn chỉnh thông thường dưới 160 MB.
> 3. **An toàn phần mềm:** Nghiêm cấm nộp các tệp thực thi lạ ngoài quy chuẩn (`.exe`, `.bat`, installer hoặc script can thiệp hệ thống). Bài nộp vi phạm sẽ bị loại ngay lập tức.

---

## 3. Cấu Trúc Gói Bài Nộp Chuẩn

Vòng Chung kết có tổng cộng **8 đội thi chính thức**:
1. **`CaHaTa-DTH`**
2. **`5ML`**
3. **`KTN`**
4. **`newbies`**
5. **`4BiA`**
6. **`Finn0.3no`**
7. **`Mimeo`**
8. **`TECH DRONE`**

Mỗi đội thi sẽ được BTC cấp riêng **1 thư mục Google Drive** tương ứng với tên đội của mình.

Đội thi nén toàn bộ thư mục bài làm của mình thành một tệp nén duy nhất theo tên đội:
$$\mathbf{<ten\_doi>\_submission.zip} \quad \text{hoặc} \quad \mathbf{<ten\_doi>\_submission.tar.gz}$$
*(Ví dụ: `CaHaTa-DTH_submission.zip`, `Finn0.3no_submission.zip`, `TECH DRONE_submission.zip`)*

```text
<ten_doi>_submission/
│
├── models/                               <-- Bắt buộc: Chứa trọng số mô hình
│   ├── best_detector.pt (hoặc .onnx / openvino_model)
│   └── tessdata/
│       └── eng.traineddata               <-- File ngôn ngữ Tesseract OCR (nếu dùng Tesseract)
│
├── venue.json                            <-- Tùy chọn (nếu dùng baseline của BTC): File hiệu chuẩn sân của đội
│                                             (Dải màu HSV ghế, phân vùng ROI tầng/hướng).
│                                             Nếu đội tự phát triển giải pháp tính Tầng/Hướng riêng trong solution.py thì không bắt buộc có file này.
│
├── custom-classes.json                   <-- Tùy chọn: Ánh xạ class nếu đội train thêm
│                                             bình cứu hỏa (fire_extinguisher)
│
├── solution.py (hoặc baseline.py)         <-- Bắt buộc: Script chạy chính của đội
├── indoor_client.py                      <-- Thư viện client giao tiếp API BTC (giữ nguyên từ kit)
└── README.md                             <-- Mô tả ngắn: Tên đội, mô hình sử dụng, lệnh khởi chạy
```

---

## 4. Các Tham Số Cần Tinh Chỉnh Trước Khi Nộp

Để bài thi đạt điểm tối đa trên sân thực tế, đội thi cần kiểm tra kỹ 3 tệp sau trong bộ kit:

1. **Hiệu chuẩn Màu sắc & Góc nhìn (`venue.json`) hoặc Thuật toán riêng:**
   - **Quy định 4 Hướng theo mốc thực địa:** `EAST` (Trống đồng), `WEST` (Thư viện), `NORTH` (Thang máy), `SOUTH` (Nhà vệ sinh).
   - **Nếu dùng baseline BTC:** Không nộp file mẫu `calibration.example.json` (sẽ bị hệ thống từ chối). Phải đổi `example_only: false`. Đo dải màu HSV thực tế tại sân thi đấu cho 3 loại ghế: `chair_orange` (Cam), `chair_white` (Trắng), `chair_gray` (Xám). Thiết lập các vùng ROI tương ứng với góc nhìn camera (`view`) để xác định đúng Tầng ($1 \to 5$) và Hướng (`NORTH`, `SOUTH`, `EAST`, `WEST`).
   - **Nếu đội tự làm giải pháp riêng:** Đội hoàn toàn có thể tự viết thuật toán xác định Tầng và Hướng trong `solution.py` (bằng thị giác máy tính, hình học camera, bối cảnh lan can, hoặc xử lý telemetry) mà **không cần nộp `venue.json`**. Chỉ cần đầu ra gọi API `submit_target` trả về đúng 5 trường chuẩn.
2. **Khai báo Bình cứu hỏa (`custom-classes.json`):**
   - Mô hình YOLO COCO mặc định **không có** class bình cứu hỏa (`fire_extinguisher`).
   - Nếu đội có huấn luyện thêm mô hình riêng phát hiện bình cứu hỏa, phải cung cấp tệp mapping rõ ràng (ví dụ: `{"0": "fire_extinguisher"}`).
3. **Cơ chế Outbox & Retry:**
   - Đảm bảo mã nguồn có cơ chế lưu outbox trước khi gửi HTTP để không bị mất bản tin khi gặp độ trễ mạng tạm thời.

---

## 5. Quy Trình Nộp Bài & Tiếp Nhận Tại Sân

### Bước 1: Khóa bài thi (Code Freeze)
- **Thời hạn nộp:** Trước giờ thi đấu chính thức **30 phút**.
- **Kênh nộp bài:** Đội thi tải tệp `<ten_doi>_submission.zip` lên đúng **Folder Google Drive riêng** mà BTC đã cấp cho đội. 
- Sau mốc thời gian này, quyền truy cập/tải file lên folder sẽ đóng, mọi chỉnh sửa mã nguồn sau giờ quy định đều không hợp lệ.

### Bước 2: Nạp bài thi lên Laptop BTC
- Kỹ thuật viên BTC sẽ tải về và giải nén bài nộp của đội vào không gian chạy riêng trên máy BTC:
  ```powershell
  C:\Workspace\thi-dau\<ten_doi>\
  ```
- Kiểm tra tính toàn vẹn của tệp mô hình và chạy thử nghiệm mồi (smoke test) 1 ảnh để đảm bảo code không bị lỗi cú pháp trước khi drone cất cánh.

### Bước 3: Vận hành lượt thi đấu (300 giây)
1. Drone DJI Matrice 4E cất cánh và thực hiện hành trình bay trinh sát trong giếng trời.
2. Trọng tài bấm nút **"Bắt đầu Lượt thi"** trên Bảng điều khiển `/ops`. Đồng hồ 300 giây bắt đầu đếm ngược.
3. Kỹ thuật viên BTC khởi chạy bài thi của đội bằng lệnh chuẩn:
   ```powershell
   uv run --no-project --python C:\Workspace\thi-dau\.venv-indoor\Scripts\python.exe `
      solution.py --server http://127.0.0.1:20201 `
                  --session <session_id_cua_doi> `
                  --source "rtsp://127.0.0.1:8554/m4e" `
                  --weights models/best_detector.pt `
                  --calibration venue.json
   ```
4. Thuật toán của đội tự động thu nhận khung hình, chạy suy luận, và bắn gói tin `submit_target` trực tiếp về server chấm điểm.
5. Khi hết 300 giây, server tự động đóng cổng nhận bài. Kết quả chấm điểm Bbox và 4 trường nội dung sẽ được trọng tài công bố trực tiếp trên màn hình Dashboard.

---
**BAN TỔ CHỨC AI DRONE CHALLENGE FA26**  
*Chúc các đội thi hoàn thành xuất sắc bài thi Chung kết!*

# Starter kit chung kết Indoor M4E 1.1

Kit dành cho đề đã duyệt `261103-de-thi-chung-ket-indoor-m4e-1.1.docx`. Kit không xin quyền bay, không vào DRC, không dùng GPS làm đầu ra. Có baseline YOLOv8n CPU + HSV + OCR local + bảng ROI; đội phải hiệu chuẩn ở sân thật. Không có detection giả hoặc tự nộp mục tiêu chưa xác nhận.

## Chạy baseline cho sinh viên

Mở terminal trong `starter-kit-indoor`. Cần Python 3.12 và uv. Cài dependency trong môi trường riêng, không cài global:

**Dataset mẫu thực địa** (video + telemetry đồng bộ, không cần server): tại repo gốc chạy `uv run python tools/build_starter_sample_data.py` để tạo `sample_data/sample_flight_atrium.mp4` và `sample_telemetry.json` từ bản ghi `recordings/261105-174737-dataset`. Xem offline:

```powershell
uv run --no-project --python .venv-baseline/Scripts/python.exe python baseline.py --source sample_data/sample_flight_atrium.mp4 --telemetry sample_data/sample_telemetry.json
```

**Tự giải nén & ghép nối bản ghi chuyến bay (`unpack_recording.py`):**
Khi nhận thêm thư mục recordings từ BTC, đội thi có thể tự tái tạo thành video MP4 và telemetry JSON bằng công cụ kẹp sẵn trong kit:

```powershell
python unpack_recording.py <duong_dan_thu_muc_recording> --output-dir sample_data/ --name flight_moi
```
Công cụ sẽ tự động ghép các file `.ts` thành `.mp4` (thông qua FFmpeg) và căn chỉnh thời gian các bản tin OSD của drone thành tệp `_telemetry.json`.

Mốc `time_offset_s` trong JSON căn theo `manifest.video_parts[0].clock.t0`; frame video đầu tiên decode = `t=0`.

```powershell
uv venv .venv-baseline --python 3.12
uv pip install --python .venv-baseline/Scripts/python.exe -r requirements-baseline.txt --torch-backend cpu
```

Chuẩn bị checkpoint **YOLOv8n COCO** local `models/yolov8n.pt` (Ultralytics), Tesseract CPU executable và `eng.traineddata` local. Không train. Windows có thể dùng bản portable đã giải nén; kit chỉ chạy executable được chỉ định, không sửa PATH/registry, không chạy installer. Tesseract có thể dùng bản hệ thống trên Linux. Nếu chưa có asset thì lỗi rõ ràng, không tự tải khi đang thi. Kiểm tra giấy phép model và binary trước khi phân phối lại.

Tải weight một lần **trước buổi thi**, có Internet (lệnh chủ động download qua Ultralytics, không train):

```powershell
uv run --no-project --python .venv-baseline/Scripts/python.exe python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
New-Item -ItemType Directory -Force models
Move-Item -LiteralPath yolov8n.pt -Destination models/yolov8n.pt
```

OCR cần bộ executable + DLL (Windows) và `eng.traineddata`; chỉ copy `tesseract.exe` đơn lẻ sẽ thiếu thư viện. Dùng portable bundle đã kiểm của BTC hoặc đường dẫn Tesseract sẵn có; `--tessdata` trỏ thư mục chứa `eng.traineddata`. Kit không gắn cứng đường dẫn máy BTC và không cài OCR global. Nếu chưa có OCR local, CLI dừng rõ ràng trước khi đọc nguồn/nộp bài.

```powershell
$env:DRONE_TEAM_TOKEN = '<token BTC cấp>'
uv run --no-project --python .venv-baseline/Scripts/python.exe python baseline.py --server http://<IP-laptop>:20201 --session <session_id> --source frame.jpg --weights models/yolov8n.pt --calibration venue.json --view east-fixed --tesseract tools/tesseract/tesseract.exe --tessdata models/tessdata
```

`--source` nhận ảnh, file video hoặc RTSP URL; video/RTSP dùng queue một frame mới nhất, bỏ frame cũ, timeout đọc 3s. Không ghi URL RTSP ra log (URL có thể có mật khẩu). Ảnh JPEG được giữ nguyên byte; PNG/video/RTSP được encode JPEG toàn khung gốc chưa vẽ bbox. Ultralytics `Results.boxes.xyxy` đã remap resize/letterbox về `orig_shape`; adapter custom dùng `remap_letterbox`. Không chuyển bbox crop thành bbox toàn khung mà chưa cộng offset.

Copy `calibration.example.json` thành `venue.json`. Mẫu **synthetic**, không phải bố trí sân thật: mặc định bị chặn; `--allow-example` chỉ dành cho fixture. Với từng view cố định: chụp frame đúng resolution, camera pose/gimbal/lens/zoom; chia ROI normalized theo các khu vực tầng/hướng thực; mỗi tâm bbox phải thuộc đúng một ROI. Dùng tên view riêng và đổi `--view` khi đổi góc nhìn. Nếu drone/camera di chuyển khỏi view đã đo thì dừng và hiệu chuẩn lại; yaw/altitude không xác định tầng/hướng. Chỉ đặt `example_only: false` sau khi kiểm thực địa. Pixel ngoài ROI, ROI chồng nhau hoặc resolution khác đều bị reject.

Ghế: YOLO COCO chỉ cho box `chair`. Đo HSV bằng ảnh thật dưới ánh sáng sân (OpenCV H 0–179, S/V 0–255). Chọn `sample_roi` bên trong phần mặt/thân ghế tránh nhãn trắng và nền; lấy dải H/S/V từ nhiều pixel sáng/tối của từng màu, sửa ba `ranges`. Thử thêm ghế không đúng màu và nền để đặt `min_fraction`/`min_margin`; màu mơ hồ bị reject. Mẫu cam/xanh/xám chỉ là điểm bắt đầu, không bảo đảm accuracy.

OCR: chọn `ocr.label_roi` tương đối bên trong box vật sao cho chỉ có **một nhãn số**, đủ nét. Tesseract local CPU đọc TSV confidence; chỉ nhận chính xác chuỗi hai chữ số `01`–`99` vượt `min_confidence`, không sửa chữ O thành 0, không dùng default. Nhãn trống, `00`, nhiều chuỗi, confidence thấp/backend lỗi đều không nộp. Nhãn 01 gửi integer 1. Có thể thay class `TesseractDigits` bằng backend khác cùng `read(crop)->int`, giữ quy tắc reject.

Backpack map trực tiếp COCO. **Fire extinguisher không có trong COCO pretrained**; `fire hydrant` và quả `orange` không phải mục tiêu. Default vẫn chạy ghế/balo và báo unsupported bình chữa cháy. Muốn thêm bình: cung cấp custom YOLO checkpoint đã có class đó và `--class-map custom-classes.example.json` (sửa key theo đúng tên/id class trong model). Adapter chỉ nhận mapping tường minh; không tự gán một class COCO thành bình. Ticket này không train/custom weight và không claim accuracy sân thật.

CLI chạy một session theo đồng hồ server, tối đa 300s, không tự finish. Mỗi quan sát hợp lệ lưu JSON outbox trước request đầu; retry 429 đọc `Retry-After`, chờ có giới hạn, cùng ID/JPEG; lỗi khác giữ file để `solution.py --retry`. CLI tránh gửi lại cùng loại/số/tầng/hướng trong một process nhằm giảm traffic; đây không phải physical dedupe chấm điểm và có thể bỏ sót hai vật trùng nhãn, đội có thể thay policy. Không suy điểm từ ACK.

Fixture xác định: `uv run --no-project --python .venv-baseline/Scripts/python.exe python make_fixture.py --output fixtures` tạo ảnh ghế cam và nhãn 17 tổng hợp. Dùng test pipeline với detector fixture; YOLO trên hình vẽ có thể không detect, không coi hình vẽ là field accuracy.

## Kết nối

BTC cấp URL, token riêng và session_id sau khi xuất phát từ `/ops`. Trong PowerShell:

```powershell
$env:DRONE_TEAM_TOKEN = '<token BTC cấp>'
uv run --with-requirements requirements.txt python solution.py --server http://<IP-laptop>:20201 --image frame.jpg --detection detection.json --outbox outbox/detection-001.json
```

`detection.json` do pipeline đội sinh, gồm `session_id`, `submission_id`, `target_id`, `frame_id`, `captured_at_ms`, `object_type`, `number`, `floor`, `direction`, `bbox`. Bbox là tọa độ integer trên chính JPEG gốc; phải đổi ngược resize/letterbox trước khi gọi `make_packet`. Thời điểm là thời điểm thu frame thật, không lấy thời điểm xử lý xong. Không vẽ bbox vào ảnh gốc; server vẽ trên Dashboard.

Giá trị hợp lệ: object_type = chair_orange/chair_blue/chair_gray/backpack/fire_extinguisher; number = 1–99; floor = 1–5; direction = NORTH/SOUTH/EAST/WEST. BTC bố trí mục tiêu tầng 1–2 theo đề 1.1. Tầng là tầng đặt vật, hướng là khu vực tòa nhà; không đồng nhất với độ cao và yaw của drone. Không có đủ bằng chứng thì quan sát lại thay vì đặt giá trị giả.

## API contract

| API | Xác thực | Tác dụng |
|---|---|---|
| GET /api/indoor/{session_id}/status | Bearer token đội | Đồng hồ server, trạng thái, số bản tin, telemetry hiện có |
| POST /api/indoor/submit_target | Bearer token đội | Payload trên + image_width/image_height/image_b64 JPEG toàn khung; image_crop_b64 tùy chọn |
| POST /api/indoor/{session_id}/finish | Bearer token đội | Chốt sớm; không mở lại được |

Ảnh gốc tối đa 6 MB (Base64 tối đa 8 triệu ký tự), mỗi chiều tối đa 8192 và tổng tối đa 20 triệu pixel. Body HTTP tối đa 20 MiB. Telemetry có thể ở tốc độ OSD chậm khi không được cấp quyền DRC; giữ nguyên giá trị thiếu, không tự suy ra tầng/hướng từ dữ liệu thiếu.

ACK chứa submission_id, received_at_ms, status=pending_review. Đây là nhận bài chờ trọng tài, chưa phải điểm. Mất kết nối/timeout: client tự retry tối đa 3 lần với cùng payload; outbox được lưu trước lần gửi đầu. Retry sau khi restart:

```powershell
uv run --with-requirements requirements.txt python solution.py --server http://<IP-laptop>:20201 --retry outbox/detection-001.json
```

401: kiểm token; 400: sửa dữ liệu với submission_id mới; 404: kiểm session; 409: ID đã dùng với nội dung khác; 410: lượt đóng; 429: đọc Retry-After, không gửi dồn. Bản tin trùng chính xác trả lại ACK cũ kể cả sau hết giờ. Không log token. Đội dùng `IndoorClient` với `async with` để đóng session đúng cách. `--finish` chỉ dùng khi đã quyết định kết thúc thi.

Hạn mức là **30 bản tin NEW hợp lệ mỗi chu kỳ**. Lần **31 bị từ chối**, khóa **15 giây**; hết khóa thì **reset bộ đếm về 0**, tiếp tục chu kỳ mới. Đồng hồ **300 giây không đổi**, không được cộng thêm thời gian khóa. Retry đúng ID/nội dung không tăng quota; invalid schema bị reject không tiêu quota. Outbox dùng publish atomic không ghi đè khác nội dung khi hai writer trùng path; giữ trên filesystem local hỗ trợ hard link.

## Chấm điểm

Trọng tài duyệt bbox bằng mắt, không dùng IoU tự động. Mỗi mục tiêu: loại 3, số 3, tầng 2, hướng 2; bbox sai/decoy = 0. Một vật chỉ lấy bản tin hoàn chỉnh cao nhất, không ghép trường. Tie-break: thời gian hoàn tất, số vật đúng cả hướng+số, độ khít bbox trung bình 1–3. Không có bước train mô hình trong kit.

Audit review ghi `BTC/shared-token`: chỉ xác nhận vai trò, không quy được từng cá nhân dùng chung token. Round hỏng bị cách ly và hiện diagnostic ở listing BTC; file gốc giữ nguyên để phục hồi thủ công. Round RUNNING khi server restart thành INTERRUPTED, không tự mở lại hay chứng nhận thắng cuộc.

# KTN — AI Drone Challenge Indoor M4E

## Khởi chạy trên máy BTC

Python 3.12, CPU. Model: YOLOv8n custom và PP-OCRv4 ONNX, tổng khoảng 22.7 MB. Mọi trọng số đã kèm local, không tải model khi chạy. Thư viện bổ sung trong requirements.txt; nếu máy BTC chưa có PyTorch, cài torch/torchvision CPU trước.

Tại thư mục KTN_submission đã giải nén, dùng Python môi trường BTC:

```powershell
$env:DRONE_TEAM_TOKEN = '<token BTC cấp>'
python solution.py --server http://127.0.0.1:20201 --session '<session_id>' --source rtsp://127.0.0.1:8554/m4e --weights models/best_detector.pt --calibration venue.json
```

Chương trình tương thích các tham số lệnh mẫu của BTC. `--calibration` được tiếp nhận để tương thích launcher, nhưng không đọc venue.json: đội dùng thuật toán tầng/hướng riêng, được kit cho phép. Không cần tạo venue.json. Khi có --server, mặc định chạy live với configs/live.json. Output tự tạo thư mục mới dưới output/. Không tự finish phiên.

## Kiểm tra ảnh mồi

```powershell
python solution.py --source test_assets/chair_gray_number_21.jpg --weights models/best_detector.pt --max-frames 1 --debug
```

Ảnh đã dùng train, chỉ kiểm tra môi trường: kỳ vọng nhận ghế xám số 21. Ảnh debug ở output/run-*/debug. Một ảnh không có telemetry không tạo candidate/gửi HTTP; candidates=0 trong phép thử này là đúng.

## Telemetry và điều kiện vận hành

Kit công bố GET /api/indoor/{session_id}/status có telemetry, state và time_left_s. Adapter tự tìm một object telemetry duy nhất có t_server (epoch ms), alt_rel, yaw trong response, không phụ thuộc tên wrapper. Không lấy mẫu từ mảng lịch sử, không dùng thời điểm polling thay timestamp OSD. Nếu không có, sai schema hoặc nhiều bản tin mơ hồ thì ghi telemetry_unavailable trong delivery.jsonl và chờ dữ liệu; không đoán tầng/hướng. Có thể cấu hình đường dẫn tường minh qua delivery.status_telemetry_path khi cần.

configs/live.json áp dụng phương án đội đã chốt: yaw thân drone, camera thẳng thân, drone quét tại vị trí đã đo ở giữa sân. scan_pose_verified=true là giả định vận hành này, không phải chức năng tự định vị. Nếu bay khác tư thế phải hiệu chuẩn lại. Giữ vật gần tâm khung, độ cao/yaw ổn định, ít nhất hai mẫu telemetry khác timestamp. Tầng: dưới 7; [7.4,9.3]; [10,12.5]; [13,15]; từ 15.5 trở lên. Các khoảng hở không được gán tầng.

Chỉ gửi vật có A4, số hợp lệ 01–99, 6/9 phải xác định chiều bằng gạch dưới, qua xác nhận nhiều frame. Loại: chair_orange, chair_white, chair_gray, backpack, fire_extinguisher. number_label là lớp phụ nội bộ, không gửi làm object_type. Mapping ở custom-classes.json.

Packet dùng JPEG toàn khung chưa vẽ, bbox trên ảnh gốc, timestamp lúc thu frame. Outbox được ghi trước gửi; ACK lưu *.ack.json. Retry giữ nguyên submission_id và payload. pending_review là nhận bài chờ duyệt, chưa phải điểm.

## Kết quả kiểm tra và phạm vi

26 kiểm thử đã qua trên máy đội, có HTTP cục bộ bằng IndoorClient gốc: đọc status, đồng bộ hai mẫu, xác nhận số qua hai frame, tính tầng/hướng, POST, lưu ACK và giữ đúng JPEG/bbox/timestamp. Detector/OCR của kiểm thử HTTP là fixture để kiểm tra giao tiếp; model thật được kiểm tra riêng bằng ảnh mồi. Đây chưa phải xác nhận từ server BTC thật; schema normalized căn cứ mẫu dữ liệu dashboard. Balo còn yếu trên holdout, chưa đánh giá toàn pipeline bằng cảnh bay A4 độc lập.

Gói không kèm sample_data, video, môi trường ảo hoặc dữ liệu train. Giữ nguyên indoor_client.py từ kit.

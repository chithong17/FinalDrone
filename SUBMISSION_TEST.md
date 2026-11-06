# Bản nộp thử FinalDrone — 06/11/2026

Mục đích: kiểm tra khả năng chạy trên máy BTC và tích hợp API. Đây chưa phải bản đã xác nhận gửi/chấm thành công trên server thật. Tên đội chưa được điền; đổi tên ZIP theo tên đội trước khi nộp chính thức.

## Môi trường

Python 3.12, CPU, FFmpeg có trên PATH. Sử dụng Python môi trường BTC nếu đã đủ thư viện. Nếu cần cài thêm:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

Đã kèm detector custom và toàn bộ OCR ONNX local; không cần chạy prepare-assets. Không kèm video, dữ liệu train hoặc môi trường ảo.

## 1. Kiểm tra chạy được

Mở PowerShell tại thư mục giải nén:

```powershell
python solution.py --help
python solution.py --source test_assets/chair_gray_number_21.jpg --config configs/trained.json --max-frames 1 --debug
```

Ảnh mẫu thật đã dùng train, chỉ để kiểm tra cài đặt. Kỳ vọng nhận ghế xám số 21; ảnh debug nằm trong output/run-*/debug. Một ảnh không có telemetry không tạo candidate và không gửi HTTP. Đây không phải phép đo accuracy.

## 2. Kiểm tra kết nối API (chỉ đọc)

```powershell
$env:DRONE_TEAM_TOKEN = '<token BTC cấp>'
python check_connection.py --server http://127.0.0.1:20201 --session '<session đội>'
```

Gửi lại file output/connection-schema.json cho đội phát triển để xác nhận đường dẫn telemetry. File chỉ ghi cấu trúc/tên trường và kiểu dữ liệu, không ghi token hoặc giá trị response. GET thành công chưa chứng minh POST submit_target thành công.

## 3. Chạy gửi bài tự động sau khi xác nhận schema

Sao chép configs/trained.json thành configs/live.json. Điền delivery.status_telemetry_path đúng response status, kiểm tra status_state_path và status_time_left_path. Adapter hiện yêu cầu telemetry normalized gồm t_server (epoch ms), alt_rel và yaw; nếu server không cung cấp telemetry trong status hoặc dùng schema khác thì phải sửa adapter/nguồn telemetry trước.

Chỉ bật location.scan_pose_verified=true khi vận hành đúng tư thế đã đo: vị trí quét phù hợp, camera thẳng theo thân drone. heading_field=aircraft_yaw đã được đội xác nhận. Giữ nguyên dải tầng/hướng đã chốt.

```powershell
python solution.py --server http://127.0.0.1:20201 --session '<session đội>' --source rtsp://127.0.0.1:8554/m4e --config configs/live.json --duration-s 300
```

Lệnh này dùng model trong config; không cần --weights hay --calibration venue.json vì đội dùng thuật toán tầng/hướng riêng. Không dùng lệnh baseline của kit cho entrypoint này.

Chỉ gửi vật có giấy A4, số hợp lệ và location hợp lệ sau xác nhận nhiều frame. Outbox được lưu trước HTTP; kiểm tra file ACK tương ứng. pending_review chỉ xác nhận nhận bài, chưa xác nhận điểm. Code không tự finish session.

## Giới hạn hiện tại

Chưa chạy với server/RTSP BTC thật; thiếu xác minh schema telemetry. Balo còn yếu trên holdout và chưa đánh giá toàn pipeline bằng cảnh bay có A4 độc lập. Nếu chưa có ACK thật thì chưa thể kết luận hệ thống chấm bài đã nhận được submission.

# Kết quả triển khai ban đầu

Ngày 06/11/2026. Báo cáo phân biệt code đã chạy và chất lượng chưa được chứng minh.

Đây là snapshot trước đợt train custom. Hiện đã có model v3; kết quả mới nhất và giới hạn xem [TRAINING_RESULTS.md](TRAINING_RESULTS.md).

## Môi trường/asset

- Python 3.12.14 trong `.venv`, PyTorch 2.15 CPU, Ultralytics 8.4.203, OpenCV 5.0.0.93, RapidOCR 3.10.0, ONNX Runtime 1.31.1.
- Model baseline local: YOLOv8n COCO; OCR PP-OCRv4 mobile (det/cls/rec), khoảng 22 MB tổng asset. Phiên bản đầy đủ ở `requirements-lock.txt`, checksum local ở `models/assets.json`.
- Client BTC gốc không sửa.

## Dữ liệu và thử nghiệm thật

- Đã trích 40 frame trải đều video 06/11 và 12 ảnh object map; manifest có 52 mẫu **pending/dev**, chưa có ground truth reviewed và holdout.
- Dự đoán baseline trên 52 ảnh: 1 detection trên nhóm frame video, 0 trên 12 ảnh map. Đây chỉ là số detection, **không phải precision/recall** vì chưa có nhãn reviewed.
- Chạy một ảnh ghế lục giác cam: 0 detection.
- Chạy 12 frame video từ 280 giây, bước 2 giây: 0 detection.
- Kết luận thực hành: không thể coi checkpoint COCO là detector đáp ứng bài thi. Cần dữ liệu có nhãn và detector custom, đặc biệt cho ghế lục giác/bình cứu hỏa.

## Kiểm tra OCR

- Smoke test số synthetic 62 có gạch chân ban đầu đọc đúng.
- Phát hiện automatic orientation classifier có thể đổi 99 thành 66. Đã tắt classifier khi đọc và thêm hướng đọc theo gạch chân.
- Sau sửa: synthetic 99/62, cả chiều thường và xoay 180°, đều đọc đúng; ảnh trắng trống bị reject.
- Không có bằng chứng accuracy trên số thật từ video. Gạch chân hiện được tìm bằng hình học connected components, chưa phải bộ phát hiện nhãn học máy đã hiệu chuẩn.

## Smoke realtime 300 giây trên máy hiện tại

Nguồn: `flight_261106.mp4` và telemetry gốc. Chế độ realtime với queue một frame mới nhất, YOLOv8n CPU, default OCR/tracking/location. Không dùng server BTC.

| Chỉ số | Kết quả |
|---|---:|
| Wall time xử lý | 300.141 s |
| Frame đã xử lý | 4.307 |
| Throughput | 14.35 FPS |
| P50 xử lý | 44.25 ms |
| P95 xử lý | 52.26 ms |
| RSS process cao nhất được lấy mẫu | 526.81 MB |
| Frame drop | 4.524 |
| Tuổi frame lớn nhất sau xử lý | 6.188 s |
| Quan sát detection | 6 |
| Candidate hoàn chỉnh | 0 |

Số liệu gốc: [baseline-20261106.json](baseline-20261106.json). RSS lấy mẫu không phải tổng RAM toàn hệ thống. P95 không mô tả các đợt OCR chậm hiếm gặp; max frame age cho thấy cần tiếp tục kiểm soát độ trễ khi có nhiều mục tiêu.

Lý do reject gồm không có số tin cậy, vật lệch tâm, tư thế chưa xác nhận, màu mơ hồ, yaw chưa ổn định hoặc sát biên. Không có candidate không đồng nghĩa đạt chất lượng; mặc định `scan_pose_verified=false` và model chưa phù hợp. Đây là smoke vận hành, không phải điểm thi hay benchmark trên laptop BTC.

Lần chạy 300 giây được thực hiện trước thay đổi sửa chiều OCR 99/66; thay đổi OCR sau đó đã được kiểm tra riêng, chưa chạy lại benchmark 300 giây trên bản cuối. Không suy số FPS này thành cam kết cho bản final/custom detector.

## Kiểm thử

18 test tự động bao phủ quy tắc tầng/hướng, tuổi mẫu và đồng bộ, tracking, consensus, pending/decoy, không ghi đè manifest, export YOLO không rò split, EXIF ảnh, hướng gạch chân và retry 429 bảo toàn payload/ACK.

Pipeline test dùng detector/OCR injected và dữ liệu synthetic, delivery test dùng fake client. Đây là kiểm tra logic, không phải field accuracy hoặc kiểm chứng API BTC.

## Những phần chưa nghiệm thu

1. Gán nhãn reviewed và chia train/dev/holdout độc lập; train/evaluate model custom.
2. OCR trên nhãn thật và kiểm chứng hướng đọc khi gạch mờ/che/nhòe.
3. Độ lệch video/OSD, tư thế quét, các ngưỡng ổn định/tuổi mẫu trong điều kiện thật.
4. Schema status, token/session và thử adapter live với server BTC.
5. Chạy lại toàn pipeline cuối trên laptop BTC, chọn cấu hình bằng holdout và đóng gói.

Chưa commit/push các thay đổi triển khai này. Xem README để chạy thử và kế hoạch để nghiệm thu các bước tiếp theo.

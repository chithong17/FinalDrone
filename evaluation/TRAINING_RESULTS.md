# Kết quả train detector ngày 06/11/2026

Model được chọn là bản tốt nhất trong các thí nghiệm dưới đây theo dev chung, không phải cam kết tốt nhất trên mọi tình huống thi.

- Checkpoint gốc được chọn: `experiments/detector-real-a4-v3/weights/best.pt`.
- Model triển khai local: `models/best_detector.pt`.
- Config triển khai: `configs/trained.json`.
- Độ phân giải suy luận chọn bằng dev: **640**.
- SHA256: `d77fdf0a727d7895f355d185d2120426b0b6cc9a77f067763acc14a8acafdd94`.

## Các lần train

| Run | Nguồn khởi đầu | Epoch thực chạy / yêu cầu | Thiết bị | Thời gian |
|---|---|---:|---|---:|
| detector-frozen-v1 | YOLOv8n COCO | 30 / 30 | CPU | 524.1 s |
| detector-full-v2 | experiments\detector-frozen-v1\weights\best.pt | 25 / 25 | CPU | 728.4 s |
| detector-real-a4-v3 | experiments\detector-refine-gpu-v2\weights\best.pt | 20 / 20 | 0 | 477.5 s |
| detector-refine-gpu-v2 | experiments\detector-full-v2\weights\best.pt | 30 / 30 | 0 | 395.2 s |
| yolo11n-gpu-v2 | models\yolo11n.pt | 20 / 50 | 0 | 225.3 s |

Dừng sớm theo patience khi dev không cải thiện; epoch yêu cầu không đồng nghĩa đã chạy đủ.

## So sánh trên cùng dev

Chọn theo trung bình mAP50–95 của năm lớp vật thể; không để lớp giấy số chi phối việc chọn. Bảng mAP tổng có cả lớp giấy số.

| Checkpoint | Img size | mAP50 tổng | mAP50–95 tổng | Macro mAP50–95 vật thể | Fixture xám A4 |
|---|---:|---:|---:|---:|---|
| detector-frozen-v1 | 416 | 0.529 | 0.285 | 0.235 | False |
| detector-frozen-v1 | 640 | 0.617 | 0.303 | 0.248 | False |
| detector-full-v2 | 416 | 0.818 | 0.513 | 0.476 | False |
| detector-full-v2 | 640 | 0.776 | 0.404 | 0.353 | False |
| yolo11n-gpu-v2 | 416 | 0.483 | 0.277 | 0.242 | False |
| yolo11n-gpu-v2 | 640 | 0.595 | 0.389 | 0.354 | False |
| detector-refine-gpu-v2 | 416 | 0.763 | 0.513 | 0.472 | False |
| detector-refine-gpu-v2 | 640 | 0.838 | 0.535 | 0.495 | False |
| detector-real-a4-v3 | 416 | 0.691 | 0.501 | 0.445 | True |
| detector-real-a4-v3 | 640 | 0.830 | 0.530 | 0.481 | True |

Với v3, chỉ xét bản nhận đúng lớp ghế xám và bbox IoU ≥0.5 trên ảnh A4 đã đưa vào train. Đây là điều kiện sanity của training fixture, không phải phép đo holdout; sau đó chọn macro dev cao nhất trong các bản đạt điều kiện.

## Theo lớp của bản chọn trên dev

| Lớp | mAP50–95 |
|---|---:|
| chair_orange | 0.746 |
| chair_white | 0.413 |
| chair_gray | 0.370 |
| backpack | 0.266 |
| fire_extinguisher | 0.609 |
| number_label | 0.776 |

## Detector holdout

Bản chọn được đánh giá trên 20 ảnh holdout: mAP50 = **0.316**, mAP50–95 = **0.117**.
Không có GT cho một số lớp trên holdout này; không suy ra chất lượng của toàn bộ năm lớp từ chỉ số đó.
Ảnh ghế dán 21 đã được đưa vào train trong v3; kết quả trên ảnh này chỉ là kiểm tra training fixture. Holdout v3 chỉ có balo, không đo được các lớp ghế/bình/giấy số.

## Nhận số và lọc vật không số

- Regression ảnh thật: **16/16** trường hợp đạt.
- Kiểm tra 62, 99, 21 ở 0/90/180/270 độ và các ảnh ghế/bình không dán số.
- Chỉ chấp nhận số 01–99 trên giấy A4; số có 6/9 cần xác định được chiều từ gạch dưới.
- `number_label` chỉ hỗ trợ tìm nhãn; bbox gửi API vẫn là bbox toàn vật.
- Proposal vật không số vẫn có thể được ghi trong log chẩn đoán, nhưng `target_recognized=false`, không vẽ như mục tiêu hợp lệ và không tạo candidate gửi.

## Dữ liệu và giới hạn

- Xem `data/TRAINING_DATA.md`: ảnh vật thật ít; nhiều ảnh tăng cường có giấy A4 tổng hợp, không phải ảnh drone mới.
- Balo từ COCO chính thức; giữ license/URL theo ảnh. Các checkpoint gốc đã pretrained COCO.
- Dev tách theo nguồn ảnh/góc nhìn nhưng có thể cùng vật vật lý. Không coi mAP dev này là accuracy sân thi.
- Chưa kiểm chứng server BTC, tư thế quét, độ lệch camera/OSD hoặc toàn pipeline trên laptop BTC.
- Cần thêm ảnh thật A4 trên từng vật ở nhiều khoảng cách/zoom/ánh sáng; ưu tiên balo và số nhỏ/mờ.

## Chạy thử

```powershell
.\.venv\Scripts\python.exe -m src.cli run --source fpt_map/object/chair_gray_number_21.jpg --config configs/trained.json --output output/trained-image-001 --debug --max-frames 1
```

Ảnh đơn không đủ OCR consensus mặc định, thiếu telemetry cũng không tạo candidate hoàn chỉnh. Xem observations/debug để kiểm tra nhận vật và số; không tự bịa tầng/hướng.

Model và ảnh lớn giữ local theo gitignore. Chưa commit/push đợt train này.

## Kiểm tra model và cổng nhận số

- Vật không số: 10/10 ảnh được loại đúng.
- Ảnh A4 số 21: đạt (ghế xám, số 21).
- Với v3, đây là kiểm tra ảnh đã dùng để train/phát triển, không phải accuracy độc lập.

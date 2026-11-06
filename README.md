# FinalDrone

> Cập nhật live 06/11: dùng [hướng dẫn bàn giao KTN](KTN_README.md) và `configs/live.json`. Adapter đã tự tìm normalized telemetry trong status; 26 test qua, gồm HTTP status → pipeline → POST → ACK bằng client gốc. Chưa xác nhận trên server BTC thật. Phần live cũ bên dưới được thay thế bởi hướng dẫn KTN.

Pipeline Python cho AI Drone Challenge Indoor M4E. Đọc [context](PROJECT_CONTEXT.md), [kế hoạch một người](IMPLEMENTATION_PLAN.md) và [quy tắc quét](starter-kit-indoor/SCAN_RULES.md).

## Hiện trạng

- Đã có pipeline offline/realtime: detector local, phân màu, OCR hai chữ số, IoU tracking, OCR consensus, đồng bộ telemetry theo timestamp, tầng/hướng, ảnh debug và candidate.
- Đã có công cụ trích ảnh, gán nhãn, dự đoán/evaluate dataset, xuất YOLO và lệnh train.
- Adapter live có polling, queue gửi và outbox/retry. **Chưa kiểm chứng với server BTC thật**, cần schema status và token/session.
- Đã train các checkpoint custom cho 5 loại vật và lớp phụ `number_label`; model được chọn lưu local ở `models/best_detector.pt`, cấu hình ở `configs/trained.json`. Kết quả và giới hạn: [TRAINING_RESULTS.md](evaluation/TRAINING_RESULTS.md).
- Chỉ công nhận mục tiêu khi có giấy A4 và đọc đúng định dạng số; số có 6/9 cần gạch dưới để xác định chiều. Vật không số chỉ là proposal trong log chẩn đoán, không được tạo candidate/gửi bài.
- Kết quả chạy thật và giới hạn: [evaluation/IMPLEMENTATION_RESULTS.md](evaluation/IMPLEMENTATION_RESULTS.md).
- Dùng `chair_orange`, `chair_white`, `chair_gray`, `backpack`, `fire_extinguisher`. Người dùng xác nhận bỏ blue, dùng white; heading là yaw thân drone, camera luôn thẳng theo thân.

## Cài đặt (PowerShell, tại thư mục repo)

Cần Python 3.12 và FFmpeg. Không sửa Python global:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.cli prepare-assets
```

Nếu máy hiện tại không có `py`, dùng Python đã kiểm tra trong [context](PROJECT_CONTEXT.md) để tạo venv. Môi trường `.venv` ở workspace hiện tại đã được tạo và cài xong.

`prepare-assets` là bước download chủ động trước khi thi: YOLOv8n và OCR PP-OCRv4 mobile qua RapidOCR, lưu dưới `models/`, kèm checksum. Lệnh nhận diện yêu cầu asset local, không tự tải khi chạy. `requirements-lock.txt` ghi phiên bản thực tế trên Windows/Python 3.12; có thể cài torch CPU trước rồi dùng file lock khi cần tái lập. Kiểm tra giấy phép checkpoint/thư viện trước khi phân phối.

Giao diện YOLO dựa theo [Ultralytics Predict](https://docs.ultralytics.com/modes/predict/); OCR dựa theo [RapidOCR](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/). Adapter đã được chạy với phiên bản ghi trong lock.

## Chạy một ảnh

```powershell
.\.venv\Scripts\python.exe -m src.cli run --source fpt_map/object/chair_orange_1.JPG --output output/image-001 --debug --max-frames 1
```

Chọn thư mục output mới cho mỗi run. Nếu thiếu telemetry, ảnh vẫn nhận diện/OCR nhưng location không hợp lệ và không tạo candidate hoàn chỉnh. Không lấy việc không có candidate làm bằng chứng code crash.

CLI tự chọn `configs/trained.json` khi config và `models/best_detector.pt` đều có local; nếu không có thì dùng baseline. Có thể chỉ rõ `--config configs/trained.json`. Ảnh ghế cam mẫu không dán số sẽ không được vẽ như mục tiêu hợp lệ. Thử ảnh có số:

```powershell
.\.venv\Scripts\python.exe -m src.cli run --source fpt_map/object/chair_gray_number_21.jpg --config configs/trained.json --output output/numbered-object-001 --debug --max-frames 1
```

## Chạy video với telemetry gốc

```powershell
.\.venv\Scripts\python.exe -m src.cli run --source starter-kit-indoor/sample_data/flight_261106.mp4 --telemetry . --output output/video-001 --start-s 280 --step-s 2 --max-frames 30 --debug
```

`--telemetry .` đọc manifest/telemetry.jsonl tại root. Có thể truyền thư mục bản ghi khác hoặc JSON rút gọn. `--start-s` chọn điểm bắt đầu; `--step-s` lấy mẫu thưa theo timestamp video. Để xử lý mọi frame, bỏ `--step-s`.

Mô phỏng realtime, queue giữ frame mới nhất, thời lượng 300 giây:

```powershell
.\.venv\Scripts\python.exe -m src.cli run --source starter-kit-indoor/sample_data/flight_261106.mp4 --telemetry . --mode realtime --duration-s 300 --output output/realtime-001
```

Output:

| File/thư mục | Nội dung |
|---|---|
| `run.json` | Config, commit hiện tại, máy và phiên bản thư viện |
| `observations.jsonl` | Detection/OCR/location/telemetry theo quan sát và lý do reject |
| `candidates.jsonl` | Các quan sát hoàn chỉnh được chọn/cải thiện theo track |
| `evidence/` | JPEG toàn khung chưa vẽ |
| `debug/`, `crops/` | Ảnh vẽ bbox và crop số khi bật debug |
| `summary.json` | Số frame/quan sát/candidate, latency, frame age, RAM lấy mẫu và drop |

Nếu không có detection thì observations rỗng; summary vẫn được ghi. RAM là RSS process lấy mẫu, không phải tổng tài nguyên toàn hệ thống.

## Cấu hình và quy tắc location

Chỉnh bản sao `configs/offline.json`, chọn bằng `--config`.

- `heading_field=aircraft_yaw`, `heading_verified=true` theo xác nhận của người dùng.
- `scan_pose_verified=false`: trước khi bật cho run hợp lệ/live, xác nhận đang quét gần vị trí đã đo, camera thẳng thân, góc gimbal phù hợp tầng và tư thế quét. Đây là cờ xác nhận vận hành, code chưa tự định vị được drone ở giữa.
- Tuổi telemetry tối đa 3 giây, ít nhất 2 mẫu trong 4.5 giây, yaw lệch tối đa 5°, độ cao dao động tối đa 0.5 m, vùng tâm theo chiều ngang 20% là **ngưỡng khởi đầu cần đo**, không phải độ chính xác đã chứng minh.
- `gimbal_pitch_range` có thể đặt theo tư thế quét thực tế; hiện chưa có số đo nên để null. Không tự suy ra góc hợp lệ.
- Các dải tầng/hướng đã chốt nằm trong `starter-kit-indoor/telemetry-location.json`, không nhân thêm dung sai độ cao.
- Màu HSV trong config là điểm bắt đầu; cần hiệu chuẩn ánh sáng sân.

Một ảnh không đủ hai lần đọc số mặc định nên chưa tạo candidate. Không giảm số phiếu chỉ để làm đẹp kết quả thử ảnh.

## Tạo dữ liệu và gán nhãn

```powershell
.\.venv\Scripts\python.exe -m src.cli extract --video starter-kit-indoor/sample_data/flight_261106.mp4 --map-dir fpt_map --count 40 --output data
.\.venv\Scripts\python.exe -m src.cli annotate --manifest data/manifest.json
```

Workspace hiện đã có 52 ảnh và contact sheet `data/contact-sheet.jpg`; không chạy lại extract đè nhãn. Trên clone mới cần tự lấy video/map rồi chạy extract. Ảnh lớn không được commit; manifest ghi checksum và nguồn.

Công cụ annotate mở cửa sổ OpenCV kéo bbox, sau đó nhập loại/số/tầng/hướng ở terminal. Nhấn `s` để đánh dấu reviewed, `n` bỏ qua, `q` thoát. Pending khác ảnh đã review không có vật. Không tự gán số/tầng/hướng khi không rõ.

Manifest hiện tất cả là dev/pending. Trước train, thêm dữ liệu khác cảnh/chuyến bay và đổi split train/dev/holdout theo source_group; không chia frame gần nhau sang các split khác. Chưa có nhãn thì không công bố accuracy.

## Đo detector/OCR trên dataset

```powershell
.\.venv\Scripts\python.exe -m src.cli predict-dataset --manifest data/manifest.json --telemetry . --split dev --output output/predictions.json
.\.venv\Scripts\python.exe -m src.cli evaluate --manifest data/manifest.json --predictions output/predictions.json --split dev --output output/evaluation.json
```

Evaluate chỉ dùng ảnh reviewed; nếu không có ảnh reviewed sẽ dừng rõ ràng. IoU mặc định 0.5 là ngưỡng nội bộ, không phải phương pháp chấm bbox chính thức của BTC. Metric ở đây theo ảnh; chưa phải điểm gộp theo vật vật lý của lượt thi.

## Train detector custom sau khi gán nhãn

```powershell
.\.venv\Scripts\python.exe -m src.cli export-yolo --manifest data/manifest.json --output artifacts/yolo-dataset
.\.venv\Scripts\python.exe -m src.cli train --data artifacts/yolo-dataset/dataset.yaml --epochs 50 --device cpu --output experiments/detector-v1
```

Export yêu cầu ảnh reviewed ở cả train/dev và chặn source_group trùng split. Train CPU có thể lâu; có thể huấn luyện trên máy GPU với `--device 0`, còn đánh giá bản thi trên phần cứng BTC. Manifest 52 ảnh video/map ban đầu vẫn là hàng đợi để gán nhãn bổ sung; đợt custom đã chạy dùng annotation seed riêng bên dưới.

Đợt train đã thực hiện dùng bộ seed bbox riêng và COCO: xem [TRAINING_DATA.md](data/TRAINING_DATA.md), `src.build_training`, `src.train_campaign` và `src.select_model`. Môi trường `.venv-train` CUDA được tạo riêng cho GTX 1650; `.venv` vẫn là CPU. Model được chọn bằng dev chung, có giữ detector holdout; ảnh thật 21/62/99 đã dùng phát triển OCR nên không coi là holdout toàn pipeline.

Đợt v3 còn đưa ảnh ghế A4 số 21 vào train để sửa lỗi màu xám sáng; ảnh này không còn là detector holdout. Balo được bổ sung từ COCO train; holdout mới 20 ảnh chỉ có balo. Kết quả cụ thể và giới hạn nằm trong báo cáo train, không coi mAP dev là accuracy sân thi.

Tạo môi trường GPU mới trên máy có NVIDIA tương thích (không dùng file lock CPU để thay các wheel CUDA):

```powershell
py -3.12 -m venv .venv-train
.\.venv-train\Scripts\python.exe -m pip install -r requirements-train-gpu.txt
.\.venv-train\Scripts\python.exe -m pip install -r requirements.txt -r requirements-data.txt
```

Sau train, dùng best.pt local và khai báo class-map theo đúng thứ tự model:

```json
{"0":"chair_orange","1":"chair_white","2":"chair_gray","3":"backpack","4":"fire_extinguisher"}
```

Đặt object này vào `class_map` trong config, không thay mapping khi model có thứ tự khác. Nếu model đã phân lớp màu thì không chạy phân màu HSV cho các lớp đó.

## Live (chờ xác minh API thật)

1. Lấy response `/status` bằng token/session đội, xác nhận đường dẫn trường telemetry.
2. Đặt `delivery.status_telemetry_path`, state/time-left path đúng schema. Adapter hiện kỳ vọng telemetry normalized có `t_server` epoch mili giây, `alt_rel`, `yaw` và gimbal; cần sửa adapter nếu server khác.
3. Xác nhận tư thế quét rồi bật `scan_pose_verified`; đặt token trong biến môi trường.

```powershell
$env:DRONE_TEAM_TOKEN = '<token BTC cấp>'
.\.venv\Scripts\python.exe -m src.cli run --mode live --source rtsp://127.0.0.1:8554/m4e --server http://127.0.0.1:20201 --session '<session>' --config configs/live.json --output output/live-001
```

`configs/live.json` là bản sao do người vận hành cấu hình sau xác minh, chưa có file mặc định hợp lệ. Không truyền token trong CLI hay commit. Code không tự finish. Outbox chưa ACK giữ nguyên để retry qua `starter-kit-indoor/solution.py --retry` theo hướng dẫn kit; giữ đúng ID và JPEG.

Live chưa được chứng minh trên server BTC, chưa kiểm chứng độ lệch video/OSD hoặc compass khi bay thật. Retry 429 và bảo toàn packet đã được kiểm thử bằng client giả trong test, không phải gửi tới BTC.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Gồm biên tầng/hướng, telemetry không lấy mẫu tương lai, duplicate polling, ổn định/tư thế, tracking, OCR consensus, pending/decoy trong evaluation, JPEG có EXIF và retry cùng ID. Test pipeline dùng detector/OCR giả có ghi rõ; không dùng kết quả đó để nhận là accuracy thực địa.

## Việc còn cần làm

Bổ sung ảnh thật A4 trên mỗi vật ở góc drone và holdout theo chuyến bay độc lập → train/đo tiếp nếu cần → hiệu chuẩn tư thế/đồng bộ → xác nhận API live → thử đầy đủ trên laptop BTC và đóng gói. Xem [kế hoạch](IMPLEMENTATION_PLAN.md) để nghiệm thu từng bước.

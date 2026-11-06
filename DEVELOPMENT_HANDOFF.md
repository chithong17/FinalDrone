# KTN — Context công việc dang dở

Cập nhật ngày 06/11/2026, múi giờ Asia/Saigon. Đọc file này trước khi tiếp tục phát triển. Đây là bàn giao trạng thái thực tế, không phải xác nhận hệ thống đã chạy thành công trên sân thi.

## 1. Mục tiêu và yêu cầu đã chốt

Dự án FinalDrone cho AI Drone Challenge Indoor M4E. Đội **KTN**. Chạy trên CPU máy BTC, nhận RTSP, nhận telemetry, nhận diện vật có số A4, xác định tầng/hướng và gửi gói `submit_target` lên server chấm.

- Các loại vật: `chair_orange`, `chair_white`, `chair_gray`, `backpack`, `fire_extinguisher`. Người dùng xác nhận bỏ blue, dùng white.
- `number_label` là lớp phụ phát hiện giấy/số, không gửi làm loại vật.
- Vật không có giấy A4 hoặc không đọc được số hợp lệ thì không nhận là mục tiêu, không gửi bài.
- Số hai chữ số 01–99; 6/9 có gạch dưới để xác định chiều. Không tự đoán số khi mơ hồ.
- Heading lấy **yaw thân drone**; người dùng xác nhận camera luôn thẳng với thân drone.
- Phương án tầng/hướng dựa trên điều kiện drone ở giữa/vị trí đã đo. Code chưa tự định vị để xác minh điều kiện đó.

### Tầng theo `alt_rel` (m)

| Tầng | Dải áp dụng |
|---|---|
| 1 | dưới 7 |
| 2 | [7.4, 9.3] |
| 3 | [10, 12.5] |
| 4 | [13, 15] |
| 5 | từ 15.5 trở lên |

7 m và các khoảng hở không có tầng hợp lệ. Không áp dụng lại dung sai ±1 m cũ. Giá trị thiếu/không hữu hạn không được gán tầng.

### Hướng theo yaw

Biên các vùng: -47°, 7.1°, 133°, -173°; chuẩn hóa yaw về [-180, 180). NORTH từ -47 đến 7.1; EAST từ 7.1 đến 133; SOUTH qua điểm ±180 từ 133 đến -173; WEST từ -173 đến -47. Reject vùng sát mỗi biên ±10° theo cấu hình hiện tại.

Mốc sân: EAST = Trống đồng, WEST = Thư viện, NORTH = Thang máy, SOUTH = Nhà vệ sinh. Quy tắc thực thi ở `starter-kit-indoor/telemetry-location.json` và `telemetry_location.py`; dùng các file đó làm nguồn chính khi kiểm tra chi tiết biên.

## 2. Workspace và môi trường

```text
D:\FPTDocuments\Semester_8\AI-Drone\FinalDrone
```

PowerShell, Windows. Lệnh `python` global trên máy này đang trỏ đến Python314 đã bị xóa; ưu tiên `.venv\Scripts\python.exe`.

- `.venv`: môi trường CPU đã cài đủ runtime; Python 3.12, torch 2.15 CPU, Ultralytics 8.4.203, RapidOCR 3.10, ONNX Runtime 1.31.1. Xem `requirements-lock.txt` để biết phiên bản thực tế.
- `.venv-train`: môi trường GPU riêng, torch 2.11 CUDA 12.8 cho GTX 1650 4 GB. Có đường dẫn phụ thuộc trỏ sang site-packages của `.venv`, nên không coi đây là môi trường có thể copy sang máy khác. Dùng requirements để dựng lại.
- Python nền hoạt động nếu cần dựng venv: `C:\Users\ACER\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
- FFmpeg/ffprobe có trên PATH máy hiện tại. Không đóng gói môi trường ảo, video hoặc các executable này vào bài nộp.
- Một số test dùng thư mục tạm/HTTP loopback cần quyền chạy ngoài sandbox của công cụ; đây là giới hạn môi trường phát triển, không phải lỗi bài thi.

## 3. Những gì đã triển khai

| Thành phần | File chính | Trạng thái |
|---|---|---|
| Entrypoint nộp bài | `solution.py` | Tương thích --server, --session, --source, --weights, --calibration; tự chọn live khi có server |
| CLI/runtime | `src/cli.py` | Offline, realtime replay, live; warmup trước thu ảnh; metadata và summary |
| Nguồn ảnh | `src/sources.py` | Replay theo PTS, RTSP, queue giữ frame mới nhất; xử lý EXIF |
| Telemetry/location | `src/telemetry.py` | Timeline không lấy mẫu tương lai; kiểm tuổi mẫu, ổn định và tư thế quét |
| Detector/OCR | `src/vision.py`, `src/paper.py` | Model local, ghép giấy vào vật, OCR, chiều gạch dưới, đổi tọa độ về ảnh gốc |
| Tracking/pipeline | `src/tracking.py`, `src/pipeline.py` | IoU tracking, nhiều phiếu số, reject, log, evidence và candidate |
| Gửi bài | `src/delivery.py` | Poll status, deadline, queue, outbox trước HTTP, retry 429, lưu ACK |
| Client BTC | `starter-kit-indoor/indoor_client.py` | Giữ nguyên từ kit; có bản sao cùng nội dung ở root của ZIP |
| Dataset/train/evaluate | Các module tương ứng trong `src/` | Đã dùng tạo dữ liệu và train; không cần train lại để nộp thử |
| Đóng gói | `tools/package_submission.py` | Allowlist file, giới hạn model, checksum, kiểm ZIP |

`--calibration venue.json` được nhận để tương thích launcher nhưng không đọc file ROI đó, vì đội dùng thuật toán tầng/hướng riêng. Điều này ghi rõ trong README bàn giao.

## 4. Live adapter vừa hoàn thiện đến đâu

Kit xác nhận `GET /api/indoor/{session_id}/status` trả trạng thái, thời gian còn lại và telemetry, nhưng tài liệu trong repo không nêu chính xác wrapper JSON của telemetry.

`configs/live.json` đã có:

- `delivery.status_telemetry_path="auto"`.
- `status_state_path="state"`, `status_time_left_path="time_left_s"`, theo code baseline của BTC.
- `heading_field="aircraft_yaw"`, `heading_verified=true`, `scan_pose_verified=true`.

Adapter tìm **một object duy nhất** có các trường normalized `t_server`, `alt_rel`, `yaw`, ở trong các object lồng nhau. `t_server` phải là epoch ms. Không tìm trong mảng lịch sử, không thay timestamp bằng giờ polling. Thiếu/sai/mơ hồ thì ghi `telemetry_unavailable`, không thêm mẫu; có thể tiếp tục nhận video nhưng location không hợp lệ sẽ không gửi bài. Nếu đã biết đường dẫn thật có thể đặt dotted path cụ thể thay `auto`.

**Điểm chưa xác minh:** server thật có trả đúng normalized object này không. Mẫu trường dựa trên ảnh dashboard người dùng cung cấp; chưa có response JSON thật, token/session BTC hoặc RTSP thật để kiểm chứng. Không được mô tả auto-discovery là đã xác nhận mọi schema server.

`scan_pose_verified=true` là xác nhận **điều kiện vận hành theo phương án người dùng chốt**, không phải đo kiểm tự động. `configs/trained.json` vẫn để false cho offline. Không tự bật cờ tương tự cho tư thế bay khác.

Ngưỡng hiện tại: mẫu tối đa 3 s, cửa sổ ổn định 4.5 s, ít nhất 2 mẫu khác timestamp, yaw spread tối đa 5°, alt spread tối đa 0.5 m, vật trong vùng tâm ngang 20%. Các ngưỡng này cần đo trên sân; chưa được chứng minh là tối ưu. Gimbal pitch chưa có dải hiệu chuẩn, đang null.

## 5. Model và dữ liệu

Model đang dùng: `models/best_detector.pt`, 6,488,938 bytes; nguồn `experiments/detector-real-a4-v3/weights/best.pt`.

```text
SHA256 d77fdf0a727d7895f355d185d2120426b0b6cc9a77f067763acc14a8acafdd94
Classes: chair_orange, chair_white, chair_gray, backpack, fire_extinguisher, number_label
```

- Đã chạy 5 đợt train, chọn v3 ở imgsz 640, confidence 0.35, CPU.
- Dữ liệu v3: 523 train / 90 dev / 20 holdout. Có ảnh địa phương, biến thể A4 tổng hợp và balo từ COCO theo yêu cầu người dùng.
- Ảnh ghế xám A4 số 21 đã đưa vào train để sửa nhầm trắng/xám. Kết quả đúng ảnh 21 chỉ là training fixture.
- Dev mAP50 khoảng 0.830; holdout mới 20 ảnh **chỉ có balo**, mAP50 khoảng 0.316. Không dùng dev metric để tuyên bố độ chính xác sân thi.
- Ảnh số 62/99 đã dùng phát triển OCR, không phải holdout độc lập.
- OCR local trong `models/ocr`: det.onnx, cls.onnx, rec.onnx, params.json.
- `configs/model-manifest.json` vẫn ghi `ready_for_competition=false` vì chưa nghiệm thu thực địa.

Chi tiết: `evaluation/TRAINING_RESULTS.md`, `data/TRAINING_DATA.md`, `evaluation/training-v3-20261106/selection.json`.

Dữ liệu bay đã ghép: `starter-kit-indoor/sample_data/flight_261106.mp4` và `flight_261106_telemetry.json`. Telemetry gốc ở root (manifest/telemetry.jsonl); dùng đồng bộ PTS, không dùng thời gian xử lý. Không đưa dữ liệu này vào ZIP/Git.

## 6. Kiểm thử đã có — phân biệt rõ phạm vi

- **26/26 unittest qua** sau thay đổi adapter live.
- `tests/test_live_http.py` chạy server aiohttp cục bộ và IndoorClient thật của kit: GET status có 2 mẫu, pipeline 2 frame → số đồng thuận → tầng 2/EAST → POST → ACK lưu file. Kiểm JPEG byte-for-byte, bbox và captured_at_ms.
- Detector/OCR trong test HTTP là fixture có chủ đích; không phải phép đánh giá model thật hoặc server BTC thật.
- Đã giải nén ZIP mới sang `output/ktn-verified-live-adapter/KTN_submission` rồi chạy model/OCR thật với ảnh 21, tham số --weights/--calibration. Exit 0, 1 detection; candidates=0 đúng vì không telemetry/chỉ 1 frame.
- Trước đó có regression 16/16 trường hợp OCR phát triển (ảnh thật + xoay), 10/10 ảnh vật không số bị loại; không coi là accuracy độc lập.
- `pip check` không có phụ thuộc hỏng; compileall qua; client BTC gốc không bị sửa.

**Chưa có ACK từ BTC thật. Chưa có test end-to-end RTSP thật + OSD thật + model thật + server chấm thật.** Benchmark realtime cũ được chạy trước model/OCR hiện tại nên không đại diện hiệu năng bản cuối.

Chi tiết kiểm tra mới: `evaluation/LIVE_INTEGRATION_RESULTS.md`.

## 7. Gói nộp hiện có và cách tái tạo

Gói mới nhất: `output/KTN_submission.zip` (~22.8 MB, model tổng ~22.7 MB). README trong ZIP lấy từ `KTN_README.md`; có model/OCR, code, config live, mapping và ảnh mồi nhỏ. Không kèm sample_data/video/dataset/môi trường ảo. Có SHA256SUMS.json cho file trong gói.

```powershell
cd D:\FPTDocuments\Semester_8\AI-Drone\FinalDrone
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/package_submission.py
```

Lệnh BTC dự kiến, tại thư mục giải nén và dùng Python môi trường BTC:

```powershell
$env:DRONE_TEAM_TOKEN = '<token BTC cấp>'
python solution.py --server http://127.0.0.1:20201 --session '<session_id>' --source rtsp://127.0.0.1:8554/m4e --weights models/best_detector.pt --calibration venue.json
```

Chưa thực hiện upload hoặc gửi thầy. Người dùng đã được cung cấp link ZIP để tự upload vào Google Drive riêng đội KTN. Không tự gửi email/tin nhắn thay người dùng.

Gói `output/FinalDrone_test_submission.zip`, `SUBMISSION_TEST.md`, `check_connection.py` và `output/KTN_SUBMISSION_README.md` là sản phẩm **bản thử cũ**. Không lấy chúng làm nguồn hiện trạng hoặc gửi thay gói KTN mới. Một số đoạn cũ trong README/context vẫn nói live bị chặn vì path null; xem cập nhật đầu file và các tài liệu KTN mới để tránh nhầm.

## 8. Công việc dang dở — thứ tự tiếp tục

1. **Ưu tiên cao nhất: kiểm chứng server thật.** Lấy quyền truy cập hợp lệ/token/session test, xác nhận response status có normalized telemetry. Nếu khác, bổ sung adapter theo response thật và test regression. Không sáng tác endpoint, trường dữ liệu hoặc độ cao/yaw thay thế.
2. Chạy phiên test đầy đủ với RTSP thật: kiểm timestamp/clock skew/độ trễ video–OSD, mẫu cũ/tương lai, mất telemetry và mất mạng. Chỉ kết luận nhận bài khi có ACK thật khớp ID; pending_review chưa phải điểm.
3. Đo hiệu năng bản model/OCR hiện tại trên CPU BTC trong 300 s: FPS, P50/P95, tuổi frame, drop, RAM, số mục tiêu gửi. Không lấy benchmark cũ thay thế. Tối ưu sau khi có số đo.
4. Kiểm thử thực địa floor/direction, tư thế quét ở giữa, camera/gimbal và các biên yaw/alt. Xác minh sai số ±10° và ngưỡng ổn định bằng dữ liệu thật; không đổi dải tầng người dùng chốt nếu chưa được yêu cầu.
5. Thu ảnh/video drone của cả 5 lớp có A4 từ xa, nghiêng, thiếu sáng, nhiều vật và decoy; gán nhãn bbox toàn vật + giấy/số. Tách source/chuyến bay trước train/dev/holdout. Ưu tiên balo, nhầm ghế trắng/xám và bbox lỏng.
6. Đánh giá chất lượng OCR/6–9 và detector trên holdout độc lập; bổ sung dữ liệu/train nếu có bằng chứng cần. Không tiếp tục tối ưu chỉ trên ảnh 21.
7. Rà delivery khi queue đầy hoặc gửi thất bại: hiện pending có outbox, cần kiểm chứng khả năng retry trong cùng lượt và khi restart; pipeline chỉ enqueue khi candidate cải thiện chất lượng, nên xem trường hợp candidate không cải thiện sau lần enqueue bị từ chối. Kiểm tra dedup khi track mất rồi tạo lại và quota 30 NEW/chu kỳ.
8. Sau mọi sửa runtime/model/config, chạy test liên quan, đóng gói lại, giải nén thử từ ZIP và kiểm lệnh launcher. Rà tài liệu cũ cho nhất quán; không chỉ sửa file ngoài ZIP.
9. Commit/push khi người dùng yêu cầu; đảm bảo code/tài liệu đủ để clone phát triển, và mô tả cách cấp trọng số ngoài Git vì model/raw data đang bị ignore.

## 9. Git và điều không được hiểu nhầm

Cập nhật khi bàn giao lên Git: nhánh tiếp tục phát triển là `ktn/live-integration-handoff`, tạo từ main theo yêu cầu người dùng. Checkpoint bàn giao bao gồm source/config/test/report/context và bộ model runtime/OCR cùng ảnh mồi 21 được stage tường minh dù nằm trong đường dẫn ignore. Clone nhánh này có thể chạy ảnh mồi và đóng gói lại mà không tải model. Video, dữ liệu train và môi trường ảo vẫn không đưa lên Git. Các ghi chú chưa commit bên dưới mô tả trạng thái trước checkpoint này; dùng `git status` và `git log` để xác nhận trạng thái hiện hành.

- Remote: `https://github.com/chithong17/FinalDrone.git`, nhánh main.
- Commit ban đầu đã push: `b8ebc7e`. **Các thay đổi triển khai, train, adapter, test và đóng gói sau đó hiện còn modified/untracked; chưa commit/push.** Xem git status trước khi thao tác.
- `.gitignore` đang được sửa để bỏ qua model, dữ liệu lớn, output, môi trường và artifacts. Không chạy git add toàn bộ thiếu kiểm tra; không commit token, raw recordings hoặc `.venv`.
- User trước đây từng yêu cầu đưa lên main, nhưng trạng thái hiện tại không đồng nghĩa các thay đổi mới đã lên Git. Không báo đã push khi chưa kiểm chứng.
- Không sửa `starter-kit-indoor/indoor_client.py`; wrapper/adapter đặt bên ngoài. API không điều khiển bay; code không tự finish lượt.
- Tài liệu chỉ hướng dẫn đo/đánh giá; không tự hạ guard, tạo telemetry giả hoặc gán tầng/hướng để làm đẹp kết quả nộp thử.

## 10. Nguồn đọc tiếp

- `KTN_README.md`: cách chạy gói bàn giao mới nhất.
- `evaluation/LIVE_INTEGRATION_RESULTS.md`: bằng chứng và giới hạn test live cục bộ.
- `PROJECT_CONTEXT.md`: bối cảnh rộng, dữ liệu và quyết định lịch sử.
- `IMPLEMENTATION_PLAN.md`: kế hoạch tuần tự cho một người, không phải chia việc nhóm.
- `starter-kit-indoor/SCAN_RULES.md`: quy tắc quét/tầng/hướng.
- `starter-kit-indoor/README.md`: contract API, ACK, quota, outbox.
- `starter-kit-indoor/261105-huong-dan-nop-bai-chung-ket-indoor.md`: quy định gói/launcher/nộp Drive.

Không cần train lại hoặc viết lại pipeline từ đầu. Việc tiếp theo có giá trị nhất là kiểm chứng tích hợp thật và thu dữ liệu A4 độc lập để biết chính xác lỗi còn lại.

# Kế hoạch triển khai FinalDrone cho một người

Cập nhật: 06/11/2026. Đây là lộ trình tuần tự từ hiện trạng đến bản thi hoàn chỉnh, không phải kế hoạch phân công nhóm. Mỗi người có thể dùng cùng lộ trình để tự triển khai và so sánh kết quả.

Đọc [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) trước khi bắt đầu. Các module và cấu trúc đề xuất trong tài liệu chưa đồng nghĩa đã triển khai.

## 1. Mục tiêu cuối

Chương trình chạy offline và live: ảnh/video/RTSP → nhận vật → tracking → tìm nhãn và đọc số → ghép telemetry → tầng/hướng → chọn bằng chứng → outbox → API BTC.

Đầu ra gồm loại vật, số 1–99, tầng, hướng, bbox toàn vật trên ảnh gốc, JPEG gốc chưa vẽ và thời điểm thu frame. Không dùng giá trị giả lấp dữ liệu thiếu. Ưu tiên bbox/decoy và độ chính xác trước tốc độ model.

## 2. Quy tắc đã chốt

### Tầng

Dùng `alt_rel`, được kit trích từ `elevation`, đơn vị mét. Dải mới thay thế quy tắc ±1 m; không cộng thêm dung sai:

| Tầng | Dải hợp lệ |
|---|---|
| 1 | alt_rel < 7 |
| 2 | [7.4, 9.3] |
| 3 | [10, 12.5] |
| 4 | [13, 15] |
| 5 | alt_rel ≥ 15.5, không có cận trên |

Tầng 1 không đặt cận dưới. Đúng 7 m và các khoảng trống giữa dải: chưa xác định tầng.

Ngoài dải hoặc thiếu dữ liệu trả None; không làm tròn và không lấy tầng gần nhất. Đây là quy ước quét theo độ cao drone, cần giữ góc camera phù hợp để tránh vật tầng khác lọt vào lượt quét.

### Hướng

| Hướng | Khoảng cơ sở | Mốc |
|---|---|---|
| NORTH | -47° đến 7.1° | Thang máy |
| EAST | 7.1° đến 133° | Trống đồng |
| SOUTH | 133° qua ±180° đến -173° | Nhà vệ sinh |
| WEST | -173° đến -47° | Thư viện |

Loại vùng ±10° quanh mỗi ranh giới. Chỉ xác nhận khi drone gần vị trí đo, vật gần tâm ảnh, camera đúng hướng hiệu chuẩn và yaw ổn định.

Dùng lại `starter-kit-indoor/telemetry_location.py` và cấu hình đi kèm. Người dùng đã xác nhận dùng yaw thân drone (`attitude_head`), camera luôn thẳng theo thân; không cộng yaw gimbal. Ghế đã xác nhận dùng cam/trắng/xám, bỏ blue.

## 3. Bước 1 — Dựng môi trường và chuẩn bị asset

Thực hiện:

1. Tạo Python 3.12 trong môi trường riêng, kiểm tra FFmpeg và dependency. Lệnh python hiện trên máy đang trỏ tới Python đã mất; xem cách chạy tạm trong context.
2. Chuẩn bị detector/OCR local, ghi phiên bản và đường dẫn tương đối; chưa tối ưu backend ngay.
3. Xác nhận BTC về nhãn ghế trắng/xanh, schema telemetry API, cách khởi chạy và tài nguyên máy thi. Trong lúc chờ vẫn triển khai offline, tách mapping nhãn gửi server khỏi lớp nội bộ.
4. Rà soát gitignore: loại token, môi trường ảo, cache, dữ liệu lớn và output sinh; không công khai telemetry thô có trường bí mật.
5. Giữ nguyên `indoor_client.py` theo hướng dẫn BTC. Giữ baseline gốc để đối chiếu, phát triển entrypoint riêng.

Đầu ra: môi trường tái lập, config mẫu, asset local và lệnh cài/chạy.

Nghiệm thu: mở được ảnh/MP4, load detector và OCR không tự tải model. Ghi rõ lớp chưa hỗ trợ; COCO không có bình cứu hỏa.

## 4. Bước 2 — Tạo tập đánh giá nhỏ

Thực hiện:

1. Chọn khoảng 30–50 ảnh khởi đầu từ video đã ghép và ảnh map; có vật xa/gần, mờ, nghiêng, thiếu sáng, số khó đọc, vật không số và nền gây nhầm. Mở rộng khi thiếu tình huống.
2. Gán bbox toàn vật và bbox nhãn số riêng. Ghi loại, chuỗi số hai chữ số, ID vật vật lý khi biết, tầng/hướng khi có bằng chứng; không đoán nhãn unknown.
3. Bổ sung balo nếu dữ liệu hiện có thiếu. Ảnh điện thoại chụp gần không thay thế đánh giá video drone.
4. Chia train/dev/holdout theo chuyến bay hoặc nhóm cảnh; không để frame kề nhau hay biến thể cùng ảnh lọt sang split khác.
5. Tạo manifest versioned: ID, nguồn, timestamp, split, đường dẫn tương đối, checksum và cách lấy dữ liệu lớn.

Đầu ra đề xuất: `data/manifest.json`, nhãn và hướng dẫn lấy dữ liệu.

Nghiệm thu: ảnh/bbox/nhãn khớp, có dữ liệu decoy, có holdout khóa trước so sánh cuối. Không tinh chỉnh liên tục theo holdout.

## 5. Bước 3 — Nhận vật trên một ảnh

Thực hiện:

1. Viết adapter detector: ảnh gốc vào, class/confidence/bbox toàn ảnh ra.
2. Chạy detector nano pretrained làm baseline thực tế; đo xem có nhận được ghế lục giác không.
3. Phân màu ghế bằng HSV đã đo hoặc model lớp màu. Tách tên lớp nội bộ khỏi mapping API để xử lý trắng/xanh sau khi BTC xác nhận.
4. Dùng checkpoint có lớp bình cứu hỏa hoặc gán nhãn/huấn luyện bổ sung nếu cần. Sửa class-map không tạo khả năng nhận diện mới.
5. Kiểm tra hoàn nguyên resize/letterbox/crop; bbox integer, diện tích dương, nằm trong ảnh gốc.
6. Xuất ảnh debug có bbox và giữ ảnh bằng chứng gốc chưa vẽ.

Đầu ra: lệnh chạy một ảnh, JSON detection, ảnh debug và báo cáo dev theo loại.

Nghiệm thu: đo precision/recall, bỏ sót/false positive và chất lượng bbox; ghi lớp chưa hỗ trợ. Chỉ train/nâng cấp khi lỗi quan sát chỉ ra nhu cầu.

## 6. Bước 4 — Tìm nhãn và OCR

Thực hiện:

1. Đo OCR trên crop nhãn chuẩn trước, sau đó crop tự tìm trong bbox vật để tách hai nguồn lỗi.
2. Không mặc định ROI nhãn cố định phù hợp mọi loại vật. Thử tìm nhãn, xoay/chỉnh phối cảnh khi cần.
3. Thử dùng gạch chân để xác định chiều, rồi loại gạch khỏi vùng đọc; không giả định mọi frame thấy gạch rõ.
4. So sánh OCR local khả dụng trên cùng crop/dev, ví dụ RapidOCR và Tesseract. Benchmark synthetic trong tài liệu không thay kết quả ảnh thật.
5. Chỉ nhận đúng hai chữ số 01–99; lưu chuỗi gốc, confidence, crop và lý do reject. Không tự sửa O thành 0 hoặc thêm 0 đầu.

Đầu ra: adapter OCR, exact match hai chữ số, tỷ lệ nhận sai/reject và thời gian xử lý trên crop chuẩn/crop tự tìm.

Nghiệm thu: vật không nhãn không sinh số mặc định; có ví dụ lỗi 6/9, xoay, che khuất và mờ, không chỉ ảnh thành công.

## 7. Bước 5 — Đồng bộ telemetry và tầng/hướng

Thực hiện:

1. Lọc OSD drone theo manifest/topic, giữ alt_rel, yaw drone/gimbal, pitch, zoom và timestamp. Giá trị thiếu giữ None.
2. Gắn PTS/timestamp cho từng frame. Mốc ban đầu: thời gian video = thời gian bản ghi trừ `manifest.video_parts[0].clock.t0`.
3. Kiểm chứng độ lệch bằng các đoạn quay/đổi độ cao. Không neo telemetry theo frame đầu được xử lý hoặc thời gian suy luận.
4. Kiểm chứng heading bằng quay thân và gimbal riêng; lưu trường được dùng và tư thế hiệu chuẩn.
5. Gọi hai hàm phân loại đã có; thêm kiểm tra tư thế quét, vật gần tâm, tuổi mẫu và yaw/độ cao ổn định.
6. Đưa ngưỡng tuổi telemetry, cửa sổ ổn định và vùng tâm ảnh vào config, chọn bằng thử nghiệm. OSD hiện khoảng 2 giây/mẫu; gọi API nhanh không tạo số đo mới.

Đầu ra: mỗi frame có mẫu telemetry, tuổi mẫu, tầng/hướng hoặc lý do chưa xác định, xem được qua debug/viewer.

Nghiệm thu: đúng ở các biên dải độ cao mới, khoảng trống tầng, wrap ±180°, đệm ±10°, mẫu thiếu/cũ và camera lệch. Không chốt location khi tư thế không hợp lệ.

## 8. Bước 6 — Ghép video offline và tracking

Thực hiện:

1. Ghép detector/OCR/location chạy video; trước tiên có chế độ xử lý đầy đủ frame để debug.
2. Thêm tracking; track ID không dùng số nhãn vì nhiều vật có thể trùng số.
3. Tích lũy OCR qua nhiều quan sát, cho phép đọc lại khi chưa chắc; không khóa vĩnh viễn kết quả đọc đầu.
4. Chọn frame rõ và bbox phù hợp, giữ nguyên một quan sát hoàn chỉnh làm bằng chứng.
5. Thử policy OCR mỗi frame/định kỳ/khi track cần đọc lại trên cùng video và detector.
6. Thêm mô phỏng realtime theo PTS với queue một frame mới nhất, drop frame cũ. Báo riêng chế độ đầy đủ và realtime.

Đầu ra: lệnh chạy video, log theo frame/track, candidate, JPEG gốc và lý do reject.

Nghiệm thu: chạy xuyên suốt không crash; rà vật gộp/tách nhầm, duplicate, số sai, ảnh/telemetry cũ và vật khác tầng lọt vào lượt quét.

## 9. Bước 7 — Live và gửi bài

Thực hiện:

1. Khi có quyền/token/session, lấy response thật `/api/indoor/{session_id}/status`, xác nhận schema/timestamp; không đoán cấu trúc từ dashboard.
2. Tạo polling async và cache telemetry live cùng schema nội bộ của offline.
3. Nhận RTSP, ghi thời điểm thu frame, đo lệch với OSD. Không lấy thời điểm xử lý xong làm thời điểm chụp.
4. Tách vòng gửi khỏi nhận diện, giới hạn queue, lưu outbox trước request đầu.
5. Dùng `make_packet`/`IndoorClient` sẵn có; retry cùng ID/payload/JPEG, xử lý 429 theo Retry-After.
6. Xử lý lỗi 401/400/404/409/410 và deadline theo server; lưu ACK/trạng thái gửi để phục hồi sau restart.
7. Không tự finish; ACK pending_review không phải điểm.

Đầu ra: CLI offline/live, config mẫu không chứa token, outbox và log.

Nghiệm thu: thử trên môi trường được phép; nhận ACK hợp lệ, truy được frame gốc; kiểm tra mất RTSP/telemetry, timeout, 429, đóng lượt và restart không làm treo nhận diện.

## 10. Bước 8 — So sánh và tối ưu

Chỉ tối ưu sau khi có baseline toàn pipeline; đo chỗ nghẽn trước khi đổi ONNX/OpenVINO, model hoặc resolution.

| Thành phần | Chỉ số |
|---|---|
| Detector | Precision/recall theo loại, bỏ sót, false positive, bbox |
| OCR | Exact match, chấp nhận sai, reject rate |
| Location | Đúng tầng/hướng, unknown, lỗi theo tuổi mẫu/tư thế |
| Tracking | Gộp/tách nhầm, duplicate, bỏ quan sát tốt |
| End-to-end | Số vật đúng đủ trường, decoy được chọn gửi, điểm ước tính |
| Hiệu năng | Latency P50/P95, FPS pipeline, tuổi frame, RAM, queue |
| Delivery | Outbox, ACK, retry, lỗi, candidate không kịp gửi |

Quy tắc:

- Cùng dataset version, split, máy và chế độ chạy; thay một thành phần mỗi lần khi muốn biết nguyên nhân cải thiện.
- Ghi model FPS riêng pipeline FPS; kết quả máy cá nhân không mặc định bằng laptop BTC.
- Điểm ước tính theo 3+3+2+2, bbox/decoy là điều kiện cần; một vật lấy bản tin hoàn chỉnh tốt nhất, không ghép trường từ nhiều bản tin.
- Review bbox bằng mắt theo đề. Nếu dùng IoU nội bộ phải công bố ngưỡng, không coi là điểm trọng tài.
- Giữ holdout cho cấu hình cuối, ghi nhận lần dùng. Chạy lặp cấu hình vào vòng cuối và báo độ biến động.
- Mỗi run lưu config, commit SHA, dependency, model/checksum, dataset version, phần cứng, metrics và lỗi tiêu biểu tại `experiments/<run_id>/` hoặc tương đương.
- Giữ baseline cũ đến khi phương án mới có bằng chứng tốt hơn.

Nghiệm thu: bảng so sánh tái lập được và lý do chọn dựa trên chất lượng/độ trễ/ổn định.

## 11. Bước 9 — Thử 300 giây và đóng gói

- Chạy trọn 300 giây trên điều kiện đích, kiểm tra crash, queue, tài nguyên và dữ liệu cũ.
- Khởi động từ môi trường sạch; model/OCR local không cần download khi thi.
- Tổng models ≤150 MB; loại sample_data, video, archive, môi trường ảo và cache khỏi bài nộp.
- Dùng đường dẫn tương đối; tuân thủ quy định BTC về binary, không tự kèm installer/executable ngoài quy định.
- README có dependency, cách lấy asset, token/session, lệnh offline/live và retry.
- Lưu commit/config đã kiểm chứng; chỉnh cấu hình sau đo phải kiểm tra lại phần bị ảnh hưởng.

Nghiệm thu: người khác có thể chạy lại theo README; có kết quả 300 giây, log và checklist đóng gói.

## 12. Cấu trúc và contract đề xuất

Chỉ tạo module khi đến bước cần dùng, giữ cấu trúc nhỏ:

```text
src/contracts.py
src/detectors/
src/ocr/
src/telemetry/
src/location/
src/tracking/
src/pipeline/
src/delivery/
configs/
data/manifest.json
evaluation/
experiments/
```

| Kiểu | Nội dung tối thiểu |
|---|---|
| Frame | ID, ảnh gốc BGR/JPEG, kích thước, PTS offline, thời điểm thu live |
| Detection | ID/frame ID, lớp gốc, loại nội bộ, confidence, bbox toàn ảnh |
| NumberRead | Detection ID, chuỗi gốc, số hoặc None, confidence, bbox nhãn, lý do reject |
| TelemetrySample | Thời gian đo/nhận/video, alt_rel, yaw drone/gimbal, pitch, zoom, nguồn |
| LocationResult | Floor/direction hoặc None, tuổi mẫu, tư thế hợp lệ, lý do reject |
| Observation | Frame/detection/track ID, detection, OCR, location, chất lượng ảnh |
| SubmissionCandidate | Một quan sát được chọn, JPEG gốc và trường gửi API |

Quy ước: bbox XYXY trên ảnh gốc; mét, độ, epoch mili giây, video giây. Giá trị thiếu giữ None. Confidence backend phải ghi thang đo. Không dùng số nhãn làm ID vật. Định nghĩa contract trước khi ghép các module.

## 13. Tiến độ và việc làm ngay

Đã triển khai CLI và pipeline mới trong `src/`; cách chạy ở [README.md](README.md). Các mục sau phân biệt đã viết công cụ với đã nghiệm thu chất lượng:

- [x] Bước 1: môi trường `.venv`, dependency và asset local đã cài/load được.
- [ ] Bước 2: đã có seed bbox local + COCO, bộ v3 633 ảnh; cần holdout chuyến bay thật cho đủ lớp và ảnh A4 thật đa dạng hơn.
- [ ] Bước 3: đã train 5 đợt, chọn `models/best_detector.pt`; chưa nghiệm thu field accuracy, lớp balo vẫn yếu trên holdout mới.
- [ ] Bước 4: OCR thật 21/62/99 đạt 16/16 case xoay/âm tính; còn cần đo số nhỏ/mờ và nhãn thực địa mới.
- [ ] Bước 5: timestamp/location và kiểm thử đã có; chờ kiểm chứng đồng bộ/tư thế thực địa.
- [ ] Bước 6: pipeline video/tracking đã chạy; chờ nghiệm thu chất lượng bằng nhãn.
- [ ] Bước 7: adapter live/outbox đã có và test retry; chờ schema/token/session BTC để xác minh.
- [ ] Bước 8: đã so sánh checkpoint/resolution trên dev và kiểm tra holdout nhỏ; kết quả ở `evaluation/TRAINING_RESULTS.md`, chưa có so sánh độc lập trên chuyến bay mới.
- [ ] Bước 9: đã smoke realtime 300 giây trên máy hiện tại; chưa nghiệm thu chất lượng, máy BTC/đóng gói. Kết quả: [IMPLEMENTATION_RESULTS.md](evaluation/IMPLEMENTATION_RESULTS.md).

Điểm tiếp tục là bước 2: gán nhãn và tạo split độc lập. Mỗi mốc cập nhật context, lệnh chạy và commit; chỉ đánh dấu hoàn thành sau nghiệm thu, không chỉ vì đã viết code. Chưa commit/push các thay đổi triển khai này.

Model và cổng nhận mục tiêu hiện yêu cầu số trên A4; trường hợp có 6/9 phải xác định được chiều qua gạch dưới. Ảnh ghế số 21 đã dùng train v3, không dùng để tuyên bố accuracy holdout.

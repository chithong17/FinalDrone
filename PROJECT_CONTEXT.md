# Context dự án FinalDrone

Cập nhật: 06/11/2026 (Asia/Saigon). Tài liệu bàn giao hiện trạng và các quyết định đã chốt; đọc trước khi tiếp tục phát triển.

Lộ trình triển khai tuần tự cho một người từ môi trường đến bản thi hoàn chỉnh: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Tài liệu có đầu ra, điều kiện nghiệm thu và cách so sánh phương án ở từng bước; các cấu trúc/module đề xuất chưa đồng nghĩa đã được triển khai.

## 1. Mục tiêu

Phát triển bài thi AI Drone Challenge FA26, chung kết Indoor DJI Matrice 4E tại FPT Quy Nhơn. Nhận video drone, phát hiện mục tiêu có nhãn số, xác định loại vật, số, tầng và hướng, rồi gửi ảnh bằng chứng cùng bbox lên server BTC trong lượt thi 300 giây.

- Tổng 10 mục tiêu, tối đa 100 điểm.
- Bbox phải khoanh đúng vật trên ảnh gốc; bbox sai hoặc vật không có số (decoy) nhận 0 điểm toàn bộ.
- Mỗi mục tiêu: loại 3 điểm, số 3 điểm, tầng 2 điểm, hướng 2 điểm.
- Số trên nhãn là 01–99; API nhận integer 1–99.
- Mỗi chu kỳ tối đa 30 bản tin mới hợp lệ; lần 31 bị từ chối và khóa 15 giây, không cộng thời gian thi.
- ACK `pending_review` chỉ xác nhận nhận bài, chưa phải điểm.
- Theo hướng dẫn BTC: bài chạy trên laptop BTC; server `http://127.0.0.1:20201`, video `rtsp://127.0.0.1:8554/m4e`. Token và session do BTC cấp khi thi, không lưu token vào Git.

## 2. Cấu trúc và dữ liệu hiện có

| Đường dẫn | Nội dung |
|---|---|
| `starter-kit-indoor/` | Kit Python, hướng dẫn, cấu hình mẫu và các module bổ sung |
| `manifest.json`, `telemetry.jsonl`, `laser.jsonl`, `video/p1/` | Bản ghi 06/11: khoảng 459 giây, 217 đoạn TS, 1.706 bản tin telemetry tổng, 224 OSD drone |
| `261105 - trong nhà/261105-174737-dataset/` | Bản ghi 05/11: khoảng 930 giây, 404 đoạn TS, 2.907 bản tin telemetry tổng, 461 OSD drone |
| `starter-kit-indoor/sample_data/` | Video MP4 và telemetry phục vụ thử nghiệm offline |
| `fpt_map/` | Ảnh tham chiếu tầng 1–5, nhiều góc nhìn và ảnh vật thể |
| `Drive/`, `fpt_map.zip` | Archive nguồn; nhiều dữ liệu trùng bản đã giải nén |
| `output/recording-viewer.html` | Trình xem video và telemetry được sinh cục bộ |
| `261103-de-thi-chung-ket-indoor-m4e-1.1.pdf` | Đề thi 3 trang |
| `261106-bao-cao-tong-hop-benchmark-laptop-btc-6-pha.md` | Báo cáo benchmark tham khảo; chưa có trial gốc kèm trong workspace |

Hai ảnh nhãn số người dùng gửi trong hội thoại là **99** và **62**, chữ đen nền trắng, có gạch chân. Gạch chân có thể hỗ trợ xác định chiều đọc; chưa triển khai xử lý này. Không giả định các ảnh đính kèm hội thoại đã được lưu thành file trong repository.

Map hiện có ảnh ghế lục giác trắng, cam, xám, bình cứu hỏa và ghế dài. Tên `d1/d2/d3/d4` trong map chưa được xác nhận ánh xạ sang hướng địa lý.

## 3. Quyết định đã chốt: xác định hướng bằng yaw

Người dùng đã đo góc tại vị trí drone ở giữa giếng trời và chốt sử dụng góc nhìn để phân loại `direction`.

Mốc thực địa theo hướng dẫn BTC:

| Direction | Mốc |
|---|---|
| `EAST` | Trống đồng |
| `WEST` | Thư viện |
| `NORTH` | Thang máy |
| `SOUTH` | Nhà vệ sinh |

Số đo do người dùng cung cấp:

| Vị trí nhìn | Yaw |
|---|---:|
| Giữa cạnh NORTH | -22.3° |
| Giữa cạnh EAST | 67.7° |
| Giữa cạnh SOUTH | 157.7° |
| Giữa cạnh WEST | -112.3° |
| Góc NORTH/EAST | 7.1° |
| Góc EAST/SOUTH | 133° |
| Góc SOUTH/WEST | -173° |
| Góc WEST/NORTH | -47° |

Khoảng phân loại cơ sở, trước khi loại vùng đệm:

| Direction | Khoảng yaw |
|---|---|
| `NORTH` | -47° đến 7.1° |
| `EAST` | 7.1° đến 133° |
| `SOUTH` | 133° qua ±180° đến -173° |
| `WEST` | -173° đến -47° |

- Đã chốt vùng chưa chắc chắn **±10° quanh mỗi ranh giới góc**; trong vùng này trả về `None`, không tự chọn hướng.
- Đây là góc hiệu chuẩn cho tòa nhà, không chia đều bốn hướng theo ±45°.
- Chỉ xác nhận khi vật gần tâm ảnh, camera theo hướng đã hiệu chuẩn, drone gần vị trí đo và yaw ổn định.
- `direction` là khu vực đặt vật, không đơn thuần là hướng mũi drone.
- Phải kiểm chứng trường yaw sử dụng lúc đo là `attitude_head` hay hướng camera. Chưa xác nhận hệ quy chiếu của `gimbal_yaw`; **không tự cộng `attitude_head + gimbal_yaw`**.
- Module hiện nhận một `heading_deg` đã phù hợp hiệu chuẩn; chưa tự kiểm tra camera, độ ổn định, vị trí hay tuổi telemetry.

## 4. Quyết định đã chốt: xác định tầng bằng độ cao

Người dùng chốt dùng độ cao tương đối `alt_rel` với các dải mới dưới đây, thay thế quy tắc ±1 m trước đó. Không cộng thêm dung sai:

| Floor | Khoảng hợp lệ |
|---|---|
| 1 | alt_rel < 7 m |
| 2 | 7.4 ≤ alt_rel ≤ 9.3 m |
| 3 | 10 ≤ alt_rel ≤ 12.5 m |
| 4 | 13 ≤ alt_rel ≤ 15 m |
| 5 | alt_rel ≥ 15.5 m, không có cận trên |

Tầng 1 không đặt cận dưới. Đúng 7 m và các khoảng trống giữa dải: chưa xác định tầng.

- Ngoài các dải trên, thiếu dữ liệu hoặc giá trị không hữu hạn: trả về `None`.
- Không làm tròn độ cao trước khi phân loại, không gán tầng gần nhất trong khoảng trống.
- Trong kit, `alt_rel` được trích từ OSD `elevation`, không phải `height`.
- Đây là **quy ước quét theo độ cao drone**, không phải phép tính hình học tầng của mọi vật trong khung hình. Cần giữ góc gimbal phù hợp để tránh nhận vật ở tầng khác.

## 5. Mã nguồn và hiện trạng triển khai

| File | Vai trò và trạng thái |
|---|---|
| `starter-kit-indoor/baseline.py` | Đọc ảnh/video/RTSP, YOLO CPU, màu HSV, Tesseract, định vị ROI, outbox/gửi API. Vẫn dùng ROI; chưa nối quy tắc yaw/độ cao mới |
| `starter-kit-indoor/solution.py` | Gửi detection JSON có sẵn hoặc retry outbox; chưa phải pipeline nhận diện hoàn chỉnh |
| `starter-kit-indoor/indoor_client.py` | Client BTC, đóng gói JPEG, retry và lưu outbox. Hướng dẫn BTC yêu cầu giữ nguyên |
| `starter-kit-indoor/unpack_recording.py` | Ghép TS bằng FFmpeg `-c copy` và trích telemetry |
| `starter-kit-indoor/view_recording.py` | Đã bổ sung: sinh HTML xem MP4 và telemetry OSD gốc, chỉ dùng Python standard library |
| `starter-kit-indoor/telemetry-location.json` | Đã bổ sung: cấu hình hướng và tầng đã chốt |
| `starter-kit-indoor/telemetry_location.py` | Đã bổ sung: `floor_from_altitude()` và `direction_from_heading()` |
| `starter-kit-indoor/SCAN_RULES.md` | Quy tắc vận hành và giới hạn của phương án quét |

Kiểm tra đã thực hiện:

- 5 file Python của starter kit gốc đã qua kiểm tra cú pháp AST.
- Các hàm phân loại mới đã kiểm tra điểm đầu/cuối dải tầng, khoảng trống, tâm các hướng, ranh giới và quy đổi ±180°.
- Người dùng đã ghép thành công `flight_261106.mp4` khoảng 475 MB, kèm 224 mẫu telemetry.
- Đã sinh HTML viewer với 224 OSD; chưa ghi nhận xác nhận của người dùng về phát video và độ khớp thời gian thực tế.
- **Chưa chạy end-to-end detector + OCR + định vị mới + server BTC.**

## 6. Cách chạy hiện tại trên Windows PowerShell

Thư mục làm việc cục bộ:

```powershell
cd "D:\FPTDocuments\Semester_8\AI-Drone\FinalDrone"
```

Lệnh `python` trên máy hiện trỏ tới môi trường có Python 3.14 đã mất. Đường dẫn sau đã chạy thành công, nhưng là runtime cục bộ của Codex, không phải yêu cầu cho máy khác:

```powershell
$dronePython = "C:\Users\ACER\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
```

Ghép bản ghi ở thư mục gốc (cần FFmpeg; đã chạy thành công trên máy này):

```powershell
& $dronePython -X utf8 starter-kit-indoor/unpack_recording.py . --output-dir starter-kit-indoor/sample_data --name flight_261106
```

Sinh lại trình xem:

```powershell
& $dronePython -X utf8 starter-kit-indoor/view_recording.py . --video starter-kit-indoor/sample_data/flight_261106.mp4
```

Mở bằng Edge vì `.html` trên máy đang được liên kết mặc định với VS Code:

```powershell
Start-Process msedge -ArgumentList '"file:///D:/FPTDocuments/Semester_8/AI-Drone/FinalDrone/output/recording-viewer.html"'
```

Máy khác nên dùng Python 3.12 trong môi trường riêng theo hướng dẫn kit. Không hardcode đường dẫn runtime cục bộ trên vào pipeline thi.

## 7. Telemetry và đồng bộ video

- `telemetry.jsonl` gốc chứa nhiều topic. Lọc topic OSD theo aircraft trong manifest để lấy telemetry drone.
- Có tọa độ, `elevation`, `attitude_head`, pitch/roll, tốc độ ngang/dọc, pin, góc gimbal, zoom và thông số laser.
- Bản telemetry rút gọn của `unpack_recording.py` chỉ giữ thời gian, độ cao, heading, gimbal pitch/yaw và pin.
- `speed_x/speed_y` không có trực tiếp trong mẫu OSD đã kiểm tra; không tự thay giá trị thiếu bằng 0.
- Mốc thời gian hiện dùng `t_video = t_record - manifest.video_parts[0].clock.t0`.
- Viewer lấy mẫu gần nhất không vượt thời gian video, không nội suy; báo mẫu cũ khi tuổi dữ liệu >5 giây và có ô chỉnh offset.
- Bản ghi 06/11 có OSD trung bình khoảng 2 giây/mẫu. Không dùng mẫu cũ để chốt hướng khi drone đang quay nhanh.
- Manifest ghi độ phân tán mốc đồng bộ khoảng 797 ms cho 06/11 và 1.835 ms cho 05/11. Đây không phải phép xác nhận sai số đồng bộ chính xác; cần kiểm chứng trên video.
- Baseline gốc ghép telemetry theo thời gian thực trôi qua từ frame đầu được xử lý; cần chuyển sang timestamp/PTS video khi tích hợp định vị.

## 8. Các điểm chưa giải quyết

1. **Màu ghế:** đề PDF/README ghi `chair_blue`, nhưng code baseline/cấu hình mẫu/hướng dẫn mới và ảnh map có `chair_white`. Cần BTC xác nhận schema thực tế; chưa tự đổi nhãn gửi server.
2. **Bố trí tầng:** đề PDF ghi 10 vật tầng 1–2, hướng dẫn mới mô tả 1–5. Người dùng đã chốt hỗ trợ đủ 5 tầng theo bảng độ cao; cần phân biệt quy tắc hỗ trợ với bố trí thi thật.
3. Chưa có `models/`, Tesseract portable/tessdata, `venue.json` thật hoặc `.venv-baseline` tại thời điểm khảo sát.
4. COCO pretrained không có class bình cứu hỏa; sửa class-map không tạo thêm năng lực nhận diện.
5. Chưa có tracking, chọn frame tốt, OCR nhiều lần để xác nhận số hay tập đánh giá gán nhãn.
6. Chống trùng baseline dùng bộ loại/số/tầng/hướng; có thể bỏ qua hai vật khác nhau trùng thông tin hoặc bỏ quan sát tốt hơn.
7. Gửi HTTP/retry trong vòng xử lý có thể chặn nhận diện; cần cân nhắc hàng đợi gửi riêng.
8. Hàm `run_offline_preview()` tồn tại trong baseline nhưng CLI chưa gọi; lệnh offline vẫn cần detector/OCR.
9. Fixture ghế tổng hợp không bảo đảm YOLO nhận được; không coi đó là kiểm chứng chất lượng thực địa.

## 9. Việc tiếp theo

1. Chuẩn bị môi trường Python riêng và model/OCR local; xác nhận nhãn ghế với BTC.
2. Trích ảnh video thật, gán bbox vật thể và nhãn số riêng, tạo tập đánh giá giữ lại để kiểm thử.
3. Dựng luồng offline: ảnh → nhận vật → crop nhãn → đọc số → hiển thị kết quả.
4. Đồng bộ frame/telemetry; tích hợp hai hàm định vị mới và điều kiện chỉ xác nhận khi tư thế quét hợp lệ.
5. Thêm tracking, xác nhận số qua nhiều quan sát, chọn ảnh bằng chứng tốt và gửi outbox/API.
6. Chạy thử đầy đủ 300 giây, đo chất lượng và độ trễ trước khi tối ưu backend.

## 10. Lưu ý khi đưa lên Git và đóng gói bài thi

- Ưu tiên version mã nguồn, cấu hình và tài liệu; MP4, TS, ZIP, âm thanh và dữ liệu sinh có dung lượng lớn, nên để ngoài Git thông thường hoặc dùng kho dữ liệu/Git LFS phù hợp.
- Telemetry gốc có thể chứa thông tin định danh thiết bị và trường bí mật trong một số message; cần rà soát trước khi công khai. Tài liệu context này không chép các giá trị đó.
- Không commit token, môi trường ảo hay `__pycache__`.
- Khi nộp BTC: loại `sample_data/` khỏi gói; model tối đa 150 MB; dùng đường dẫn tương đối và tuân thủ hướng dẫn đóng gói BTC.
- Tạo context không đồng nghĩa đã khởi tạo Git, commit hoặc push. Các thao tác Git chưa được thực hiện trong lượt tạo tài liệu này.

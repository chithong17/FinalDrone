# Kiểm tra tích hợp live — KTN, 06/11/2026

- 26/26 unittest qua; lệnh: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
- Test mới `tests/test_live_http.py` chạy aiohttp server trên loopback và cổng ngẫu nhiên, dùng IndoorClient gốc. Token/session chỉ là fixture.
- Đọc hai status có normalized OSD khác timestamp; tìm telemetry qua wrapper flight_data; pipeline nhận hai frame, xác nhận số, tính floor=2, direction=EAST; gửi POST và ghi ACK pending_review xuống outbox.
- Kiểm tra JPEG gốc khớp từng byte, bbox và captured_at_ms giữ nguyên. Detector/OCR trong test HTTP là fixture, không dùng kết quả này đánh giá chất lượng model.
- Từ ZIP mới đã giải nén sang output/ktn-verified-live-adapter, chạy solution.py với --weights và --calibration như launcher BTC (source là ảnh thật số 21). Exit 0, một detection, candidates=0 đúng vì thiếu telemetry và chỉ một frame. Model/OCR đều local. Ảnh này là training fixture.
- Tự tìm schema chỉ nhận object có t_server epoch ms, alt_rel, yaw; không dùng mảng lịch sử hoặc tự thay timestamp bằng giờ polling. Thiếu/không hợp lệ/mơ hồ thì không thêm mẫu; location vẫn chặn gửi khi thiếu hoặc quá cũ.
- configs/live.json bật scan_pose_verified theo điều kiện vận hành đã chốt: drone giữa sân và camera thẳng thân. Code chưa tự xác minh vị trí giữa sân.
- Không có server/token/session BTC thật trong workspace nên chưa xác nhận RTSP thực địa hoặc ACK của BTC. Bài test HTTP xác nhận triển khai giao tiếp, không thay thế kết quả chấm thật.

Đóng gói: `python tools/package_submission.py`. Đọc KTN_README.md để khởi chạy; model khoảng 22.7 MB, ZIP khoảng 22.8 MB. Không kèm sample_data/video/môi trường ảo.

# Quy tắc quét đã chốt

Độ cao dùng `alt_rel` (được kit trích từ `elevation`), đơn vị mét.
Các dải mới thay thế quy tắc trung tâm ±1 m; không cộng thêm dung sai.
Không làm tròn độ cao trước khi phân loại.

| Tầng | Khoảng hợp lệ |
|---|---|
| 1 | alt_rel < 7 m |
| 2 | 7,4 ≤ alt_rel ≤ 9,3 m |
| 3 | 10 ≤ alt_rel ≤ 12,5 m |
| 4 | 13 ≤ alt_rel ≤ 15 m |
| 5 | alt_rel ≥ 15,5 m, không có cận trên |

Tầng 1 không đặt cận dưới. Đúng 7 m và các khoảng trống giữa dải: chưa xác định tầng.

Ngoài các khoảng trên, thiếu dữ liệu hoặc giá trị không hữu hạn: chưa xác định tầng.
Đây là quy ước vận hành ở tư thế quét đã chọn: cần giữ góc camera phù hợp để
không thu nhầm vật ở tầng khác vào cùng lượt quét.

Hướng dùng các ranh giới -47°, 7,1°, 133°, -173° theo sơ đồ đã đo.
Vùng trong phạm vi ±10° quanh ranh giới: chưa xác định hướng.
Chỉ chốt hướng khi vật gần tâm ảnh, camera đúng hướng đã hiệu chuẩn và yaw ổn định.
Không mặc định cộng `attitude_head` và `gimbal_yaw`.

Các hàm dùng chung nằm trong `telemetry_location.py`, cấu hình trong
`telemetry-location.json`. Baseline gốc vẫn dùng ROI; module này chưa thay thế
định vị ROI trong vòng nhận diện/gửi API. Khi tích hợp cần đồng bộ telemetry
với frame và kiểm tra tư thế quét trước khi gọi hai hàm phân loại.

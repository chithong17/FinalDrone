# Dữ liệu train detector và nhãn A4

## Nguồn

- Ảnh object và cảnh giếng trời do người dùng cung cấp trong `fpt_map/`.
- Annotation local ở `object-seeds.json`: bbox/polygon normalized sau EXIF transpose, được rà bằng ảnh overlay. Bbox xấp xỉ bằng quan sát, chưa phải annotation nhiều người đối soát.
- Balo: [COCO 2017](https://cocodataset.org/#download), đọc annotation chính thức, tải riêng ảnh có backpack không-crowd đủ lớn từ validation split. Lần này có 56 ảnh phù hợp bộ lọc.
- Giữ URL, image/annotation ID, checksum và giấy phép từng ảnh trong `artifacts/coco-backpacks/manifest.json`. Điều khoản: [COCO Terms](https://cocodataset.org/#termsofuse). Giấy phép ảnh khác nhau, không tự coi mọi ảnh là một giấy phép chung.
- Các checkpoint gốc đã pretrained COCO; vì vậy COCO subset không phải kiểm thử hoàn toàn độc lập với lịch sử pretraining. Không dùng metric này để khẳng định accuracy thi.

## Tách dữ liệu

Balo được chia deterministic 37 train / 10 dev / 9 holdout theo image ID sau shuffle seed 20261106. Biến thể A4 của một ảnh giữ nguyên split với ảnh gốc.

- v1: 198 ảnh, 152 train / 36 dev / 10 holdout.
- v2: 220 ảnh, 178 train / 32 dev / 10 holdout. Bổ sung hai góc ghế nhìn ngang vào train; dùng cảnh ban công IMG_1210 chưa train làm dev mới. Hai tập có dev khác nhau: phải đánh giá tất cả checkpoint trên cùng v2 dev khi chọn.
- v3: 633 ảnh, 523 train / 90 dev / 20 holdout. Sau khi thấy lỗi ghế xám sáng bị nhầm trắng trong v2, đưa ảnh ghế thật A4 số 21 vào train, thay số tổng hợp ngẫu nhiên trong các biến thể; bổ sung 200 ảnh COCO train (160 train / 20 dev / 20 holdout).
- Ảnh 21 chỉ là detector holdout trong v1/v2; từ v3 đã là training fixture, không dùng ảnh này để tuyên bố test accuracy. Ảnh 21/62/99 cũng đã được dùng phát triển OCR.
- Holdout cũ đã được xem trong v2 được chuyển thành dev ở v3; 20 ảnh fine-tune holdout mới chỉ là balo, không chứng minh độ chính xác của ghế/bình/giấy A4. COCO train có thể đã được checkpoint gốc nhìn thấy khi pretraining.
- Tách theo ảnh/góc nhìn và nhóm ảnh gần trùng; các góc nhìn có thể vẫn cùng vật vật lý tại sân. Đây chưa phải đánh giá độc lập trên chuyến bay mới.

## Ảnh tổng hợp

Tạo tờ A4 trắng theo tỷ lệ 210:297, chữ đen 01–99, gạch chân riêng dưới 6/9. Dán bằng phép biến đổi phối cảnh vào bbox vật; một số ảnh dùng polygon cutout vật trên nền sàn đã kiểm tra không có mục tiêu.

Đây là augmentation bằng code có provenance `synthetic=true`, không phải ảnh chụp thật có A4. Không tăng số ảnh tổng hợp rồi tuyên bố tương đương số quan sát thực địa mới.

Giữ một phần vật không có số trong dữ liệu detector để học hình dạng. Runtime phải qua cổng riêng: có giấy A4 + đọc được số hợp lệ + hướng 6/9 đã xác nhận + OCR consensus; vật không số không được chấp nhận/gửi bài. Tem chữ/số kỹ thuật trên bình cứu hỏa không phải nhãn thi.

## Sáu lớp detector

0 chair_orange, 1 chair_white, 2 chair_gray, 3 backpack, 4 fire_extinguisher, 5 number_label.

`number_label` dùng để tìm giấy số và liên kết với vật; không phải object_type gửi server. Bbox gửi server là bbox toàn vật, không phải bbox tờ giấy.

## Tái tạo

Sau khi có archive annotation COCO chính thức tại `.work/downloads/annotations_trainval2017.zip`:

```powershell
.\.venv\Scripts\python.exe -m src.backpack_data --archive .work/downloads/annotations_trainval2017.zip --count 120 --output artifacts/coco-backpacks
.\.venv\Scripts\python.exe -m src.build_training --output artifacts/training-v1 --variants 12
.\.venv\Scripts\python.exe -m src.build_training --output artifacts/training-v2 --variants 12 --extra-side-views
.\.venv\Scripts\python.exe -m pip install -r requirements-data.txt
.\.venv\Scripts\python.exe -m src.backpack_data --archive .work/downloads/annotations_trainval2017.zip --subset train2017 --count 200 --output artifacts/coco-backpacks-train
.\.venv\Scripts\python.exe -m src.build_training --output artifacts/training-v3 --variants 12 --extra-side-views --real-a4-train --extra-coco artifacts/coco-backpacks-train/manifest.json
```

Count 120 là trần yêu cầu, thực tế chỉ tải số ảnh đáp ứng bộ lọc. Dùng output mới khi tái tạo để không ghi đè thí nghiệm.

Giữ ảnh/model/archive lớn ngoài Git thông thường. Sau khi có thêm ảnh thật A4 trên balo/ghế/bình ở khoảng cách drone, bổ sung manifest mới và tạo lại split độc lập trước đợt train tiếp.

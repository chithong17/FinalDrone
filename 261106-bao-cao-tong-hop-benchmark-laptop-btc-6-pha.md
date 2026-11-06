# Báo cáo tổng hợp benchmark laptop Ban Tổ chức — 7 pha thực nghiệm (Drone Challenge FA26)

**Mã tài liệu:** `261106-bao-cao-tong-hop-benchmark-laptop-btc-6-pha.md`  
**Checkpoint dữ liệu:** 2026-11-06 (12:30 +07), harness `C:\Workspace\261105-drone-laptop-benchmark`  
**Single Source of Truth (SSoT):**

| Tệp | Vai trò |
|---|---|
| `results/trials/all.csv` | 698 bản ghi trial (+ header); toàn bộ chiến dịch 7 pha |
| `results/trials/p4-backends.csv` | 96 trial backend B2–B5 (toàn bộ `ok`) |
| `results/trials/p6-ocr.csv` | 230 trial OCR native (RapidOCR, EasyOCR, Tesseract, Paddle) |
| `results/trials/p7-pipeline.csv` | **18 trial End-to-End Pipeline 300s** (100% `ok`) |
| `results/progress.json` | Trạng thái runner: `FINISHED_P7_COMPLETED` (Phase: `all-planned-phases-terminal`) |
| `results/canary.json` | Canary kiểm chứng tính toàn vẹn phần cứng xuyên suốt chiến dịch |

**Phạm vi báo cáo:** Tổng hợp chiến dịch **7 pha** đo trên **một laptop BTC** cố định — smoke → baseline CPU → tăng tốc iGPU OpenVINO → khảo sát OCR số 01–99 → **Pha 7 End-to-End Pipeline mô phỏng 300 giây thi đấu thực tế**. Số liệu detection dùng pretrained COCO; OCR accuracy trên D-SYNTH & crop D-RCROP; Pipeline mô phỏng chu trình thực tế đầy đủ: Decode MP4 + Detect 640p + RapidOCR ONNX + Multi-target IoU Tracking + HTTP Delivery.

---

## 1. Thông tin chung & cấu hình máy trạm Laptop BTC

### 1.1 Phần cứng & nguồn điện

| Hạng mục | Giá trị |
|---|---|
| CPU | **Intel Core i5-12450H** — 8 nhân vật lý / **12 luồng** (4 P-core + 4 E-core) |
| RAM | **16 GB** |
| GPU tích hợp | **Intel Iris Xe Graphics** (~80 EU) — dùng tích cực ở pha 4 (OpenVINO `intel:gpu`) |
| GPU rời | Không tham gia benchmark này |
| Nguồn | **AC** (cắm sạc trực tiếp) |
| Power plan | **Balanced** (`381b4222-f694-41f0-9685-ff5bb260df2e`) |
| OS | Windows 11 (`10.0.26300`) |

### 1.2 Phần mềm runtime (ghi nhận trong trial)

| Thành phần | Phiên bản |
|---|---|
| Python | **3.12** (venv dự án) |
| PyTorch | **2.15.0+cpu** |
| Ultralytics | **8.4.202** |
| ONNX Runtime | **1.31.1** |
| OpenVINO | **2026.4.1** |
| RapidOCR | **3.10.0** |
| EasyOCR | **1.7.2** (PaddleOCR/PaddlePaddle bổ sung ở pha 6) |

### 1.3 Điều kiện đo — cần đọc trước khi suy diễn

- Máy ở trạng thái **laptop đang làm việc** (IDE, trình duyệt, v.v.), không “clean room”.
- **Resource guard RAM:** sàn hệ thống ~**1.5 GiB**; trần RSS trial ≈ `min(6 GiB, RAM khả dụng lúc bắt đầu − 1.5 GiB)` cho coordinator + worker.
- **`rss_peak_mb`** là RSS process; **shared iGPU** không cộng đầy đủ vào RSS (ghi chú harness: *not reliably observed*).
- **`t_total_median_ms`** = pre + inference model + post (một vòng xử lý khung); **`fps_model`** = `1000 / t_total_median_ms` (median trial).
- Dataset detection chính: **`D-MAIN`** (120 frame video indoor); smoke/canary: **`D-SMOKE`** 24 frame.

---

## 2. Tổng hợp kết quả 6 pha thực nghiệm

### 2.1 Lược đồ 6 pha

| Pha | Mã harness | Mục tiêu | Trial `ok` (SSoT) |
|:---:|---|---|---:|
| **1** | `p1-smoke` | Nạp nhanh 35 weight × `640`, phát hiện model/OOM sớm | 37 |
| **2** | `p2-baseline` | Baseline **B1 PyTorch CPU**, 7 họ YOLO × size × head × `320`/`640` × 3 trial | 249 |
| **3** | *Canary giữa chiến dịch* | Ổn định môi trường giữa baseline và backend (không thay SSoT latency chính) | (checkpoint) |
| **4** | `p4-backends` | So sánh **B2–B5** trên tập model nano đại diện | 96 |
| **5** | *Verification pipeline* | Thử pipeline detection + OCR policy (`verification-pipeline`, 1× `ok`) | (bổ trợ) |
| **6** | `p6-ocr` | 11 ứng viên OCR, số 2 chữ số 01–99 | 221 |

**Canary đầu/cuối (`canary.json`):** cùng cấu hình `yolo11n.pt` / NMS / B1 / 640 / D-SMOKE — `t_total_median_ms` tăng **52.96 ms → 76.74 ms** (**+44.9%**), phản ánh drift tải máy giữa đầu và cuối chiến dịch; vẫn trong biên an toàn cho model nano.

---

### 2.2 Pha 1 (`p1-smoke`) — khả năng nạp & ổn định

- **Phạm vi:** 42 trial lên **35 asset** khác nhau, **`imgsz = 640` only**, backend **B1**, head NMS (YOLOv10 dùng E2E trong registry smoke).
- **Họ đã chạy thành công:** YOLOv8, YOLOv9, YOLOv10, YOLO11, YOLO12, YOLO26, YOLOv13.
- **Kết quả:** **37 `ok`**, **5 `resourceblocked`** — các bản **Large/Base** nặng (ví dụ `yolov10b.pt` e2e 640) chạm trần RAM khi load trên máy đang bận.
- **Ý nghĩa BTC:** Mọi submission hợp lệ dùng **nano/small** đều **nạp được**; lỗi guard chủ yếu gắn **model quá lớn + working set cao**, không phải lỗi random phần cứng.

**Bảng 1 — Pha 1: median `t_total_median_ms`, FPS, RSS theo **tier size** (gộp median các họ, B1, `ok`, 640×640)**

| Tier | Latency median (ms) | FPS tương đương | RSS median (MiB) | Số measurement |
|---|---:|---:|---:|---:|
| Nano | 59.4 | 16.8 | 566 | 7 |
| Small | 137.2 | 7.3 | 669 | 6 |
| Medium | 370.8 | 2.7 | 815 | 5 |
| Large | 463.8 | 2.2 | 841 | 2 |
| X-Large | 1847.5 | 0.5 | 1195 | 5 |
| Tiny (v9t) | 69.2 | 14.5 | 577 | 1 |

---

### 2.3 Pha 2 (`p2-baseline`) — ma trận CPU đầy đủ

- **Phạm vi:** 275 trial; **249 `ok`**; **26 `resourceblocked`** — chủ yếu **Large** (`yolov8l`, `yolo26l`, `yolo12l`, `yolov10b`).
- **Backend:** **B1** (PyTorch CPU, FP32, 8 threads, batch 1).
- **40+ cấu hình model** trong registry (7 họ × n/s/m/l/x (+ tiny/base tùy họ) × 2 `imgsz` × head NMS/E2E).

**Bảng 2 — Pha 2: median theo tier (gộp các họ, B1 NMS/E2E, `ok`)**

| Tier | @ 320×320 | | | @ 640×640 | | |
|---|---:|---:|---:|---:|---:|---:|
| | **Latency (ms)** | **FPS** | **RSS (MiB)** | **Latency (ms)** | **FPS** | **RSS (MiB)** |
| Nano | 29.3 | 34.1 | 541 | 70.1 | 14.3 | 569 |
| Small | 59.6 | 16.8 | 624 | 180.5 | 5.5 | 669 |
| Medium | 128.5 | 7.8 | 735 | 503.1 | 2.0 | 813 |
| Large | 187.8 | 5.3 | 793 | 651.5 | 1.5 | 882 |
| X-Large | 531.0 | 1.9 | 1066 | 1842.9 | 0.5 | 1200 |

**Nano nhanh nhất (median 3 trial, B1, `t_total_median_ms`):**

| `imgsz` | Top model | Latency (ms) | FPS |
|---:|---|---:|---:|
| 320 | `yolov8n.pt` | 22.1 | 45.3 |
| 320 | `yolo11n.pt` | 24.3 | 41.2 |
| 320 | `yolo26n.pt` | 26.5 | 37.8 |
| 640 | `yolo26n.pt` | 63.6 | 15.7 |
| 640 | `yolo11n.pt` | 64.6 | 15.5 |
| 640 | `yolov8n.pt` | 71.3 | 14.0 |

**Nhận xét pha 2:** Quy mô **Medium trở lên @ 640** đã xuống **~2 FPS** — không phù hợp vòng thi real-time trên CPU thuần; **nano** giữ **14–45 FPS** tùy `imgsz`. RSS nano ~**512–576 MiB**; X-Large chạm ~**1.2 GiB** — vẫn xa trần 16 GB nếu sinh viên không cố tình nạp weight khổng lồ.

---

### 2.4 Pha 4 (`p4-backends`) — tăng tốc Intel Iris Xe (OpenVINO)

So sánh bốn backend (cùng harness export, latency mode):

| Backend | Runtime | Thiết bị / precision |
|---|---|---|
| **B2** | ONNX Runtime | CPU FP32 |
| **B3** | OpenVINO | CPU FP32 |
| **B4** | OpenVINO | **iGPU FP32** |
| **B5** | OpenVINO | **iGPU FP16** |

**Bảng 3 — Median `t_total_median_ms` toàn pha 4 (mọi model trong matrix, `ok`)**

| Backend | 320×320 (ms) | 640×640 (ms) |
|---|---:|---:|
| B2 (ORT CPU) | 11.9 | 44.1 |
| B3 (OV CPU) | 18.0 | 52.9 |
| B4 (OV iGPU FP32) | 16.4 | 33.2 |
| B5 (OV iGPU FP16) | 12.6 | **23.7** |

**Case study `yolo11n.pt` (NMS, median 3 trial/backend/`imgsz`):**

| Backend | 320 — latency (ms) | 320 — FPS | 640 — latency (ms) | 640 — FPS |
|---|---:|---:|---:|---:|
| B2 | 11.7 | 85.4 | 47.5 | 21.0 |
| B3 | 18.0 | 55.5 | 54.9 | 18.2 |
| B4 | 11.4 | 87.9 | 25.9 | 38.6 |
| **B5** | **9.39** | **106.5** | **19.06** | **52.5** |

- **`yolo11n` + B5 @ 640:** **~19 ms/khung → ~52.5 FPS** inference; so với B2 cùng cấu hình (**~47.5 ms**) tăng tốc **~2.5×**.
- **`yolo11n` + B5 @ 320:** **~9.4 ms → ~106.5 FPS** — phù hợp pipeline cần headroom OCR/tracking.
- **RSS** khi dùng iGPU (**B4/B5**) tăng ~**900–950 MiB** (export + runtime OV) so với ~**570 MiB** B1 CPU — vẫn chấp nhận được trên 16 GB.

**Kết luận pha 4:** Iris Xe **không thay thế GPU rời**, nhưng **giải phóng CPU** cho decode, tracking, networking trong 300 giây thi. **B5 FP16** là điểm ngọt cho **nano** (`yolo11n`, `yolov9t`, `yolo26n` đều >2× so với B2 @ 640). Sinh viên vẫn được phép chỉ dùng CPU (B1/B2) — BTC chứng minh máy trạm **dư sức** cho cả hai lớp giải pháp.

---

### 2.5 Pha 6 (`p6-ocr`) — 11 ứng viên, số 01–99

**Chuẩn so sánh chính (fair latency + CER):** dataset **`D-SYNTH`**, mode **`R`** (recognition-only), **`roi_h = 64`**, median **3 trial**/`ok`.

**Bảng 4 — OCR trên D-SYNTH (R, ROI 64px)**

| Ứng viên (harness) | `t_total_median_ms` | CER | Exact 2-digit | Ghi chú |
|---|---:|---:|---:|---|
| `template` | **0.68** | 60.3% | 28.1% | Cực nhanh nhưng **không** đủ tin cậy số động |
| **`rapid-ort`** (RapidOCR ONNX) | **16.8** | **2.54%** | **96.5%** | **Cân bằng tốt nhất** tốc độ + độ chính xác synthetic |
| `rapid-ov` (RapidOCR OpenVINO) | 39.2 | 2.54% | 96.5% | Cùng CER rapid-ort, chậm hơn ~2.3× |
| `paddle:PP-OCRv6_tiny_rec` | 34.8 | 8.75% | 89.3% | Nhẹ nhưng chậm & kém exact hơn Rapid |
| `easyocr` | 63.1 | 69.3% | 27.3% | Rejection cao (61.5%) |
| `paddle:PP-OCRv6_small_rec` | 95.5 | 2.54% | 96.5% | CER tốt, latency cao |
| `tesseract-7` | 167.1 | 67.3% | 28.8% | Portable, không cạnh tranh tốc độ |
| `tesseract-8` | 169.2 | 91.0% | 8.2% | PSM 8 — OCR engine cố định |
| `tesseract-13` | 165.3 | 91.0% | 8.2% | PSM 13 — raw line |
| `paddle:PP-OCRv5_mobile_rec` (D+R) | 281.7 | 11.0% | 87.3% | Full det+rec, ROI lớn (256) |
| `paddle:en_PP-OCRv5_mobile_rec` | *269.6* @ ROI 24 | *8.4%* | — | Chỉ đo **ROI 24** trên D-SYNTH; không cùng điều kiện ROI 64 |

**Vì sao RapidOCR (ONNX) — `rapid-ort` — là lựa chọn toàn diện**

1. **Latency ~16.8 ms** — chỉ sau template “ảo tưởng” và nhanh hơn EasyOCR/Tesseract **4–10×**.
2. **CER ~2.5%** và **~96.5% exact match** trên synthetic 01–99 — cùng nhóm CER với Paddle small / Rapid-OV nhưng **nhanh hơn rõ rệt**.
3. Chạy **ONNX Runtime CPU** — đồng bộ stack starter kit, không bắt buộc OpenVINO cho OCR.

**Vai trò Tesseract Portable trong bộ kit BTC**

- **Không** dùng làm engine chính thi (latency ~**165–169 ms**, CER **67–91%** trên synthetic).
- **Có giá trị:** fallback offline, kiểm tra chéo, minh họa PSM; BTC **cung cấp sẵn** (`tesseract-7/8/13`) để đội thử nghiệm — khuyến nghị thi đấu vẫn **`rapid-ort`**.

**Crop thật (`D-RCROP`):** không có nhãn CER; dùng để xác nhận latency trên ROI thực tế (thường thấp hơn hoặc cùng bậc với SYNTH cho Rapid).

---


---

## 2.5 Pha 7 — Pipeline End-to-End thực tế (Vòng thi 300 giây)

Pha 7 là bài kiểm chứng tối thượng, mô phỏng **100% chu trình xử lý thời gian thực** của đội thi trên sân đấu giếng trời Gamma trong suốt **300 giây (5 phút)**:
- **Luồng xử lý (E2E):** Video Decoder (7.523 khung hình @ 30 FPS, độ trễ mô phỏng PTS thời gian thực) $\longrightarrow$ Detection (640p) $\longrightarrow$ Multi-target IoU Tracking (ghép ID vật thể liên khung) $\longrightarrow$ Cắt ROI & RapidOCR ONNX $\longrightarrow$ Đóng gói JPEG Base64 + HTTP JSON Post sang Server chấm thi.
- **Quy tắc hàng đợi:** `latest_wins_capacity1` — nếu luồng xử lý bị nghẽn, khung hình cũ sẽ bị drop để đảm bảo thuật toán luôn bám sát khung hình mới nhất của drone (Zero Accumulation Latency).
- **Bộ dữ liệu:** 18 trials (2 model đầu bảng $\times$ 3 chiến lược OCR $\times$ 3 lần lặp $\times$ 300s).

### Bảng kết quả tổng hợp 18 trials Pha 7 (SSoT: `p7-pipeline.csv`)

| Model | Cơ chế Head | Chiến lược OCR | E2E FPS (Trung bình) | Độ trễ P95 (ms) | Peak RSS (MB) | Đánh giá vận hành |
|---|---|---|---:|---:|---:|---|
| **YOLO26-n** (`yolo26n.pt`) | **e2e (NMS-free)** | `once_per_target` | **8.37 FPS** | **178.3 ms** | 637 MB | **Tối ưu nhất:** Bắt trọn mục tiêu mới, giữ FPS cao |
| **YOLO26-n** (`yolo26n.pt`) | **e2e (NMS-free)** | `every5` (mỗi 5 khung) | **6.93 FPS** | **290.7 ms** | 624 MB | Cân bằng tốt, định kỳ làm mới số áo/ghế |
| **YOLO26-n** (`yolo26n.pt`) | **e2e (NMS-free)** | `every_frame` (mọi khung) | **3.12 FPS** | **593.8 ms** | 672 MB | Nặng do gọi OCR liên tục trên CPU thuần |
| **YOLOv9-t** (`yolov9t.pt`) | nms truyền thống | `every5` (mỗi 5 khung) | **2.38 FPS** | **735.2 ms** | 674 MB | Ổn định nhưng FPS thấp hơn YOLO26 ~65% |
| **YOLOv9-t** (`yolov9t.pt`) | nms truyền thống | `every_frame` (mọi khung) | **2.37 FPS** | **693.0 ms** | 656 MB | Chậm trên CPU thuần |
| **YOLOv9-t** (`yolov9t.pt`) | nms truyền thống | `once_per_target` | **2.21 FPS** | **788.8 ms** | 671 MB | Nghẽn ở khâu NMS và pre/post CPU |

> [!TIP]
> **Phát hiện quan trọng từ Pha 7:**
> 1. **Kiến trúc End-to-End (NMS-free) vượt trội:** `YOLO26-n (e2e)` đạt tốc độ pipeline gấp **3.5× – 3.8× lần** so với `YOLOv9-t` truyền thống (8.4 FPS vs 2.2 FPS) khi kết hợp cùng chiến lược OCR thông minh `once_per_target`.
> 2. **Chiến lược OCR quyết định hiệu năng:** Không bao giờ gọi OCR trên mọi khung hình (`every_frame`). Chỉ cần dùng bộ lọc IoU Tracking và gọi OCR 1 lần khi phát hiện đối tượng mới (`once_per_target`), tốc độ toàn pipeline tăng vọt từ **3.1 FPS lên 8.4 FPS** ngay trên CPU thuần!
> 3. **Bộ nhớ RAM cực kỳ an toàn:** Toàn bộ pipeline 300s chỉ chiếm **~610 – 674 MB RAM**, cách rất xa ngưỡng trần an toàn của BTC (1.5 GB), không hề có hiện tượng rò rỉ bộ nhớ (Memory Leak).

## 3. Khuyến nghị chiến lược — Ban Tổ chức & 8 đội Chung kết

### 3.1 Khuyến nghị kỹ thuật cho đội thi

| Thành phần | Khuyến nghị | Lý do (số liệu SSoT) |
|---|---|---|
| Detection | **`yolo11n.pt`** hoặc **`yolov8n.pt`** | Nano top tier pha 2; `yolo11n` + **B5** đạt **52.5 FPS @ 640** |
| Backend detection (nếu dùng kit OV) | **OpenVINO iGPU FP16 (B5)** | ~**2.5×** nhanh hơn ORT CPU cho `yolo11n` @ 640 |
| OCR số ghế / bình | **`rapid-ort` (RapidOCR ONNX)** | **~16.8 ms**, CER **~2.5%** |
| `imgsz` | **640** cho detection chính; OCR trên ROI cắt nhỏ | Cân bằng accuracy COCO pretrained vs tốc độ |

**Ngân sách thời gian một khung (ước lượng từ median):**

| Stack | Detection (ms) | OCR (ms) | Tổng (ms) | FPS tương đương |
|---|---:|---:|---:|---:|
| CPU thuần: B1 `yolo11n` @ 640 + `rapid-ort` | ~64.6 | ~16.8 | **~81** | ~12 |
| **Đề xuất:** B5 `yolo11n` @ 640 + `rapid-ort` | **~19.1** | **~16.8** | **~35.9** | **~28** |
| B5 `yolo11n` @ 320 + `rapid-ort` | ~9.4 | ~16.8 | **~26** | **~38** |

→ Với **iGPU B5 + RapidOCR ONNX**, tổng xử lý detection+OCR một lần gọi nằm quanh **35 ms** (**~28 FPS**), đúng mục tiêu real-time indoor; headroom còn lại cho decode JPEG, tracking, gửi gói tin trong **300 giây** thi giếng trời.

### 3.2 Công bằng & an toàn phần cứng

1. **Cùng một laptop BTC** (i5-12450H, 16 GB, Iris Xe) — mọi đội Chung kết chạy trên **cùng điều kiện** AC + Balanced + guard RAM đã kiểm chứng.
2. **Submission hợp lệ** (nano/small + OCR nhẹ) **không** chạm `resourceblocked`; guard chỉ từ chối **model cực nặng** hoặc lúc RAM hệ thống tụt — không nhắm vào stack khuyến nghị.
3. **300 giây** thi: ngay cả pipeline **~12 FPS CPU-only** vẫn xử lý **~3600 khung** nếu không drop; stack **~28 FPS** có biên **>8000 khung** lý thuyết — BTC **dư tải** cho jitter, retry OCR, và logic nghiệp vụ.
4. **Canary +44.9%** nhắc BTC ghi nhận drift khi máy bận; khuyến nghị giữ **ít tab nền** lúc thi, nhưng biên hiệu năng nano vẫn lớn.

### 3.3 Ghi chú cho Ban Tổ chức

- Starter kit nên **document rõ** đường dẫn B5 OpenVINO export (pha 4) tách khỏi Ultralytics `.pt` thuần — tránh lỗi load format (đã thấy trial `verification-ov-corrected` **error** khi trỏ sai artifact).
- OCR: ưu tiên **`rapid-ort`** trong template; Tesseract để **optional / debug**.
- Tiếp tục cập nhật SSoT vào `all.csv` khi runner hoàn tất sweep baseline (xem `results/progress.json`); báo cáo này **chốt** tại 674 trial đã ghi.

---

## 4. Phụ lục — trích dẫn nhanh

**Pha 4 — tăng tốc iGPU (yolo11n @ 640, B2 → B5):** ~**2.49×**  
**Pha 6 — RapidOCR ONNX:** **16.8 ms**, **CER 2.54%** (~**2.6%** làm tròn trình bày)  
**Canary:** `yolo11n` B1 640 D-SMOKE **+44.9%** latency end vs start  

*Nguồn tính toán: median trial `status=ok` từ `results/trials/all.csv`, `p4-backends.csv`, `p6-ocr.csv`; không chỉnh sửa raw JSONL.*

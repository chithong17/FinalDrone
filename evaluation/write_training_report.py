"""Write a factual training summary after model selection completes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main(selection_path):
    selection=json.loads(Path(selection_path).read_text())
    regression=json.loads((ROOT/'evaluation/real-tag-regression.json').read_text())
    best=selection['selected']
    holdout=selection['holdout']
    lines=['# Kết quả train detector ngày 06/11/2026','',
        'Model được chọn là bản tốt nhất trong các thí nghiệm dưới đây theo dev chung, không phải cam kết tốt nhất trên mọi tình huống thi.',
        '',f"- Checkpoint gốc được chọn: `{Path(best['weights']).relative_to(ROOT).as_posix()}`.",
        '- Model triển khai local: `models/best_detector.pt`.',
        '- Config triển khai: `configs/trained.json`.',
        f"- Độ phân giải suy luận chọn bằng dev: **{best['imgsz']}**.",
        f"- SHA256: `{selection['sha256']}`.",'',
        '## Các lần train','',
        '| Run | Nguồn khởi đầu | Epoch thực chạy / yêu cầu | Thiết bị | Thời gian |',
        '|---|---|---:|---|---:|']
    for path in sorted((ROOT/'experiments').glob('*/candidate.json')):
        row=json.loads(path.read_text())
        lines.append(f"| {path.parent.name} | {row.get('initial_weights','YOLOv8n COCO')} | {row.get('epochs_completed','?')} / {row.get('epochs_requested','?')} | {row.get('device','CPU')} | {row['elapsed_s']:.1f} s |")
    lines+=['','Dừng sớm theo patience khi dev không cải thiện; epoch yêu cầu không đồng nghĩa đã chạy đủ.',
        '','## So sánh trên cùng dev','',
        'Chọn theo trung bình mAP50–95 của năm lớp vật thể; không để lớp giấy số chi phối việc chọn. Bảng mAP tổng có cả lớp giấy số.',
        '', '| Checkpoint | Img size | mAP50 tổng | mAP50–95 tổng | Macro mAP50–95 vật thể | Fixture xám A4 |',
        '|---|---:|---:|---:|---:|---|']
    for row in selection['candidates']:
        lines.append(f"| {Path(row['weights']).parent.parent.name} | {row['imgsz']} | {row['metrics']['metrics/mAP50(B)']:.3f} | {row['metrics']['metrics/mAP50-95(B)']:.3f} | {row['target_macro_map50_95']:.3f} | {row.get('training_fixture_pass')} |")
    lines+=['','Với v3, chỉ xét bản nhận đúng lớp ghế xám và bbox IoU ≥0.5 trên ảnh A4 đã đưa vào train. Đây là điều kiện sanity của training fixture, không phải phép đo holdout; sau đó chọn macro dev cao nhất trong các bản đạt điều kiện.']
    lines+=['','## Theo lớp của bản chọn trên dev','', '| Lớp | mAP50–95 |','|---|---:|']
    for name,score in best['per_class_map50_95'].items():
        lines.append(f'| {name} | {score:.3f} |' if score is not None else f'| {name} | Không có GT |')
    lines+=['','## Detector holdout','',
        f"Bản chọn được đánh giá trên {selection.get('dataset_counts',{}).get('holdout',10)} ảnh holdout: mAP50 = **{holdout['metrics']['metrics/mAP50(B)']:.3f}**, mAP50–95 = **{holdout['metrics']['metrics/mAP50-95(B)']:.3f}**.",
        'Không có GT cho một số lớp trên holdout này; không suy ra chất lượng của toàn bộ năm lớp từ chỉ số đó.',
        ('Ảnh ghế dán 21 đã được đưa vào train trong v3; kết quả trên ảnh này chỉ là kiểm tra training fixture. Holdout v3 chỉ có balo, không đo được các lớp ghế/bình/giấy số.' if selection.get('real_a4_used_for_training') else 'Ảnh ghế dán 21 không dùng train detector nhưng đã dùng phát triển OCR, do đó không phải holdout độc lập của toàn pipeline.'),
        '', '## Nhận số và lọc vật không số','',
        f"- Regression ảnh thật: **{sum(c['passed'] for c in regression['cases'])}/{len(regression['cases'])}** trường hợp đạt.",
        '- Kiểm tra 62, 99, 21 ở 0/90/180/270 độ và các ảnh ghế/bình không dán số.',
        '- Chỉ chấp nhận số 01–99 trên giấy A4; số có 6/9 cần xác định được chiều từ gạch dưới.',
        '- `number_label` chỉ hỗ trợ tìm nhãn; bbox gửi API vẫn là bbox toàn vật.',
        '- Proposal vật không số vẫn có thể được ghi trong log chẩn đoán, nhưng `target_recognized=false`, không vẽ như mục tiêu hợp lệ và không tạo candidate gửi.',
        '', '## Dữ liệu và giới hạn','',
        '- Xem `data/TRAINING_DATA.md`: ảnh vật thật ít; nhiều ảnh tăng cường có giấy A4 tổng hợp, không phải ảnh drone mới.',
        '- Balo từ COCO chính thức; giữ license/URL theo ảnh. Các checkpoint gốc đã pretrained COCO.',
        '- Dev tách theo nguồn ảnh/góc nhìn nhưng có thể cùng vật vật lý. Không coi mAP dev này là accuracy sân thi.',
        '- Chưa kiểm chứng server BTC, tư thế quét, độ lệch camera/OSD hoặc toàn pipeline trên laptop BTC.',
        '- Cần thêm ảnh thật A4 trên từng vật ở nhiều khoảng cách/zoom/ánh sáng; ưu tiên balo và số nhỏ/mờ.',
        '', '## Chạy thử','', '```powershell',
        r'.\.venv\Scripts\python.exe -m src.cli run --source fpt_map/object/chair_gray_number_21.jpg --config configs/trained.json --output output/trained-image-001 --debug --max-frames 1',
        '```','',
        'Ảnh đơn không đủ OCR consensus mặc định, thiếu telemetry cũng không tạo candidate hoàn chỉnh. Xem observations/debug để kiểm tra nhận vật và số; không tự bịa tầng/hướng.',
        '', 'Model và ảnh lớn giữ local theo gitignore. Chưa commit/push đợt train này.','']
    checks=ROOT/'evaluation/trained-target-checks.json'
    if checks.exists():
        checked=json.loads(checks.read_text())['samples']
        no_number=[r for r in checked if r['file']!='chair_gray_number_21.jpg']
        numbered=next(r for r in checked if r['file']=='chair_gray_number_21.jpg')
        lines+=['## Kiểm tra model và cổng nhận số','',
            f"- Vật không số: {sum(r['passed'] for r in no_number)}/{len(no_number)} ảnh được loại đúng.",
            f"- Ảnh A4 số 21: {'đạt (ghế xám, số 21)' if numbered['passed'] else 'chưa đạt đúng loại/số; xem trained-target-checks.json'}.",
            '- Với v3, đây là kiểm tra ảnh đã dùng để train/phát triển, không phải accuracy độc lập.','']
    (ROOT/'evaluation/TRAINING_RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',default=str(ROOT/'evaluation/training-20261106/selection.json'))
    main(parser.parse_args().selection)

"""Create a local video player with original OSD telemetry. Standard library only."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote


def build(recording, video, output):
    manifest = json.loads((recording / 'manifest.json').read_text(encoding='utf-8'))
    t0 = manifest['video_parts'][0]['clock']['t0']
    topic = 'thing/product/' + manifest['aircraft_sn'] + '/osd'
    payload = manifest.get('payload_index') or '88-0-0'
    points = []
    with (recording / 'telemetry.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get('topic') != topic:
                continue
            data = row.get('msg', {}).get('data', {})
            camera = data.get(payload) or {}
            points.append(dict(
                time_offset_s=row['t'] - t0,
                t_server_ms=round(row['t'] * 1000),
                lat=data.get('latitude'), lon=data.get('longitude'),
                alt_rel=data.get('elevation'), yaw=data.get('attitude_head'),
                pitch=data.get('attitude_pitch'), roll=data.get('attitude_roll'),
                horizontal_speed=data.get('horizontal_speed'),
                vertical_speed=data.get('vertical_speed'),
                gimbal_pitch=camera.get('gimbal_pitch'),
                gimbal_yaw=camera.get('gimbal_yaw'),
                gimbal_roll=camera.get('gimbal_roll'),
                zoom_factor=camera.get('zoom_factor'),
                battery=(data.get('battery') or {}).get('capacity_percent'),
                laser_distance=camera.get('measure_target_distance'),
                laser_error=camera.get('measure_target_error_state'),
            ))
    points.sort(key=lambda p: p['time_offset_s'])
    if not points:
        raise ValueError('No aircraft OSD records found')
    output.parent.mkdir(parents=True, exist_ok=True)
    url = quote(Path(os.path.relpath(video, output.parent)).as_posix())
    page = TEMPLATE.replace('__VIDEO__', url).replace(
        '__DATA__', json.dumps(points, ensure_ascii=True, allow_nan=False))
    output.write_text(page, encoding='utf-8')
    print(f'Created: {output.resolve()} ({len(points)} OSD samples)')


TEMPLATE = r'''<!doctype html>
<html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Video và dữ liệu drone</title>
<style>
body{margin:0;background:#101722;color:#e7edf5;font:16px system-ui;padding:24px}h1{font-size:24px}main{display:grid;grid-template-columns:minmax(0,2fr) minmax(290px,1fr);gap:24px}video{width:100%;max-height:78vh;background:#000}aside{background:#1b2635;padding:20px;border-radius:12px}table{width:100%;border-collapse:collapse}td{padding:7px 0;border-bottom:1px solid #334155}td:last-child{text-align:right;font-variant-numeric:tabular-nums}small,p{color:#b4c4d8;line-height:1.6}input{width:85px;padding:6px}pre{font-size:12px;overflow:auto}#status{color:#ffc86b}@media(max-width:850px){main{grid-template-columns:1fr}}
</style>
<h1>Video và dữ liệu drone</h1>
<main><section><video id="video" controls src="__VIDEO__"></video>
<p>Phát, tạm dừng hoặc tua video để xem dữ liệu tương ứng.</p>
<label>Hiệu chỉnh thời gian (giây): <input id="offset" type="number" value="0" step="0.1"></label>
<p><small>Tra dữ liệu tại thời gian video + hiệu chỉnh. Dùng mẫu gần nhất ở phía trước, không nội suy. Mốc đồng bộ lấy từ manifest; có thể có sai lệch ghi hình.</small></p>
<p id="error"></p></section><aside><strong id="clock">00:00</strong><p id="status"></p><table id="fields"></table><details><summary>Dữ liệu mẫu hiện tại</summary><pre id="raw"></pre></details></aside></main>
<script>
const points=__DATA__;
const video=document.getElementById('video'), offset=document.getElementById('offset');
const fields=[['alt_rel','Độ cao tương đối','m'],['yaw','Hướng mũi drone','°'],['pitch','Pitch drone','°'],['roll','Roll drone','°'],['gimbal_pitch','Gimbal pitch','°'],['gimbal_yaw','Gimbal yaw','°'],['gimbal_roll','Gimbal roll','°'],['zoom_factor','Zoom (giá trị gốc)',''],['horizontal_speed','Tốc độ ngang','m/s'],['vertical_speed','Tốc độ dọc','m/s'],['battery','Pin','%'],['lat','Vĩ độ',''],['lon','Kinh độ',''],['laser_distance','Khoảng cách laser','m'],['laser_error','Trạng thái laser (gốc)','']];
function update(){
 const t=video.currentTime+Number(offset.value||0);
 document.getElementById('clock').textContent='Video: '+video.currentTime.toFixed(2)+' s';
 let lo=0,hi=points.length-1,index=-1;
 while(lo<=hi){const m=(lo+hi)>>1;if(points[m].time_offset_s<=t){index=m;lo=m+1}else hi=m-1}
 const p=index<0?null:points[index],age=p?t-p.time_offset_s:null;
 document.getElementById('status').textContent=p?'Mẫu tại '+p.time_offset_s.toFixed(2)+' s · cách '+age.toFixed(2)+' s'+(age>5?' · Dữ liệu đã cũ':''):'Chưa có dữ liệu tại thời điểm này';
 document.getElementById('fields').innerHTML=fields.map(([k,label,unit])=>{let v=p?.[k];let s=v==null?'—':typeof v==='number'?v.toFixed(k==='lat'||k==='lon'?7:k==='laser_error'?0:2):String(v);if(k==='laser_distance'&&p?.laser_error!==0)s+=' (chưa xác nhận hợp lệ)';return '<tr><td>'+label+'</td><td>'+s+(v==null?'':' '+unit)+'</td></tr>'}).join('');
 document.getElementById('raw').textContent=JSON.stringify(p,null,2);
}
video.addEventListener('timeupdate',update);video.addEventListener('seeked',update);offset.addEventListener('input',update);
video.addEventListener('error',()=>document.getElementById('error').textContent='Không mở được video. Giữ file HTML ở vị trí đã tạo và kiểm tra file MP4 còn tồn tại.');update();
</script></html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('output/recording-viewer.html'))
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error('Video file does not exist')
    build(args.recording, args.video, args.output)

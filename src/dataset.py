"""Build a reproducible labeling queue; no fabricated ground-truth boxes."""
import hashlib
import json
from pathlib import Path


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def build_dataset(video, output, map_dir=None, count=40, split='dev', source_group='flight_261106'):
    import cv2
    from .sources import replay
    output = Path(output)
    if (output/'manifest.json').exists():
        raise FileExistsError('Manifest already exists; use another directory to preserve annotations')
    (output / 'images').mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    fps, total = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps <= 0 or total <= 0:
        raise ValueError('Cannot determine video duration')
    duration = total/fps
    samples = []
    for index in range(count):
        timestamp = duration*(index+.5)/count
        frame = next(replay(video, start_s=timestamp, limit=1))
        name = f'{source_group}-{index:04d}'
        destination = output / 'images' / f'{name}.jpg'
        destination.write_bytes(frame.jpeg)
        samples.append(dict(sample_id=name, image=f'images/{name}.jpg', sha256=checksum(destination),
            source_group=source_group, source=str(Path(video).as_posix()), video_time_s=frame.video_time_s,
            split=split, annotation_status='pending', objects=[]))
    if map_dir:
        from PIL import Image, ImageOps
        for path in sorted((Path(map_dir) / 'object').glob('*.JPG')):
            name = 'map-'+path.stem
            destination = output / 'images' / f'{name}.jpg'
            with Image.open(path) as image:
                ImageOps.exif_transpose(image).convert('RGB').save(destination, quality=95)
            samples.append(dict(sample_id=name, image=f'images/{name}.jpg', sha256=checksum(destination),
                source_group='map-object-'+path.stem.rsplit('_', 1)[0], source=path.as_posix(), video_time_s=None,
                split=split, annotation_status='pending', objects=[]))
    manifest = dict(version=1, note='Pending annotations are not empty ground truth. Keep a separate flight/scene for holdout.', samples=samples)
    path = output / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    contact_sheet(path)
    return len(samples)


def contact_sheet(manifest_path):
    from PIL import Image, ImageDraw, ImageOps
    path = Path(manifest_path)
    samples = json.loads(path.read_text(encoding='utf-8'))['samples']
    sheet = Image.new('RGB', (1000, ((len(samples)+3)//4)*180), '#192433')
    draw = ImageDraw.Draw(sheet)
    for i, sample in enumerate(samples):
        with Image.open(path.parent/sample['image']) as image:
            thumb = ImageOps.contain(image.convert('RGB'), (244, 145))
        x, y = (i % 4)*250, (i//4)*180
        sheet.paste(thumb, (x, y))
        draw.text((x+3, y+148), sample['sample_id'], fill='white')
    sheet.save(path.parent/'contact-sheet.jpg')

"""Export reviewed object boxes and train a local custom detector."""
import json
import shutil
from pathlib import Path

CLASSES = ['chair_orange', 'chair_white', 'chair_gray', 'backpack', 'fire_extinguisher']


def export_yolo(manifest_path, destination):
    from PIL import Image
    path, destination = Path(manifest_path), Path(destination)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    reviewed = [s for s in manifest['samples'] if s['annotation_status'] == 'reviewed' and s['split'] in ('train', 'dev')]
    if not any(s['split'] == 'train' for s in reviewed) or not any(s['split'] == 'dev' for s in reviewed):
        raise ValueError('Need reviewed train and dev images; do not split neighboring frames between them')
    groups = {}
    for sample in manifest['samples']:
        groups.setdefault(sample['source_group'], set()).add(sample['split'])
    if any(len(splits) > 1 for splits in groups.values()):
        raise ValueError('Source-group leakage across splits; fix manifest before export')
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError('Export directory must be empty')
    for sample in reviewed:
        split = 'train' if sample['split'] == 'train' else 'val'
        images, labels = destination / 'images' / split, destination / 'labels' / split
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        source = path.parent/sample['image']
        with Image.open(source) as image:
            width, height = image.size
        rows = []
        for obj in sample['objects']:
            if obj['object_type'] not in CLASSES:
                continue
            x1,y1,x2,y2 = obj['bbox']
            if not 0 <= x1 < x2 <= width or not 0 <= y1 < y2 <= height:
                raise ValueError(f"Invalid annotation bbox: {sample['sample_id']}")
            rows.append(f'{CLASSES.index(obj["object_type"])} {(x1+x2)/2/width:.8f} {(y1+y2)/2/height:.8f} {(x2-x1)/width:.8f} {(y2-y1)/height:.8f}')
        shutil.copyfile(source, images/(sample['sample_id']+source.suffix.lower()))
        (labels/(sample['sample_id']+'.txt')).write_text('\n'.join(rows), encoding='utf-8')
    # JSON is valid YAML and avoids adding a parser dependency for writing config.
    dataset = dict(path=str(destination.resolve()), train='images/train', val='images/val', names=dict(enumerate(CLASSES)))
    (destination/'dataset.yaml').write_text(json.dumps(dataset, indent=2), encoding='utf-8')
    return destination/'dataset.yaml'


def train(data, weights, output, epochs=50, device='cpu'):
    from ultralytics import YOLO
    if not Path(weights).is_file():
        raise FileNotFoundError('Training requires local initial weights')
    if epochs < 1:
        raise ValueError('Epochs must be positive')
    YOLO(weights).train(data=str(data), epochs=epochs, imgsz=640, batch=4,
                        device=device, workers=0, seed=42, project=str(Path(output).parent),
                        name=Path(output).name, exist_ok=False)

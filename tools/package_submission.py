"""Build a bounded, explicit runtime package, excluding recordings and secrets."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build():
    paths = ['solution.py', 'requirements.txt', 'requirements-lock.txt', 'custom-classes.json',
             'configs/live.json', 'configs/trained.json', 'configs/model-manifest.json',
             'models/best_detector.pt', 'starter-kit-indoor/indoor_client.py',
             'starter-kit-indoor/telemetry_location.py', 'starter-kit-indoor/telemetry-location.json',
             'starter-kit-indoor/solution.py']
    paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/'src').glob('*.py')]
    paths += ['models/ocr/'+name for name in ('det.onnx','cls.onnx','rec.onnx','params.json')]
    model_bytes = sum((ROOT/p).stat().st_size for p in paths if p.startswith('models/'))
    if model_bytes > 150_000_000:
        raise ValueError('Model limit exceeded')
    destination = ROOT/'output/KTN_submission.zip'
    destination.parent.mkdir(exist_ok=True)
    checksums = {}
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        def add(source, target):
            data = (ROOT/source).read_bytes()
            archive.writestr('KTN_submission/'+target, data)
            checksums[target] = hashlib.sha256(data).hexdigest()
        for path in paths:
            add(path, path)
        add('KTN_README.md', 'README.md')
        add('starter-kit-indoor/indoor_client.py','indoor_client.py')
        add('fpt_map/object/chair_gray_number_21.jpg','test_assets/chair_gray_number_21.jpg')
        archive.writestr('KTN_submission/SHA256SUMS.json',json.dumps(checksums,indent=2))
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert not any('sample_data/' in name or name.endswith(('.mp4','.exe','.bat')) for name in archive.namelist())
    print(json.dumps(dict(archive=str(destination),bytes=destination.stat().st_size,
        model_bytes=model_bytes, sha256=hashlib.sha256(destination.read_bytes()).hexdigest()),indent=2))


if __name__ == '__main__':
    build()

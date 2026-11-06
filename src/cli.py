"""FinalDrone command line. Execute from repository root: python -m src.cli --help."""
import argparse
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / '.work/ultralytics'))


def default_config():
    return 'configs/trained.json' if (ROOT/'configs/trained.json').is_file() and (ROOT/'models/best_detector.pt').is_file() else 'configs/offline.json'


def read_config(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    weights = Path(cfg['weights'])
    cfg['weights'] = str(weights if weights.is_absolute() else ROOT / weights)
    if cfg['location']['heading_field'] not in ('aircraft_yaw', 'gimbal_yaw'):
        raise ValueError('heading_field must be aircraft_yaw or gimbal_yaw')
    if cfg['tracking']['min_votes'] < 1 or not 0 < cfg['tracking']['vote_fraction'] <= 1:
        raise ValueError('Invalid OCR consensus thresholds')
    return cfg


def prepare_assets(args):
    """Explicit preparation command; inference itself never downloads assets."""
    import shutil
    from ultralytics import YOLO
    directory = ROOT / 'models'
    directory.mkdir(exist_ok=True)
    weight = directory / 'yolov8n.pt'
    if not weight.exists():
        # Ultralytics downloads an official named checkpoint in this explicit command.
        original = Path.cwd()
        try:
            os.chdir(directory)
            YOLO('yolov8n.pt')
        finally:
            os.chdir(original)
    from rapidocr import RapidOCR
    from rapidocr.utils.typings import OCRVersion, ModelType
    from rapidocr.inference_engine.base import FileInfo, InferSession
    from rapidocr.utils.download_models import download_task
    ocr_dir = directory / 'ocr'
    ocr_dir.mkdir(exist_ok=True)
    params = {'Global.model_root_dir': str(ocr_dir.resolve()),
              'Det.ocr_version': 'PP-OCRv4', 'Det.model_type': 'mobile',
              'Rec.ocr_version': 'PP-OCRv4', 'Rec.model_type': 'mobile',
              'EngineConfig.onnxruntime.intra_op_num_threads': 2,
              'EngineConfig.onnxruntime.inter_op_num_threads': 1}
    enum_params = {k: OCRVersion(v) if k.endswith('ocr_version') else ModelType(v) if k.endswith('model_type') else v
                   for k, v in params.items()}
    engine = RapidOCR(params=enum_params)
    for component, name in [('Det', 'det.onnx'), ('Cls', 'cls.onnx'), ('Rec', 'rec.onnx')]:
        component_cfg = getattr(engine.cfg, component)
        info = FileInfo(component_cfg.engine_type, component_cfg.ocr_version, component_cfg.task_type,
                        component_cfg.lang_type, component_cfg.model_type)
        download_task(ocr_dir, info)
        downloaded = ocr_dir / Path(InferSession.get_model_url(info)['model_dir']).name
        shutil.copyfile(downloaded, ocr_dir/name)
        # The renamed copy is the portable asset; remove duplicate source checkpoint.
        downloaded.unlink()
    params.pop('Global.model_root_dir')
    (ocr_dir/'params.json').write_text(json.dumps(params, indent=2), encoding='utf-8')
    from .dataset import checksum
    manifest = {p.relative_to(directory).as_posix(): {'sha256': checksum(p), 'bytes': p.stat().st_size}
                for p in sorted(directory.rglob('*')) if p.is_file() and p.name != 'assets.json'}
    (directory/'assets.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


def metadata(config, output):
    import importlib.metadata
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Run directory is not empty; choose a new --output')
    output.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    versions = {}
    for name in ('torch', 'ultralytics', 'opencv-python', 'rapidocr', 'onnxruntime'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    (output/'run.json').write_text(json.dumps(dict(commit=commit, config=config, platform=platform.platform(),
                                                  python=platform.python_version(), dependencies=versions), indent=2), encoding='utf-8')


def run(args):
    from .pipeline import Pipeline
    from .sources import LatestSource, paced, replay, rtsp_frames
    from .telemetry import Timeline
    from .vision import Detector, DigitsOCR
    cfg = read_config(args.config)
    if getattr(args, 'weights', None):
        cfg['weights'] = str(Path(args.weights).resolve())
    live = args.mode == 'live'
    if args.max_frames < 1 or not math.isfinite(args.step_s) or not math.isfinite(args.start_s) or args.step_s < 0 or args.start_s < 0:
        raise ValueError('max-frames must be positive; start/step must be nonnegative')
    if args.duration_s is not None and (not math.isfinite(args.duration_s) or args.duration_s <= 0):
        raise ValueError('duration-s must be finite and positive')
    if live:
        if not args.server or not args.session:
            raise ValueError('Live mode requires --server and --session')
        if not cfg['delivery']['status_telemetry_path']:
            raise ValueError('Configure verified delivery.status_telemetry_path before live use')
        if not cfg['location']['heading_verified'] or not cfg['location']['scan_pose_verified']:
            raise ValueError('Verify heading/scan pose in location config before live use')
    elif str(args.source).lower().startswith(('rtsp://', 'http://', 'https://')):
        raise ValueError('Offline/realtime modes require a local source')
    metadata(cfg, args.output)
    detector = Detector(cfg)
    ocr = DigitsOCR(ROOT / 'models/ocr', cfg['ocr'])
    import numpy as np
    detector.detect(np.zeros((cfg['imgsz'], cfg['imgsz'], 3), dtype=np.uint8))
    timeline = Timeline.load(args.telemetry) if args.telemetry else Timeline()
    print('Supported detector targets:', detector.supported)
    if 'fire_extinguisher' not in detector.supported:
        print('Fire extinguisher unsupported by this checkpoint; supply custom weights/class_map.')
    with ExitStack() as stack:
        delivery = None
        if live:
            from .delivery import Delivery
            delivery = stack.enter_context(Delivery(cfg['delivery'], args.server, args.session, args.output, timeline))
            source = stack.enter_context(LatestSource(rtsp_frames(args.source)))
            frames = source
        else:
            frames = replay(args.source, args.start_s, args.step_s, args.max_frames, timeline.t0)
            source = None
            if args.mode == 'realtime':
                stop = threading.Event()
                stack.callback(stop.set)
                source = stack.enter_context(LatestSource(paced(frames, stop)))
                # Stop the pacer before waiting for the source thread on shutdown.
                stack.callback(stop.set)
                frames = source
        pipeline = Pipeline(cfg, detector, ocr, timeline, args.output, args.session, delivery)
        started = time.monotonic()
        try:
            for frame in frames:
                if pipeline.frames >= args.max_frames:
                    break
                if args.duration_s is not None and time.monotonic()-started >= args.duration_s:
                    break
                if live and (time.monotonic() >= delivery.deadline or delivery.state != 'RUNNING' or delivery.error):
                    break
                pipeline.process(frame, debug=args.debug, live=live)
                if pipeline.frames == 1 or pipeline.frames % 30 == 0:
                    print(f'frames={pipeline.frames} detections={pipeline.observations} candidates={pipeline.candidates}', flush=True)
        finally:
            summary = pipeline.close()
            summary['wall_time_s'] = time.monotonic()-started
            summary['throughput_fps'] = pipeline.frames/max(summary['wall_time_s'], 1e-9)
            summary['dropped_frames'] = source.dropped if source else 0
            (Path(args.output)/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            print(json.dumps(summary, indent=2))


def predict_dataset(args):
    from dataclasses import asdict
    import cv2
    from .telemetry import Locator, Timeline
    from .vision import Detector, DigitsOCR, classify_chair
    cfg = read_config(args.config)
    detector = Detector(cfg)
    ocr = DigitsOCR(ROOT/'models/ocr', cfg['ocr'])
    timeline = Timeline.load(args.telemetry) if args.telemetry else Timeline()
    locator = Locator(cfg['location'])
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    predictions = {}
    for sample in manifest['samples']:
        if sample['split'] != args.split:
            continue
        image = cv2.imread(str(manifest_path.parent/sample['image']))
        if image is None:
            raise ValueError(f"Missing image: {sample['image']}")
        found = []
        for detection in detector.detect(image):
            x1,y1,x2,y2 = detection.bbox
            if detection.object_type == 'chair':
                detection.object_type = classify_chair(image[y1:y2,x1:x2], cfg['color'])
            read = ocr.read(image, detection.bbox,label_hint=detection.label_bbox)
            location = locator.locate(sample['video_time_s'], detection.bbox, (image.shape[1],image.shape[0]), timeline) if sample['video_time_s'] is not None else None
            found.append(dict(bbox=detection.bbox, object_type=detection.object_type, confidence=detection.confidence,
                              number=read.number, ocr=asdict(read), floor=location.floor if location and location.valid else None,
                              direction=location.direction if location and location.valid else None))
        predictions[sample['sample_id']] = found
        print(sample['sample_id'], len(found), flush=True)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(predictions, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('prepare-assets', help='Explicitly download baseline detector/OCR before offline use')
    extract = commands.add_parser('extract', help='Create an annotation queue from video/map')
    extract.add_argument('--video', required=True)
    extract.add_argument('--output', default='data')
    extract.add_argument('--map-dir')
    extract.add_argument('--count', type=int, default=40)
    extract.add_argument('--source-group', default='flight_261106')
    extract.add_argument('--split', choices=['train', 'dev', 'holdout'], default='dev')
    label = commands.add_parser('annotate', help='Draw object/number boxes and enter labels')
    label.add_argument('--manifest', default='data/manifest.json')
    evaluate = commands.add_parser('evaluate', help='Evaluate reviewed labels against predictions JSON')
    evaluate.add_argument('--manifest', required=True)
    evaluate.add_argument('--predictions', required=True)
    evaluate.add_argument('--split', default='dev', choices=['train', 'dev', 'holdout'])
    evaluate.add_argument('--output', default='output/evaluation.json')
    evaluate.add_argument('--iou', type=float, default=.5)
    predict = commands.add_parser('predict-dataset')
    predict.add_argument('--manifest', default='data/manifest.json')
    predict.add_argument('--split', choices=['train','dev','holdout'], default='dev')
    predict.add_argument('--config', default=default_config())
    predict.add_argument('--telemetry')
    predict.add_argument('--output', default='output/predictions.json')
    export = commands.add_parser('export-yolo')
    export.add_argument('--manifest', default='data/manifest.json')
    export.add_argument('--output', default='artifacts/yolo-dataset')
    train_parser = commands.add_parser('train')
    train_parser.add_argument('--data', required=True)
    train_parser.add_argument('--weights', default='models/yolov8n.pt')
    train_parser.add_argument('--output', default='experiments/train-detector')
    train_parser.add_argument('--epochs', type=int, default=50)
    train_parser.add_argument('--device', default='cpu')
    execute = commands.add_parser('run')
    execute.add_argument('--source', required=True)
    execute.add_argument('--telemetry', help='Recording folder or compact JSON timeline')
    execute.add_argument('--config', default=default_config())
    execute.add_argument('--weights', help='Optional local detector override (BTC launcher compatibility)')
    execute.add_argument('--calibration', help='Accepted for BTC launcher compatibility; location uses config, not venue ROI')
    execute.add_argument('--output', required=True)
    execute.add_argument('--mode', choices=['offline', 'realtime', 'live'], default='offline')
    execute.add_argument('--start-s', type=float, default=0)
    execute.add_argument('--step-s', type=float, default=0)
    execute.add_argument('--max-frames', type=int, default=100000)
    execute.add_argument('--duration-s', type=float, help='Optional wall-clock processing limit')
    execute.add_argument('--debug', action='store_true')
    execute.add_argument('--server')
    execute.add_argument('--session')
    args = parser.parse_args()
    if args.command == 'prepare-assets':
        prepare_assets(args)
    elif args.command == 'extract':
        from .dataset import build_dataset
        if args.count < 1:
            parser.error('count must be positive')
        print('Samples:', build_dataset(args.video, args.output, args.map_dir, args.count, args.split, args.source_group))
    elif args.command == 'annotate':
        from .annotation import annotate
        annotate(args.manifest)
    elif args.command == 'evaluate':
        from .evaluation import evaluate
        report = evaluate(args.manifest, args.predictions, args.split, args.iou)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
    elif args.command == 'predict-dataset':
        predict_dataset(args)
    elif args.command == 'export-yolo':
        from .training import export_yolo
        print(export_yolo(args.manifest, args.output))
    elif args.command == 'train':
        from .training import train
        train(args.data,args.weights,args.output,args.epochs,args.device)
    else:
        run(args)


if __name__ == '__main__':
    main()

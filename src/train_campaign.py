"""Train one reproducible candidate and save class metrics without touching holdout."""
import argparse
import csv
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR',str(ROOT/'.work/ultralytics'))


def run(args):
    import torch
    from ultralytics import YOLO
    import ultralytics.utils.torch_utils as torch_utils
    torch_utils.NUM_THREADS=4
    torch.set_num_threads(4)
    output=Path(args.output).resolve()
    if output.exists():
        raise FileExistsError('Use a new training run directory')
    output.mkdir(parents=True)
    initial=Path(args.weights).resolve()
    model=YOLO(str(initial))
    started=time.monotonic()

    def progress(trainer):
        record=dict(epoch=min(trainer.epoch+1,args.epochs),total_epochs=args.epochs,elapsed_s=time.monotonic()-started,
                    metrics={str(k):float(v) for k,v in trainer.metrics.items()})
        (output/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')

    model.add_callback('on_fit_epoch_end',progress)
    model.train(data=str(Path(args.data).resolve()),epochs=args.epochs,imgsz=args.imgsz,batch=args.batch,
        device=args.device,workers=0,freeze=args.freeze,optimizer='AdamW',lr0=args.lr,weight_decay=.0005,
        warmup_epochs=2,patience=12,cos_lr=True,seed=42,deterministic=True,
        project=str(output.parent),name=output.name,exist_ok=True,plots=False,
        degrees=20,translate=.1,scale=.5,hsv_h=.005,hsv_s=.15,hsv_v=.25,
        fliplr=0,flipud=0,mosaic=.5,close_mosaic=5,mixup=0,cache=False,amp=False,save=True)
    best=output/'weights/best.pt'
    validated=YOLO(str(best)).val(data=str(Path(args.data).resolve()),split='val',imgsz=args.imgsz,
                                   batch=args.batch,device=args.device,workers=0,plots=False,project=str(output),name='dev-evaluation')
    report=dict(weights=str(best.relative_to(ROOT)),initial_weights=str(initial.relative_to(ROOT)),
        data=str(Path(args.data).relative_to(ROOT) if Path(args.data).is_absolute() else args.data),
        freeze=args.freeze,imgsz=args.imgsz,epochs_requested=args.epochs,
        epochs_completed=len(list(csv.DictReader((output/'results.csv').open()))),device=args.device,learning_rate=args.lr,
        torch_version=torch.__version__,cuda_version=torch.version.cuda,
        gpu=torch.cuda.get_device_name(0) if args.device!='cpu' else None,
        elapsed_s=time.monotonic()-started,metrics={str(k):float(v) for k,v in validated.results_dict.items()},
        per_class_map50_95={str(name):float(validated.box.maps[i]) if i in set(validated.box.ap_class_index) else None
                            for i,name in validated.names.items()},
        note='Source-photo-held-out dev includes synthetic A4. Not competition field accuracy. Holdout not used here.')
    (output/'candidate.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',default='artifacts/training-v1/dataset.yaml')
    parser.add_argument('--output',required=True)
    parser.add_argument('--epochs',type=int,default=30)
    parser.add_argument('--imgsz',type=int,default=416)
    parser.add_argument('--freeze',type=int,default=10)
    parser.add_argument('--weights',default='models/yolov8n.pt')
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--batch',type=int,default=8)
    parser.add_argument('--lr',type=float,default=.001)
    run(parser.parse_args())

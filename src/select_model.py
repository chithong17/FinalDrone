"""Select on common dev, then evaluate the chosen candidate once on detector holdout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR',str(ROOT/'.work/ultralytics'))


def evaluate(weights,data,split,imgsz,output,name,check_fixture=False):
    from ultralytics import YOLO
    import ultralytics.utils.torch_utils as torch_utils
    torch_utils.NUM_THREADS=4
    model=YOLO(str(weights))
    result=model.val(data=str(data),split=split,imgsz=imgsz,batch=8,device='cpu',workers=0,
                     plots=False,project=str(output),name=name,exist_ok=True)
    present={int(i) for i in result.box.ap_class_index}
    classes={str(label):float(result.box.maps[i]) if i in present else None for i,label in result.names.items()}
    target_maps=[score for name,score in classes.items() if name!='number_label' and score is not None]
    fixture_pass=None
    if check_fixture:
        import cv2
        from .tracking import iou
        image=cv2.imread(str(ROOT/'fpt_map/object/chair_gray_number_21.jpg'))
        h,w=image.shape[:2]
        expected=[.210*w,.201*h,.844*w,.675*h]
        prediction=model.predict(image,imgsz=imgsz,conf=.35,device='cpu',verbose=False)[0]
        fixture_pass=any(model.names[int(box.cls.item())]=='chair_gray' and iou(box.xyxy[0].tolist(),expected)>=.5 for box in prediction.boxes)
    return dict(weights=str(weights),split=split,imgsz=imgsz,per_class_map50_95=classes,training_fixture_pass=fixture_pass,
                target_macro_map50_95=sum(target_maps)/len(target_maps) if target_maps else 0,
                metrics={str(k):float(v) for k,v in result.results_dict.items()})


def main(args):
    data=Path(args.data).resolve()
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    reports=[]
    provenance=json.loads((data.parent/'provenance.json').read_text(encoding='utf-8'))
    check_fixture=any(s['source']=='chair_gray_number_21.jpg' and s['split']=='train' for s in provenance['samples'])
    for i,weights in enumerate(args.candidates):
        for size in args.sizes:
            reports.append(evaluate(Path(weights).resolve(),data,'val',size,output,f'candidate-{i}-{size}-dev',check_fixture))
    eligible=[r for r in reports if not check_fixture or r['training_fixture_pass']]
    if not eligible:
        raise ValueError('No candidate passes the required gray-chair A4 training fixture; do not deploy silently')
    best=max(eligible,key=lambda r:r['target_macro_map50_95'])
    selected=ROOT/'models/best_detector.pt'
    shutil.copyfile(best['weights'],selected)
    cfg=json.loads((ROOT/'configs/offline.json').read_text(encoding='utf-8-sig'))
    cfg['weights']='models/best_detector.pt'
    cfg['imgsz']=best['imgsz']
    cfg['class_map']={name:name for name in ['chair_orange','chair_white','chair_gray','backpack','fire_extinguisher']}
    (ROOT/'configs/trained.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    holdout=evaluate(selected,data,'test',best['imgsz'],output,'selected-holdout')
    report=dict(selection_metric='macro mAP50-95 across five object classes on common dev; excludes number_label',
        eligibility_rule='When real A4 fixture is in train: require gray-chair detection with IoU>=0.5/conf>=0.35 on that known training fixture. This is not holdout accuracy.',
        data=str(data),dataset_counts={split:sum(s['split']==split for s in provenance['samples']) for split in ['train','dev','holdout']},
        real_a4_used_for_training=any(s['source']=='chair_gray_number_21.jpg' and s['split']=='train' for s in provenance['samples']),
        candidates=reports,selected=best,holdout=holdout,sha256=hashlib.sha256(selected.read_bytes()).hexdigest(),
        note='Small source-separated dataset with synthetic A4. Detector holdout does not establish competition accuracy. Real number fixtures were used for OCR development.')
    (output/'selection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',nargs='+',required=True)
    parser.add_argument('--data',default='artifacts/training-v2/dataset.yaml')
    parser.add_argument('--sizes',type=int,nargs='+',default=[416,640])
    parser.add_argument('--output',default='evaluation/training-20261106')
    main(parser.parse_args())

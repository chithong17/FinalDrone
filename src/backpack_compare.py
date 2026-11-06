"""Compare backpack-only AP on a common source-separated dev split."""
import json
import os
from pathlib import Path

import numpy as np

from .tracking import iou

os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parents[1]/'.work/ultralytics'))


def average_precision(truth,predictions,threshold):
    total=sum(len(boxes) for boxes in truth.values())
    if total==0:
        return None
    ranked=sorted(predictions,key=lambda p:p['confidence'],reverse=True)
    matched={key:set() for key in truth}
    tp,fp=[],[]
    for pred in ranked:
        image=pred['image']
        boxes=truth.get(image,[])
        candidates=[(iou(pred['bbox'],box),i) for i,box in enumerate(boxes) if i not in matched.get(image,set())]
        score,index=max(candidates,default=(0,-1))
        good=index>=0 and score>=threshold
        tp.append(int(good))
        fp.append(int(not good))
        if good:
            matched[image].add(index)
    if not ranked:
        return 0.0
    recall=np.cumsum(tp)/total
    precision=np.cumsum(tp)/np.maximum(1,np.cumsum(tp)+np.cumsum(fp))
    # 101-point interpolation; same implementation used for both checkpoints.
    return float(np.mean([np.max(precision[recall>=r],initial=0) for r in np.linspace(0,1,101)]))


def evaluate_backpacks(weights,dataset,split='dev',imgsz=640):
    import cv2
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(2)
    dataset=Path(dataset)
    model=YOLO(str(weights))
    class_id=next(i for i,name in model.names.items() if name=='backpack')
    classes=json.loads((dataset/'provenance.json').read_text())['classes']
    target_id=classes.index('backpack')
    truth,predictions={},[]
    for path in sorted((dataset/'images'/split).glob('*.jpg')):
        image=cv2.imread(str(path))
        h,w=image.shape[:2]
        label=dataset/'labels'/split/(path.stem+'.txt')
        truth[path.name]=[]
        for line in label.read_text().splitlines():
            cls,cx,cy,bw,bh=map(float,line.split())
            if int(cls)==target_id:
                truth[path.name].append([(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h])
        result=model.predict(image,classes=[class_id],conf=.001,imgsz=imgsz,device='cpu',verbose=False)[0]
        for box in result.boxes:
            predictions.append(dict(image=path.name,bbox=box.xyxy[0].tolist(),confidence=float(box.conf.item())))
    values=[average_precision(truth,predictions,t) for t in np.linspace(.5,.95,10)]
    return dict(weights=str(weights),ap50=values[0],map50_95=float(np.mean(values)),
                ground_truth=sum(map(len,truth.values())),images=len(truth),imgsz=imgsz,
                note='Internal 101-point backpack AP, identical evaluator for all candidates; dev contains synthetic tags.')

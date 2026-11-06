"""Local detector and two-digit OCR. Assets must be prepared before inference."""
import math
import json
import re
from pathlib import Path

from .contracts import Detection, NumberRead


def original_box(box, width, height):
    if len(box) != 4 or not all(math.isfinite(float(x)) for x in box):
        raise ValueError('Invalid bbox')
    x1, y1 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
    x2, y2 = min(width, math.ceil(box[2])), min(height, math.ceil(box[3]))
    if x1 >= x2 or y1 >= y2:
        raise ValueError('Empty bbox')
    return [x1, y1, x2, y2]


class Detector:
    def __init__(self, config):
        import torch
        from ultralytics import YOLO
        if not Path(config['weights']).is_file():
            raise FileNotFoundError(f"Local weights missing: {config['weights']}; run prepare-assets first")
        torch.set_num_threads(config['threads'])
        self.model = YOLO(config['weights'])
        self.config = config
        self.mapping = config.get('class_map') or {'chair': 'chair', 'backpack': 'backpack'}
        self.supported = sorted({self.mapping.get(str(k), self.mapping.get(v))
                                 for k, v in self.model.names.items()} - {None})

    def detect(self, image):
        cfg = self.config
        result = self.model.predict(image, imgsz=cfg['imgsz'], conf=cfg['confidence'],
                                    device=cfg['device'], verbose=False, max_det=30)[0]
        h, w = image.shape[:2]
        if tuple(result.orig_shape) != (h, w):
            raise ValueError('Detector original resolution mismatch')
        found, papers = [], []
        for b in result.boxes:
            class_id = int(b.cls.item())
            name = self.model.names[class_id]
            if name == 'number_label':
                papers.append(original_box(b.xyxy[0].tolist(), w, h))
                continue
            kind = self.mapping.get(str(class_id), self.mapping.get(name))
            if kind:
                found.append(Detection(original_box(b.xyxy[0].tolist(), w, h), name, kind, float(b.conf.item())))
        for paper in papers:
            cx,cy=(paper[0]+paper[2])/2,(paper[1]+paper[3])/2
            owners=[d for d in found if d.bbox[0]<=cx<=d.bbox[2] and d.bbox[1]<=cy<=d.bbox[3]]
            if owners:
                owner=min(owners,key=lambda d:abs(cx-(d.bbox[0]+d.bbox[2])/2)/(d.bbox[2]-d.bbox[0])+
                          abs(cy-(d.bbox[1]+d.bbox[3])/2)/(d.bbox[3]-d.bbox[1]))
                if owner.label_bbox is None:
                    owner.label_bbox=paper
        return found


def classify_chair(crop, config):
    import cv2
    import numpy as np
    h, w = crop.shape[:2]
    sample = crop[int(h*.65):max(int(h*.9), int(h*.65)+1), int(w*.15):max(int(w*.85), int(w*.15)+1)]
    if not sample.size:
        return None
    hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
    scores = {kind: float(np.count_nonzero(cv2.inRange(hsv, np.array(low), np.array(high)))) / (hsv.shape[0]*hsv.shape[1])
              for kind, (low, high) in config['ranges'].items()}
    ranked = sorted(scores, key=scores.get, reverse=True)
    if scores[ranked[0]] < config['min_fraction'] or scores[ranked[0]]-scores[ranked[1]] < config['min_margin']:
        return None
    return ranked[0]


def label_regions(crop, config):
    """Propose bright paper regions; OCR still rejects textless white objects."""
    import cv2
    import numpy as np
    h, w = crop.shape[:2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 0, 135]), np.array([179, 100, 255]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        if bw*bh < h*w*config['min_label_area_fraction'] or bw < 12 or bh < 12:
            continue
        if not .3 <= bw/bh <= 5:
            continue
        pad = max(2, round(min(bw, bh)*.05))
        regions.append([max(0, x-pad), max(0, y-pad), min(w, x+bw+pad), min(h, y+bh+pad)])
    regions.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
    regions = regions[:config['max_label_candidates']]
    if [0, 0, w, h] not in regions:
        regions.append([0, 0, w, h])  # OCR detection may find a label missed by paper proposal.
    return regions


def _underline_signal(label):
    """Use a separate long underline below/above digits; otherwise test orientations."""
    import cv2
    gray = cv2.cvtColor(label, cv2.COLOR_BGR2GRAY)
    block=max(15,min(151,(min(gray.shape)//4)|1))
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,block,15)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    height, width = gray.shape
    components = [tuple(map(int, stats[i])) for i in range(1,count)]
    signals = []
    for x,y,w,h,area in components:
        if w < max(15,width*.2) or w/max(h,1) < 5 or h > height*.15 or area/(w*h) < .5:
            continue
        digits = [(a,b,c,d,s) for a,b,c,d,s in components
                  if d >= max(8,height*.1) and .1 <= c/max(d,1) <= 2 and s >= 10]
        above = any(-2 <= y-(b+d) <= max(10,d*.6) for a,b,c,d,s in digits)
        below = any(-2 <= b-(y+h) <= max(10,d*.6) for a,b,c,d,s in digits)
        if above and not below:
            signals.append((0,y))
        elif below and not above:
            signals.append((180,height-y-h))
    if signals and len({rotation for rotation,_ in signals}) == 1:
        rotation, end = max(signals, key=lambda item:item[1])
        oriented = label if rotation == 0 else cv2.rotate(label,cv2.ROTATE_180)
        return oriented[:max(1,end)],rotation
    return None


def label_orientations(label, rotations):
    import cv2
    signal=_underline_signal(label)
    if signal:
        return [signal]
    return [(label if r == 0 else cv2.rotate(label,cv2.ROTATE_180),r) for r in rotations]


def paper_orientations(paper):
    """Normalize 0/90/180/270; only an underline determines ambiguous 6/9 direction."""
    import cv2
    candidates=[]
    for rotation,code in [(0,None),(90,cv2.ROTATE_90_CLOCKWISE)]:
        oriented=paper if code is None else cv2.rotate(paper,code)
        signal=_underline_signal(oriented)
        if signal:
            cropped,extra=signal
            candidates.append((cropped,(rotation+extra)%360,True))
    if candidates:
        return candidates
    return [(paper,0,False),(cv2.rotate(paper,cv2.ROTATE_90_CLOCKWISE),90,False),
            (cv2.rotate(paper,cv2.ROTATE_180),180,False),(cv2.rotate(paper,cv2.ROTATE_90_COUNTERCLOCKWISE),270,False)]


def read_digit_line(result):
    """Join two separate digit detections only when they form one aligned line."""
    import numpy as np
    texts=list(result.txts) if result.txts is not None else []
    scores=list(result.scores) if result.scores is not None else []
    boxes=np.asarray(result.boxes) if result.boxes is not None else None
    if len(texts)==1 and len(scores)==1:
        return texts[0].strip(),float(scores[0]),boxes[0] if boxes is not None else None
    if len(texts)==2 and len(scores)==2 and boxes is not None and all(re.fullmatch('[0-9]',t.strip()) for t in texts):
        order=np.argsort(boxes[:,:,0].mean(axis=1))
        bounds=[(box[:,0].min(),box[:,1].min(),box[:,0].max(),box[:,1].max()) for box in boxes]
        a,b=[bounds[i] for i in order]
        heights=[v[3]-v[1] for v in [a,b]]
        overlap=max(0,min(a[3],b[3])-max(a[1],b[1]))
        if min(heights)>0 and overlap/min(heights)>.6 and max(heights)/min(heights)<1.7 and b[0]-a[2]<max(heights):
            return ''.join(texts[i].strip() for i in order),min(float(s) for s in scores),boxes.reshape(-1,2)
    return None,None,None


class DigitsOCR:
    def __init__(self, model_dir, config):
        from rapidocr import RapidOCR
        model_dir = Path(model_dir)
        names = {'Det.model_path': 'det.onnx', 'Cls.model_path': 'cls.onnx', 'Rec.model_path': 'rec.onnx'}
        paths = {key: str((model_dir/name).resolve()) for key, name in names.items()}
        if any(not Path(p).is_file() for p in paths.values()):
            raise FileNotFoundError('Local RapidOCR models missing; run prepare-assets first')
        params = json.loads((model_dir/'params.json').read_text(encoding='utf-8'))
        from rapidocr.utils.typings import OCRVersion, ModelType
        params = {k: OCRVersion(v) if k.endswith('ocr_version') else ModelType(v) if k.endswith('model_type') else v
                  for k, v in params.items()}
        params.update(paths)
        params['Global.model_root_dir'] = str(model_dir.resolve())
        params['Global.log_level'] = 'error'
        # Verify the recognition alphabet exists locally before RapidOCR can fall back to a download.
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        check = ort.InferenceSession(paths['Rec.model_path'], sess_options=options, providers=['CPUExecutionProvider'])
        if 'character' not in check.get_modelmeta().custom_metadata_map:
            raise ValueError('Recognition ONNX must embed its character dictionary for offline use')
        del check
        self.engine = RapidOCR(params=params)
        self.config = config

    def read(self, image, bbox, label_hint=None):
        import cv2
        import numpy as np
        from .paper import paper_candidates, undo_rotation
        accepted = []
        papers=paper_candidates(image,bbox,label_hint)
        if not papers:
            return NumberRead(reject_reason='a4_number_paper_not_found')
        for paper,inverse,quad in papers:
            for oriented,rotation,verified in paper_orientations(paper):
                # An automatic classifier can invert 99 into 66 even with a visible underline.
                result = self.engine(oriented, use_cls=False)
                text,score,box=read_digit_line(result)
                if text is None:
                    continue
                if not re.fullmatch(r'0[1-9]|[1-9][0-9]', text) or score < self.config['min_confidence']:
                    continue
                if any(digit in '69' for digit in text) and not verified:
                    continue
                # Use OCR polygon for the label bbox, transformed back from orientation.
                box = box if box is not None else np.array([[0,0],[oriented.shape[1],oriented.shape[0]]])
                box=undo_rotation(box,rotation,paper.shape[1],paper.shape[0])
                box=cv2.perspectiveTransform(np.float32(box)[None,:,:],inverse)[0]
                original=original_box([box[:,0].min(),box[:,1].min(),box[:,0].max(),box[:,1].max()],image.shape[1],image.shape[0])
                paper_box=original_box([quad[:,0].min(),quad[:,1].min(),quad[:,0].max(),quad[:,1].max()],image.shape[1],image.shape[0])
                accepted.append(NumberRead(text,int(text),score,original,paper_bbox=paper_box,orientation_verified=verified))
            # The learned paper proposal is tried first. Once its orientations agree at high
            # confidence, avoid repeatedly OCR-ing the object's other white surfaces.
            if label_hint is not None and accepted:
                best=max(accepted,key=lambda r:r.confidence)
                if best.confidence>=.95 and not any(r.number!=best.number and best.confidence-r.confidence<.03 for r in accepted):
                    return best
        if not accepted:
            return NumberRead(reject_reason='no_confident_two_digit_label')
        best=max(accepted,key=lambda r:r.confidence)
        if any(r.number!=best.number and best.confidence-r.confidence<.03 for r in accepted):
            return NumberRead(reject_reason='conflicting_label_or_orientation')
        return best

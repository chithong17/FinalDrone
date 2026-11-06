"""One-frame gate checks for the selected detector; no API submissions."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import cv2
    from src.cli import read_config
    from src.vision import Detector,DigitsOCR
    cfg=read_config(ROOT/'configs/trained.json')
    detector=Detector(cfg)
    ocr=DigitsOCR(ROOT/'models/ocr',cfg['ocr'])
    samples=json.loads((ROOT/'data/object-seeds.json').read_text())['samples']
    results=[]
    for sample in samples:
        path=ROOT/'fpt_map/object'/sample['file']
        image=cv2.imread(str(path))
        observations=[]
        for detection in detector.detect(image):
            read=ocr.read(image,detection.bbox,label_hint=detection.label_bbox)
            recognized=(read.number is not None and read.paper_bbox is not None and
                        (not any(c in '69' for c in (read.text or '')) or read.orientation_verified))
            observations.append(dict(detection=asdict(detection),ocr=asdict(read),target_recognized=recognized))
        accepted=[o for o in observations if o['target_recognized']]
        if sample['file']=='chair_gray_number_21.jpg':
            passed=(len(accepted)==1 and accepted[0]['ocr']['number']==21 and accepted[0]['detection']['object_type']=='chair_gray')
        else:
            passed=not accepted
        results.append(dict(file=sample['file'],passed=passed,accepted=accepted,proposals=len(observations),observations=observations))
        print(sample['file'],'accepted',[(o['detection']['object_type'],o['ocr']['number']) for o in accepted],passed,flush=True)
    report=dict(note='Known development/training object fixtures, not independent field holdout. Single-frame recognition gate only; does not bypass location/consensus or submit API.',samples=results)
    (ROOT/'evaluation/trained-target-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()

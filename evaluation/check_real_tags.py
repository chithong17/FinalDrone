"""Regression checks on user-provided real tag fixtures, not a blind accuracy set."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import cv2
    from src.cli import read_config
    from src.vision import DigitsOCR
    engine=DigitsOCR(ROOT/'models/ocr',read_config(ROOT/'configs/offline.json')['ocr'])
    cases=[]
    for name,expected in [('number_62.jpg',62),('number_99.jpg',99),('chair_gray_number_21.jpg',21)]:
        image=cv2.imread(str(ROOT/'fpt_map/object'/name))
        for angle,code in [(0,None),(90,cv2.ROTATE_90_CLOCKWISE),(180,cv2.ROTATE_180),(270,cv2.ROTATE_90_COUNTERCLOCKWISE)]:
            im=image if code is None else cv2.rotate(image,code)
            result=engine.read(im,[0,0,im.shape[1],im.shape[0]])
            cases.append(dict(file=name,rotation=angle,expected=expected,passed=result.number==expected,result=asdict(result)))
            print(name,angle,result.number,'OK' if result.number==expected else 'FAIL',flush=True)
    for name in ['chair_gray_1.JPG','chair_white_1.JPG','fire_extinguisher_1.JPG','fire_extinguisher_3.JPG']:
        im=cv2.imread(str(ROOT/'fpt_map/object'/name))
        result=engine.read(im,[0,0,im.shape[1],im.shape[0]])
        cases.append(dict(file=name,expected=None,passed=result.number is None,result=asdict(result)))
        print(name,result.number,'OK' if result.number is None else 'FAIL',flush=True)
    out=ROOT/'evaluation/real-tag-regression.json'
    out.write_text(json.dumps(dict(note='Development regression fixtures; not independent field accuracy.',cases=cases),indent=2),encoding='utf-8')
    if not all(c['passed'] for c in cases):
        raise SystemExit('Some tag regressions failed; inspect saved report')


if __name__=='__main__':
    main()

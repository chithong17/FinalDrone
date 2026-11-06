"""Reproducible, source-separated detector data with explicitly synthetic A4 tags."""
import argparse
import hashlib
import json
from pathlib import Path
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

CLASSES=['chair_orange','chair_white','chair_gray','backpack','fire_extinguisher','number_label']
ROOT=Path(__file__).resolve().parents[1]


def make_paper(number, width=210, height=297):
    paper=Image.new('RGB',(width,height),'white')
    draw=ImageDraw.Draw(paper)
    font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',round(width*.55))
    text=f'{number:02d}'
    box=draw.textbbox((0,0),text,font=font)
    x=(width-(box[2]-box[0]))/2-box[0]
    y=height*.42-box[1]
    draw.text((x,y),text,fill='#151515',font=font)
    # Underline each 6/9, matching partial-underlines such as 62 and 99.
    for i,digit in enumerate(text):
        if digit in '69':
            left=x+draw.textlength(text[:i],font=font)
            right=x+draw.textlength(text[:i+1],font=font)
            baseline=y+box[3]+width*.06
            draw.line((left,baseline,right,baseline),fill='#151515',width=max(2,round(width*.035)))
    return cv2.cvtColor(np.array(paper),cv2.COLOR_RGB2BGR)


def paste_paper(image, bbox, rng):
    height,width=image.shape[:2]
    x1,y1,x2,y2=bbox
    bw,bh=x2-x1,y2-y1
    pw=min(bw*rng.uniform(.45,.7),bh*.55/1.414)
    ph=pw*1.414
    if pw<12:
        return None
    cx=(x1+x2)/2+rng.uniform(-.08,.08)*bw
    cy=(y1+y2)/2+rng.uniform(-.08,.08)*bh
    angle=rng.uniform(-30,30)
    rect=((cx,cy),(pw,ph),angle)
    quad=cv2.boxPoints(rect).astype(np.float32)
    quad[:,0]=np.clip(quad[:,0],0,width-1)
    quad[:,1]=np.clip(quad[:,1],0,height-1)
    number=rng.randint(1,99)
    paper=make_paper(number)
    source=np.float32([[0,0],[209,0],[209,296],[0,296]])
    # boxPoints order is cyclic; choose top-left and keep winding.
    center=quad.mean(axis=0)
    quad=quad[np.argsort(np.arctan2(quad[:,1]-center[1],quad[:,0]-center[0]))]
    quad=np.roll(quad,-np.argmin(quad.sum(axis=1)),axis=0)
    transform=cv2.getPerspectiveTransform(source,quad)
    overlay=cv2.warpPerspective(paper,transform,(width,height))
    mask=cv2.warpPerspective(np.full(paper.shape[:2],255,np.uint8),transform,(width,height))
    image[mask>128]=overlay[mask>128]
    return dict(class_name='number_label',bbox=[float(quad[:,0].min()),float(quad[:,1].min()),
                float(quad[:,0].max()),float(quad[:,1].max())],number=number,synthetic=True)


def normalized_objects(objects,width,height):
    return [dict(class_name=obj['class'],bbox=[obj['bbox'][0]*width,obj['bbox'][1]*height,
                 obj['bbox'][2]*width,obj['bbox'][3]*height]) for obj in objects]


def write_sample(output,name,image,objects,split,provenance,records):
    h,w=image.shape[:2]
    image_path=output/'images'/split/(name+'.jpg')
    label_path=output/'labels'/split/(name+'.txt')
    image_path.parent.mkdir(parents=True,exist_ok=True)
    label_path.parent.mkdir(parents=True,exist_ok=True)
    cv2.imwrite(str(image_path),image,[cv2.IMWRITE_JPEG_QUALITY,92])
    lines=[]
    clean=[]
    for obj in objects:
        x1,y1,x2,y2=map(float,obj['bbox'])
        x1,y1=max(0,x1),max(0,y1)
        x2,y2=min(w,x2),min(h,y2)
        if x2-x1<2 or y2-y1<2:
            continue
        lines.append(f"{CLASSES.index(obj['class_name'])} {(x1+x2)/2/w:.7f} {(y1+y2)/2/h:.7f} {(x2-x1)/w:.7f} {(y2-y1)/h:.7f}")
        clean.append(dict(obj,bbox=[x1,y1,x2,y2]))
    label_path.write_text('\n'.join(lines),encoding='utf-8')
    records.append(dict(image=str(image_path.relative_to(output)),split=split,objects=clean,**provenance,
                        sha256=hashlib.sha256(image_path.read_bytes()).hexdigest()))


def build(output,coco_manifest,seed=20261106,variants=12,extra_side_views=False,real_a4_train=False,extra_coco=None):
    output=Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Training output must be new')
    rng=random.Random(seed)
    seeds=json.loads((ROOT/'data/object-seeds.json').read_text(encoding='utf-8'))
    if extra_side_views:
        # v2 adds previously held-out side poses to train, then uses a NEW balcony scene for dev.
        # v1 scores are not compared to v2 scores directly; both models must use common v2 dev.
        for sample in seeds['samples']:
            if sample['file'] in {'chair_gray_3.JPG','chair_white_2.JPG'}:
                sample['split']='train'
        seeds['samples'].append(dict(file='../IMG_1210.JPG',split='dev',group='balcony-IMG1210',objects=[
            {'class':'chair_white','bbox':[.252,.208,.380,.303]},
            {'class':'chair_gray','bbox':[.285,.285,.406,.403]},
            {'class':'chair_gray','bbox':[.332,.392,.461,.508]},
            {'class':'chair_white','bbox':[.343,.515,.477,.633]}]))
    if real_a4_train:
        for sample in seeds['samples']:
            if sample['file']=='chair_gray_number_21.jpg':
                sample['split']='train'
                sample['objects'][0]['polygon']=[[.210,.470],[.330,.230],[.650,.201],[.844,.387],[.729,.630],[.394,.675]]
    records=[]
    # Floor-only crop visually inspected from f1_d1_m; no targets are pasted from holdout.
    with Image.open(ROOT/'fpt_map/floor1/f1_d1_m.JPG') as raw:
        floor=np.array(ImageOps.exif_transpose(raw).convert('RGB'))
    floor=cv2.cvtColor(floor[int(floor.shape[0]*.72):],cv2.COLOR_RGB2BGR)
    for sample in seeds['samples']:
        with Image.open(ROOT/'fpt_map/object'/sample['file']) as raw:
            image=cv2.cvtColor(np.array(ImageOps.exif_transpose(raw).convert('RGB')),cv2.COLOR_RGB2BGR)
        scale=min(1,960/max(image.shape[:2]))
        image=cv2.resize(image,None,fx=scale,fy=scale)
        h,w=image.shape[:2]
        objects=normalized_objects(sample['objects'],w,h)
        paper_quad=None
        if any(a.get('paper_quad') for a in sample['objects']):
            # Actual A4 tag location is known; no other split uses this photo.
            for obj,annotation in zip(objects,sample['objects']):
                if annotation.get('paper_quad'):
                    quad=np.array(annotation['paper_quad'])*[w,h]
                    paper_quad=quad.astype(np.float32)
                    objects.append(dict(class_name='number_label',bbox=[quad[:,0].min(),quad[:,1].min(),quad[:,0].max(),quad[:,1].max()],number=annotation.get('number'),synthetic=False))
                    break
        provenance=dict(source=sample['file'],source_group=sample['group'],origin='local_real',synthetic=False)
        write_sample(output,Path(sample['file']).stem,image,objects,sample['split'],provenance,records)
        if sample['split']=='holdout':
            continue
        repeats=variants*2 if real_a4_train and paper_quad is not None else variants if sample['split']=='train' else 3
        for index in range(repeats):
            composite=image.copy()
            new_objects=[dict(o) for o in objects]
            current_paper=paper_quad
            has_number=index%4!=0
            if real_a4_train and paper_quad is not None:
                current_number=rng.randint(1,99) if has_number else None
                paper=make_paper(current_number) if has_number else np.full((297,210,3),255,np.uint8)
                rotation=rng.choice([None,cv2.ROTATE_90_CLOCKWISE,cv2.ROTATE_180,cv2.ROTATE_90_COUNTERCLOCKWISE])
                if rotation is not None:
                    paper=cv2.rotate(paper,rotation)
                ph,pw=paper.shape[:2]
                transform=cv2.getPerspectiveTransform(np.float32([[0,0],[pw,0],[pw,ph],[0,ph]]),paper_quad)
                projected=cv2.warpPerspective(paper,transform,(w,h))
                alpha=cv2.warpPerspective(np.full((ph,pw),255,np.uint8),transform,(w,h))
                composite[alpha>128]=projected[alpha>128]
                new_objects=[o for o in new_objects if o['class_name']!='number_label']
                if has_number:
                    new_objects.append(dict(class_name='number_label',bbox=[paper_quad[:,0].min(),paper_quad[:,1].min(),paper_quad[:,0].max(),paper_quad[:,1].max()],number=current_number,synthetic=True))
            # Alternate original photos with cutout composites for scale/background diversity.
            if index%2 and sample['objects'][0].get('polygon'):
                mask=np.zeros((h,w),np.uint8)
                polygon=(np.array(sample['objects'][0]['polygon'])*[w,h]).astype(np.int32)
                cv2.fillPoly(mask,[polygon],255)
                x,y,bw,bh=cv2.boundingRect(polygon)
                cutout=composite[y:y+bh,x:x+bw].copy()
                alpha=mask[y:y+bh,x:x+bw]
                composite=cv2.resize(floor,(640,640))
                target_long=rng.randint(100,440)
                resize=target_long/max(bw,bh)
                cw,ch=max(2,round(bw*resize)),max(2,round(bh*resize))
                cutout=cv2.resize(cutout,(cw,ch))
                alpha=cv2.resize(alpha,(cw,ch))
                px,py=rng.randint(0,640-cw),rng.randint(0,640-ch)
                roi=composite[py:py+ch,px:px+cw]
                roi[alpha>128]=cutout[alpha>128]
                new_objects=[dict(class_name=objects[0]['class_name'],bbox=[px,py,px+cw,py+ch])]
                if current_paper is not None and has_number:
                    transformed=(current_paper-np.float32([x,y]))*np.float32([cw/bw,ch/bh])+np.float32([px,py])
                    new_objects.append(dict(class_name='number_label',bbox=[float(transformed[:,0].min()),float(transformed[:,1].min()),float(transformed[:,0].max()),float(transformed[:,1].max())],number=current_number if real_a4_train else None,synthetic=True))
            # Train shape on some unnumbered objects too; final target gate rejects those.
            if index%4!=0 and paper_quad is None:
                for obj in list(new_objects):
                    tag=paste_paper(composite,obj['bbox'],rng)
                    if tag:
                        new_objects.append(tag)
            write_sample(output,Path(sample['file']).stem+f'-synth-{index:03}',composite,new_objects,sample['split'],
                dict(provenance,origin='synthetic_A4_or_composite',synthetic=True),records)
    coco=json.loads(Path(coco_manifest).read_text(encoding='utf-8'))
    if extra_coco:
        if real_a4_train:
            # The old holdout has been inspected. It becomes dev; new unseen fine-tune photos provide holdout.
            for sample in coco['samples']:
                if sample['split']=='holdout':
                    sample['split']='dev'
        coco['samples']+=json.loads(Path(extra_coco).read_text(encoding='utf-8'))['samples']
    for sample in coco['samples']:
        image=cv2.imread(sample['file'])
        h,w=image.shape[:2]
        objects=normalized_objects(sample['objects'],w,h)
        provenance=dict(source=sample['source_url'],source_group=sample['group'],origin='COCO2017',synthetic=False,
                        license=sample['license'])
        name='coco-'+str(sample['coco_image_id'])
        write_sample(output,name,image,objects,sample['split'],provenance,records)
        if sample['split']!='holdout':
            composite=image.copy()
            new_objects=[dict(o) for o in objects]
            for obj in objects:
                tag=paste_paper(composite,obj['bbox'],rng)
                if tag:
                    new_objects.append(tag)
            write_sample(output,name+'-A4',composite,new_objects,sample['split'],dict(provenance,synthetic=True),records)
    manifest=dict(seed=seed,classes=CLASSES,note='Synthetic A4/composites explicitly marked; splits are source-photo separated, not independent field validation.',samples=records)
    (output/'provenance.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    # Ultralytics expects train/val keys; dev remains the folder name.
    (output/'dataset.yaml').write_text(json.dumps(dict(path=str(output.resolve()),train='images/train',val='images/dev',test='images/holdout',names=CLASSES),indent=2),encoding='utf-8')
    print('Built',len(records),'images:',{s:sum(r['split']==s for r in records) for s in ['train','dev','holdout']})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='artifacts/training-v1')
    parser.add_argument('--coco-manifest',default='artifacts/coco-backpacks/manifest.json')
    parser.add_argument('--variants',type=int,default=12)
    parser.add_argument('--extra-side-views',action='store_true')
    parser.add_argument('--real-a4-train',action='store_true')
    parser.add_argument('--extra-coco')
    args=parser.parse_args()
    build(args.output,args.coco_manifest,variants=args.variants,extra_side_views=args.extra_side_views,
          real_a4_train=args.real_a4_train,extra_coco=args.extra_coco)

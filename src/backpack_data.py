"""Download only a bounded, annotated backpack subset from official COCO 2017 val."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import random
import urllib.request
import zipfile


def download_backpacks(archive, output, count=120, subset='val2017'):
    output = Path(output)
    (output/'images').mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    with zipfile.ZipFile(archive) as z:
        member='annotations/instances_'+subset+'.json'
        if subset=='train2017':
            import ijson
            with z.open(member) as stream:
                categories=list(ijson.items(stream,'categories.item',use_float=True))
            category=next(c['id'] for c in categories if c['name']=='backpack')
            with z.open(member) as stream:
                for item in ijson.items(stream,'annotations.item',use_float=True):
                    if item['category_id']==category:
                        grouped[item['image_id']].append({k:item[k] for k in ['bbox','image_id','id','area','iscrowd']})
            with z.open(member) as stream:
                images=[im for im in ijson.items(stream,'images.item',use_float=True) if im['id'] in grouped]
            with z.open(member) as stream:
                license_rows=list(ijson.items(stream,'licenses.item',use_float=True))
        else:
            annotations = json.loads(z.read(member))
            category = next(c['id'] for c in annotations['categories'] if c['name']=='backpack')
            for item in annotations['annotations']:
                if item['category_id']==category:
                    grouped[item['image_id']].append(item)
            images,license_rows=annotations['images'],annotations['licenses']
    available = [im for im in images if im['id'] in grouped and
                 any(a['area'] >= im['width']*im['height']*.015 and not a['iscrowd'] for a in grouped[im['id']])]
    random.Random(20261106).shuffle(available)
    selected = available[:count]
    count = len(selected)
    licenses = {x['id']:x for x in license_rows}

    def fetch(pair):
        i, im = pair
        destination = output/'images'/im['file_name']
        url = 'http://images.cocodataset.org/'+subset+'/'+im['file_name']
        if not destination.exists():
            last = None
            for _ in range(3):
                try:
                    with urllib.request.urlopen(url,timeout=45) as response:
                        raw = response.read()
                    destination.write_bytes(raw)
                    break
                except Exception as error:
                    last=error
            else:
                raise last
        # COCO bboxes include all backpacks in the selected image, not just the largest.
        boxes = []
        for a in grouped[im['id']]:
            if a['iscrowd']:
                continue
            x,y,w,h = a['bbox']
            boxes.append({'class':'backpack','bbox':[x/im['width'],y/im['height'],(x+w)/im['width'],(y+h)/im['height']],
                          'annotation_id':a['id']})
        train_fraction,dev_end=(.8,.9) if subset=='train2017' else (.67,.84)
        return dict(file=destination.as_posix(), split='train' if i<int(count*train_fraction) else 'dev' if i<int(count*dev_end) else 'holdout',
            group=f'coco-{subset}-{im["id"]}',objects=boxes, source_url=url,coco_image_id=im['id'],
            license=licenses[im['license']],flickr_url=im.get('flickr_url'),
            sha256=hashlib.sha256(destination.read_bytes()).hexdigest())

    result=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(fetch,p) for p in enumerate(selected)]
        for future in as_completed(futures):
            result.append(future.result())
            if len(result)%20==0:
                print('Backpack images downloaded:',len(result),flush=True)
    result.sort(key=lambda r:r['coco_image_id'])
    manifest=dict(dataset='COCO '+subset+' backpack subset',seed=20261106,
        source='https://cocodataset.org/#download',terms='https://cocodataset.org/#termsofuse',
        note='Annotations supplied by COCO; image licenses vary and are retained per image. No competition number labels in these photos.',
        samples=result)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return len(result)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',required=True)
    parser.add_argument('--output',default='artifacts/coco-backpacks')
    parser.add_argument('--count',type=int,default=120)
    parser.add_argument('--subset',choices=['val2017','train2017'],default='val2017')
    args=parser.parse_args()
    print(download_backpacks(args.archive,args.output,args.count,args.subset))

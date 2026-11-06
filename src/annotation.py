"""Small desktop annotation tool. Mouse-drag boxes; metadata entered in terminal."""
import json
from pathlib import Path


def annotate(manifest_path):
    import cv2
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    print('Draw bbox with mouse. ENTER/SPACE accepts, C cancels. Terminal prompts for labels.')
    print('Object type: chair_orange/chair_white/chair_gray/backpack/fire_extinguisher/decoy')
    try:
        for sample in manifest['samples']:
            if sample['annotation_status'] == 'reviewed':
                continue
            image = cv2.imread(str(path.parent/sample['image']))
            if image is None:
                raise ValueError(f"Missing image: {sample['image']}")
            scale = min(1.0, 1200/image.shape[1], 800/image.shape[0])
            preview = cv2.resize(image, None, fx=scale, fy=scale)
            objects = []
            print('\nSample:', sample['sample_id'])
            while True:
                command = input('[a] add object, [s] save reviewed (empty allowed), [n] skip, [q] quit: ').strip().lower()
                if command == 'q':
                    return
                if command == 'n':
                    break
                if command == 's':
                    sample['objects'] = objects
                    sample['annotation_status'] = 'reviewed'
                    # Replace a complete file, never leave a partial annotation document.
                    temp = path.with_suffix('.tmp')
                    temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
                    temp.replace(path)
                    break
                if command != 'a':
                    continue
                x, y, w, h = cv2.selectROI('Object bbox', preview, showCrosshair=True)
                cv2.destroyWindow('Object bbox')
                if not w or not h:
                    continue
                bbox = [round(x/scale), round(y/scale), min(image.shape[1], round((x+w)/scale)), min(image.shape[0], round((y+h)/scale))]
                kind = input('object_type (or decoy): ').strip()
                if kind not in {'chair_orange', 'chair_white', 'chair_gray', 'backpack', 'fire_extinguisher', 'decoy'}:
                    print('Invalid class, object not saved')
                    continue
                presence = input('Number label present? [y] yes, [n] absent, [?] unknown: ').strip().lower()
                if presence not in {'y', 'n', '?'}:
                    print('Invalid label presence, object not saved')
                    continue
                number_text = input('Two-digit number, blank if unreadable: ').strip() if presence == 'y' else ''
                if number_text and (len(number_text) != 2 or not number_text.isascii() or not number_text.isdigit() or not 1 <= int(number_text) <= 99):
                    print('Invalid two-digit number, object not saved')
                    continue
                label_box = None
                if number_text:
                    a, b, c, d = cv2.selectROI('Number label bbox', preview, showCrosshair=True)
                    cv2.destroyWindow('Number label bbox')
                    if c and d:
                        label_box = [round(a/scale), round(b/scale), min(image.shape[1], round((a+c)/scale)), min(image.shape[0], round((b+d)/scale))]
                floor = input('Known floor 1-5, blank if unknown: ').strip()
                direction = input('Known NORTH/EAST/SOUTH/WEST, blank if unknown: ').strip().upper()
                if (floor and floor not in {'1', '2', '3', '4', '5'}) or (direction and direction not in {'NORTH', 'EAST', 'SOUTH', 'WEST'}):
                    print('Invalid location, object not saved')
                    continue
                object_id = input('Physical object ID, blank if unknown: ').strip() or None
                objects.append(dict(bbox=bbox, object_type=kind, number=int(number_text) if number_text else None,
                    label_bbox=label_box, floor=int(floor) if floor else None, direction=direction or None,
                    physical_id=object_id, has_number_label={'y':True,'n':False,'?':None}[presence],
                    decoy=(kind == 'decoy' or presence == 'n')))
                cv2.rectangle(preview, (x, y), (x+w, y+h), (0, 255, 0), 2)
    finally:
        cv2.destroyAllWindows()

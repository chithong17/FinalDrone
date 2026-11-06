import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from src.dataset import build_dataset
from src.training import export_yolo


class DataTests(unittest.TestCase):
    def test_existing_manifest_is_rejected_before_touching_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'manifest.json').write_text('original annotation')
            with self.assertRaises(FileExistsError):
                build_dataset('missing-video',path)
            self.assertEqual((path/'manifest.json').read_text(),'original annotation')
            self.assertFalse((path/'images').exists())

    def test_export_yolo_normalizes_coordinates_and_preserves_class_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            Image.new('RGB',(100,200),'gray').save(path/'sample.jpg')
            samples = [dict(sample_id=split,image='sample.jpg',source_group=split,split=split,
                annotation_status='reviewed',objects=[dict(object_type='chair_white',bbox=[10,20,50,100])])
                       for split in ['train','dev']]
            (path/'manifest.json').write_text(json.dumps({'samples':samples}))
            output = export_yolo(path/'manifest.json',path/'export')
            self.assertTrue(output.is_file())
            row = (path/'export/labels/train/train.txt').read_text().split()
            self.assertEqual(int(row[0]),1)
            self.assertEqual([float(v) for v in row[1:]],[.3,.3,.4,.4])

    def test_export_rejects_source_group_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            samples = [dict(sample_id=split,image='missing.jpg',source_group='same-flight',split=split,
                            annotation_status='reviewed',objects=[]) for split in ['train','dev']]
            (path/'manifest.json').write_text(json.dumps({'samples':samples}))
            with self.assertRaisesRegex(ValueError,'leakage'):
                export_yolo(path/'manifest.json',path/'export')


if __name__ == '__main__':
    unittest.main()

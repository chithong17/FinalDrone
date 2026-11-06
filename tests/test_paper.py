from types import SimpleNamespace
import unittest

import cv2
import numpy as np

from src.paper import paper_candidates, undo_rotation
from src.vision import _underline_signal, read_digit_line


class PaperTests(unittest.TestCase):
    def test_split_digits_join_only_on_same_line(self):
        boxes=np.float32([[[10,10],[30,10],[30,50],[10,50]],[[35,10],[55,10],[55,50],[35,50]]])
        result=SimpleNamespace(txts=['9','9'],scores=[.99,.95],boxes=boxes)
        text,score,_=read_digit_line(result)
        self.assertEqual(text,'99')
        self.assertEqual(score,.95)
        result.boxes[1,:,1]+=80
        self.assertIsNone(read_digit_line(result)[0])

    def test_coordinate_mapping_after_90_degree_rotation(self):
        restored=undo_rotation(np.float32([[40,10],[30,20]]),90,100,50)
        np.testing.assert_allclose(restored,[[10,10],[20,20]])

    def test_dark_object_without_paper_has_no_proposal(self):
        image=np.full((200,200,3),40,dtype=np.uint8)
        self.assertEqual(paper_candidates(image,[0,0,200,200]),[])

    def test_paper_edge_far_from_digits_is_not_an_underline(self):
        image=np.full((400,300,3),255,dtype=np.uint8)
        cv2.putText(image,'99',(65,220),cv2.FONT_HERSHEY_SIMPLEX,2,(0,0,0),4)
        cv2.line(image,(10,20),(290,20),(0,0,0),5)
        self.assertIsNone(_underline_signal(image))


if __name__=='__main__':
    unittest.main()

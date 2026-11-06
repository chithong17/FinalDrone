"""Find white A4-like quadrilaterals and keep coordinate transforms for OCR."""
import cv2
import numpy as np


def sort_quad(points):
    points=np.asarray(points,dtype=np.float32)
    center=points.mean(axis=0)
    points=points[np.argsort(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))]
    return np.roll(points,-np.argmin(points.sum(axis=1)),axis=0)


def paper_candidates(image,bbox,hint=None):
    x1,y1,x2,y2=bbox
    crop=image[y1:y2,x1:x2]
    if crop.size==0:
        return []
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    quads=[]
    # Whole-crop fallback is permitted only for a predominantly white/neutral paper-like surface.
    white=cv2.inRange(hsv,np.array([0,0,125]),np.array([179,90,255]))
    if np.count_nonzero(white)/white.size>.7:
        quads.append(np.float32([[x1,y1],[x2,y1],[x2,y2],[x1,y2]]))
    for value in [210,190,165,230]:
        mask=cv2.inRange(hsv,np.array([0,0,value]),np.array([179,80,255]))
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours,key=cv2.contourArea,reverse=True):
            area=cv2.contourArea(contour)
            if area<max(200,crop.shape[0]*crop.shape[1]*.003):
                continue
            approx=cv2.approxPolyDP(contour,cv2.arcLength(contour,True)*.025,True)
            if len(approx)!=4 or not cv2.isContourConvex(approx):
                continue
            quad=sort_quad(approx[:,0,:])+np.array([x1,y1],dtype=np.float32)
            if not any(np.max(np.abs(quad-other))<min(crop.shape[:2])*.03 for other in quads):
                quads.append(quad)
    if hint is not None:
        a,b,c,d=hint
        # Learned proposal is an additional candidate, not a substitute for the ink/number checks.
        quads.insert(0,np.float32([[a,b],[c,b],[c,d],[a,d]]))
    candidates=[]
    for quad in quads:
        tl,tr,br,bl=quad
        width=max(np.linalg.norm(tr-tl),np.linalg.norm(br-bl))
        height=max(np.linalg.norm(bl-tl),np.linalg.norm(br-tr))
        if min(width,height)<18 or not .45<=width/max(height,1)<=2.2:
            continue
        # Normalize pixels but preserve portrait/landscape orientation.
        scale=720/max(width,height)
        out_w,out_h=max(20,round(width*scale)),max(20,round(height*scale))
        destination=np.float32([[0,0],[out_w,0],[out_w,out_h],[0,out_h]])
        transform=cv2.getPerspectiveTransform(quad,destination)
        warped=cv2.warpPerspective(image,transform,(out_w,out_h),borderValue=(255,255,255))
        gray=cv2.cvtColor(warped,cv2.COLOR_BGR2GRAY)
        _,ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
        foreground=np.count_nonzero(ink)/ink.size
        if not .002<=foreground<=.4:
            continue
        count,_,stats,_=cv2.connectedComponentsWithStats(ink)
        # Reject paragraphs/manufacturer tables; a 2-digit tag has few large ink components.
        significant=sum(h>=out_h*.045 and area>=max(15,out_w*out_h*.0003)
                        for x,y,w,h,area in stats[1:])
        if significant>8:
            continue
        candidates.append((warped,np.linalg.inv(transform),quad))
        if len(candidates)>=5:
            break
    return candidates


def undo_rotation(points,rotation,width,height):
    points=np.asarray(points,dtype=float).copy()
    x,y=points[:,0].copy(),points[:,1].copy()
    if rotation==90:
        points[:,0],points[:,1]=y,height-x
    elif rotation==180:
        points[:,0],points[:,1]=width-x,height-y
    elif rotation==270:
        points[:,0],points[:,1]=width-y,x
    return points

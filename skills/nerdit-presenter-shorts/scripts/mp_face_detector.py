"""Drop-in FaceDetector for LatentSync using MediaPipe Face Mesh (Apache-2.0) instead of
InsightFace, whose pretrained models are non-commercial.

LatentSync reads only three points from the 106-point array: the two eyebrow centres
(indices 43,48,49,50,51 and 101..105) and the nose centre (74,77,83,86), plus the bbox.
This fills exactly those slots from Face Mesh landmarks; the other slots stay at the nose.
"""
import mediapipe as mp
import numpy as np

# Face Mesh indices: eyebrows on the image left and right, and the nose bridge/tip
BROW_A = [70, 63, 105, 66, 107]
BROW_B = [300, 293, 334, 296, 336]
NOSE = [1, 4, 5, 195]


class FaceDetector:
    def __init__(self, device="cuda"):
        self.mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1,
                                                    refine_landmarks=False, min_detection_confidence=0.5)

    def __call__(self, frame, threshold=0.5):
        h, w, _ = frame.shape
        res = self.mesh.process(frame)   # LatentSync passes RGB frames
        if not res.multi_face_landmarks:
            return None, None
        pts = np.array([(p.x * w, p.y * h) for p in res.multi_face_landmarks[0].landmark])
        a, b, nose = pts[BROW_A].mean(0), pts[BROW_B].mean(0), pts[NOSE].mean(0)
        left, right = (a, b) if a[0] < b[0] else (b, a)
        lmk = np.tile(nose, (106, 1))
        lmk[[43, 48, 49, 50, 51]] = left
        lmk[101:106] = right
        lmk[[74, 77, 83, 86]] = nose
        x1, y1 = pts.min(0)
        x2, y2 = pts.max(0)
        bbox = (max(0, int(x1)), max(0, int(y1)), min(w, int(x2)), min(h, int(y2)))
        return bbox, np.round(lmk).astype(np.int_)

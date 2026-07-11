import uuid
import numpy as np
import cv2
import torch
import torchreid

import config
from detector import PersonDetector


class ReIDChecker:
    # Re-identifies a person crop against known visitors stored in LocalDB.
    # Uses OSNet-x0.25 embeddings + cosine similarity to decide new vs. repeat.

    def __init__(self, local_db):
        self.local_db = local_db
        self.threshold = config.REID_THRESHOLD
        self.extractor = torchreid.utils.FeatureExtractor(
            model_name="osnet_x0_25",
            device="cpu",
        )
        self._detector = PersonDetector()

    def normalize_crop(self, crop):
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=config.CLAHE_CLIP_LIMIT, tileGridSize=config.CLAHE_TILE)
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def get_embedding(self, crop):
        h, w = crop.shape[:2]
        if not self._detector.is_good_crop([0, 0, w, h]):
            return None

        crop = self.normalize_crop(crop)
        crop = cv2.resize(crop, (config.EMBED_CROP_W, config.EMBED_CROP_H))

        # torchreid expects a list of numpy arrays in RGB, uint8
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        features = self.extractor([crop_rgb])  # returns tensor (1, D)
        return features[0].cpu().numpy()

    def check(self, crop, track_id):
        embedding = self.get_embedding(crop)
        if embedding is None:
            return None

        visitor_id, similarity = self.local_db.find_similar(embedding, self.threshold)

        if visitor_id is not None:
            return {
                "status": "repeat",
                "visitor_id": visitor_id,
                "similarity": similarity,
            }

        visitor_id = str(uuid.uuid4())
        self.local_db.save_embedding(visitor_id, embedding)
        return {
            "status": "new",
            "visitor_id": visitor_id,
            "similarity": 0.0,
        }

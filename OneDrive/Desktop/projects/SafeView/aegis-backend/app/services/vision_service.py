"""YOLOv8-based vision analysis service for image moderation."""

import cv2
import numpy as np
from ultralytics import YOLO

from app.models.analysis import AnalysisResult, BoundingBox


class VisionService:
    """Loads YOLO once and performs image inference for each request."""

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        # Model is loaded one time at process startup for performance.
        self.model = YOLO(model_path)
        # Business Rule BR-01: Minimum confidence threshold (75%).
        self.min_confidence = 0.75
        # Mapping YOLO labels to SafeView restricted categories (placeholder).
        # Only detections that appear in this mapping are returned.
        self.label_to_category: dict[str, str] = {
            # Violence-related placeholders
            "knife": "Violence",
            "scissors": "Violence",
            "sports ball": "Violence_Placeholder",
            "baseball bat": "Violence_Placeholder",
            "baseball glove": "Violence_Placeholder",
            "skateboard": "Violence_Placeholder",
            "snowboard": "Violence_Placeholder",
            "skis": "Violence_Placeholder",
            "frisbee": "Violence_Placeholder",
            # Firearms-related (if present in custom labels; YOLO COCO may not have 'gun')
            "gun": "Violence",
            "rifle": "Violence",
            "pistol": "Violence",
            "shotgun": "Violence",
            # Nudity placeholder (until custom NSFW model is integrated)
            "person": "Nudity_Placeholder",
        }

    def analyze_image(
        self,
        image_bytes: bytes,
        sensitivity: float = 0.75,
        filter_nudity: bool = True,
        filter_violence: bool = True,
    ) -> list[AnalysisResult]:
        """Run YOLOv8 on image bytes and map detections to AnalysisResult.
        
        Applies user sensitivity (never below BR-01 minimum) and category toggles.
        """
        if not image_bytes:
            return []

        # Decode raw bytes into an OpenCV image.
        np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode image bytes.")

        img_h, img_w = image.shape[:2]
        if img_h == 0 or img_w == 0:
            raise ValueError("Decoded image has invalid dimensions.")

        predictions = self.model(image, verbose=False)
        results: list[AnalysisResult] = []

        # Enforce BR-01 with user override (never below 0.75)
        effective_threshold = max(self.min_confidence, float(sensitivity or 0.0))

        for pred in predictions:
            boxes = pred.boxes
            if boxes is None:
                continue

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                cls_id = int(box.cls[0].item())
                label = pred.names.get(cls_id, str(cls_id))

                # Enforce threshold
                if conf < effective_threshold:
                    continue

                # Only include detections mapped to SafeView categories
                category = self.label_to_category.get(str(label))
                if category is None:
                    continue

                # Respect user toggles
                if category.startswith("Nudity") and not filter_nudity:
                    continue
                if category.startswith("Violence") and not filter_violence:
                    continue

                # Convert to normalized x/y/width/height expected by BoundingBox.
                norm_x = max(0.0, min(1.0, x1 / img_w))
                norm_y = max(0.0, min(1.0, y1 / img_h))
                norm_w = max(1e-6, min(1.0, (x2 - x1) / img_w))
                norm_h = max(1e-6, min(1.0, (y2 - y1) / img_h))

                results.append(
                    AnalysisResult(
                        # Return the SafeView category label instead of raw YOLO label
                        label=str(category),
                        score=max(0.0, min(1.0, conf)),
                        box=BoundingBox(
                            x=norm_x,
                            y=norm_y,
                            width=norm_w,
                            height=norm_h,
                        ),
                    )
                )

        return results

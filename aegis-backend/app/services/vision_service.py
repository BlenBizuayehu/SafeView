"""YOLOv11-based vision analysis service for image moderation."""

import os
import logging

import cv2
import numpy as np
from ultralytics import YOLO

from app.models.analysis import AnalysisResult, BoundingBox

logger = logging.getLogger("aegis")


class VisionService:
    """Loads YOLO once and performs image inference for each request."""
    PERSISTENCE_HINT_FRAMES = 3
    CATEGORY_MAP: dict[str, str] = {
        "nudity": "nudity",
        "skin": "nudity",
        "gun": "violence",
        "knife": "violence",
        "pistol": "violence",
        "kiss": "kissing",
        "affection": "kissing",
        "pride_flag": "thematic",
        "symbol": "thematic",
    }

    def __init__(self, model_path: str = "yolov11n.pt") -> None:
        # Model is loaded one time at process startup for performance.
        resolved_model_path = model_path if os.path.exists(model_path) else "yolov8n.pt"
        self.model = YOLO(resolved_model_path)
        self.default_confidence_threshold = 0.5

    def _normalize_enabled_categories(
        self,
        filter_nudity: bool,
        filter_violence: bool,
        user_preferences: dict[str, object] | None = None,
    ) -> dict[str, bool]:
        normalized = {
            "nudity": bool(filter_nudity),
            "violence": bool(filter_violence),
            "kissing": True,
            "thematic": True,
        }
        if not user_preferences:
            return normalized
        # Expected keys from extension user preferences:
        # nudity, violence, kissing, thematic, sensitivity
        for key in ("nudity", "violence", "kissing", "thematic"):
            if key in user_preferences:
                normalized[key] = bool(user_preferences.get(key))
        return normalized

    def _coerce_sensitivity_level(
        self,
        sensitivity_level: int | float | None,
        sensitivity: float,
        user_preferences: dict[str, object] | None = None,
    ) -> int:
        if user_preferences and user_preferences.get("sensitivity") is not None:
            value = int(float(user_preferences.get("sensitivity")))
            return max(1, min(10, value))
        if sensitivity_level is not None:
            value = int(float(sensitivity_level))
            return max(1, min(10, value))
        # Backward-compatible behavior: if existing sensitivity already in 1..10, treat it as level.
        if 1.0 <= float(sensitivity) <= 10.0:
            return int(round(float(sensitivity)))
        return 5

    def _confidence_threshold_from_level(self, sensitivity_level: int) -> float:
        # Formula requested by product: 0.8 - (level * 0.06)
        return 0.8 - (float(sensitivity_level) * 0.06)

    def analyze_image(
        self,
        image_bytes: bytes,
        sensitivity: float = 0.75,
        sensitivity_level: int | None = None,
        filter_nudity: bool = True,
        filter_violence: bool = True,
        enabled_categories: dict[str, bool] | None = None,
        user_preferences: dict[str, object] | None = None,
    ) -> list[AnalysisResult]:
        """Run YOLO on image bytes and return strict preference-aware results.

        Strict policy:
        - For each detection, map label via CATEGORY_MAP.
        - If mapped category is enabled and confidence > dynamic threshold,
          immediately return a blocking result.
        - If none match strict criteria, return [] (ALLOW).
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

        merged_preferences = dict(user_preferences or {})
        if enabled_categories:
            for key, value in enabled_categories.items():
                key_norm = str(key).strip().lower()
                if key_norm in {"nudity", "violence", "kissing", "thematic"}:
                    merged_preferences[key_norm] = bool(value)

        effective_sensitivity_level = self._coerce_sensitivity_level(
            sensitivity_level=sensitivity_level,
            sensitivity=sensitivity,
            user_preferences=merged_preferences,
        )
        confidence_threshold = self._confidence_threshold_from_level(effective_sensitivity_level)
        category_toggles = self._normalize_enabled_categories(
            filter_nudity=filter_nudity,
            filter_violence=filter_violence,
            user_preferences=merged_preferences,
        )

        for pred in predictions:
            boxes = pred.boxes
            if boxes is None:
                continue

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                cls_id = int(box.cls[0].item())
                label = str(pred.names.get(cls_id, str(cls_id))).lower()

                category = self.CATEGORY_MAP.get(label)
                if category is None:
                    continue

                if not category_toggles.get(category, False):
                    continue
                if conf <= confidence_threshold:
                    continue

                logger.info(f"Blocking due to ENABLED category: {category}")

                norm_x = max(0.0, min(1.0, x1 / img_w))
                norm_y = max(0.0, min(1.0, y1 / img_h))
                norm_w = max(1e-6, min(1.0, (x2 - x1) / img_w))
                norm_h = max(1e-6, min(1.0, (y2 - y1) / img_h))

                return [
                    AnalysisResult(
                        label=category,
                        score=max(0.0, min(1.0, conf)),
                        box=BoundingBox(
                            x=norm_x,
                            y=norm_y,
                            width=norm_w,
                            height=norm_h,
                        ),
                        action_required="blur",
                        persistence_hint=self.PERSISTENCE_HINT_FRAMES,
                    )
                ]

        return []

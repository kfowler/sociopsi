"""Visual perception using OpenCV."""

import cv2
from typing import Optional
import numpy as np

from sociopsi.core.event_bus import EventBus


class VisualPerception:
    """Visual perception subsystem."""

    def __init__(
        self,
        event_bus: EventBus,
        camera_index: int = 0,
    ) -> None:
        """Initialize visual perception.

        Args:
            event_bus: Event bus for publishing perception events
            camera_index: Camera device index
        """
        self.event_bus = event_bus
        self.camera_index = camera_index

        # Initialize OpenCV Haar Cascade face detector
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        self.camera: Optional[cv2.VideoCapture] = None

    def start_camera(self) -> bool:
        """Start camera capture.

        Returns:
            True if camera started successfully
        """
        self.camera = cv2.VideoCapture(self.camera_index)
        return self.camera.isOpened()

    def stop_camera(self) -> None:
        """Stop camera capture."""
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    def read_frame(self) -> Optional[np.ndarray]:
        """Read frame from camera.

        Returns:
            Frame as numpy array or None if failed
        """
        if self.camera is None or not self.camera.isOpened():
            return None

        ret, frame = self.camera.read()
        if not ret:
            return None

        return frame

    def process_frame(self, frame: np.ndarray) -> dict:
        """Process frame for face detection.

        Args:
            frame: Image frame as numpy array

        Returns:
            Dictionary with detection results
        """
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        faces_detected = len(faces)
        if faces_detected > 0:
            # Publish face detection event
            self.event_bus.publish("perception.visual.face_detected", {
                "count": faces_detected,
                "timestamp": cv2.getTickCount() / cv2.getTickFrequency(),
            })

        return {
            "faces_detected": faces_detected,
            "frame_shape": frame.shape,
            "faces": faces.tolist() if faces_detected > 0 else [],
        }

    def draw_detections(self, frame: np.ndarray, faces: list) -> np.ndarray:
        """Draw face detection boxes on frame.

        Args:
            frame: Original frame
            faces: List of face bounding boxes [(x, y, w, h), ...]

        Returns:
            Frame with drawings
        """
        if not faces:
            return frame

        annotated_frame = frame.copy()

        for (x, y, w, h) in faces:
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return annotated_frame

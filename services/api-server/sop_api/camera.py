"""Camera runtime used by the API service without changing SOP state."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from typing import Iterator, Protocol

from .config import Settings


@dataclass(frozen=True)
class CameraView:
    adapter: str
    status: str
    kind: str
    stream_url: str | None
    snapshot_url: str | None


class CameraRuntime(Protocol):
    @property
    def adapter_name(self) -> str: ...

    def start(self) -> None: ...

    def close(self) -> None: ...

    def view(self, station_id: str) -> CameraView: ...

    def snapshot_jpeg(self) -> bytes | None: ...

    def mjpeg(self) -> Iterator[bytes]: ...


class SimulatedCameraRuntime:
    adapter_name = "simulated"

    def start(self) -> None:
        return None

    def close(self) -> None:
        return None

    def view(self, station_id: str) -> CameraView:
        return CameraView(
            adapter=self.adapter_name,
            status="SIMULATED_ONLINE",
            kind="SIMULATED",
            stream_url=None,
            snapshot_url=None,
        )

    def snapshot_jpeg(self) -> bytes | None:
        return None

    def mjpeg(self) -> Iterator[bytes]:
        return iter(())


class UsbOpenCvCameraRuntime:
    adapter_name = "usb-opencv"

    def __init__(self, index: int, width: int, height: int, fps: int) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self._capture = None
        self._cv2 = None
        self._status = "INITIALIZING"
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        self._running = True
        self._open()

    def close(self) -> None:
        self._running = False
        with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None

    def view(self, station_id: str) -> CameraView:
        base = f"/api/v1/cameras/{station_id}"
        return CameraView(
            adapter=self.adapter_name,
            status=self._status,
            kind="USB_MJPEG",
            stream_url=f"{base}/stream.mjpg",
            snapshot_url=f"{base}/snapshot.jpg",
        )

    def snapshot_jpeg(self) -> bytes | None:
        if not self._open():
            return None
        with self._lock:
            if self._capture is None:
                self._status = "UNAVAILABLE"
                return None
            ok, frame = self._capture.read()
        if not ok:
            self._release_unavailable()
            return None
        ok, encoded = self._cv2.imencode(".jpg", frame, [self._cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            self._status = "UNAVAILABLE"
            return None
        self._status = "ONLINE"
        return encoded.tobytes()

    def mjpeg(self) -> Iterator[bytes]:
        interval = 1 / max(self.fps, 1)
        while self._running:
            jpeg = self.snapshot_jpeg()
            if jpeg is not None:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            time.sleep(interval)

    def _open(self) -> bool:
        with self._lock:
            if self._capture is not None and self._capture.isOpened():
                return True
            try:
                import cv2  # Imported lazily so simulated P0 stays dependency-free.
            except ImportError:
                self._status = "UNAVAILABLE"
                return False
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
            capture = cv2.VideoCapture(self.index, backend)
            if not capture.isOpened():
                capture.release()
                self._status = "UNAVAILABLE"
                return False
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.fps)
            self._cv2 = cv2
            self._capture = capture
            self._status = "ONLINE"
            return True

    def _release_unavailable(self) -> None:
        with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._status = "UNAVAILABLE"


def create_camera_runtime(settings: Settings) -> CameraRuntime:
    if settings.camera_mode == "USB":
        return UsbOpenCvCameraRuntime(
            index=settings.camera_index,
            width=settings.camera_width,
            height=settings.camera_height,
            fps=settings.camera_fps,
        )
    return SimulatedCameraRuntime()

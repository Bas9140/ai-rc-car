"""
oak_node.py
ROS2 node voor de Luxonis OAK-D Lite camera.

Pipeline op de Myriad X chip:
  ColorCamera (RGB, 1080p) → ImageManip (resize 640×352)
                                            ↓
  MonoCamera (links + rechts, 400p) → StereoDepth (LRCHECK, SUBPIXEL)
                                            ↓
  YoloSpatialDetectionNetwork (YOLOv8n blob, 640×352)
    – detecties + 3D (X, Y, Z in mm ten opzichte van camera) via ROI

Publicaties:
  /camera/color/image_raw           sensor_msgs/Image           (RGB, 30 Hz)
  /camera/color/camera_info         sensor_msgs/CameraInfo
  /camera/depth/image_rect_raw      sensor_msgs/Image           (mono16, mm)
  /camera/annotated/image_raw       sensor_msgs/Image           (debug overlay)
  /detections                       rc_interfaces/msg/Detection[]
                                    → verpakt als DetectionArray

MOCK MODE (RC_PLATFORM=mock):
  Geen hardware vereist. Publiceert synthetische dummy data zodat
  tracking_node en depth_node getest kunnen worden op de PC.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Header

from rc_interfaces.msg import Detection, DetectionArray

from .model_utils import get_model_path, label_for, is_obstacle, is_person

# ── QoS ────────────────────────────────────────────────────────────────────
_SENSOR_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)
_RELIABLE_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
)

# ── Constanten ──────────────────────────────────────────────────────────────
FRAME_W = 640
FRAME_H = 352
RGB_FPS = 30
DEPTH_FPS = 30
CONFIDENCE_THRESHOLD = 0.45
IOU_THRESHOLD = 0.5
NUM_CLASSES = 80

# YOLOv8n anchor-vrij (de blob bevat de anchors intern)
ANCHORS: list[list[float]] = []
ANCHOR_MASKS: dict[str, list[int]] = {}

# Depth ROI per detectie (fractie van bounding box midden)
DEPTH_LOWER_THRESHOLD = 100    # mm
DEPTH_UPPER_THRESHOLD = 10_000  # mm (10 m)


class OakNode(Node):
    """
    Interfacenode voor de Luxonis OAK-D Lite.

    Parameters (ROS2):
      model_name        str     yolov8n_coco_640x352
      shaves            int     6
      confidence        float   0.45
      frame_id          str     oak_rgb_camera_optical_frame
      publish_annotated bool    True
      mock              bool    False  (auto-detect via RC_PLATFORM)
    """

    def __init__(self) -> None:
        super().__init__("oak_node")

        # ── parameters ──────────────────────────────────────────────────
        self.declare_parameter("model_name",        "yolov8n_coco_640x352")
        self.declare_parameter("shaves",            6)
        self.declare_parameter("confidence",        CONFIDENCE_THRESHOLD)
        self.declare_parameter("frame_id",          "oak_rgb_camera_optical_frame")
        self.declare_parameter("publish_annotated", True)
        self.declare_parameter("mock",              False)

        platform = os.environ.get("RC_PLATFORM", "").lower()
        self._mock: bool = (
            self.get_parameter("mock").value
            or platform == "mock"
        )

        self._model_name: str = self.get_parameter("model_name").value
        self._shaves: int     = self.get_parameter("shaves").value
        self._conf: float     = self.get_parameter("confidence").value
        self._frame_id: str   = self.get_parameter("frame_id").value
        self._pub_annotated: bool = self.get_parameter("publish_annotated").value

        # ── publishers ──────────────────────────────────────────────────
        self._pub_rgb = self.create_publisher(
            Image, "/camera/color/image_raw", _SENSOR_QOS)
        self._pub_info = self.create_publisher(
            CameraInfo, "/camera/color/camera_info", _RELIABLE_QOS)
        self._pub_depth = self.create_publisher(
            Image, "/camera/depth/image_rect_raw", _SENSOR_QOS)
        self._pub_detections = self.create_publisher(
            DetectionArray, "/detections", _RELIABLE_QOS)

        if self._pub_annotated:
            self._pub_annot = self.create_publisher(
                Image, "/camera/annotated/image_raw", _SENSOR_QOS)

        # ── camera info (interne OAK-D Lite kalibratie) ─────────────────
        self._camera_info = self._make_camera_info()

        # ── pipeline starten ────────────────────────────────────────────
        self._pipeline_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if self._mock:
            self.get_logger().warn("MOCK MODE – geen OAK-D hardware vereist")
            self._timer = self.create_timer(1.0 / RGB_FPS, self._mock_publish)
            self._mock_t = 0.0
        else:
            self._start_pipeline()

        self.get_logger().info(
            f"OakNode gestart | model={self._model_name} "
            f"shaves={self._shaves} conf={self._conf:.2f} "
            f"mock={self._mock}"
        )

    # ── Camera info ─────────────────────────────────────────────────────────

    def _make_camera_info(self) -> CameraInfo:
        """
        Standaard intrinsics voor OAK-D Lite RGB camera @ 640×352.
        Voor echte kalibratie: gebruik `depthai_ros_driver` of
        camera_calibration pakket.
        """
        info = CameraInfo()
        info.width  = FRAME_W
        info.height = FRAME_H
        # Fx, Fy, Cx, Cy (geschatte waarden, kalibreer voor productie)
        fx = 563.7
        fy = 563.7
        cx = 320.0
        cy = 176.0
        info.k = [fx, 0.0, cx,
                  0.0, fy, cy,
                  0.0, 0.0, 1.0]
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]   # geen distortie model (rectified)
        info.distortion_model = "plumb_bob"
        info.r = [1.0, 0.0, 0.0,
                  0.0, 1.0, 0.0,
                  0.0, 0.0, 1.0]
        info.p = [fx, 0.0, cx, 0.0,
                  0.0, fy, cy, 0.0,
                  0.0, 0.0, 1.0, 0.0]
        return info

    # ── depthai pipeline ────────────────────────────────────────────────────

    def _start_pipeline(self) -> None:
        try:
            import depthai as dai  # type: ignore
        except ImportError:
            self.get_logger().error(
                "depthai niet geïnstalleerd! Voer uit:\n"
                "  pip install depthai\n"
                "Of gebruik RC_PLATFORM=mock voor development."
            )
            raise

        blob_path = get_model_path(self._model_name, shaves=self._shaves)

        pipeline = dai.Pipeline()

        # ── Camera nodes ───────────────────────────────────────────────
        cam_rgb = pipeline.createColorCamera()
        cam_rgb.setPreviewSize(FRAME_W, FRAME_H)
        cam_rgb.setInterleaved(False)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        cam_rgb.setFps(RGB_FPS)

        cam_left  = pipeline.createMonoCamera()
        cam_right = pipeline.createMonoCamera()
        cam_left.setResolution(
            dai.MonoCameraProperties.SensorResolution.THE_400_P)
        cam_right.setResolution(
            dai.MonoCameraProperties.SensorResolution.THE_400_P)
        cam_left.setBoardSocket(dai.CameraBoardSocket.LEFT)
        cam_right.setBoardSocket(dai.CameraBoardSocket.RIGHT)
        cam_left.setFps(DEPTH_FPS)
        cam_right.setFps(DEPTH_FPS)

        # ── Stereo diepte ──────────────────────────────────────────────
        stereo = pipeline.createStereoDepth()
        stereo.setDefaultProfilePreset(
            dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
        stereo.initialConfig.setMedianFilter(
            dai.MedianFilter.KERNEL_7x7)
        stereo.setLeftRightCheck(True)
        stereo.setSubpixel(False)          # subpixel kost extra geheugen
        stereo.setDepthAlign(
            dai.CameraBoardSocket.RGB)     # diepte uitgelijnd op RGB frame
        cam_left.out.link(stereo.left)
        cam_right.out.link(stereo.right)

        # ── ImageManip: resize voor YOLO ───────────────────────────────
        manip = pipeline.createImageManip()
        manip.initialConfig.setResize(FRAME_W, FRAME_H)
        manip.initialConfig.setFrameType(
            dai.RawImgFrame.Type.BGR888p)
        cam_rgb.preview.link(manip.inputImage)

        # ── YOLO Spatial Detection Network ─────────────────────────────
        yolo = pipeline.createYoloSpatialDetectionNetwork()
        yolo.setBlobPath(str(blob_path))
        yolo.setConfidenceThreshold(self._conf)
        yolo.setNumClasses(NUM_CLASSES)
        yolo.setCoordinateSize(4)
        yolo.setAnchors([])         # YOLOv8 anchor-vrij
        yolo.setAnchorMasks({})
        yolo.setIouThreshold(IOU_THRESHOLD)
        yolo.setBoundingBoxScaleFactor(0.5)
        yolo.setDepthLowerThreshold(DEPTH_LOWER_THRESHOLD)
        yolo.setDepthUpperThreshold(DEPTH_UPPER_THRESHOLD)
        yolo.input.setBlocking(False)
        yolo.inputDepth.setBlocking(False)

        manip.out.link(yolo.input)
        stereo.depth.link(yolo.inputDepth)

        # ── Outputs naar host ─────────────────────────────────────────
        xout_rgb = pipeline.createXLinkOut()
        xout_rgb.setStreamName("rgb")
        manip.out.link(xout_rgb.input)

        xout_depth = pipeline.createXLinkOut()
        xout_depth.setStreamName("depth")
        stereo.disparity.link(xout_depth.input)

        xout_det = pipeline.createXLinkOut()
        xout_det.setStreamName("detections")
        yolo.out.link(xout_det.input)

        xout_spatial = pipeline.createXLinkOut()
        xout_spatial.setStreamName("spatialData")
        yolo.boundingBoxMapping.link(xout_spatial.input)

        # ── Thread starten ────────────────────────────────────────────
        self._device_pipeline = pipeline
        self._pipeline_thread = threading.Thread(
            target=self._pipeline_loop, daemon=True)
        self._pipeline_thread.start()

    def _pipeline_loop(self) -> None:
        """Draait in aparte thread; haalt frames op en publiceert naar ROS2."""
        try:
            import depthai as dai  # type: ignore
        except ImportError:
            return

        with dai.Device(self._device_pipeline) as device:
            q_rgb   = device.getOutputQueue("rgb",        maxSize=1, blocking=False)
            q_depth = device.getOutputQueue("depth",      maxSize=1, blocking=False)
            q_det   = device.getOutputQueue("detections", maxSize=1, blocking=False)

            self.get_logger().info("OAK-D Lite verbonden, pipeline loopt")

            while not self._stop_event.is_set():
                in_rgb   = q_rgb.tryGet()
                in_depth = q_depth.tryGet()
                in_det   = q_det.tryGet()

                now = self.get_clock().now().to_msg()

                if in_rgb is not None:
                    self._pub_rgb.publish(
                        self._dai_to_image(in_rgb, now, "bgr8"))
                    ci = self._camera_info
                    ci.header.stamp = now
                    ci.header.frame_id = self._frame_id
                    self._pub_info.publish(ci)

                if in_depth is not None:
                    # Disparity → depth image (mono16, mm)
                    arr = in_depth.getFrame().astype(np.uint16)
                    self._pub_depth.publish(
                        self._ndarray_to_image(arr, now, "mono16"))

                if in_det is not None:
                    det_msg = self._parse_detections(in_det.detections, now)
                    self._pub_detections.publish(det_msg)

                    if self._pub_annotated:
                        if in_rgb is not None:
                            frame = in_rgb.getCvFrame()
                            annotated = self._draw_detections(
                                frame, in_det.detections)
                            self._pub_annot.publish(
                                self._ndarray_to_image(
                                    annotated, now, "bgr8"))

                time.sleep(0.001)

    # ── Conversie hulpfuncties ──────────────────────────────────────────────

    def _header(self, stamp) -> Header:
        h = Header()
        h.stamp = stamp
        h.frame_id = self._frame_id
        return h

    def _dai_to_image(self, dai_frame, stamp, encoding: str) -> Image:
        import cv2  # type: ignore
        frame = dai_frame.getCvFrame()
        if encoding == "rgb8":
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self._ndarray_to_image(frame, stamp, encoding)

    def _ndarray_to_image(self, arr: np.ndarray, stamp, encoding: str) -> Image:
        msg = Image()
        msg.header = self._header(stamp)
        if arr.ndim == 2:
            msg.height, msg.width = arr.shape
            msg.step = arr.shape[1] * arr.dtype.itemsize
        else:
            msg.height, msg.width, _ = arr.shape
            msg.step = arr.shape[1] * arr.shape[2] * arr.dtype.itemsize
        msg.encoding = encoding
        msg.is_bigendian = False
        msg.data = arr.tobytes()
        return msg

    def _parse_detections(self, dets, stamp) -> DetectionArray:
        """Zet depthai ImgDetections om naar rc_interfaces/DetectionArray."""
        array_msg = DetectionArray()
        array_msg.header = self._header(stamp)

        for d in dets:
            det = Detection()
            det.class_id    = int(d.label)
            det.class_name  = label_for(int(d.label))
            det.confidence  = float(d.confidence)

            # Bounding box in pixels (relatief aan FRAME_W × FRAME_H)
            det.xmin = int(d.xmin * FRAME_W)
            det.ymin = int(d.ymin * FRAME_H)
            det.xmax = int(d.xmax * FRAME_W)
            det.ymax = int(d.ymax * FRAME_H)

            # 3D positie in mm (camerafrane: +X rechts, +Y omlaag, +Z vooruit)
            det.x_mm = float(d.spatialCoordinates.x)
            det.y_mm = float(d.spatialCoordinates.y)
            det.z_mm = float(d.spatialCoordinates.z)

            det.is_obstacle = is_obstacle(det.class_id)
            det.is_person   = is_person(det.class_id)

            array_msg.detections.append(det)

        return array_msg

    def _draw_detections(self, frame: np.ndarray, dets) -> np.ndarray:
        """Teken bounding boxes op frame (voor debug topic)."""
        import cv2  # type: ignore
        out = frame.copy()
        for d in dets:
            x1 = int(d.xmin * FRAME_W)
            y1 = int(d.ymin * FRAME_H)
            x2 = int(d.xmax * FRAME_W)
            y2 = int(d.ymax * FRAME_H)
            label = label_for(int(d.label))
            z_m = d.spatialCoordinates.z / 1000.0

            color = (0, 255, 0) if not is_obstacle(d.label) else (0, 0, 255)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            cv2.putText(out,
                        f"{label} {d.confidence:.2f} ({z_m:.1f}m)",
                        (x1, max(y1 - 5, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return out

    # ── Mock modus ──────────────────────────────────────────────────────────

    def _mock_publish(self) -> None:
        """Synthetische data voor development zonder hardware."""
        self._mock_t += 1.0 / RGB_FPS
        now = self.get_clock().now().to_msg()

        # Dummy RGB frame (640×352, blauw-grijs)
        rgb = np.full((FRAME_H, FRAME_W, 3), [80, 80, 60], dtype=np.uint8)
        # Bewegende rechthoek als "persoon"
        cx = int(FRAME_W / 2 + 100 * np.sin(self._mock_t * 0.3))
        cy = FRAME_H // 2
        rgb[cy - 40:cy + 40, cx - 20:cx + 20] = [180, 100, 60]

        self._pub_rgb.publish(self._ndarray_to_image(rgb, now, "bgr8"))
        ci = self._camera_info
        ci.header.stamp = now
        ci.header.frame_id = self._frame_id
        self._pub_info.publish(ci)

        # Dummy depth (mono16, vaste afstand 1500 mm)
        depth = np.full((FRAME_H, FRAME_W), 1500, dtype=np.uint16)
        self._pub_depth.publish(self._ndarray_to_image(depth, now, "mono16"))

        # Dummy detectie (persoon, midden-voor)
        det = Detection()
        det.class_id   = 0
        det.class_name = "person"
        det.confidence = 0.82
        det.xmin = cx - 20
        det.ymin = cy - 40
        det.xmax = cx + 20
        det.ymax = cy + 40
        det.x_mm = float((cx - FRAME_W / 2) * 3.0)
        det.y_mm = 0.0
        det.z_mm = 1500.0
        det.is_person   = True
        det.is_obstacle = False

        array_msg = DetectionArray()
        array_msg.header = self._header(now)
        array_msg.detections.append(det)
        self._pub_detections.publish(array_msg)

    # ── Shutdown ────────────────────────────────────────────────────────────

    def destroy_node(self) -> None:
        self._stop_event.set()
        if self._pipeline_thread is not None:
            self._pipeline_thread.join(timeout=3.0)
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OakNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

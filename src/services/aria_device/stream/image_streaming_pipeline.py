import logging
import multiprocessing
from multiprocessing import Queue
from multiprocessing.synchronize import Event
from typing import Any

import aria.sdk as aria
import cv2
import numpy as np
from geometry_msgs.msg import Point, PoseStamped
from projectaria_tools.core.calibration import (
    device_calibration_from_json_string,
    get_linear_camera_calibration,
)
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header

from config import AriaConfig, ROS2Topics
from services.arcuo import detect_aruco
from services.aria_device import AriaStreamClient, ImageObserver
from services.aria_device.eye_tracking import EyeTrackingPipeline
from services.aria_device.stream.undistortion_helper import build_remap_maps
from services.ros import ROSPublisher

logger = logging.getLogger(__name__)


def _put_latest(queue: Queue, item) -> None:
    """Discard stale item and put the latest one."""
    try:
        queue.get_nowait()
    except Exception:
        pass
    try:
        queue.put_nowait(item)
    except Exception:
        pass


def _publish_aruco_detections(
    detection: Any,
    publisher: ROSPublisher,
) -> None:
    """Publish the first detected ArUco marker as a PoseStamped in camera frame.

    The message encodes T_camera_marker — the marker's pose expressed in the
    RGB camera frame.  The pose fusion node converts this into the SLAM map
    frame using the known marker position in the map.
    """
    if not detection:
        return

    T = detection["T_camera_tag"]  # 4×4 homogeneous, camera → marker

    msg = PoseStamped()
    msg.header = Header()
    msg.header.stamp = publisher.get_clock().now().to_msg()
    msg.header.frame_id = "camera_rgb"

    msg.pose.position.x = float(T[0, 3])
    msg.pose.position.y = float(T[1, 3])
    msg.pose.position.z = float(T[2, 3])

    q = Rotation.from_matrix(T[:3, :3]).as_quat()  # [x, y, z, w]
    msg.pose.orientation.x = float(q[0])
    msg.pose.orientation.y = float(q[1])
    msg.pose.orientation.z = float(q[2])
    msg.pose.orientation.w = float(q[3])

    publisher.publish(msg)


def rgb_worker(
    rgb_queue: Queue,
    quit_event: Event,
    sensors_calib_json_str: str,
) -> None:
    rgb_publisher = ROSPublisher(
        "Aria_RGB_camera_publisher",
        CompressedImage,
        ROS2Topics.RGB_CAMERA_RAW.value,
    )
    undistorted_rgb_publisher = ROSPublisher(
        "Aria_RGB_camera_undistorted_publisher",
        CompressedImage,
        ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
    )
    aruco_pose_publisher = ROSPublisher(
        "Aria_aruco_pose_publisher",
        PoseStamped,
        ROS2Topics.ARUCO_POSE.value,
    )

    aria_device_calibration = device_calibration_from_json_string(
        sensors_calib_json_str
    )
    dest_calibration = get_linear_camera_calibration(
        AriaConfig.DEST_CALIBRATION_WIDTH_PX,
        AriaConfig.DEST_CALIBRATION_HEIGHT_PX,
        AriaConfig.DEST_CALIBRATION_FOCAL_LENGTH,
        "camera-rgb",
    )
    source_calibration = aria_device_calibration.get_camera_calib(
        AriaConfig.RGB_STREAM_LABEL
    )

    if not source_calibration:
        logger.error("Failed to retrieve RGB camera calibration data")
        return

    map_x, map_y = build_remap_maps(source_calibration, dest_calibration)

    fx = fy = AriaConfig.DEST_CALIBRATION_FOCAL_LENGTH
    cx = AriaConfig.DEST_CALIBRATION_WIDTH_PX / 2.0
    cy = AriaConfig.DEST_CALIBRATION_HEIGHT_PX / 2.0
    camera_matrix = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
    dist_coeffs = np.zeros(5, dtype=np.float64)

    while not quit_event.is_set():
        try:
            image = rgb_queue.get(timeout=0.1)
        except Exception:
            continue

        image = np.rot90(image, -1)
        rgb_publisher.publish_image(image)

        undistorted_image = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR)
        undistorted_rgb_publisher.publish_image(undistorted_image)

        result, frame = detect_aruco(
            undistorted_image.copy(), camera_matrix, dist_coeffs
        )
        _publish_aruco_detections(result, aruco_pose_publisher)


def et_worker(
    eye_queue: Queue,
    quit_event: Event,
    sensors_calib_json_str: str,
) -> None:
    gaze_estimate_publisher = ROSPublisher(
        "gaze_estimate_publisher",
        Point,
        ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
    )
    device_calibration = device_calibration_from_json_string(sensors_calib_json_str)
    rgb_camera_calibration = device_calibration.get_camera_calib(
        AriaConfig.RGB_STREAM_LABEL
    )
    if not rgb_camera_calibration:
        logger.error("Failed to retrieve RGB camera calibration data")
        return

    eye_tracking = EyeTrackingPipeline(device_calibration, rgb_camera_calibration)

    while not quit_event.is_set():
        try:
            image = eye_queue.get(timeout=0.1)
        except Exception:
            continue

        gaze_estimate = eye_tracking.predict_eye_gaze(image)
        gaze_estimate = eye_tracking.project_gaze(gaze_estimate=gaze_estimate)

        if gaze_estimate is None:
            continue

        gaze_estimate_publisher.publish(
            Point(x=gaze_estimate[0], y=gaze_estimate[1], z=0.0)
        )


class ImageStreamingPipeline:
    def __init__(self, quit_event: Event, sensors_calib_json_str: str):
        self.quit_event = quit_event

        self.rgb_queue = multiprocessing.Queue(maxsize=1)
        self.eye_queue = multiprocessing.Queue(maxsize=1)

        self.rgb_process = multiprocessing.Process(
            target=rgb_worker,
            args=(self.rgb_queue, self.quit_event, sensors_calib_json_str),
            daemon=True,
        )
        self.eye_process = multiprocessing.Process(
            target=et_worker,
            args=(self.eye_queue, self.quit_event, sensors_calib_json_str),
            daemon=True,
        )
        self.rgb_process.start()
        self.eye_process.start()

    # --- Callbacks registered with the observer ---

    def _on_rgb_frame(self, image: np.ndarray, record) -> None:
        """Rate-limit RGB frames before handing off to the worker process."""
        _put_latest(self.rgb_queue, image)

    def _on_et_frame(self, image: np.ndarray, record) -> None:
        """Rate-limit eye-track frames before handing off to the worker process."""
        _put_latest(self.eye_queue, image)

    # --- Main run loop ---

    def run(self) -> None:
        try:
            with AriaStreamClient() as aria_stream_client:
                data_channels = [
                    (aria.StreamingDataType.Rgb, 1),
                    (aria.StreamingDataType.EyeTrack, 1),
                ]
                observer = ImageObserver()
                observer.register_on_image_callback(
                    aria.CameraId.Rgb, self._on_rgb_frame
                )
                observer.register_on_image_callback(
                    aria.CameraId.EyeTrack, self._on_et_frame
                )
                aria_stream_client.subscribe(data_channels, observer)

                logger.info("Started image streaming")

                self.quit_event.wait()

        except KeyboardInterrupt:
            logger.warning("\nStreaming interrupted by user")
        except Exception as e:
            logger.error("Error in image streaming pipeline: %s", e, exc_info=True)
            raise
        finally:
            self.rgb_process.join(timeout=5)
            self.eye_process.join(timeout=5)
            logging.info("Image streaming service stopped")


# sensors_calib_json_str is only passed when aria_streaming_started is set
def stream_visual_feed(
    aria_streaming_started: Event, quit_event: Event, sensors_calib_json_str: str
) -> None:
    pipeline = ImageStreamingPipeline(quit_event, sensors_calib_json_str)
    pipeline.run()

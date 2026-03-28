"""
VIO pose streaming pipeline.

Receives SLAM camera frames and IMU samples from the Aria device, forwards them
to OpenVINS via ROS 2, and publishes the resulting pose estimates on
/aria/vio_pose for downstream consumers.
"""

import logging
import multiprocessing
import queue
from multiprocessing import Queue
from multiprocessing.synchronize import Event
from typing import Sequence

import aria.sdk as aria
import numpy as np
from builtin_interfaces.msg import Time
from projectaria_tools.core.calibration import (
    CameraCalibration,
    DeviceCalibration,
    device_calibration_from_json_string,
    distort_by_calibration,
    get_linear_camera_calibration,
)
from projectaria_tools.core.sensor_data import ImageDataRecord, MotionData
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image, Imu

from config import AriaConfig, ROS2Topics
from services.aria_device import (
    AriaStreamClient,
    AriaVIOObserver,
)
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


def _log_calibration(calibration: DeviceCalibration) -> None:
    def format_matrix(matrix):
        """Formats a 4x4 matrix into [[W, X, Y, Z], ...] string format."""
        lines = []
        for row in matrix:
            formatted_row = ", ".join([f"{val:12.8f}" for val in row])
            lines.append(f"[{formatted_row}]")
        return "[\n    - " + "\n    - ".join(lines) + "\n  ]"

    with open("temp.txt", "w") as f:
        f.write("=== PROJECT ARIA TO OPENVINS CALIBRATION LOG ===\n\n")

        # 1. Get IMU-Left Transform (Common Base)
        T_dev_imu = calibration.get_transform_device_sensor("imu-left").to_matrix()

        temp = calibration.get_imu_calib("imu-left")

        accel_bias = temp.get_accel_model().get_bias()
        accel_rect = temp.get_accel_model().get_rectification()
        gyro_bias = temp.get_gyro_model().get_bias()
        gyro_rect = temp.get_gyro_model().get_rectification()

        f.write(f"Accel Bias: {accel_bias}\n")
        f.write(f"Accel Rectification:\n{accel_rect}\n")
        f.write(f"Gyro Bias: {gyro_bias}\n")
        f.write(f"Gyro Rectification:\n{gyro_rect}\n")

        f.write("STEP 1: Raw Device -> IMU-LEFT (T_dev_imu)\n")
        f.write(format_matrix(T_dev_imu) + "\n\n")

        # 2. Invert to get IMU as the Base Frame
        T_imu_dev = np.linalg.inv(T_dev_imu)
        f.write("STEP 2: Inverted IMU-LEFT -> Device (T_imu_dev)\n")
        f.write(format_matrix(T_imu_dev) + "\n\n")

        for cam_name in ["camera-slam-left", "camera-slam-right"]:
            f.write(f"--- PROCESSING: {cam_name} ---\n")
            T_dev_cam = calibration.get_transform_device_sensor(cam_name).to_matrix()

            f.write(f"  A. Raw Device -> {cam_name} (T_dev_cam):\n")
            f.write(format_matrix(T_dev_cam) + "\n")

            # Chain: T_IMU_Device @ T_Device_Camera
            T_imu_cam = T_imu_dev @ T_dev_cam

            R_optical = np.array(
                [[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                dtype=float,
            )

            T_imu_cam_corrected = T_imu_cam @ R_optical

            f.write(
                f"  B. IMU -> {cam_name} with 90 degrees clockwise rotation (T_imu_cam):\n"
            )

            f.write(format_matrix(T_imu_cam_corrected) + "\n")


def slam_worker(
    slam_left_queue: Queue,
    slam_right_queue: Queue,
    quit_event: Event,
    sensors_calib_json_str: str,
) -> None:
    """Process and publish images in a dedicated thread, off the SDK callback."""

    slam_left_publisher = ROSPublisher(
        "Aria_SLAM_left_publisher",
        Image,
        ROS2Topics.SLAM_LEFT_RAW.value,
        QoSProfile(reliability=ReliabilityPolicy.RELIABLE, depth=10),
    )
    slam_right_publisher = ROSPublisher(
        "Aria_SLAM_right_publisher",
        Image,
        ROS2Topics.SLAM_RIGHT_RAW.value,
        QoSProfile(reliability=ReliabilityPolicy.RELIABLE, depth=10),
    )

    aria_device_calibration = device_calibration_from_json_string(
        sensors_calib_json_str
    )
    slam_left_calib = aria_device_calibration.get_camera_calib(
        AriaConfig.SLAM_LEFT_STREAM_LABEL
    )
    slam_right_calib = aria_device_calibration.get_camera_calib(
        AriaConfig.SLAM_RIGHT_STREAM_LABEL
    )

    _src_calibs = {
        aria.CameraId.Slam1: slam_left_calib,
        aria.CameraId.Slam2: slam_right_calib,
    }

    def _make_pinhole_calibration(
        src: CameraCalibration,
        label: str,
    ) -> CameraCalibration:
        """Build a linear (pinhole) calibration matching *src*'s resolution and
        focal length, derived entirely from the source calibration object.

        Args:
            src:   Camera calibration from the device.
            label: Sensor label forwarded to get_linear_camera_calibration.

        Returns:
            A pinhole CameraCalibration suitable for use as the undistortion target.
        """
        width, height = src.get_image_size()
        focal_length = float(src.get_focal_lengths()[0])
        return get_linear_camera_calibration(width, height, focal_length, label)

    _dst_calibs = {
        aria.CameraId.Slam1: _make_pinhole_calibration(
            slam_left_calib, AriaConfig.SLAM_LEFT_STREAM_LABEL
        ),
        aria.CameraId.Slam2: _make_pinhole_calibration(
            slam_right_calib, AriaConfig.SLAM_RIGHT_STREAM_LABEL
        ),
    }

    _queues = {
        aria.CameraId.Slam1: slam_left_queue,
        aria.CameraId.Slam2: slam_right_queue,
    }

    _publishers = {
        aria.CameraId.Slam1: slam_left_publisher,
        aria.CameraId.Slam2: slam_right_publisher,
    }

    _frame_ids = {
        aria.CameraId.Slam1: "slam_left",
        aria.CameraId.Slam2: "slam_right",
    }

    def _cv2_to_imgmsg_mono8(image: np.ndarray) -> Image:
        assert image.ndim == 2, "Expected a grayscale (2D) image"
        assert image.dtype == np.uint8, "Expected uint8 image"

        msg = Image()
        msg.height = image.shape[0]
        msg.width = image.shape[1]
        msg.encoding = "mono8"
        msg.is_bigendian = 0
        msg.step = image.shape[1]  # 1 byte per pixel
        msg.data = image.tobytes()

        return msg

    while not quit_event.is_set():
        for camera_id, q in _queues.items():
            try:
                image, timestamp_ns = q.get(timeout=0.05)
                undistorted = distort_by_calibration(
                    image,
                    _dst_calibs[camera_id],
                    _src_calibs[camera_id],
                )
                undistorted = np.rot90(undistorted, k=3)

                msg = _cv2_to_imgmsg_mono8(undistorted)
                msg.header.stamp = Time()
                msg.header.stamp.sec = int(timestamp_ns // 1_000_000_000)
                msg.header.stamp.nanosec = int(timestamp_ns % 1_000_000_000)
                msg.header.frame_id = _frame_ids[camera_id]

                _publishers[camera_id].publish(msg)

            except queue.Empty:
                pass
            except Exception as e:
                logger.error(
                    "SLAM worker error for %s: %s", camera_id, e, exc_info=True
                )


class PoseStreamingPipeline:
    def __init__(self, quit_event: Event, sensors_calib_json_str: str):
        self.imu_publisher = ROSPublisher(
            "Aria_IMU_publisher",
            Imu,
            ROS2Topics.IMU.value,
            qos_profile_sensor_data,
        )

        self.quit_event = quit_event

        self.slam_left_queue = multiprocessing.Queue(maxsize=1)
        self.slam_right_queue = multiprocessing.Queue(maxsize=1)

        self.slam_process = multiprocessing.Process(
            target=slam_worker,
            args=(
                self.slam_left_queue,
                self.slam_right_queue,
                self.quit_event,
                sensors_calib_json_str,
            ),
            daemon=True,
        )
        self.slam_process.start()

        self._imu_msg = Imu()
        self._imu_msg.header.frame_id = "imu"
        # Covariance unknown — set diagonal to -1 per REP-145
        self._imu_msg.linear_acceleration_covariance[0] = -1.0
        self._imu_msg.angular_velocity_covariance[0] = -1.0
        self._imu_msg.orientation_covariance[0] = -1.0

    # --- Callbacks registered with the observer ---
    def _on_imu_received(self, samples: Sequence[MotionData], imu_idx: int) -> None:
        """Handle incoming IMU samples."""

        for sample in samples:
            accel = sample.accel_msec2
            gyro = sample.gyro_radsec
            ts = sample.capture_timestamp_ns

            self._imu_msg.header.stamp.sec = int(ts // 1_000_000_000)
            self._imu_msg.header.stamp.nanosec = int(ts % 1_000_000_000)

            self._imu_msg.linear_acceleration.x = float(accel[0])
            self._imu_msg.linear_acceleration.y = float(accel[1])
            self._imu_msg.linear_acceleration.z = float(accel[2])

            self._imu_msg.angular_velocity.x = float(gyro[0])
            self._imu_msg.angular_velocity.y = float(gyro[1])
            self._imu_msg.angular_velocity.z = float(gyro[2])

            self.imu_publisher.publish(self._imu_msg)

    def _on_slam_frame(self, image: np.ndarray, record: ImageDataRecord) -> None:
        """Handle incoming SLAM frames."""
        if record.camera_id == aria.CameraId.Slam1:
            _put_latest(self.slam_left_queue, (image, record.capture_timestamp_ns))
        else:
            _put_latest(self.slam_right_queue, (image, record.capture_timestamp_ns))

    # --- Main run loop ---

    def run(self) -> None:
        try:
            with AriaStreamClient() as aria_stream_client:
                data_channels = [
                    (aria.StreamingDataType.Imu, 200),
                    (aria.StreamingDataType.Slam, 10),
                ]
                observer = AriaVIOObserver()
                observer.register_on_imu_callback(1, self._on_imu_received)
                observer.register_on_image_callback(
                    aria.CameraId.Slam1, self._on_slam_frame
                )
                observer.register_on_image_callback(
                    aria.CameraId.Slam2, self._on_slam_frame
                )
                aria_stream_client.subscribe(data_channels, observer)

                logger.info("Started pose streaming")

                self.quit_event.wait()

        except KeyboardInterrupt:
            logger.warning("\nStreaming interrupted by user")
        except Exception as e:
            logger.error("Error in pose pipeline: %s", e, exc_info=True)
            raise
        finally:
            self.slam_process.join(timeout=5)
            logger.info("VIO pose streaming service stopped.")


# sensors_calib_json_str is only passed when aria_streaming_started is set
def stream_pose(
    aria_streaming_started: Event, quit_event: Event, sensors_calib_json_str: str
) -> None:
    pipeline = PoseStreamingPipeline(quit_event, sensors_calib_json_str)
    pipeline.run()

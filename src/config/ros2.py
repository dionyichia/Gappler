from enum import Enum

from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy


class ROS2Topics(Enum):
    RGB_CAMERA_RAW = "/aria/rgb_camera/raw"
    RGB_CAMERA_UNDISTORTED = "/aria/rgb_camera/undistorted"

    SLAM_LEFT_RAW = "/aria/slam_left/raw"
    SLAM_RIGHT_RAW = "/aria/slam_right/raw"

    EYE_TRACKING_RAW = "/aria/eye_tracking/raw"
    EYE_TRACKING_GAZE_ESTIMATE = "/aria/eye_tracking/gaze_estimate"

    RGB_CAMERA_WITH_OBJECT_MASKS = "/aria/rgb_camera/object_masks"
    ROS_CAMERA_WITH_OBJECT_MASKS = "/realman/rgb_camera/object_masks"

    FEATURE_MATCH_RESULTS = "/aria/rgb_camera/feature_match"

    AUDIO_TRANSCRIPTION_PROMPT = "/aria/audio/prompt"

    IMU = "/aria/imu"

    ARUCO_POSE = "/aria/aruco_pose"
    VIO_POSE = "/aria/vio_pose"
    FUSED_POSE = "/aria/fused_pose"
    IS_STATIONARY = "/aria/is_stationary"


class ROS2Config:
    TOPICS = ROS2Topics
    VIDEO_QOS = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )

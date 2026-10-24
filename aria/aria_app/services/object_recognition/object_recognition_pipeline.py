import logging
import pickle
import threading
import time
from multiprocessing.synchronize import Event
from typing import Any, Dict, Optional, Tuple

import numpy as np
import rclpy.duration
import tf2_geometry_msgs
import tf2_ros
import torch
from geometry_msgs.msg import PointStamped, PoseStamped
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from segmentation_interfaces.msg import Target
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from std_msgs.msg import String, UInt8MultiArray

from config import VIDEO_QOS, AudioStreamingPipelineConfig, ModelPaths, ROS2Topics
from gappler_common import config as gappler_config
from memory_graph.clip_encoder import OpenClipEncoder
from memory_graph.image_feature import l2_normalise
# T8.7: LightGlue no longer runs (the CLIP rule replaced it). Kept in case it comes back.
# from services.feature_matching import FeatureMatcher
from services.object_recognition import SAM3Model
# T8.9a: the matcher moved to grasp, which uses it. This pipeline keeps it for its replay view.
from grasp.grasp_segmentation_client.cross_camera_mask_match_rule import crop_to_mask, pick_mask_pair
from services.ros import ImageHelper, ROSPublisher
from services.visualizer.renderers.object_mask_visualizer import ObjectMaskVisualizer

logger = logging.getLogger(__name__)

# Wrist camera values from shared/global_config.yaml
DEPTH_SCALE = gappler_config()["wrist_camera"]["depth_scale_m"]  # metres per depth unit

TOPIC_RGB = ROS2Topics.WRIST_CAMERA_COLOR.value
TOPIC_DEPTH = ROS2Topics.WRIST_CAMERA_ALIGNED_DEPTH.value
TOPIC_CAMERA_INFO = ROS2Topics.WRIST_CAMERA_INFO.value
TOPIC_MASK = ROS2Topics.WRIST_CAMERA_OBJECT_MASK.value
TOPIC_CENTROID_2D = ROS2Topics.OBJECT_CENTROID_2D.value
TOPIC_CENTROID_VIZ = ROS2Topics.OBJECT_CENTROID_VIZ.value


class CameraFeed:
    """Holds the latest frame and a monotonic ID for one camera."""

    def __init__(self):
        self._image: Optional[np.ndarray] = None
        self._image_id: int = 0
        self._lock = threading.Lock()

    def update(self, frame: np.ndarray) -> None:
        with self._lock:
            self._image = frame
            self._image_id += 1

    def get(self) -> Tuple[Optional[np.ndarray], int]:
        with self._lock:
            if self._image is None:
                return None, -1
            return self._image.copy(), self._image_id


class RealSenseFrame:
    """Holds the latest synchronised RGB+depth pair for the RealSense camera."""

    def __init__(self):
        self._rgb: Optional[np.ndarray] = None
        self._depth: Optional[np.ndarray] = None
        self._frame_id: int = 0
        self._header = None
        self._lock = threading.Lock()

    def update(self, rgb: np.ndarray, depth: np.ndarray, header) -> None:
        with self._lock:
            self._rgb = rgb
            self._depth = depth
            self._header = header
            self._frame_id += 1

    def get(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Any, int]:
        with self._lock:
            if self._rgb is None:
                return None, None, None, -1
            return self._rgb.copy(), self._depth.copy(), self._header, self._frame_id


def _to_full_image(points: np.ndarray, x0: int, y0: int, shape) -> np.ndarray:
    """Crop pixel coordinates back to whole-image ones, as ints inside the image.
    Unused since T8.7 (LightGlue stopped). Consider deleting if LightGlue does not come back."""
    full = points.round().astype(int).reshape(-1, 2) + (x0, y0)
    full[:, 0] = full[:, 0].clip(0, shape[1] - 1)
    full[:, 1] = full[:, 1].clip(0, shape[0] - 1)
    return full


class ObjectRecognitionPipeline:
    def __init__(self, quit_event: Event):
        self._quit_event = quit_event

        self.prompt = ""

        self.model = SAM3Model(
            checkpoint_path=ModelPaths.SAM3_PATH,
            confidence_threshold=0.3,  # T8.7: 0.5 missed the box, as T2.9 found for the glasses
        )

        self._aria_inference_state: Optional[Dict[str, Any]] = None
        self._aria_locked_image: Optional[np.ndarray] = None

        # self._feature_matcher = FeatureMatcher()
        self._clip = OpenClipEncoder()

        self._aria_feed = CameraFeed()
        self._ros_feed = RealSenseFrame()
        self._gaze_point: Optional[Tuple[float, float]] = None
        # T8.5: the crop of the object you looked at when you said the word (rgb, from the aria
        # client's /grasp/target), or None. Kept until the next Target.
        self._reference: Optional[np.ndarray] = None
        self._state_lock = threading.Lock()

        # RealSense intrinsics — gated until received
        self._fx = self._fy = None
        self._cx = self._cy = None
        self._intrinsics_received = False

        self._setup_ros_node()

    # ---------------------------------------------------------------------------
    # ROS setup
    # ---------------------------------------------------------------------------

    def _setup_ros_node(self) -> None:
        self._object_recognition_node = Node("object_recognition_node")

        image_cb_group = ReentrantCallbackGroup()
        state_cb_group = MutuallyExclusiveCallbackGroup()

        # CameraInfo — one-time latch
        self._object_recognition_node.create_subscription(
            CameraInfo,
            TOPIC_CAMERA_INFO,
            self._on_camera_info,
            1,
            callback_group=state_cb_group,
        )

        # T8.5: the glasses image, the word and the live gaze are no longer read here. The aria client
        # already picks the object with the gaze from when you spoke, and sends its crop on
        # /grasp/target. Parked, consider deleting with _on_aria_image, _on_prompt, _on_gaze and
        # _process_aria_frame once T8.5 has run on the box.
        # self._object_recognition_node.create_subscription(
        #     CompressedImage,
        #     ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
        #     self._on_aria_image,
        #     VIDEO_QOS,
        #     callback_group=image_cb_group,
        # )

        # Synchronised RealSense RGB + depth
        self._rgb_sub = Subscriber(self._object_recognition_node, Image, TOPIC_RGB)
        self._depth_sub = Subscriber(self._object_recognition_node, Image, TOPIC_DEPTH)
        self._sync = ApproximateTimeSynchronizer(
            [self._rgb_sub, self._depth_sub], queue_size=10, slop=0.05
        )
        self._sync.registerCallback(self._on_realsense_image)

        # What to look for and the reference crop (T8.5), from the aria client
        self._object_recognition_node.create_subscription(
            Target,
            ROS2Topics.GRASP_TARGET.value,
            self._on_target,
            10,
            callback_group=state_cb_group,
        )
        # Audio prompt + gaze: parked by T8.5, see the glasses image above
        # self._object_recognition_node.create_subscription(
        #     String,
        #     ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value,
        #     self._on_prompt,
        #     VIDEO_QOS,
        #     callback_group=state_cb_group,
        # )
        # self._object_recognition_node.create_subscription(
        #     PointStamped,
        #     ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
        #     self._on_gaze,
        #     VIDEO_QOS,
        #     callback_group=state_cb_group,
        # )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._object_recognition_node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        # Inference bundle publishers (Aria + ROS)
        self.aria_inference_publisher = ROSPublisher(
            "Aria_inference_publisher",
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
        )
        self.ros_inference_publisher = ROSPublisher(
            "ROS_inference_publisher",
            UInt8MultiArray,
            ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS.value,
        )
        self.combined_publisher = ROSPublisher(
            "combined_publisher",
            UInt8MultiArray,
            ROS2Topics.COMBINED_VISUALIZATION.value,
        )
        # Nothing publishes here since T8.7 (it carried LightGlue results). Consider deleting.
        self._match_publisher = ROSPublisher(
            "match_publisher", UInt8MultiArray, ROS2Topics.FEATURE_MATCH_RESULTS.value
        )

        # Mask + centroid publishers (RealSense only)
        self._mask_pub = self._object_recognition_node.create_publisher(
            Image, TOPIC_MASK, 10
        )
        self._centroid_pub = self._object_recognition_node.create_publisher(
            PointStamped, TOPIC_CENTROID_2D, 10
        )
        self._centroid_viz_pub = self._object_recognition_node.create_publisher(
            PointStamped, TOPIC_CENTROID_VIZ, 10
        )

        # TF buffer, publisher
        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(
            self._tf_buffer, self._object_recognition_node
        )
        self._goal_pose_pub = self._object_recognition_node.create_publisher(
            PoseStamped, ROS2Topics.MANIPULATION_GOAL_POSE.value, 10
        )

    # ---------------------------------------------------------------------------
    # ROS callbacks
    # ---------------------------------------------------------------------------

    def _on_camera_info(self, msg: CameraInfo) -> None:
        if self._intrinsics_received:
            return
        self._fx = msg.k[0]
        self._fy = msg.k[4]
        self._cx = msg.k[2]
        self._cy = msg.k[5]
        self._intrinsics_received = True
        # logger.info(
        #     f"Intrinsics received: fx={self._fx:.2f} fy={self._fy:.2f} "
        #     f"cx={self._cx:.2f} cy={self._cy:.2f}"
        # )

    def _on_aria_image(self, msg: CompressedImage) -> None:
        try:
            frame = ImageHelper.uncompress_image(msg.data)
            if frame is None:
                logger.warning("Received empty Aria frame, skipping")
                return
            self._aria_feed.update(frame)
        except Exception as e:
            logger.error(f"Error decoding Aria image: {e}", exc_info=True)

    def _on_realsense_image(self, rgb_msg: Image, depth_msg: Image) -> None:
        if not self._intrinsics_received:
            return
        rgb = np.frombuffer(rgb_msg.data, dtype=np.uint8).reshape(
            rgb_msg.height, rgb_msg.width, -1
        )
        depth = np.frombuffer(depth_msg.data, dtype=np.uint16).reshape(
            depth_msg.height, depth_msg.width
        )
        self._ros_feed.update(rgb, depth, rgb_msg.header)

    def _on_target(self, msg: Target) -> None:
        """Every Target replaces the last. The client sends the word at once with no reference, then
        the same word with the reference once its gaze pick is done. An empty word is stop."""
        reference = None
        if msg.reference.width:
            rows = np.frombuffer(msg.reference.data, np.uint8).reshape(msg.reference.height, msg.reference.step)
            reference = rows[:, :msg.reference.width * 3].reshape(msg.reference.height, msg.reference.width, 3)
        with self._state_lock:
            self.prompt = msg.prompt.strip().lower()
            self._reference = reference

    def _on_gaze(self, msg: PointStamped) -> None:
        with self._state_lock:
            self._gaze_point = (msg.point.x, msg.point.y)

    def _on_prompt(self, msg: String) -> None:
        command = msg.data.strip().lower()
        if not command:
            return
        with self._state_lock:
            if command == AudioStreamingPipelineConfig.STOP_KEYWORD:
                self.prompt = ""
                self._aria_inference_state = None
            elif command != self.prompt:
                self.prompt = command
                self._aria_inference_state = None

    # ---------------------------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------------------------

    def run(self) -> None:
        logger.info("Object recognition pipeline started. Waiting for command...")

        last_ros_id = -1

        try:
            while not self._quit_event.is_set():
                with self._state_lock:
                    prompt = self.prompt
                    reference = self._reference

                if not prompt:
                    time.sleep(0.1)
                    continue

                ros_image, depth, header, ros_id = self._ros_feed.get()

                if ros_id != last_ros_id:
                    last_ros_id = ros_id
                    self._process_ros_frame(ros_image, depth, header, prompt, reference)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error during mask generation: {e}", exc_info=True)
        finally:
            self.cleanup()

    # ---------------------------------------------------------------------------
    # Frame processing
    # ---------------------------------------------------------------------------

    # Unused since T8.5 (the glasses side comes from the client's Target). Consider deleting.
    def _process_aria_frame(
        self,
        aria_image: Optional[np.ndarray],
        prompt: str,
        gaze_point: Optional[Tuple[float, float]],
        aria_inference_state: Optional[Dict[str, Any]],
    ) -> None:
        # if aria_image is None or aria_inference_state is not None:
        #     return

        # Run the SAM model with the prompt to generate masks
        inference_state = self._generate_mask(aria_image, prompt)
        if inference_state is None:
            return

        # All glasses masks are kept. The latest gaze at processing time is stored with them (not
        # the gaze at the picture's capture time: the T2.9 client does that, this matcher does not).
        inference_state["gaze_point"] = gaze_point

        with self._state_lock:
            if self.prompt != prompt:
                logger.debug("Prompt changed during Aria inference, discarding result")
                return
            self._aria_inference_state = inference_state
            self._aria_locked_image = aria_image
            print("Success")

        self._publish_inference(
            self.aria_inference_publisher, aria_image, inference_state
        )

    def _process_ros_frame(
        self,
        ros_image: Optional[np.ndarray],
        depth: Optional[np.ndarray],
        header,
        prompt: str,
        reference: Optional[np.ndarray],
    ) -> None:
        if ros_image is None or depth is None:
            return

        # Run SAM generate masks from the wrist camera
        inference_state = self._generate_mask(ros_image, prompt)
        if inference_state is None:
            return

        with self._state_lock:
            if self.prompt != prompt:
                logger.debug("Prompt changed during ROS inference, discarding result")
                return

        # No reference (word only, or nothing near the gaze): all wrist masks are shown, none matched
        matched = None
        if reference is not None:
            matched = self._find_matching_ros_mask(reference, ros_image, inference_state)
            if matched is not None:
                inference_state = matched

        self._publish_inference(
            self.ros_inference_publisher, ros_image, inference_state
        )
        # self._publish_mask_and_centroid(inference_state, depth, header, ros_image)

        if matched is not None:
            # The reference crop beside the wrist frame. No points (LightGlue is gone since T8.7),
            # no glasses masks and no gaze: the crop is the looked-at object already.
            no_points = np.zeros((0, 2), dtype=int)
            self._publish_combined(ros_image, inference_state, no_points, no_points, reference, {})

    # ---------------------------------------------------------------------------
    # Mask + centroid publishing (RealSense)
    # ---------------------------------------------------------------------------

    def _publish_mask_and_centroid(
        self,
        inference_state: Dict[str, Any],
        depth: np.ndarray,
        header,
        ros_image: np.ndarray,
    ) -> None:
        best_mask, best_score, centroid_px = ObjectMaskVisualizer.get_best_mask(
            inference_state
        )

        if best_mask is None:
            logger.debug("No detection above threshold for mask/centroid publishing")
            return

        # Mono8 mask
        mask_msg = Image()
        mask_msg.header = header
        mask_msg.height, mask_msg.width = best_mask.shape[:2]
        mask_msg.encoding = "mono8"
        mask_msg.step = mask_msg.width
        mask_msg.data = bytes(best_mask.astype(np.uint8).flatten())
        self._mask_pub.publish(mask_msg)
        logger.debug(f"Mask published with score: {best_score:.3f}")

        if centroid_px is None:
            return

        cx_px, cy_px = centroid_px

        # Median depth over valid mask pixels
        depth_vals = depth[best_mask]
        depth_vals = depth_vals[depth_vals > 0]
        if len(depth_vals) == 0:
            logger.warning("No valid depth in mask region, skipping centroid")
            return
        z = float(np.median(depth_vals)) * DEPTH_SCALE

        # 2D centroid + depth
        pt = PointStamped()
        pt.header = header
        pt.header.frame_id = "camera_color_optical_frame"
        pt.point.x = float(cx_px)
        pt.point.y = float(cy_px)
        pt.point.z = z
        self._centroid_pub.publish(pt)

        # Back-projected 3D centroid for visualisation, w.r.t wrist camera
        viz_pt = PointStamped()
        viz_pt.header = header
        viz_pt.header.frame_id = "camera_color_optical_frame"
        viz_pt.point.x = (float(cx_px) - self._cx) * z / self._fx
        viz_pt.point.y = (float(cy_px) - self._cy) * z / self._fy
        viz_pt.point.z = z
        self._centroid_viz_pub.publish(viz_pt)

        logger.debug(f"Centroid published: px=({cx_px}, {cy_px}) depth={z:.3f}m")

        # Base link frame - 3D centroid publishing, w.r.t base of robot
        try:
            stamped_in = PoseStamped()
            stamped_in.header = viz_pt.header
            stamped_in.pose.position.x = viz_pt.point.x
            stamped_in.pose.position.y = viz_pt.point.y
            stamped_in.pose.position.z = viz_pt.point.z
            stamped_in.pose.orientation.w = 1.0
            goal_pose_base = self._tf_buffer.transform(
                stamped_in, "base_link", timeout=rclpy.duration.Duration(seconds=1.0)
            )
            self._goal_pose_pub.publish(goal_pose_base)
            logger.debug(
                f"Goal pose published in base_link: {goal_pose_base.pose.position}"
            )
        except Exception as e:
            logger.warning(f"TF transform to base_link failed: {e}")

    # ---------------------------------------------------------------------------
    # Inference helpers
    # ---------------------------------------------------------------------------

    def _generate_mask(
        self, image: np.ndarray, prompt: str
    ) -> Optional[Dict[str, Any]]:
        inference_state = self.model.process_text_prompt(image, prompt)
        masks = inference_state.get("masks")
        if masks is None or len(masks) == 0:
            logger.debug("No objects detected")
            return None
        logger.debug(f"Found {len(masks)} object(s)")
        return inference_state

    # Unused since T8.7: gaze_pick.pick_mask (with a radius) replaced it. Consider deleting.
    def _find_closest_mask(
        self,
        masks: list,
        gaze_point: Optional[Tuple[float, float]],
    ) -> int:
        if gaze_point is None or len(masks) == 0:
            return 0

        gx, gy = int(round(gaze_point[0])), int(round(gaze_point[1]))

        for i, mask in enumerate(masks):
            m = mask.bool().squeeze()
            if 0 <= gy < m.shape[0] and 0 <= gx < m.shape[1]:
                if m[gy, gx].item():
                    return i

        best_idx = 0
        best_dist = float("inf")

        for i, mask in enumerate(masks):
            m = mask.bool().squeeze()
            ys, xs = torch.where(m)
            if len(ys) == 0:
                continue
            min_dist = ((xs - gx).float() ** 2 + (ys - gy).float() ** 2).min().item()
            if min_dist < best_dist:
                best_dist = min_dist
                best_idx = i

        return best_idx

    def _find_matching_ros_mask(
        self,
        reference: np.ndarray,
        ros_image: np.ndarray,
        ros_inference_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """The wrist mask that is the object in the reference crop (T8.5), as a one-mask state, or
        None: no wrist mask at or above the cutoff, or two within DELTA of each other (a wrist tie)."""
        ros_masks = ros_inference_state.get("masks", [])
        if not len(ros_masks):
            return None

        # Both are RGB in memory: the client cut the reference from the rgb8 glasses image and the
        # wrist camera sends rgb8.
        try:
            ref_vec = l2_normalise(self._clip.encode([reference]))
            ros_vecs = self._embed_masks(ros_image, ros_masks)
        except Exception as e:  # e.g. CUDA out of memory on the shared box: skip this match, keep running
            logger.error(f"CLIP embedding failed: {e}", exc_info=True)
            return None
        scores = ref_vec @ ros_vecs.T   # one row: the reference against each wrist mask
        logger.info(f"CLIP scores, reference x wrist masks: {np.array2string(scores, precision=3)}")

        # One glasses row, so the rule's gaze step has nothing to choose: the client already chose.
        pair = pick_mask_pair(scores, lambda rows: rows[0])
        if pair is None:
            return None
        best_idx = pair[1]
        box = ros_inference_state["boxes"][best_idx].cpu().numpy().round().astype(int).tolist()
        logger.info(f"Matched the reference to wrist mask {best_idx} (box {box}), score {scores[0, best_idx]:.3f}")
        return {
            **ros_inference_state,
            "masks": [ros_masks[best_idx]],
            "scores": [ros_inference_state["scores"][best_idx]],
            "boxes": [ros_inference_state["boxes"][best_idx]],
        }

    def _embed_masks(self, image: np.ndarray, masks: list) -> np.ndarray:
        """One L2-normalised CLIP vector per mask, from the mask's box plus the margin. An empty
        mask gets a zero vector, so it scores 0 against everything."""
        crops = [crop_to_mask(image, m.squeeze(0).cpu().numpy() > 0) for m in masks]
        vecs = l2_normalise(self._clip.encode([image if c is None else c[0] for c in crops]))
        vecs[[c is None for c in crops]] = 0
        return vecs

    # ---------------------------------------------------------------------------
    # Publishing
    # ---------------------------------------------------------------------------

    def _publish_inference(
        self,
        ros_publisher: ROSPublisher,
        image: np.ndarray,
        inference_state: Dict[str, Any],
    ) -> None:
        try:
            success, compressed = ImageHelper.compress_image(image=image)
            if not success:
                logger.warning("Failed to encode image for publishing")
                compressed = None

            state_to_publish = {
                k: v
                for k, v in inference_state.items()
                if k not in ("backbone_out", "masks_logits")
            }

            payload = pickle.dumps(
                {"image": compressed, "inference_state": state_to_publish}
            )

            msg = UInt8MultiArray()
            msg.data = payload
            logger.debug(f"Payload size: {len(payload) / 1024:.1f} KB")
            ros_publisher.publish(msg)
        except Exception as e:
            logger.error(f"Error publishing results: {e}", exc_info=True)

    def _publish_combined(
        self,
        ros_image: np.ndarray,
        inference_state: Dict[str, Any],
        keypoints0: np.ndarray,
        keypoints1: np.ndarray,
        reference_image: np.ndarray,
        aria_inference_state: Dict[str, Any],
        gaze_point: Optional[Tuple[float, float]] = None,
    ) -> None:
        try:
            _, compressed_ros = ImageHelper.compress_image(image=ros_image)
            _, compressed_ref = ImageHelper.compress_image(image=reference_image)

            state_to_publish = {
                k: v
                for k, v in inference_state.items()
                if k not in ("backbone_out", "masks_logits")
            }

            # Gaze now arrives in the undistorted image's pixels, already rotated (T2.9), so it is
            # passed on as is. The old rotation is commented out, not deleted (Dion, 2026-10-14).
            # Delete once T2.9 passes end to end on the live glasses.
            rotated_gaze = gaze_point
            # rotated_gaze = None
            # if gaze_point is not None:
            #     h = reference_image.shape[0]
            #     gx, gy = gaze_point
            #     rotated_gaze = (h - gy, gx)

            payload = pickle.dumps(
                {
                    "image": compressed_ros,
                    "inference_state": state_to_publish,
                    "keypoints0": keypoints0,
                    "keypoints1": keypoints1,
                    "reference_image": compressed_ref,
                    "aria_inference_state": {
                        k: v
                        for k, v in aria_inference_state.items()
                        if k not in ("backbone_out", "masks_logits")
                    },
                    "gaze_point": rotated_gaze,
                }
            )

            msg = UInt8MultiArray()
            msg.data = payload
            self.combined_publisher.publish(msg)
        except Exception as e:
            logger.error(f"Error publishing combined bundle: {e}", exc_info=True)

    # ---------------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------------

    def cleanup(self) -> None:
        self._executor.shutdown()
        self._spin_thread.join(timeout=2.0)
        logger.info("Cleanup complete")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def generate_mask(aria_streaming_started: Event, quit_event: Event) -> None:
    pipeline = ObjectRecognitionPipeline(quit_event=quit_event)
    aria_streaming_started.wait()
    pipeline.run()


if __name__ == "__main__":
    import multiprocessing

    import rclpy

    rclpy.init()  # main.py:34 does this inside the glasses app. Run on its own, nobody else does.
    quit_event = multiprocessing.Event()
    pipeline = ObjectRecognitionPipeline(quit_event=quit_event)
    pipeline.run()

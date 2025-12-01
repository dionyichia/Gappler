import logging
from pathlib import Path
import cv2

from config import ModelConfig, PathConfig, ROSConfig, DetectionConfig
from services.unused.grounding_sam import GroundingSAM
from services.unused.feature_matcher import FeatureMatcher
from services.unused.action_planner import ActionPlanner
from services.unused.image_service import ImageService
from services.unused.eye_tracking_service import EyeTrackingService
from services.unused.ros_service import ROSService
from utils.visualization import Visualizer
from schemas.schemas import GPTRequest, ObjectDetection, ActionPlanRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AriaObjectDetectionPipeline:
    """Main pipeline for Aria object detection and manipulation"""

    def __init__(self):
        # Load configurations
        self.model_config = ModelConfig()
        self.path_config = PathConfig()
        self.ros_config = ROSConfig()
        self.detection_config = DetectionConfig()

        # Initialize services
        self.grounding_sam = GroundingSAM(self.model_config)
        self.feature_matcher = FeatureMatcher()
        self.action_planner = ActionPlanner(str(self.path_config.system_prompt_path))
        self.ros_service = ROSService(self.ros_config)
        self.image_service = ImageService()
        self.eye_tracking_service = EyeTrackingService()
        self.visualizer = Visualizer()

        logger.info("AriaObjectDetectionPipeline initialized successfully")

    def run(self):
        """Main execution loop"""
        logger.info("Waiting for GPT request...")

        # Wait for ROS message with object detection request
        gpt_request_data = self.ros_service.wait_for_gpt_request()
        gpt_request = GPTRequest(**gpt_request_data)
        detections = gpt_request.to_detections()

        logger.info(f"Processing {len(detections)} objects")

        # Process each object
        processed_detections = []
        for i, detection in enumerate(detections):
            logger.info(
                f"Processing object {i+1}/{len(detections)}: {detection.object_name}"
            )

            output_dir = self.path_config.output_dir / str(i)
            processed_detection = self._process_detection(detection, output_dir)
            processed_detections.append(processed_detection)

        # Create action plan request
        action_request = ActionPlanRequest(
            object_names=[d.object_name for d in processed_detections],
            lexemes=[d.lexeme for d in processed_detections],
            positions_2d=[list(d.position_2d) for d in processed_detections],
            question=gpt_request.question,
        )

        # Generate action plan with GPT
        logger.info("Generating action plan with GPT...")
        action_plan = self.action_planner.plan_actions(action_request.to_dict())

        # Publish action plan
        self.ros_service.publish_action(action_plan)

        logger.info("Pipeline completed successfully")
        logger.info(f"Final action plan: {action_plan}")

    def _process_detection(
        self,
        detection: ObjectDetection,
        output_dir: Path,
    ) -> ObjectDetection:
        """
        Process a single object detection

        Args:
            detection: ObjectDetection instance
            output_dir: Directory for output files

        Returns:
            Updated ObjectDetection with position_2d filled
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        realsense_dir = output_dir / "realsense"
        realsense_dir.mkdir(exist_ok=True)

        # Get robot camera image
        robot_image = self.ros_service.get_image_from_topic(
            self.ros_config.color_image_topic
        )
        robot_image_path = realsense_dir / "camera_image.png"
        cv2.imwrite(str(robot_image_path), robot_image)

        # Load AR glasses image
        ar_image = self.image_service.load_pil_image(detection.rgb_path)

        # Process based on lexeme type
        if detection.lexeme == "noun":
            return self._process_noun(
                detection, ar_image, robot_image_path, output_dir, realsense_dir
            )
        elif detection.lexeme == "pronoun":
            return self._process_pronoun(
                detection, ar_image, robot_image_path, output_dir, realsense_dir
            )
        else:
            raise ValueError(f"Unknown lexeme: {detection.lexeme}")

    def _process_noun(
        self,
        detection: ObjectDetection,
        ar_image,
        robot_image_path: Path,
        output_dir: Path,
        realsense_dir: Path,
    ) -> ObjectDetection:
        """Process noun objects (specific objects)"""

        # Determine text prompt
        if detection.object_name == "other object":
            text_prompt = "stuff."
        else:
            text_prompt = f"{detection.object_name}."

        # Detect in AR view
        logger.info(f"Detecting '{text_prompt}' in AR view...")
        masks_ar, boxes_ar = self.grounding_sam.detect_and_segment(
            ar_image,
            text_prompt,
            output_dir,
            box_threshold=self.detection_config.box_threshold,
            text_threshold=self.detection_config.text_threshold,
        )

        if len(masks_ar) == 0:
            logger.warning("No objects detected in AR view")
            return detection

        # Find object using eye tracking
        closest_index = self.eye_tracking_service.find_closest_mask(
            detection.eye_track_path,
            masks_ar,
        )
        detection.bbox = boxes_ar[closest_index].tolist()

        # Match to robot view
        mkpts0, mkpts1, mconf = self.feature_matcher.match_object_between_views(
            detection.rgb_path,
            str(robot_image_path),
            detection.bbox,
            str(output_dir / "superglue.png"),
        )

        # Detect in robot view
        robot_image = self.image_service.load_pil_image(str(robot_image_path))
        masks_robot, boxes_robot = self.grounding_sam.detect_and_segment(
            robot_image,
            text_prompt,
            realsense_dir,
        )

        if len(masks_robot) == 0:
            logger.warning("No objects detected in robot view")
            return detection

        # Find best matching box
        points_per_bbox, max_bbox_index = self.feature_matcher.find_target_in_boxes(
            mkpts1,
            boxes_robot,
        )

        # Get target center
        robot_image_np = self.image_service.load_image(str(robot_image_path))
        annotated_image, target_center = self.visualizer.draw_target_center(
            robot_image_np,
            masks_robot,
            max_bbox_index,
        )

        # Save visualization
        self.image_service.save_image(
            annotated_image,
            str(output_dir / "grasping_point.png"),
        )

        detection.position_2d = tuple(target_center)
        return detection

    def _process_pronoun(
        self,
        detection: ObjectDetection,
        ar_image,
        robot_image_path: Path,
        output_dir: Path,
        realsense_dir: Path,
    ) -> ObjectDetection:
        """Process pronoun objects (this, that, etc.)"""

        if detection.object_name == "other object":
            # Similar to noun processing
            return self._process_noun(
                detection, ar_image, robot_image_path, output_dir, realsense_dir
            )

        elif detection.object_name == "position":
            # User is pointing at a location, not an object
            logger.info("Processing position reference...")

            ar_image_np = self.image_service.load_image(detection.rgb_path)
            mid_point, bbox = self.eye_tracking_service.find_position_bbox(
                detection.eye_track_path,
                ar_image_np.shape[:2],
                box_size=self.detection_config.eye_tracking_box_size,
            )

            detection.bbox = bbox

            # Match to robot view
            mkpts0, mkpts1, mconf = self.feature_matcher.match_object_between_views(
                detection.rgb_path,
                str(robot_image_path),
                detection.bbox,
                str(output_dir / "superglue.png"),
            )

            # Calculate center of matched points
            target_center = self.feature_matcher.calculate_center(mkpts1)

            # Save visualization
            robot_image_np = self.image_service.load_image(str(robot_image_path))
            annotated_image = self.visualizer.draw_eye_tracking_bbox(
                robot_image_np,
                detection.bbox,
            )

            self.image_service.save_image(
                annotated_image,
                str(output_dir / "position.png"),
            )

            detection.position_2d = tuple(target_center)
            return detection

        else:
            raise ValueError(f"Unknown pronoun object_name: {detection.object_name}")


def main():
    """Entry point"""
    try:
        pipeline = AriaObjectDetectionPipeline()
        pipeline.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()

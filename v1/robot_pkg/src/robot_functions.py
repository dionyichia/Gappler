from foundation_pose.PoseEstimationApp import PoseEstimatorApp
from foundation_pose.helper_functions import compute_image_difference_without_mask

import math

class Robot:
    def __init__(self, webcam, maskModel) -> None:
        self.webcam = webcam
        self.maskModel = maskModel
        self.robot = PoseEstimatorApp(reader=self.webcam, maskModel=self.maskModel)
        print("robot initialized correctly")
        self.old_3d = (None, None, None)


    def display_bricks(self):
        _, bricks = self.get_3d_bricks_and_image()
        size_and_colors = [(brick[1], brick[2])
                           for brick in bricks]
        print(f"Detected all bricks in Robot View:\n {size_and_colors} \n")
        return True


    def display_collision_free_bricks(self):
            _, bricks = self.get_3d_bricks_and_image()
            _, free_bricks = self.robot.get_collision_free_bricks_and_grips(bricks)
            size_and_colors = [(brick[1], brick[2]) for brick in free_bricks.values()]
            print(f"Detected all collision-free bricks in Robot View:\n {size_and_colors} \n")
            return True


    def grab_brick_by_center_point(self, target_center, tolerance=50):
            # Get registered bricks and their 3D poses
            registered_bricks, bricks = self.get_3d_bricks_and_image()
            print("bricks recognized")
            # Find brick with closest center point
            closest_brick_idx = None
            min_distance = float('inf')
            x, y = target_center
            for i, box in enumerate(registered_bricks.boxes):
                # Get bounding box center and distance
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                distance = math.hypot(center_x - x, center_y - y)
                print(f"\n distance {distance} to brick {i}\n" )
                if distance < tolerance and distance < min_distance:
                    min_distance = distance
                    closest_brick_idx = i
            
            if closest_brick_idx is None:
                print("no closest brick, return")
                return False
            print(f"closest brick: brick {closest_brick_idx} with \n {bricks[closest_brick_idx]}")
            
            # Find the grip for our target brick
            target_brick = bricks[closest_brick_idx]

            # Get collision-free grips
            grips, _ = self.robot.get_collision_free_bricks_and_grips([target_brick])
            print("collision free bricks computed")

            target_brick_id = target_brick[4]  # brick_class_id
            # print(f"target brick id: {target_brick_id}")
            if target_brick_id not in grips:
                print(f"targeted brick {target_brick_id} can't be grabbed collision-free")
                return False
                
            # grab brick
            best_grip = self.robot.get_best_grip(grips[target_brick_id])
            print("best grip identified")
            success = not self.robot.sort_brick(best_grip, sort_by_color=False)
            if success:
                print(f"Success: The brick at position {target_center} has been sorted.")
                return True
            else:
                print(f"Failed: The brick at position {target_center} could not be sorted.")
                return False
        

    def sort_bricks(self, by_color: bool = False):
        registered_bricks, bricks = self.get_3d_bricks_and_image()
        if not bricks:
            print(f"Success: No bricks detected, no sorting necessary.")
            return
        sort_status = "pending"
        while sort_status == "pending":
            registered_bricks, bricks = self.get_3d_bricks_and_image()
            sort_status = self.robot.start_sort_pipeline(
                registered_bricks, bricks, by_color)
        print(f"Sort status: {sort_status}")


    def get_3d_bricks_and_image(self):
        color_image, depth_image, _ = self.webcam.capture_image()
        registered_bricks = self.maskModel(color_image, iou=0.9, verbose=False)[0]
        score = 0
        old_image, old_registered_bricks, old_bricks = self.old_3d
        if old_image is not None:
            score = compute_image_difference_without_mask(self.old_3d[0], color_image)
        if score > 0.994:
            return old_registered_bricks, old_bricks
        else:
            bricks, _ = self.robot.get_brick_poses(
                registered_bricks,
                color_image,
                depth_image
            )
            self.old_3d = (color_image, registered_bricks, bricks)
            return registered_bricks, bricks
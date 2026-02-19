#  cv2.imshow("Aria + ROS2 Camera Matching", display)

#                     # Handle key presses
#                     key = cv2.waitKey(1) & 0xFF
#                     if key == ord("q"):
#                         break
#                     elif key == ord("m"):
#                         self.toggle_matching()
#                     elif key == ord("v"):
#                         self.toggle_match_visualization()
#                     elif key == ord("s"):
#                         timestamp = time.strftime("%Y%m%d_%H%M%S")
#                         filename = f"feature_match_{timestamp}.png"
#                         cv2.imwrite(filename, display)
#                         logger.info(f"Saved frame to {filename}")
# print("\n=== Dual Stream Feature Matcher ===")
# print("Controls:")
# print("  'q' - Quit")
# print("  'm' - Toggle matching on/off")
# print("  'v' - Toggle match visualization")
# print("  's' - Save current frame")
# print("=" * 30 + "\n")
# cv2.namedWindow("Aria + ROS2 Camera Matching", cv2.WINDOW_NORMAL)

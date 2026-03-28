import cv2
import numpy as np
from cv2 import aruco

# dictionary = aruco.getPredefinedDictionary(aruco.DICT_6X6_250)

# marker_image = aruco.generateImageMarker(dictionary, id=0, sidePixels=500)
# cv2.imwrite("aruco_marker_0.png", marker_image)


dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
detector_params = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(dictionary, detector_params)

TAG_SIZE = 0.15  # your marker's physical size in metres

# 3D corners of the tag in the tag's own coordinate frame
# Order: top-left, top-right, bottom-right, bottom-left
TAG_CORNERS_3D = np.array(
    [
        [-TAG_SIZE / 2, TAG_SIZE / 2, 0],
        [TAG_SIZE / 2, TAG_SIZE / 2, 0],
        [TAG_SIZE / 2, -TAG_SIZE / 2, 0],
        [-TAG_SIZE / 2, -TAG_SIZE / 2, 0],
    ],
    dtype=np.float32,
)


def detect_aruco(frame, camera_matrix, dist_coeffs):
    corners, ids, _ = detector.detectMarkers(frame)

    results = []
    if ids is not None:
        for i, marker_id in enumerate(ids.flatten()):
            img_pts = corners[i][0].astype(np.float32)  # shape (4, 2)

            success, rvec, tvec = cv2.solvePnP(
                TAG_CORNERS_3D,
                img_pts,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE,  # best flag for square markers
            )

            if not success:
                continue

            frame = draw_tag_pose(
                frame, corners[i], rvec, tvec, camera_matrix, dist_coeffs, marker_id
            )

            R, _ = cv2.Rodrigues(rvec)
            T_camera_tag = np.eye(4)
            T_camera_tag[:3, :3] = R
            T_camera_tag[:3, 3] = tvec.flatten()

            results.append(
                {"id": marker_id, "T_camera_tag": T_camera_tag, "corners": corners[i]}
            )

    return results, frame


def draw_tag_pose(frame, corners, rvec, tvec, camera_matrix, dist_coeffs, marker_id):
    # Draw the tag border
    aruco.drawDetectedMarkers(frame, [corners])

    # Draw XYZ axes on the tag (red=X, green=Y, blue=Z)
    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, TAG_SIZE * 0.5)

    # Extract position
    x, y, z = tvec.flatten()

    # Convert rotation vector to Euler angles (degrees)
    R, _ = cv2.Rodrigues(rvec)
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    roll = np.degrees(np.arctan2(R[2, 1], R[2, 2]))
    pitch = np.degrees(np.arctan2(-R[2, 0], sy))
    yaw = np.degrees(np.arctan2(R[1, 0], R[0, 0]))

    # Get tag corner to anchor the text
    corner_px = tuple(corners[0][0].astype(int))

    lines = [
        f"ID: {marker_id}",
        f"X: {x:+.3f}m  Y: {y:+.3f}m  Z: {z:+.3f}m",
        f"R: {roll:+.1f}  P: {pitch:+.1f}  Yaw: {yaw:+.1f} deg",
    ]

    for j, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (corner_px[0], corner_px[1] - 10 - j * 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
        )

    return frame

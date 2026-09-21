class VisualizerConfig:
    DEFAULT_WINDOW_NAME = "RGB Visual Feed"
    DEFAULT_WINDOW_SIZE = (1024, 1024)
    DEFAULT_WINDOW_POSITION = (50, 50)

    # Color definitions (BGR format for OpenCV)
    CV2_COLORS = [
        (0, 0, 255),  # red
        (255, 0, 0),  # blue
        (0, 255, 0),  # green
        (0, 255, 255),  # yellow
        (255, 255, 0),  # cyan
        (255, 0, 255),  # magenta
        (0, 165, 255),  # orange
        (128, 0, 128),  # purple
    ]

    GAZE_POINT_RADIUS = 20
    GAZE_POINT_COLOR = (0, 0, 255)  # Red in BGR

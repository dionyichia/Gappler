import logging
import roslibpy
import cv2
import numpy as np
import base64
from threading import Lock

logger = logging.getLogger(__name__)


class CameraDisplayClient:
    def __init__(self, ros_bridge_ip="localhost", ros_bridge_port=9090):
        """Initialize rosbridge client for camera display"""
        self.client = roslibpy.Ros(host=ros_bridge_ip, port=ros_bridge_port)
        self.bridge_lock = Lock()
        self.latest_image = None

        # Connect to rosbridge
        self.client.run()
        print(f"Connected to rosbridge at {ros_bridge_ip}:{ros_bridge_port}")

        # Subscribe to camera topic
        self.image_subscriber = roslibpy.Topic(
            self.client, "/camera/color/image_raw", "sensor_msgs/Image"
        )
        self.image_subscriber.subscribe(self.image_callback)
        print("Subscribed to /camera/color/image_raw")

    def image_callback(self, message):
        """Callback for receiving image messages"""
        try:
            # Extract image data
            width = message["width"]
            height = message["height"]
            encoding = message["encoding"]

            if not encoding == "rgb8":
                logger.error(f"Decoding RGB8 image")
            data = message["data"]

            # Decode base64 data if necessary
            if isinstance(data, str):
                image_data = base64.b64decode(data)
            else:
                image_data = bytes(data)

            # Convert to numpy array
            image_array = np.frombuffer(image_data, dtype=np.uint8)
            image_array = image_array.reshape((height, width, 3))
            # Convert RGB to BGR for OpenCV
            cv_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

            # Store latest image
            with self.bridge_lock:
                self.latest_image = cv_image

        except Exception as e:
            print(f"Error processing image: {e}")

    def display_loop(self):
        """Display images in a loop"""
        print("Starting display loop. Press 'q' to quit.")

        while True:
            with self.bridge_lock:
                if self.latest_image is not None:
                    cv2.imshow("Camera Feed", self.latest_image)

            # Wait for key press (1ms delay)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        print("Cleaning up...")
        self.image_subscriber.unsubscribe()
        self.client.terminate()
        cv2.destroyAllWindows()
        print("Cleanup complete")


def main():
    # Create camera display client
    camera_client = CameraDisplayClient(ros_bridge_ip="localhost", ros_bridge_port=9090)

    # Start display loop
    try:
        camera_client.display_loop()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        camera_client.cleanup()


if __name__ == "__main__":
    main()

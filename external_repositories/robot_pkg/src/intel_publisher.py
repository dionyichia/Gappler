import cv2
import numpy as np
import time
import zmq



def get_images(webcam, maskModel):
    try:
        color_image, depth_image, depth_colormap = webcam.capture_image()
        registered_bricks = maskModel(color_image, iou=0.9, verbose=False)[0]
        annotated_frame = registered_bricks.plot()

        # Normalize depth image to [0, 255] range for visualization
        depth_image_normalized = cv2.normalize(
            depth_image, None, 0, 255, cv2.NORM_MINMAX)
        
        depth_image_uint8 = depth_image_normalized.astype(np.uint8)
        depth_image_colored = cv2.applyColorMap(
            depth_image_uint8, cv2.COLORMAP_JET)  # Visualize depth with color
        # color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
        # depth_colormap = cv2.cvtColor(depth_colormap, cv2.COLOR_BGR2RGB)
        # annotated_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        return color_image, depth_image_colored, depth_colormap, annotated_frame
    except:
        print("camera is busy")
        return None, None, None, None


def show_webcams(webcam, maskModel):
    # Visualize default image
    def_window = "default image"
    cv2.namedWindow(def_window, cv2.WINDOW_NORMAL)
    cv2.moveWindow(def_window, 100, 100)
    cv2.setWindowProperty(def_window, cv2.WND_PROP_TOPMOST, 1)
    cv2.resizeWindow(def_window, 512, 512)
    # Visualize depth image
    depth_window = "depth image"
    cv2.namedWindow(depth_window, cv2.WINDOW_NORMAL)
    cv2.moveWindow(depth_window, 612, 100)
    cv2.setWindowProperty(depth_window, cv2.WND_PROP_TOPMOST, 1)
    cv2.resizeWindow(depth_window, 512, 512)
    
    # Visualize color map
    cmap_window = "depth color map"
    cv2.namedWindow(cmap_window, cv2.WINDOW_NORMAL)
    cv2.moveWindow(cmap_window, 100, 612)
    cv2.setWindowProperty(cmap_window, cv2.WND_PROP_TOPMOST, 1)
    cv2.resizeWindow(cmap_window, 512, 512)

   # Visualize YOLO image
    yolo_window = "yolo annotation"
    cv2.namedWindow(yolo_window, cv2.WINDOW_NORMAL)
    cv2.moveWindow(yolo_window, 612, 612)
    cv2.setWindowProperty(yolo_window, cv2.WND_PROP_TOPMOST, 1)
    cv2.resizeWindow(yolo_window, 512, 512)

    # Visualization Loop
    while True:
        # Get images from webcam
        color_image, depth_image_colored, depth_colormap, annotated_frame = get_images(webcam, maskModel)
        
        # visualize images with cv2
        cv2.imshow(def_window, color_image)
        cv2.imshow(depth_window, depth_image_colored)
        cv2.imshow(cmap_window, depth_colormap)
        cv2.imshow(yolo_window, annotated_frame)

        key=cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):  # Save images
            # Save images to disk
            path = '/home/panda3/Desktop/thesis_ws/robot_pkg/data/images/'
            cv2.imwrite(path + "color_image.png", color_image)
            cv2.imwrite(path + "depth_image_colored.png", depth_image_colored)
            cv2.imwrite(path + "depth_colormap.png", depth_colormap)
            cv2.imwrite(path + "annotated_frame.png", annotated_frame)
            print(f"Saved images to disk.")
         
    cv2.destroyAllWindows()


def zmq_publish_image(context, webcam, maskModel):
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5560")
    print("ZMQ socket bound, waiting for image request...")

    while True:
        # Wait for request from Aria PC
        message = socket.recv()
        print(f"Received request: {message.decode()}")

        color_image, depth_image_colored, depth_colormap, annotated_frame = get_images(webcam, maskModel)
        if color_image is not None:
            # encode images in bytes to send over ZMQ
            color_bytes = cv2.imencode('.png', color_image)[1].tobytes()
            # depth_bytes = cv2.imencode('.png', depth_image_colored)[1].tobytes()
            # cmap_bytes = cv2.imencode('.png', depth_colormap)[1].tobytes()
            # yolo_bytes = cv2.imencode('.png', annotated_frame)[1].tobytes()

            # Send color image
            socket.send(color_bytes)
            print("Sent image in response")
            socket.close()
            break
        else:
            print("No image captured, retrying...")
            time.sleep(1)   


# from ultralytics import YOLO
# from real_sense_reader import RealSenseReader

# webcam = RealSenseReader()
# maskModel = YOLO('/home/panda3/Desktop/thesis_ws/robot_pkg/data/best.pt')

# show_webcams(webcam, maskModel)
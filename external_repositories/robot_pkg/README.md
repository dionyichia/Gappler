# Robotic Arm component - robot_pkg

A Python library for controlling a robotic arm. This component controls the Franka Emika Panda robotic arm using Deoxys to pick up distinct bricks by position and sort them. Moreover, training data can be used to create newly trained YOLO models.

## Overview

This library is one of three components in a complete multimodal manipulation system developed for a Bachelor's thesis. It specifically handles:

- brick detection using YOLO
- 6D pose estimation using FoundationPose
- computing the optimal grip
- collision checking using pybullet
- manipulation using inverse kinematics and the Deoxys library

## Requirements

- Ubuntu 20
- Python 3.8+
- [FoundationPose](https://github.com/NVlabs/FoundationPose) installation
- [Deoxys](https://github.com/UT-Austin-RPL/deoxys_control) installation
- YOLO model file (`best.pt`)
- Additional dependencies listed in `requirements.txt`
  
## Installation

1. Clone the repository:
```bash
git clone https://github.com/joshopp/robot_pkg.git
cd robot_pkg
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Substitute files from external libraries with our [files to replace](https://https://github.com/joshopp/robot_pkg/tree/main/data/files_to_replace): 
- The deoxys charmander.ymlcontrol_config.yml (in deoxys_control/deoxys/config)
- The deoxys motion_utils.py (in deoxys_control/deoxys/deoxys/experimental) to include the gripper width 
- The Yolo results.py (in ultralytics/ultralytics/engine) and plotting.py(in ultralytics/ultralytics/utils/plotting.py) have been modified to show the match the bounding box color to the brick color 


4. Download required models:
   - Place YOLO mask model `best.pt` in `src/` directory


**Note**: As pytorch3d does not support pip, we had to build and install it from a local clone https://github.com/facebookresearch/pytorch3d
Install Infos: https://github.com/facebookresearch/pytorch3d/blob/main/INSTALL.md 

## Quick Start

### 1. Go to the franka web interface: https://172.16.0.2

### 2. Unlock all joints and activate FCI

### 3. Run the scripts in deoxys_control/deoxys/auto_scripts:   
  ./auto_arm.sh ../config/charmander.yml ../config/control_config.yml  
  ./auto_gripper.sh ../config/charmander.yml ../config/control_config.yml  
  You can use the helper scripts: [run_arm](./src/run_arm.sh) and [run_gripper](./src/run_gripper.sh), if you change the target directory to your version of deoxys.
  
### 4. Start the Interaction System
```bash
cd src
python3 -m start_robot
```

## Configuration

### Camera Calibration
To calibrate the camera (Intel RealSense) mounted on top of the robot, place a camera calibration board on the table and run this script
```bash
python3 -m start_robot --calibrate
```

### YOLO Dataset
To train a new YOLOv8 model for Lego Duplo bricks, run:
```bash
cd src/yolo_segmentation
python3 train.py
```
You can also use a custom dataset

### Image Generation
- Execute in BlenderProc-main: "blenderproc download cc_textures" and copy cc_textures folder into brick_pile_generation
- Copy brick_pile_generation in BlenderProc-main and execute:
```bash
cd brick_pile_generation
python3 loop.py
```
More information [here](https://github.com/joshopp/robot_pkg/tree/main/src/brick_pile_generation/README.md)



## Core Components

### Main Scripts
- **`start_robot.py`**: Main script - run this to start interaction
- **`grobot_functions.py`**: Defines executable functions
- **`real_sense_reader.py`**: Handles image capturing from the Intel RealSense camera
- **`intel_publisher.py`**: Can stream the camera images and published them to the AriaPC via ZMQ


## Architecture
This component operates as part of a three-part system:

1. **[Multimodal data straming component](https://github.com/joshopp/aria_pkg):** Streams and processes data from the Meta Aria glasses
2. **Robot Component (this package):** Handles robot control
3. **[LLM Component](https://github.com/joshopp/llama_pkg):** Manages language understanding and tool calling 
   
The components communicate through a distributed architecture using ZeroMQ for efficient inter-process communication.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Academic Context

This work was developed as part of a Bachelor's thesis on multimodal manipulation systems. If you use this work in academic research, please cite appropriately.

## Contact

**Author**: joshopp  
**Project Link**: [https://github.com/joshopp/aria_pkg](https://github.com/joshopp/aria_pkg)

# Record of how the 2026-08-25 hardware session ran AnyGrasp: the tracker node with
# checkpoint_tracking.tar. main.py launches the detector instead (ros2_robot_ws/src/main.py:28).
# Which one is authoritative is PROJECT_PLAN T1.10. Nothing calls this file.
# Run it from this directory, since the checkpoint path is relative (log/ here).
# Taken from the realman_manip branch 2026-09-21 (T0.0), command line unchanged.
python anygrasp_node.py --checkpoint_path log/checkpoint_tracking.tar --filter oneeuro #--debug
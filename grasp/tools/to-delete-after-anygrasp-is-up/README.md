# Parked: the AnyGrasp tracker node. Consider deleting

Parked 2026-10-13 by T1.10. Delete with T1.27 once the AnyGrasp path grasps on the real arm (T1.17).

- `anygrasp_node.py` runs the AnyGrasp **tracker** (`checkpoint_tracking.tar`), the node from the
  2026-08-25 hardware session. `anygrasp_node.sh` is how that session started it.
- The detector, `grasp/anygrasp_node/anygrasp_detection_node.py`, is the one used (Dion, 2026-10-13):
  stateless per frame, the state machine does its own stability lock, and the replay bench runs it.
- It no longer runs as it is. It reads config section `anygrasp_node`, which `grasp/grasp_config.yaml`
  does not have, and it imports `tracker` from the compiled `.so` left in `grasp/anygrasp_node/`.

If the detector turns out worse on the real arm, this is the fallback to bring back.

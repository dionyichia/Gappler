"""The mapper and camera YAMLs staged for the live T3.5f session (stdlib, static).

The live container mounts docs/sherman_docs/tools/fastlivo/live/config. It must hold the corrected files, byte for byte the reviewed
replay copies, so the live run is the configuration the offline evidence was measured with. The T3.5d pre-correction contrast file stays
(evidence) but must never be what the live runbook names.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
FASTLIVO = REPO / "docs/sherman_docs/tools/fastlivo"
LIVE = FASTLIVO / "live/config"
REPLAY = FASTLIVO / "replay/config"
MAPPER = "t35c_stationary02_20261019_visual.yaml"
CAMERA = "t35c_stationary02_20261019_camera.yaml"
RUNBOOK = REPO / "docs/sherman_docs/t3.5f/T3.5f_LIVE_RUNBOOK_20261020.md"


class LiveConfigTests(unittest.TestCase):
    def test_staged_files_are_byte_identical_to_the_reviewed_replay_copies(self):
        for name in (MAPPER, CAMERA):
            self.assertEqual((LIVE / name).read_bytes(), (REPLAY / name).read_bytes(), name)

    def test_the_mapper_config_carries_the_corrected_extrinsic_and_live_topics(self):
        text = (LIVE / MAPPER).read_text()
        self.assertIn("extrin_calib.extrinsic_T: [-0.011, -0.02329, 0.04412]", text)
        self.assertIn("extrin_calib.extrinsic_R: [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]", text)
        for needle in ('common.img_topic: "/camera/camera/color/image_raw"', 'common.lid_topic: "/livox/lidar"', 'common.imu_topic: "/livox/imu"',
                       "common.img_en: 1", "preprocess.lidar_type: 1", "uav.gravity_align_en: true"):
            self.assertIn(needle, text)

    def test_the_precorrection_contrast_file_is_still_there_and_still_pre_correction(self):
        text = (LIVE / "t35d_contrast_precorrection_visual.yaml").read_text()
        self.assertIn("extrin_calib.extrinsic_T: [0.011, 0.02329, -0.04412]", text)

    def test_the_live_config_folder_holds_exactly_the_three_reviewed_files(self):
        self.assertEqual(sorted(p.name for p in LIVE.iterdir()), sorted([MAPPER, CAMERA, "t35d_contrast_precorrection_visual.yaml"]))

    def test_the_runbook_names_the_corrected_files_and_never_the_contrast_file(self):
        text = RUNBOOK.read_text()
        self.assertIn("T35_MAPPER_CONFIG=%s" % MAPPER, text)
        self.assertIn("T35_CAMERA_CONFIG=%s" % CAMERA, text)
        self.assertNotIn("t35d_contrast_precorrection_visual.yaml", text)
        self.assertEqual(len(re.findall(r"T35_MAPPER_CONFIG=", text)), 1, "one mapper command, one place")


if __name__ == "__main__":
    unittest.main()

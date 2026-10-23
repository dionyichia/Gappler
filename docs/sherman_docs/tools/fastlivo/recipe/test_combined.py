"""Combined-mode guards and inherited-source checks; never starts Docker or ROS."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BASE = 'sha256:2fa9f264ab48a01942b706f1a93a29d798f09d64e2ca7e0c314cf3cc32df81a2'
IMAGE = 't35-fastlivo-visibility-voxel-blind-sqr:experimental'
VIO_SHA = '60f3c99b526af61b20a9aa75dd0397c77dd74bdad37e87ebe1b1380e16ee816c'
HEADER_SHA = '9e3e66edd4f7323a5bd698ce3abdf229ba81486b96a3af66e893362dcb4e7f00'


class CombinedTests(unittest.TestCase):
    def test_fixed_combined_mode_reuses_f2_incremental_path(self):
        wrapper = (HERE / 'run_build.sh').read_text()
        self.assertIn('T35_COMBINED_REPAIR', wrapper, 'combined mode is not implemented')
        self.assertIn('COMBINED_BASE=' + BASE, wrapper)
        self.assertIn(IMAGE, wrapper)
        self.assertIn('t35-fastlivo-visibility-voxel-blind-sqr-build', wrapper)
        self.assertIn('combined build must use a separate image', wrapper)
        self.assertIn('BLIND_ENTRY="$BLIND_ENTRY visibility-voxel"', wrapper)
        self.assertIn('blind-sqr', wrapper.split('sudo docker start -a', 1)[1])
        self.assertIn('IMAGE="${T35_BUILD_IMAGE:-t59-fast-livo2:experimental}"', wrapper)
        self.assertIn('DIAGNOSTIC_BASE=sha256:d0dcfa8a', wrapper)
        for item in ('--network none', '--memory 8g', '--memory-swap 8g', '--cpus 2', '--pids-limit 512'):
            self.assertIn(item, wrapper)

    def test_invalid_combined_options_fail_before_tool_discovery(self):
        wrapper = (HERE / 'run_build.sh').read_text()
        self.assertIn('T35_COMBINED_REPAIR', wrapper, 'combined mode is not implemented')
        cases = [({'T35_COMBINED_REPAIR': '2'}, 'must be 0 or 1')]
        for extra in ({'T35_BLIND_SQR': '1'}, {'T35_VIO_DIAGNOSTIC': '1'},
                      {'T35_VIO_REPAIR': 'visibility-voxel'},
                      {'T35_VIO_DIAGNOSTIC': '1', 'T35_VIO_REPAIR': 'visibility-voxel'}):
            cases.append(({'T35_COMBINED_REPAIR': '1', **extra}, 'combined mode requires other selectors off'))
        for image in ('t59-fast-livo2:experimental', 't35-fastlivo-blind-sqr:experimental',
                      't35-fastlivo-visibility-voxel:experimental', 'docker.io/library/' + IMAGE):
            cases.append(({'T35_COMBINED_REPAIR': '1', 'T35_BUILD_IMAGE': image}, 'separate image'))
        for knob in ('T35_CXXFLAGS_EXTRA', 'T35_LDFLAGS_EXTRA', 'T35_EXTRA_CMAKE_ARGS'):
            cases.append(({'T35_COMBINED_REPAIR': '1', knob: '-arbitrary'}, 'unchanged compiler'))
        for extra, expected in cases:
            env = {k: v for k, v in os.environ.items() if not k.startswith('T35_')}
            env.update(extra)
            result = subprocess.run(['bash', str(HERE / 'run_build.sh')], env=env,
                                    capture_output=True, text=True)
            with self.subTest(options=extra):
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stderr)
                self.assertNotIn('sudo:', result.stderr)

    def test_mode_selection_preserves_existing_image_names(self):
        wrapper = (HERE / 'run_build.sh').read_text()
        self.assertIn('T35_COMBINED_REPAIR', wrapper, 'combined mode is not implemented')
        prefix = wrapper.split('command -v python3', 1)[0]
        cases = [({}, 't59-fastlivo-build', 't59-fast-livo2:experimental', 'bridge'),
                 ({'T35_BLIND_SQR': '1'}, 't35-fastlivo-blind-sqr-build',
                  't35-fastlivo-blind-sqr:experimental', 'none'),
                 ({'T35_VIO_DIAGNOSTIC': '1'}, 't35-fastlivo-vio-diagnostic-build',
                  't35-fastlivo-vio-diagnostic:experimental', 'none'),
                 ({'T35_VIO_DIAGNOSTIC': '1', 'T35_VIO_REPAIR': 'visibility-voxel'},
                  't35-fastlivo-visibility-voxel-build', 't35-fastlivo-visibility-voxel:experimental', 'none'),
                 ({'T35_COMBINED_REPAIR': '1'}, 't35-fastlivo-visibility-voxel-blind-sqr-build', IMAGE, 'none')]
        for extra, name, image, network in cases:
            env = {k: v for k, v in os.environ.items() if not k.startswith('T35_')}
            env.update(extra)
            result = subprocess.run(['bash', '-c', prefix + '\nprintf "%s\\n" "$NAME" "$IMAGE" "$NETWORK"',
                                     str(HERE / 'run_build.sh')], env=env, capture_output=True, text=True)
            with self.subTest(options=extra):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [name, image, network])

    def test_all_patch_suites_are_wrapper_preflight(self):
        wrapper = (HERE / 'run_build.sh').read_text()
        for name in ('test_recipe.py', 'test_diagnostics.py', 'test_visual_fixes.py',
                     'test_blind_sqr.py', 'test_combined.py'):
            self.assertIn('python3 -B ' + name, wrapper)
            self.assertLess(wrapper.index('python3 -B ' + name), wrapper.index('sudo docker create'))

    def test_combined_is_in_bench(self):
        bench = HERE.parents[4] / 'bench' / 'run.sh'
        canonical = HERE.parents[4] / 'docs/sherman_docs/tools/fastlivo/recipe'
        if not bench.is_file() or canonical.resolve() != HERE:
            self.skipTest('standalone staged recipe has no repository bench')
        self.assertIn('recipe/test_combined.py', bench.read_text())

    def test_inherited_visual_hashes_checked_before_patch_and_after_build(self):
        inside = (HERE / 'blind_sqr_inside.sh').read_text()
        self.assertIn('verify_visual_sources()', inside, 'inherited visual source gate missing')
        self.assertIn(VIO_SHA, inside)
        self.assertIn(HEADER_SHA, inside)
        self.assertIn('inherited-visual.sha256', inside)
        self.assertLess(inside.index('\n  verify_visual_sources\n'), inside.index('python3 /opt/recipe/patch_blind_sqr.py'))
        self.assertGreater(inside.rindex('\n  verify_visual_sources\n'), inside.index('colcon build'))
        self.assertIn('--baseline "$BASELINE"', inside)
        for marker in ('[T35_BLIND_SQR]', '[T35_DIAG_RETRIEVE]', '[T35_DIAG_CLOUD]'):
            self.assertIn(marker, inside)
        for forbidden in ('apt-get', 'git fetch', 'git clone'):
            self.assertNotIn(forbidden, inside)

    def visual_gate(self):
        inside = (HERE / 'blind_sqr_inside.sh').read_text()
        self.assertIn('verify_visual_sources() {', inside, 'inherited visual source gate missing')
        return inside.split('verify_visual_sources() {', 1)[1].split('\n}\n', 1)[0]

    def test_inherited_visual_gate_rejects_unknown_sources(self):
        function = self.visual_gate()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'src' / 'fast_livo'
            (root / 'src').mkdir(parents=True)
            (root / 'include').mkdir()
            (root / 'src' / 'vio.cpp').write_text('not reviewed')
            (root / 'include' / 'visual_geometry.h').write_text('not reviewed')
            result = subprocess.run(['bash', '-c', 'set -eo pipefail\nWS="$1"\n'
                                     'verify_visual_sources() {' + function + '\n}\nverify_visual_sources',
                                     'visual-gate', tmp], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('FAILED', result.stdout)

    @unittest.skipUnless(os.environ.get('T35_PINNED_SOURCE_DIR'), 'needs preserved pinned source, no download')
    def test_inherited_visual_gate_accepts_exact_composed_sources(self):
        function = self.visual_gate()
        def load(name):
            spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        source = Path(os.environ['T35_PINNED_SOURCE_DIR'])
        safety = load('patch_vio').transform_vio((source / 'vio.cpp').read_text())
        diagnostic, _ = load('patch_diagnostics').transform(safety, (source / 'LIVMapper.cpp').read_text())
        visual = load('patch_visual_fixes').transform(diagnostic, 'visibility-voxel')
        header = (HERE / 'visual_geometry.h').read_bytes()
        self.assertEqual(hashlib.sha256(visual.encode()).hexdigest(), VIO_SHA)
        self.assertEqual(hashlib.sha256(header).hexdigest(), HEADER_SHA)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'src' / 'fast_livo'
            (root / 'src').mkdir(parents=True)
            (root / 'include').mkdir()
            (root / 'src' / 'vio.cpp').write_text(visual)
            (root / 'include' / 'visual_geometry.h').write_bytes(header)
            command = ['bash', '-c', 'set -eo pipefail\nWS="$1"\n'
                       'verify_visual_sources() {' + function + '\n}\nverify_visual_sources',
                       'visual-gate', tmp]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for rel in ('src/vio.cpp', 'include/visual_geometry.h'):
                path = root / rel
                old = path.read_bytes()
                path.write_bytes(old + b' ')
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, rel)
                path.write_bytes(old)


if __name__ == '__main__':
    unittest.main(verbosity=2)

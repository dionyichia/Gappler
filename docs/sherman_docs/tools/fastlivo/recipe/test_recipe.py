"""Offline recipe checks; no Docker, network, ROS, or hardware execution."""
import importlib.util
from pathlib import Path
import unittest
import copy
import subprocess

ROOT = Path(__file__).resolve().parent


class RecipeTests(unittest.TestCase):
    def test_process_gate_accepts_only_no_matches(self):
        wrapper = (ROOT / 'run_build.sh').read_text()
        function = wrapper.split('check_host_idle() {', 1)[1].split('\n}\n', 1)[0]
        for process_status, expected in ((0, 1), (1, 0), (2, 1)):
            script = (f'pgrep() {{ return {process_status}; }}\n'
                      'check_host_idle() {' + function + '\n}\ncheck_host_idle')
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
            with self.subTest(pgrep_status=process_status):
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_shared_host_gate_precedes_download_and_start(self):
        wrapper = (ROOT / 'run_build.sh').read_text()
        for required in ('flock -n 9', 'pgrep -af',
                         'Runner[.]Worker', 'check_host_idle'):
            self.assertIn(required, wrapper)
        self.assertLess(wrapper.index('flock -n 9'), wrapper.index('sudo docker pull'))
        # Entering the command is the confirmation; no typed custody gate remains.
        self.assertNotIn('read -r -p', wrapper)
        self.assertNotIn('IDLE', wrapper)
        accepted_image_branch = 'check_host_idle\nif [ "$DIAGNOSTIC" = 1 ] || [ "$BLIND_SQR" = 1 ]; then'
        self.assertIn(accepted_image_branch, wrapper)
        self.assertLess(wrapper.index(accepted_image_branch), wrapper.index('sudo docker pull'))
        self.assertIn('check_host_idle\nset +e', wrapper)

    def test_sanitizer_overrides_default_to_reviewed_build(self):
        recipe = (ROOT / 'build_inside.sh').read_text()
        wrapper = (ROOT / 'run_build.sh').read_text()
        self.assertIn('overridden build image requires T35_CXXFLAGS_EXTRA', wrapper)
        recipe = (ROOT / 'build_inside.sh').read_text()
        wrapper = (ROOT / 'run_build.sh').read_text()
        for required in ('T35_CXXFLAGS_EXTRA', 'T35_LDFLAGS_EXTRA', 'T35_EXTRA_CMAKE_ARGS'):
            self.assertIn(required, recipe)
            self.assertIn(required, wrapper)
        self.assertIn('NAME="${T35_BUILD_NAME:-t59-fastlivo-build}"', wrapper)
        self.assertIn('IMAGE="${T35_BUILD_IMAGE:-t59-fast-livo2:experimental}"', wrapper)
        self.assertIn('check_container.py pre "$LOGDIR/pre-inspect.json" "$NAME"', wrapper)
        self.assertIn('check_container.py post "$LOGDIR/post-inspect.json" "$NAME"', wrapper)
        self.assertIn('libasan', recipe)
        self.assertIn('grep -q libasan', recipe)
        self.assertIn('IMAGE="${T35_BUILD_IMAGE:-t59-fast-livo2:experimental}"',
                      (ROOT / 'check_compile.sh').read_text())
        for forbidden in ('-fsanitize=address',):
            self.assertNotIn(forbidden, recipe)
            self.assertNotIn(forbidden, wrapper)

    def test_recipe_contract(self):
        self.assertTrue((ROOT / 'build_inside.sh').is_file(), 'canonical build script missing')
        recipe = (ROOT / 'build_inside.sh').read_text()
        for pin in (
            'a09599a288c56b832114d7ad9e898248a4111d9e',
            '6f213c7fe6be1aff1fc79c7bd6103e3e9bc4a02d',
            '13eb05e4e6dd7a765b934d0c5fd6236676a57b49',
            'f5d9375f84efe2b15bc0a052d3e18482ed13adf4',
        ):
            self.assertIn(pin, recipe)
        for required in (
            'CMAKE_BUILD_PARALLEL_LEVEL=1', 'MAKEFLAGS=-j1', '--parallel 1',
            '--executor sequential', '-DBUILD_TESTING=OFF',
            '-DCMAKE_CXX_STANDARD=17',
            '-Dvikit_common_DIR=/usr/local/lib/cmake/vikit_common',
            'ros-humble-sophus', 'ros-humble-demo-nodes-cpp',
            'ros-humble-compressed-image-transport', 'pkg-config',
            'git fetch --depth 1 origin "$commit"',
            'test "$(git rev-parse HEAD)" = "$commit"',
            'useradd --create-home --uid 10001 user', 'source-pins.txt',
        ):
            self.assertIn(required, recipe)
        for forbidden in ('nproc', '--continue-on-error', 'libmimalloc', 'COPY .', '--privileged'):
            self.assertNotIn(forbidden, recipe)

    def test_wrapper_contract(self):
        self.assertTrue((ROOT / 'run_build.sh').is_file(), 'wrapper missing')
        wrapper = (ROOT / 'run_build.sh').read_text()
        for required in ('sudo -v', 'docker create', 'docker cp', 'docker start -a',
                         'docker commit', '--memory 8g', '--memory-swap 8g',
                         '--cpus 2', '--pids-limit 512', '--network bridge',
                         't59-fastlivo-build', 'docker info', 'RepoDigests',
                         'check_container.py pre', 'check_container.py post',
                         'set -eo pipefail'):
            self.assertIn(required, wrapper)
        for forbidden in ('docker rm', 'docker prune', '--privileged', '--mount',
                          '--volume', '--device', 'timeout ', 'buildx create'):
            self.assertNotIn(forbidden, wrapper)
        self.assertLess(wrapper.index('check_container.py pre'), wrapper.index('docker start -a'))
        self.assertLess(wrapper.index('check_container.py post'), wrapper.index('docker commit'))
        dockerfile = (ROOT / 'Dockerfile').read_text()
        self.assertIn('RUN bash /opt/recipe/build_inside.sh', dockerfile)
        self.assertNotIn('apt-get', dockerfile)

    def test_compile_check_is_read_only_without_nodes(self):
        self.assertTrue((ROOT / 'check_compile.sh').is_file(), 'compile check missing')
        script = (ROOT / 'check_compile.sh').read_text()
        for required in ('--entrypoint bash', '--user user', '--network none',
                         '--read-only', '--cap-drop ALL', '--security-opt no-new-privileges',
                         '--tmpfs /tmp:', 'HOME=/tmp', 'ROS_HOME=/tmp/ros',
                         'ROS_LOG_DIR=/tmp/ros/log', 'ros2 pkg executables fast_livo',
                         'ldd "$binary"'):
            self.assertIn(required, script)
        for forbidden in ('ros2 run', 'ros2 launch', '--rm', '--privileged', '--device'):
            self.assertNotIn(forbidden, script)

    def test_container_limits_fail_closed(self):
        self.assertTrue((ROOT / 'check_container.py').is_file(), 'inspect validator missing')
        spec = importlib.util.spec_from_file_location('check_container', ROOT / 'check_container.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = dict(Memory=8589934592, MemorySwap=8589934592, NanoCpus=2000000000,
                      CpuQuota=0, CpuPeriod=0, PidsLimit=512, Privileged=False,
                      NetworkMode='bridge', Binds=None, Mounts=None, Devices=[],
                      DeviceRequests=None, CapAdd=None, VolumesFrom=None)
        state = dict(Status='created', Running=False, ExitCode=0, OOMKilled=False, Error='')
        data = dict(Name='/t59-fastlivo-build', HostConfig=config, State=state, Mounts=[])
        module.validate(data, 'pre')
        for key, bad in dict(Memory=0, MemorySwap=-1, NanoCpus=0, CpuQuota=100000,
                             PidsLimit=0, Privileged=True, NetworkMode='host',
                             Binds=['/:/host'], Devices=[{}], CapAdd=['ALL'],
                             DeviceRequests=[{}], Mounts=[{}], VolumesFrom=['other']).items():
            mutated = copy.deepcopy(data)
            mutated['HostConfig'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate(mutated, 'pre')
        with self.assertRaises(ValueError):
            module.validate({}, 'pre')
        data['State']['Status'] = 'exited'
        module.validate(data, 'post')
        data['HostConfig']['NetworkMode'] = 'none'
        module.validate(data, 'post', network='none')
        with self.assertRaises(ValueError):
            module.validate(data, 'post')
        with self.assertRaises(ValueError):
            module.validate(data, 'post', network='host')
        data['HostConfig']['NetworkMode'] = 'bridge'
        for key, bad in dict(ExitCode=1, OOMKilled=True, Running=True, Error='failed').items():
            mutated = copy.deepcopy(data)
            mutated['State'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate(mutated, 'post')

    def test_arch_flags_match_prebuilt_pcl_alignment(self):
        spec = importlib.util.spec_from_file_location('patch_cmake', ROOT / 'patch_cmake.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        new_fragments = [new for _, replacements in module.PATCHES.items() for _, new in replacements]
        old_fragments = [old for _, replacements in module.PATCHES.items() for old, _ in replacements]
        # Ubuntu's prebuilt PCL uses 16-byte Eigen alignment (plain malloc/free
        # pair); -march=native would raise ours to 32 bytes (handmade header
        # pair), corrupting VoxelGrid output buffers at teardown (T3.5a ASan
        # diagnosis). No new fragment may reintroduce native-arch codegen.
        self.assertTrue(any('-march=native' in old for old in old_fragments),
                        'expected a replacement anchored on -march=native')
        for new in new_fragments:
            self.assertNotIn('-march=native', new)
        self.assertTrue(any('-O3' in new and '-funroll-loops' in new for new in new_fragments),
                        'x86 Release must keep its remaining optimizations')
        self.assertTrue(any('-mssse3' in new for new in new_fragments),
                        'Vikit must keep its SSE baseline flags')

    def test_guarded_patches(self):
        self.assertTrue((ROOT / 'patch_cmake.py').is_file(), 'patcher missing')
        spec = importlib.util.spec_from_file_location('patch_cmake', ROOT / 'patch_cmake.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for filename, replacements in module.PATCHES.items():
            original = '\n'.join(old for old, _ in replacements)
            expected = '\n'.join(new for _, new in replacements)
            with self.subTest(file=filename):
                self.assertEqual(module.transform(original, replacements), expected)
                self.assertIn('Sophus::Sophus', expected)
                if 'vikit_common/' in filename:
                    self.assertIn('SET(CMAKE_CXX_STANDARD 17)', expected)
                    self.assertIn('IF(BUILD_TESTING)', expected)
                    self.assertNotIn('-std=c++0x', expected)
                    self.assertNotIn('-std=c++11', expected)
                with self.assertRaises(ValueError):
                    module.transform('', replacements)
                with self.assertRaises(ValueError):
                    module.transform(original + '\n' + original, replacements)
                with self.assertRaises(ValueError):
                    module.transform(expected, replacements)

    def test_vio_sampling_patch_is_staged_and_applied_fail_closed(self):
        self.assertTrue((ROOT / 'patch_vio.py').is_file(), 'VIO patch transformer missing')
        self.assertTrue((ROOT / 'patch_sampling.h').is_file(), 'VIO sampling guard header missing')
        spec = importlib.util.spec_from_file_location('patch_vio', ROOT / 'patch_vio.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.PINNED_SHA256,
                         '741f755fcc2ef86f6ab7dda4d5fb242c77b750540d84088ea43bc851cdd6d9eb')
        recipe = (ROOT / 'build_inside.sh').read_text()
        apply_line = 'python3 /opt/recipe/patch_vio.py "$WS/src/fast_livo/src/vio.cpp"'
        self.assertIn(apply_line, recipe)
        self.assertLess(recipe.index('FAST-LIVO2-ROS2.git'), recipe.index(apply_line))
        self.assertLess(recipe.index(apply_line), recipe.index('colcon build'))
        self.assertIn('cp /tmp/vio-candidate/src/vio.cpp "$WS/src/fast_livo/src/vio.cpp"', recipe)
        self.assertIn('cp /tmp/vio-candidate/include/patch_sampling.h "$WS/src/fast_livo/include/patch_sampling.h"', recipe)
        wrapper = (ROOT / 'run_build.sh').read_text()
        self.assertIn('sudo docker cp patch_vio.py "$NAME:/patch_vio.py"', wrapper)
        self.assertIn('sudo docker cp patch_sampling.h "$NAME:/patch_sampling.h"', wrapper)
        self.assertIn('cp /build_inside.sh /patch_cmake.py /patch_vio.py /patch_sampling.h /opt/recipe/', wrapper)
        dockerfile = (ROOT / 'Dockerfile').read_text()
        self.assertIn('COPY build_inside.sh patch_cmake.py patch_vio.py patch_sampling.h /opt/recipe/', dockerfile)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Offline diagnostic-patch checks; never starts Docker, ROS or a build."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent


class DiagnosticTests(unittest.TestCase):
    def module(self):
        path = HERE / 'patch_diagnostics.py'
        self.assertTrue(path.is_file(), 'diagnostic patch generator missing')
        spec = importlib.util.spec_from_file_location('patch_diagnostics', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_source_drift_is_refused(self):
        module = self.module()
        with self.assertRaisesRegex(ValueError, 'source'):
            module.transform('not the reviewed source', 'also not reviewed')

    def test_anchor_drift_is_refused(self):
        module = self.module()
        with self.assertRaises(ValueError):
            module.insert_before('absent', 'anchor', 'counter;')
        with self.assertRaises(ValueError):
            module.insert_before('anchor anchor', 'anchor', 'counter;')
        self.assertEqual(module.insert_before('anchor', 'anchor', 'counter;'),
                         '/* T35_DIAG */ counter;\nanchor')

    def test_build_is_opt_in_and_cannot_replace_acceptance_image(self):
        self.module()
        script = (HERE / 'run_build.sh').read_text()
        self.assertIn('T35_VIO_DIAGNOSTIC', script)
        self.assertIn('t35-fastlivo-vio-diagnostic:experimental', script)
        self.assertIn('diagnostic build must use a separate image', script)
        self.assertIn('DIAGNOSTIC_BASE=sha256:d0dcfa8af10fa8d1b2f1cf42434ab1b763838d798139f266da7bcc65719de8b1', script)
        self.assertIn('diagnostic_inside.sh', script)
        inside = (HERE / 'diagnostic_inside.sh').read_text()
        self.assertNotIn('apt-get', inside)
        self.assertNotIn('git fetch', inside)
        self.assertIn('--packages-select fast_livo', inside)
        self.assertIn('patch_diagnostics.py', inside)
        self.assertIn('vio-diagnostic.sha256', inside)

    def test_bad_modes_and_acceptance_tag_refused_before_docker(self):
        for extra in ({'T35_VIO_DIAGNOSTIC': '2'},
                      {'T35_VIO_DIAGNOSTIC': '1', 'T35_BUILD_IMAGE': 't59-fast-livo2:experimental'},
                      {'T35_VIO_DIAGNOSTIC': '1', 'T35_BUILD_IMAGE': 'docker.io/library/t59-fast-livo2:experimental'},
                      {'T35_VIO_DIAGNOSTIC': '1', 'T35_CXXFLAGS_EXTRA': '-g'}):
            env = {k: v for k, v in os.environ.items() if not k.startswith('T35_')}
            env.update(extra)
            result = subprocess.run(['bash', str(HERE / 'run_build.sh')], env=env,
                                    capture_output=True, text=True)
            with self.subTest(extra=extra):
                self.assertEqual(result.returncode, 1)
                self.assertTrue('must be 0 or 1' in result.stderr
                                or 'diagnostic build must use a separate image' in result.stderr,
                                result.stderr)

    @unittest.skipUnless(os.environ.get('T35_PINNED_SOURCE_DIR'), 'needs preserved pinned source, no download')
    def test_real_sources_are_additions_only_and_fail_closed(self):
        module = self.module()
        spec = importlib.util.spec_from_file_location('patch_vio', HERE / 'patch_vio.py')
        safety = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(safety)
        source = Path(os.environ['T35_PINNED_SOURCE_DIR'])
        vio = safety.transform_vio((source / 'vio.cpp').read_text())
        mapper = (source / 'LIVMapper.cpp').read_text()
        patched = module.transform(vio, mapper)
        for before, after in zip((vio, mapper), patched):
            restored = ''.join(line for line in after.splitlines(keepends=True)
                               if '/* T35_DIAG */' not in line)
            self.assertEqual(restored, before, 'instrumentation changed existing algorithm text')
        self.assertIn('[T35_DIAG_RETRIEVE]', patched[0])
        self.assertIn('shadow_key_hits=', patched[0])
        self.assertIn('photo_reject=', patched[0])
        self.assertIn('[T35_DIAG_CLOUD]', patched[1])
        with self.assertRaises(ValueError):
            module.transform(*patched)
        with self.assertRaises(ValueError):
            module.transform(vio + ' ', mapper)
        self.assertEqual(hashlib.sha256(vio.encode()).hexdigest(), module.VIO_SHA256)


if __name__ == '__main__':
    unittest.main(verbosity=2)

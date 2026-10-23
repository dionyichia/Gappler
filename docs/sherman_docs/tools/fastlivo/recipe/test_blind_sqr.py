"""Offline F2 blind_sqr-patch checks; never starts Docker, ROS or a build."""
import hashlib
import importlib.util
import inspect
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
UPSTREAM_LINE = 'p_pre->blind_sqr = p_pre->blind * p_pre->blind;'


class BlindSqrTests(unittest.TestCase):
    def module(self):
        path = HERE / 'patch_blind_sqr.py'
        self.assertTrue(path.is_file(), 'blind_sqr patch generator missing')
        spec = importlib.util.spec_from_file_location('patch_blind_sqr', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_source_drift_is_refused(self):
        module = self.module()
        with self.assertRaisesRegex(ValueError, 'pinned baseline'):
            module.transform('not the reviewed mapper')

    def test_anchor_drift_is_refused(self):
        module = self.module()
        with self.assertRaises(ValueError):
            module.insert_after('absent', 'anchor', 'counter;')
        with self.assertRaises(ValueError):
            module.insert_after('anchor\nanchor\n', 'anchor', 'counter;')
        self.assertEqual(module.insert_after('anchor\nrest\n', 'anchor', 'added;'),
                         'anchor\n/* T35_BLIND_SQR */ added;\nrest\n')

    def test_combined_baseline_is_explicit_and_hash_gated(self):
        module = self.module()
        self.assertIn('baseline', inspect.signature(module.transform).parameters,
                      'combined baseline selection is not implemented')
        self.assertEqual(module.BASELINES, {
            'pinned': module.MAPPER_SHA256,
            'visibility-voxel': 'ae4d3072bdd18bcb00269ddc42751533165282fa0bdce9bb11a31de138459fdd',
        })
        with self.assertRaises(ValueError):
            module.transform('unreviewed source', baseline='visibility-voxel')
        with self.assertRaises(ValueError):
            module.transform('unreviewed source', baseline='unknown')

    def test_build_is_opt_in_and_cannot_replace_acceptance_image(self):
        self.module()
        wrapper = (HERE / 'run_build.sh').read_text()
        self.assertIn('T35_BLIND_SQR', wrapper)
        self.assertIn('t35-fastlivo-blind-sqr:experimental', wrapper)
        self.assertIn('t35-fastlivo-blind-sqr-build', wrapper)
        self.assertIn('blind_sqr build must use a separate image', wrapper)
        self.assertIn('DIAGNOSTIC_BASE=sha256:d0dcfa8af10fa8d1b2f1cf42434ab1b763838d798139f266da7bcc65719de8b1',
                      wrapper)
        # The accepted-image modes must stay reachable: this mode is additive.
        self.assertIn('diagnostic build must use a separate image', wrapper)
        self.assertIn('IMAGE="${T35_BUILD_IMAGE:-t59-fast-livo2:experimental}"', wrapper)
        inside = (HERE / 'blind_sqr_inside.sh').read_text()
        self.assertNotIn('apt-get', inside)
        self.assertNotIn('git fetch', inside)
        self.assertIn('--packages-select fast_livo', inside)
        self.assertIn('patch_blind_sqr.py', inside)
        self.assertIn('blind-sqr.sha256', inside)
        self.assertIn('strings "$binary"', inside)

    def test_bad_modes_and_acceptance_tag_refused_before_docker(self):
        for extra, expected in (
                ({'T35_BLIND_SQR': '2'}, 'must be 0 or 1'),
                ({'T35_BLIND_SQR': '1', 'T35_VIO_DIAGNOSTIC': '1'}, 'its own mode'),
                ({'T35_BLIND_SQR': '1', 'T35_BUILD_IMAGE': 't59-fast-livo2:experimental'},
                 'separate image'),
                ({'T35_BLIND_SQR': '1', 'T35_BUILD_IMAGE': 'docker.io/library/t35-fastlivo-blind-sqr:experimental'},
                 'separate image')):
            env = {k: v for k, v in os.environ.items() if not k.startswith('T35_')}
            env.update(extra)
            result = subprocess.run(['bash', str(HERE / 'run_build.sh')], env=env,
                                    capture_output=True, text=True)
            with self.subTest(extra=extra):
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stderr)

    @unittest.skipUnless(os.environ.get('T35_PINNED_SOURCE_DIR'), 'needs preserved pinned source, no download')
    def test_real_source_is_addition_only_and_reversible(self):
        module = self.module()
        source = Path(os.environ['T35_PINNED_SOURCE_DIR'])
        mapper = (source / 'LIVMapper.cpp').read_text()
        self.assertEqual(hashlib.sha256(mapper.encode()).hexdigest(), module.MAPPER_SHA256)
        patched = module.transform(mapper)
        restored = ''.join(line for line in patched.splitlines(keepends=True)
                           if module.MARKER not in line)
        self.assertEqual(restored, mapper, 'the patch changed existing source text')
        added = [line for line in patched.splitlines() if module.MARKER in line]
        self.assertEqual(len(added), 4)
        self.assertEqual([line for line in added if UPSTREAM_LINE in line],
                         [module.MARKER + ' ' + UPSTREAM_LINE])
        self.assertTrue(any('[T35_BLIND_SQR]' in line for line in added))
        # Applied once only: the result no longer matches the pinned hash.
        with self.assertRaises(ValueError):
            module.transform(patched)
        with self.assertRaises(ValueError):
            module.transform(mapper + ' ')

    @unittest.skipUnless(os.environ.get('T35_PINNED_SOURCE_DIR'), 'needs preserved pinned source, no download')
    def test_real_combined_source_restores_its_own_base(self):
        module = self.module()
        self.assertIn('baseline', inspect.signature(module.transform).parameters,
                      'combined baseline selection is not implemented')
        source = Path(os.environ['T35_PINNED_SOURCE_DIR'])
        def load(name):
            spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
            loaded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loaded)
            return loaded
        vio = load('patch_vio').transform_vio((source / 'vio.cpp').read_text())
        _, base = load('patch_diagnostics').transform(vio, (source / 'LIVMapper.cpp').read_text())
        self.assertEqual(hashlib.sha256(base.encode()).hexdigest(), module.BASELINES['visibility-voxel'])
        patched = module.transform(base, baseline='visibility-voxel')
        restored = ''.join(line for line in patched.splitlines(keepends=True)
                           if module.MARKER not in line)
        self.assertEqual(restored, base)
        self.assertEqual(sum(module.MARKER in line for line in patched.splitlines()), 4)
        self.assertEqual(patched.count(module.MARKER + ' ' + UPSTREAM_LINE), 1)
        self.assertEqual(patched.count('[T35_DIAG_CLOUD]'), base.count('[T35_DIAG_CLOUD]'))
        for changed in (patched, base + ' ', (source / 'LIVMapper.cpp').read_text()):
            with self.subTest(changed_sha=hashlib.sha256(changed.encode()).hexdigest()):
                with self.assertRaises(ValueError):
                    module.transform(changed, baseline='visibility-voxel')
        with self.assertRaises(ValueError):
            module.transform(base)


if __name__ == '__main__':
    unittest.main(verbosity=2)

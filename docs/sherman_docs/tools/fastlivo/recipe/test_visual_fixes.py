"""Synthetic C++ and source-level regressions; never starts ROS or Docker."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VisualFixTests(unittest.TestCase):
    def patcher(self):
        self.assertTrue((HERE / 'patch_visual_fixes.py').is_file(), 'visual fix generator missing')
        return load('patch_visual_fixes')

    def compile_run(self, program):
        compiler = shutil.which('c++')
        if compiler is None:
            self.skipTest('standalone C++ regression needs a compiler')
        with tempfile.TemporaryDirectory() as directory:
            # A host that cannot compile <cmath> has a broken toolchain (stale macOS
            # Command Line Tools), not a defect here: skip, so --no-skips still fails the box.
            probe = Path(directory) / 'probe.cpp'
            probe.write_text('#include <cmath>\nint main() { return 0; }\n')
            if subprocess.run([compiler, '-std=c++17', str(probe), '-o', str(Path(directory) / 'probe')],
                              capture_output=True).returncode != 0:
                self.skipTest('host C++ toolchain cannot compile <cmath>; fix the compiler setup')
            source = Path(directory) / 'regression.cpp'
            binary = Path(directory) / 'regression'
            source.write_text(program)
            built = subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                    '-I', str(HERE), str(source), '-o', str(binary)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True)

    def test_broken_toolchain_skips_not_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'c++'
            fake.write_text("#!/bin/sh\necho \"fatal error: 'cmath' file not found\" >&2\nexit 1\n")
            fake.chmod(0o755)
            with mock.patch('shutil.which', return_value=str(fake)):
                with self.assertRaises(unittest.SkipTest):
                    self.compile_run('int main() { return 0; }\n')

    def test_camera_visibility_before_projection(self):
        self.assertTrue((HERE / 'visual_geometry.h').is_file(), 'camera-depth predicate missing')
        result = self.compile_run('''#include "visual_geometry.h"
#include <limits>
#include <cassert>
int main() {
  using fast_livo_geometry::inFrontOfCamera;
  const double nan=std::numeric_limits<double>::quiet_NaN();
  const double inf=std::numeric_limits<double>::infinity();
  assert(inFrontOfCamera(0,0,1));
  assert(inFrontOfCamera(-2,3,0.001));
  assert(!inFrontOfCamera(0,0,-1));
  assert(!inFrontOfCamera(0,0,0));
  assert(!inFrontOfCamera(0,0,-0.0));
  assert(!inFrontOfCamera(nan,0,1));
  assert(!inFrontOfCamera(0,inf,1));
  assert(!inFrontOfCamera(0,0,nan));
  assert(!inFrontOfCamera(0,0,inf));
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_drift_and_unknown_stage_refused(self):
        module = self.patcher()
        with self.assertRaises(ValueError):
            module.transform('unknown source', 'visibility')
        with self.assertRaises(ValueError):
            module.transform('unknown source', 'unknown-stage')

    def test_build_modes_are_explicit_and_have_separate_fixed_tags(self):
        wrapper=(HERE / 'run_build.sh').read_text()
        inside=(HERE / 'diagnostic_inside.sh').read_text()
        self.assertIn('T35_VIO_REPAIR',wrapper)
        for tag in ('t35-fastlivo-visibility:experimental','t35-fastlivo-visibility-voxel:experimental'):
            self.assertIn(tag,wrapper)
        self.assertIn('patch_visual_fixes.py',inside)
        self.assertIn('visual-fixes.sha256',inside)
        for extra in ({'T35_VIO_REPAIR':'visibility'},
                      {'T35_VIO_DIAGNOSTIC':'1','T35_VIO_REPAIR':'invalid'},
                      {'T35_VIO_DIAGNOSTIC':'1','T35_VIO_REPAIR':'visibility',
                       'T35_BUILD_IMAGE':'docker.io/library/t59-fast-livo2:experimental'}):
            env={k:v for k,v in os.environ.items() if not k.startswith('T35_')}
            env.update(extra)
            result=subprocess.run(['bash',str(HERE/'run_build.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertTrue('repair' in result.stderr.lower() or 'separate image' in result.stderr,
                            result.stderr)

    @unittest.skipUnless(os.environ.get('T35_PINNED_SOURCE_DIR'), 'needs preserved pinned source, no download')
    def test_real_source_guards_all_seed_paths_and_preserves_other_code(self):
        module = self.patcher()
        root = Path(os.environ['T35_PINNED_SOURCE_DIR'])
        safety = load('patch_vio').transform_vio((root / 'vio.cpp').read_text())
        baseline, _ = load('patch_diagnostics').transform(safety, (root / 'LIVMapper.cpp').read_text())
        visible = module.transform(baseline, 'visibility')
        both = module.transform(baseline, 'visibility-voxel')
        start='void VIOManager::generateVisualMapPoints('
        end='void VIOManager::updateVisualMapPoints('
        body=visible.split(start,1)[1].split(end,1)[0]
        self.assertEqual(body.count('inFrontOfCamera'), 3)
        self.assertEqual(body.count('world2cam(pt_camera)'), 3)
        self.assertNotIn('w2c(pt)', body)
        for path in body.split('V3D pt_camera(')[1:]:
            self.assertLess(path.index('inFrontOfCamera'),path.index('world2cam(pt_camera)'))
            if 'dir.normalize()' in path:
                self.assertLess(path.index('inFrontOfCamera'),path.index('dir.normalize()'))
        self.assertEqual(baseline.split(start)[1].split(end)[1], visible.split(start)[1].split(end)[1])
        self.assertEqual(baseline.count('[T35_DIAG_'), visible.count('[T35_DIAG_'))
        # Visibility-only must leave retrieval/voxel arithmetic unchanged.
        a=baseline.split('void VIOManager::retrieveFromVisualSparseMap(',1)[1].split(start,1)[0]
        b=visible.split('void VIOManager::retrieveFromVisualSparseMap(',1)[1].split(start,1)[0]
        self.assertEqual(a,b)
        for patched in (visible,both):
            with self.assertRaises(ValueError):module.transform(patched,'visibility')
        # Compile the ACTUAL source expressions, not a hand-written replacement.
        def key_function(text, name, function_start, variable, declaration_override=None):
            fragment=text.split(function_start,1)[1]
            declaration=declaration_override or re.search(r'(?:float|int) loc_xyz\[3\];',fragment).group()
            assignment=re.search(r'loc_xyz\[j\] = [^;]+;',fragment).group()
            return ('long long '+name+'(double x) { double voxel_size=0.5; (void)voxel_size; '
                    'double '+variable+'[3]={x,x,x}; '+declaration+
                    ' for(int j=0;j<3;++j) { '+assignment+
                    ' if(loc_xyz[j]<0) loc_xyz[j]-=1.0; } return (long long)loc_xyz[0]; }\n')
        def program(text):
            retrieval=text.split('void VIOManager::retrieveFromVisualSparseMap(',1)[1]
            declaration=re.search(r'(?:float|int) loc_xyz\[3\];',retrieval).group()
            return ('#include <cmath>\n#include <cstdio>\nusing std::floor;\n'+
                    key_function(text,'store','void VIOManager::insertPointIntoVoxelMap(','pt_w')+
                    key_function(text,'lookup','void VIOManager::retrieveFromVisualSparseMap(','pt_w')+
                    key_function(text,'ray','if (raycast_en)','sample_point_w',declaration)+
                    key_function(text,'reference','void VIOManager::updateReferencePatch(','p_w')+
                    '''int main() {
double xs[]={-2.0,-1.1,-1.0,-0.6,-0.5,-0.1,-0.0,0.0,0.1,0.5,1.0,
  std::nextafter(-0.5,-1.0),std::nextafter(-0.5,0.0),-0.50000001,-0.49999999};
for(double x:xs) { if(store(x)!=lookup(x)||store(x)!=ray(x)||store(x)!=reference(x)) {
 std::fprintf(stderr,"voxel mismatch x=%.17g store=%lld lookup=%lld ray=%lld\\n",x,store(x),lookup(x),ray(x)); return 1;
} } return 0; }
''')
        original_result=self.compile_run(program(baseline))
        self.assertNotEqual(original_result.returncode,0,'baseline must reproduce defect')
        self.assertIn('voxel mismatch',original_result.stderr)
        fixed_result=self.compile_run(program(both))
        self.assertEqual(fixed_result.returncode,0,fixed_result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)

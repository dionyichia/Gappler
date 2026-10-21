"""Fail-closed, independently selectable fixes on the reviewed diagnostic source."""
import difflib
import hashlib
from pathlib import Path
import sys
from patch_vio import replace_once

DIAGNOSTIC_SHA256 = '2027ef6f0dc7ab8f393a418c5a2b8676a4c9e4b4ddcdfb2fbc0f7771fd5bf096'
HERE = Path(__file__).resolve().parent


def transform(source: str, stage: str) -> str:
    """Keep visibility-only and cumulative visibility/voxel candidates distinct."""
    if stage not in ('visibility', 'visibility-voxel'):
        raise ValueError('unknown visual repair stage')
    if hashlib.sha256(source.encode()).hexdigest() != DIAGNOSTIC_SHA256:
        raise ValueError('source differs from reviewed diagnostic baseline')
    source = replace_once(source, '#include "patch_sampling.h"\n',
                          '#include "patch_sampling.h"\n#include "visual_geometry.h"\n')
    marker = 'void VIOManager::generateVisualMapPoints('
    end = 'void VIOManager::updateVisualMapPoints('
    prefix, body = source.split(marker, 1)
    body, suffix = body.split(end, 1)
    for declaration in ('    V3D pt = pg[i].point_w;',
                        '    V3D pt = visual_submap->add_from_voxel_map[j].point_w;',
                        '      V3D pt = pt_var.point_w;'):
        indent = declaration[:len(declaration) - len(declaration.lstrip())]
        body = replace_once(body, declaration, declaration + '\n' + indent +
                            'V3D pt_camera(new_frame_->w2f(pt));\n' + indent +
                            'if (!fast_livo_geometry::inFrontOfCamera(pt_camera[0], pt_camera[1], pt_camera[2])) continue;')
    old = 'V2D pc(new_frame_->w2c(pt));'
    if body.count(old) != 3:
        raise ValueError('expected three seed projection sites')
    body = body.replace(old, 'V2D pc(new_frame_->cam_->world2cam(pt_camera));')
    source = prefix + marker + body + end + suffix
    if stage == 'visibility-voxel':
        # Match insertion and the LiDAR plane-map convention, including its
        # legacy negative-boundary behaviour. Do not reindex stored maps.
        start = 'void VIOManager::retrieveFromVisualSparseMap('
        end = 'void VIOManager::computeJacobianAndUpdateEKF('
        prefix, retrieval = source.split(start, 1)
        retrieval, suffix = retrieval.split(end, 1)
        retrieval = replace_once(retrieval, '  int loc_xyz[3];', '  float loc_xyz[3];')
        for variable in ('pt_w', 'sample_point_w'):
            retrieval = replace_once(retrieval, f'loc_xyz[j] = floor({variable}[j] / voxel_size);',
                                      f'loc_xyz[j] = {variable}[j] / voxel_size;')
        source = prefix + start + retrieval + end + suffix
    return source


def write_candidate(source: Path, stage: str, output: Path) -> None:
    """Produce a new tree, diff and hashes, never overwriting input or output."""
    original = source.read_bytes().decode()
    patched = transform(original, stage)
    header = (HERE / 'visual_geometry.h').read_text()
    output.mkdir()
    (output / 'src').mkdir()
    (output / 'include').mkdir()
    (output / 'src/vio.cpp').write_text(patched)
    (output / 'include/visual_geometry.h').write_text(header)
    diff = ''.join(difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
                                       fromfile='a/src/vio.cpp', tofile='b/src/vio.cpp'))
    diff += ''.join(difflib.unified_diff([], header.splitlines(keepends=True),
                                        fromfile='/dev/null', tofile='b/include/visual_geometry.h'))
    (output / 'source.patch').write_text(diff)
    (output / 'visual-fixes.sha256').write_text(
        hashlib.sha256(patched.encode()).hexdigest() + '  src/vio.cpp\n' +
        hashlib.sha256(header.encode()).hexdigest() + '  include/visual_geometry.h\n')
    (output / 'stage.txt').write_text(stage + '\n')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: patch_visual_fixes.py DIAGNOSTIC_VIO_CPP STAGE NEW_OUTPUT_DIR')
    write_candidate(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))

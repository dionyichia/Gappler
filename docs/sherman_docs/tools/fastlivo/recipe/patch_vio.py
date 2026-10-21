"""Fail-closed candidate generation for the pinned FAST-LIVO2 forward sampler."""
import difflib
import hashlib
from pathlib import Path
import sys

PINNED_SHA256 = '741f755fcc2ef86f6ab7dda4d5fb242c77b750540d84088ea43bc851cdd6d9eb'
HERE = Path(__file__).resolve().parent


def replace_once(text: str, old: str, new: str) -> str:
    """Refuse source drift rather than guessing where to apply a safety change."""
    if text.count(old) != 1:
        raise ValueError('expected exactly one source fragment: ' + repr(old))
    return text.replace(old, new, 1)


def transform_vio(source: str) -> str:
    """Guard updateState and empty-frame gain reuse; never accept patched input."""
    if hashlib.sha256(source.encode()).hexdigest() != PINNED_SHA256:
        raise ValueError('vio.cpp differs from the reviewed pinned source; refusing patch')
    marker = 'void VIOManager::updateState(cv::Mat img, int level)'
    end = 'void VIOManager::updateFrameState(StatesGroup state)'
    prefix, rest = source.split(marker, 1)
    forward, suffix = rest.split(end, 1)
    prefix = replace_once(prefix, '#include "vio.h"\n', '#include "vio.h"\n#include "patch_sampling.h"\n#include <stdexcept>\n')
    prefix = replace_once(prefix, '''void VIOManager::computeJacobianAndUpdateEKF(cv::Mat img)
{
  if (total_points == 0) return;
''', '''void VIOManager::computeJacobianAndUpdateEKF(cv::Mat img)
{
  if (total_points == 0) return;
  // No accepted measurement this frame must not reuse the previous frame's gain.
  G.setZero();
''')
    forward = replace_once(forward, '  if (total_points == 0) return;\n', '''  if (total_points == 0) return;
  if (img.type() != CV_8UC1 || img.cols != width || img.rows != height ||
      img.step != static_cast<size_t>(width))
    throw std::invalid_argument("VIO patch sampling requires tightly packed grayscale at configured dimensions");
''')
    forward = replace_once(forward, '''  for (int iteration = 0; iteration < max_iterations; iteration++)
  {
    double t1''', '''  for (int iteration = 0; iteration < max_iterations; iteration++)
  {
    // A patch rejected at this iteration must not retain earlier residual/Jacobian rows.
    z.setZero();
    H_sub.setZero();
    double t1''')
    forward = replace_once(forward, '      int v_ref_i = floorf(pc[1] / scale) * scale;\n', '''      int v_ref_i = floorf(pc[1] / scale) * scale;
      // The fixed camera border does not include the point's extra search level.
      if (!fast_livo_sampling::patchSamplingInBounds(u_ref_i, v_ref_i, patch_size, scale, width, height)) continue;
''')
    forward = replace_once(forward, '    error = error / n_meas;\n', '''    if (n_meas == 0)
    {
      (*state) = old_state;
      break;
    }
    error = error / n_meas;
''')
    return prefix + marker + forward + end + suffix


def write_candidate(source: Path, output: Path) -> None:
    """Generate a new standalone patch tree without touching the source or an image."""
    original = source.read_bytes().decode('utf-8')
    patched = transform_vio(original)
    header = (HERE / 'patch_sampling.h').read_text()
    diff = ''.join(difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
                                       fromfile='a/src/vio.cpp', tofile='b/src/vio.cpp'))
    diff += ''.join(difflib.unified_diff([], header.splitlines(keepends=True),
                                        fromfile='/dev/null', tofile='b/include/patch_sampling.h'))
    output.mkdir()  # Existing output is refused; no replacement or deletion.
    (output / 'src').mkdir()
    (output / 'include').mkdir()
    (output / 'src/vio.cpp').write_text(patched)
    (output / 'include/patch_sampling.h').write_text(header)
    (output / 'source.patch').write_text(diff)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python3 patch_vio.py PINNED_VIO_CPP NEW_OUTPUT_DIRECTORY')
    write_candidate(Path(sys.argv[1]), Path(sys.argv[2]))

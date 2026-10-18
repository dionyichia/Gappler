"""Add counters to reviewed mapper sources; no existing source line is changed."""
import difflib
import hashlib
from pathlib import Path
import sys

VIO_SHA256 = '9a2398ee931be64324e36b52f8b254132ef2117d31b24cf169072462d0cee2de'
MAPPER_SHA256 = '815b5f8996f245e0d4a3ec79ca42861610e94d5057f8295a17ad1ae5731cc559'
MARKER = '/* T35_DIAG */'


def insert_before(source: str, anchor: str, addition: str) -> str:
    """Fail closed on missing/ambiguous anchors; tag every added line for audit."""
    if source.count(anchor) != 1:
        raise ValueError('expected one source anchor: ' + repr(anchor))
    tagged = ''.join(MARKER + ' ' + line + '\n' for line in addition.splitlines())
    return source.replace(anchor, tagged + anchor, 1)


def transform(vio: str, mapper: str) -> tuple[str, str]:
    """Accept only the safety-patched VIO source and unchanged pinned mapper."""
    for source, expected in ((vio, VIO_SHA256), (mapper, MAPPER_SHA256)):
        if hashlib.sha256(source.encode()).hexdigest() != expected:
            raise ValueError('source differs from reviewed diagnostic baseline')
    start = 'void VIOManager::retrieveFromVisualSparseMap('
    end = 'void VIOManager::computeJacobianAndUpdateEKF('
    prefix, body = vio.split(start, 1)
    body, suffix = body.split(end, 1)
    body = insert_before(body, '  if (feat_map.size() <= 0) return;', '''  unsigned long long diag_key_queries=0, diag_key_hits=0, diag_shadow_key_hits=0;
  unsigned long long diag_projected=0, diag_visible=0, diag_grids=0;
  unsigned long long diag_null=0, diag_noobs=0, diag_behind=0;
  unsigned long long diag_depth=0, diag_normal=0, diag_ncc=0, diag_photo=0;
  if (feat_map.size() <= 0) std::cout << "[T35_DIAG_RETRIEVE] empty_map=1" << std::endl;''')
    body = insert_before(body, '    VOXEL_LOCATION position(loc_xyz[0], loc_xyz[1], loc_xyz[2]);', '''    ++diag_key_queries;
    VOXEL_LOCATION diag_current(loc_xyz[0], loc_xyz[1], loc_xyz[2]);
    if (feat_map.find(diag_current) != feat_map.end()) ++diag_key_hits;
    // Shadow only: reproduce insertion's float/truncate key, never select it.
    float diag_q[3];
    for (int j=0; j<3; ++j) { diag_q[j]=pt_w[j]/voxel_size; if (diag_q[j]<0) diag_q[j]-=1.0; }
    VOXEL_LOCATION diag_shadow((int64_t)diag_q[0], (int64_t)diag_q[1], (int64_t)diag_q[2]);
    if (feat_map.find(diag_shadow) != feat_map.end()) ++diag_shadow_key_hits;''')
    visible_path, raycast_path = body.split('  // RayCasting Module', 1)
    visible_path = insert_before(visible_path, '        if (pt == nullptr) continue;', '        if (pt == nullptr) ++diag_null;')
    visible_path = insert_before(visible_path, '        if (pt->obs_.size() == 0) continue;', '        if (pt->obs_.size() == 0) ++diag_noobs;')
    visible_path = insert_before(visible_path, '        if (dir[2] < 0) continue;', '        if (dir[2] < 0) ++diag_behind;')
    visible_path = insert_before(visible_path, '        if (new_frame_->cam_->isInFrame(pc.cast<int>(), border))', '''        ++diag_projected;
        if (new_frame_->cam_->isInFrame(pc.cast<int>(), border)) ++diag_visible;''')
    body = visible_path + '  // RayCasting Module' + raycast_path
    body = insert_before(body, '      VisualPoint *pt = retrieve_voxel_points[i];', '      ++diag_grids;')
    body = insert_before(body, '      if (depth_continous) continue;', '      if (depth_continous) ++diag_depth;')
    body = insert_before(body, '      if (!pt->is_normal_initialized_) continue;', '      if (!pt->is_normal_initialized_) ++diag_normal;')
    body = insert_before(body, '        if (ncc < ncc_thre)', '        if (ncc < ncc_thre) ++diag_ncc;')
    body = insert_before(body, '      if (error > outlier_threshold * patch_size_total) continue;',
                         '      if (error > outlier_threshold * patch_size_total) ++diag_photo;')
    body = insert_before(body, '  printf("[ VIO ] Retrieve %d points from visual sparse map\\n", total_points);', '''  std::cout << "[T35_DIAG_RETRIEVE] empty_map=0 key_queries=" << diag_key_queries
    << " key_hits=" << diag_key_hits << " shadow_key_hits=" << diag_shadow_key_hits
    << " projected=" << diag_projected << " visible=" << diag_visible << " grids=" << diag_grids
    << " null_reject=" << diag_null << " noobs_reject=" << diag_noobs << " behind_reject=" << diag_behind
    << " depth_reject=" << diag_depth << " normal_reject=" << diag_normal
    << " ncc_reject=" << diag_ncc << " photo_reject=" << diag_photo
    << " accepted=" << total_points << std::endl;''')
    vio = prefix + start + body + end + suffix
    mapper = insert_before(mapper, '  /*** Publish Frame ***/', '''  if (LidarMeasures.lio_vio_flg == VIO)
    std::cout << "[T35_DIAG_CLOUD] source_points=" << pcl_wait_pub->size()
      << " coloured_points=" << laserCloudWorldRGB->size() << " pub_scan_num=" << pub_scan_num << std::endl;''')
    return vio, mapper


def write_candidate(source_dir: Path, output: Path) -> None:
    """Write a new candidate tree and diff, refusing to overwrite any directory."""
    names = ('vio.cpp', 'LIVMapper.cpp')
    original = tuple((source_dir / name).read_bytes().decode() for name in names)
    patched = transform(*original)
    output.mkdir()
    (output / 'src').mkdir()
    diff = []
    hashes = []
    for name, before, after in zip(names, original, patched):
        (output / 'src' / name).write_text(after)
        diff.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                        fromfile='a/src/' + name, tofile='b/src/' + name))
        hashes.append(hashlib.sha256(after.encode()).hexdigest() + '  src/' + name + '\n')
    (output / 'source.patch').write_text(''.join(diff))
    (output / 'vio-diagnostic.sha256').write_text(''.join(hashes))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: patch_diagnostics.py SAFETY_PATCHED_SOURCE_DIR NEW_OUTPUT_DIR')
    write_candidate(Path(sys.argv[1]), Path(sys.argv[2]))

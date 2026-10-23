"""Restore upstream's blind_sqr assignment in the pinned mapper.

Finding F2 (`T3.5_CONFIG_SWEEP_20261019.md`): the ROS 2 port dropped upstream's
`p_pre->blind_sqr = p_pre->blind * p_pre->blind`, so the AVIA/CustomMsg range
gate compared against an never-assigned member. This generator adds that line
back, plus one tagged stdout line that reports the threshold actually in force,
and nothing else.
"""
import argparse
import difflib
import hashlib
from pathlib import Path

MAPPER_SHA256 = '815b5f8996f245e0d4a3ec79ca42861610e94d5057f8295a17ad1ae5731cc559'
BASELINES = {
    'pinned': MAPPER_SHA256,
    'visibility-voxel': 'ae4d3072bdd18bcb00269ddc42751533165282fa0bdce9bb11a31de138459fdd',
}
MARKER = '/* T35_BLIND_SQR */'
# Unique in the pinned file: the last read of the constructor's parameter block,
# which is exactly where upstream computes blind_sqr.
ANCHOR = '  this->node->get_parameter("publish.dense_map_en", dense_map_en);'
ADDITION = '''// F2: restore the line the port dropped; without it the gate at
// preprocess.cpp:194 reads an uninitialised member (config sweep 2026-10-19).
p_pre->blind_sqr = p_pre->blind * p_pre->blind;
std::cout << "[T35_BLIND_SQR] blind=" << p_pre->blind << " blind_sqr=" << p_pre->blind_sqr << std::endl;'''


def insert_after(source: str, anchor: str, addition: str) -> str:
    """Fail closed on missing/ambiguous anchors; tag every added line for audit."""
    if source.count(anchor) != 1:
        raise ValueError('expected one source anchor: ' + repr(anchor))
    tagged = ''.join(MARKER + ' ' + line + '\n' for line in addition.splitlines())
    return source.replace(anchor + '\n', anchor + '\n' + tagged, 1)


def transform(mapper: str, baseline: str = 'pinned') -> str:
    """Accept only the explicitly selected, byte-identical reviewed baseline."""
    if baseline not in BASELINES:
        raise ValueError('unknown mapper baseline: ' + repr(baseline))
    if hashlib.sha256(mapper.encode()).hexdigest() != BASELINES[baseline]:
        raise ValueError('mapper source differs from the ' + baseline + ' baseline')
    return insert_after(mapper, ANCHOR, ADDITION)


def write_candidate(source_dir: Path, output: Path, baseline: str = 'pinned') -> None:
    """Write the patched source, its diff and its hash; never overwrite a directory."""
    name = 'LIVMapper.cpp'
    original = (source_dir / name).read_bytes().decode()
    patched = transform(original, baseline)
    output.mkdir()
    (output / 'src').mkdir()
    (output / 'src' / name).write_text(patched)
    diff = difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
                               fromfile='a/src/' + name, tofile='b/src/' + name)
    (output / 'source.patch').write_text(''.join(diff))
    (output / 'blind-sqr.sha256').write_text(
        hashlib.sha256(patched.encode()).hexdigest() + '  src/' + name + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--baseline', choices=tuple(BASELINES), default='pinned')
    args = parser.parse_args()
    write_candidate(args.source_dir, args.output, args.baseline)

"""Pinned-mapper callback evidence, not estimator-completion instrumentation."""
from collections import Counter
from contextlib import closing
import math
from pathlib import Path
import re
import sqlite3
import struct

ROLE_PATTERNS = {
    'lidar': re.compile(r'Get LiDAR, its header time: ([0-9]+\.[0-9]{6})'),
    'imu': re.compile(r'get imu at time: ([0-9]+\.[0-9]{6})'),
    'image': re.compile(r'Get image, its header time: ([0-9]+\.[0-9]{6})'),
}
# The reviewed public raw bag's topic names; unchanged as the default mapping.
PATTERNS = {'/livox/lidar': ROLE_PATTERNS['lidar'],
            '/livox/imu': ROLE_PATTERNS['imu'],
            '/left_camera/image': ROLE_PATTERNS['image']}


def callback_patterns(params: dict) -> dict:
    """Role-driven log patterns for the staged config's own topic names.

    img_en=0 selects ONLY_LIO: no camera callback is expected, so an image line
    in the log stays an unmatched source event instead of expected coverage.
    """
    patterns = {params['common.lid_topic']: ROLE_PATTERNS['lidar'],
                params['common.imu_topic']: ROLE_PATTERNS['imu']}
    if params['common.img_en']:
        patterns[params['common.img_topic']] = ROLE_PATTERNS['image']
    return patterns


def playback_rate(value: str, duration: float) -> float:
    """Allow slower playback only when startup/drain still fit the existing window."""
    rate = float(value)
    if not math.isfinite(rate) or not 0 < rate <= 0.25:
        raise ValueError('T35_REPLAY_RATE must be finite, positive and no faster than 0.25')
    if not math.isfinite(duration) or duration <= 0 or duration / rate + 60 + 120 + 10 > 600:
        raise ValueError('playback plus 60s startup/120s drain/10s cleanup exceeds 600s budget')
    return rate


def expected_callbacks(database: Path, topics: dict, image_offset: float,
                       image_topic: str = '/left_camera/image') -> dict:
    """Read only CDR1 Header prefixes; every played type starts with Header.

    Every played topic must exist in the bag with its exact type; topics the
    mapper does not play are skipped here and accounted separately from bag
    metadata. Match the source's %.6f logs, including its configured image
    offset. This is microsecond-resolution callback evidence, not full
    serialized-message proof.
    """
    if not math.isfinite(image_offset):
        raise ValueError('nonfinite image offset')
    expected = {name: Counter() for name in topics}
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT id,name,type,serialization_format FROM topics').fetchall()
        present = {name: typ for _, name, typ, _ in rows}
        if {name: present.get(name) for name in topics} != topics:
            raise ValueError('bag is missing a reviewed input topic or its exact type')
        for topic_id, name, _, encoding in rows:
            if name not in expected:
                continue
            if encoding != 'cdr':
                raise ValueError('expected CDR serialization')
            offset = image_offset if name == image_topic else 0.0
            for (header,) in db.execute('SELECT substr(data,1,12) FROM messages WHERE topic_id=?', (topic_id,)):
                if len(header) != 12 or header[:4] not in (b'\x00\x01\x00\x00', b'\x00\x00\x00\x00'):
                    raise ValueError('unsupported or truncated CDR1 header')
                endian = '<' if header[1] == 1 else '>'
                sec, nsec = struct.unpack(endian + 'iI', header[4:])
                if sec < 0 or nsec >= 10**9:
                    raise ValueError('invalid sensor timestamp')
                # stamp2Sec uses rclcpp::Time::seconds(): chrono converts the
                # combined int64 nanoseconds to double, then divides by 1e9.
                # Split sec/nsec arithmetic differs at six-decimal boundaries.
                stamp = float(sec * 10**9 + nsec) / 1e9 + offset
                expected[name][f'{stamp:.6f}'] += 1
            if not expected[name]:
                raise ValueError('bag input topic is empty: ' + name)
    return expected


class CallbackTracker:
    """Incrementally reconcile pinned callback log stamps with bag header stamps."""

    def __init__(self, expected: dict, patterns: dict = None):
        self.expected = expected
        self.patterns = PATTERNS if patterns is None else patterns
        self.observed = {name: Counter() for name in expected}
        self.last = {name: None for name in expected}
        self.offset = 0
        self.pending = b''

    def update(self, log: Path) -> None:
        """Consume new complete lines only; missing prelaunch log is normal."""
        if not log.exists():
            return
        with log.open('rb') as source:
            source.seek(self.offset)
            data = source.read()
            self.offset = source.tell()
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for raw in lines:
            line = raw.decode(errors='replace')
            for name, counts in self.observed.items():
                pattern = self.patterns.get(name)
                match = pattern.search(line) if pattern is not None else None
                if match:
                    stamp = match.group(1)
                    counts[stamp] += 1
                    self.last[name] = stamp
                    break

    def tails_seen(self) -> bool:
        """A terminal callback is only a drain heuristic; gaps still fail coverage."""
        return all(seen[max(expected, key=float)] >= expected[max(expected, key=float)]
                   for name, expected in self.expected.items()
                   for seen in (self.observed[name],))

    def summary(self) -> dict:
        """Bound report size while retaining total gaps and representative stamps."""
        result = {}
        for name, expected in self.expected.items():
            seen = self.observed[name]
            missing, unexpected = expected - seen, seen - expected
            result[name] = {
                'expected': sum(expected.values()), 'observed': sum(seen.values()),
                'matched': sum((expected & seen).values()),
                'missing': sum(missing.values()), 'unexpected': sum(unexpected.values()),
                'last_callback_stamp': self.last[name],
                'expected_last_stamp': max(expected, key=float),
                'missing_stamp_examples': list(missing)[:5],
                'unexpected_stamp_examples': list(unexpected)[:5],
            }
        return result


def drain_state(now: float, deadline: float, last_activity: float, satisfied: bool) -> str:
    """Never extend custody; five quiet log seconds do not prove estimator idle."""
    if now >= deadline:
        return 'timeout'
    if satisfied and now - last_activity >= 5:
        return 'callbacks_quiet'
    return 'waiting'


def prestart_allowance(imu_expected_count: int, duration_seconds: float) -> int:
    """Bound the startup race window: at most one 10 Hz lidar period of IMU.

    Pinned imu_cbk drops IMU processed before the first lidar callback, before
    logging. Only a strict timestamp prefix within this bound is reconcilable;
    anything else stays missing.
    """
    if (type(imu_expected_count) is not int or imu_expected_count <= 0
            or not math.isfinite(duration_seconds) or duration_seconds <= 0):
        raise ValueError('prestart allowance needs a positive IMU count and duration')
    return math.ceil(imu_expected_count / duration_seconds * 0.1)


def reconcile_imu(seen: Counter, expected: Counter, allowance: int) -> dict:
    """Split IMU gaps into explained prestart drops vs real coverage failures."""
    missing = expected - seen
    unexpected = seen - expected
    row = {'prestart_drops': 0, 'missing': sum(missing.values()),
           'unexpected': sum(unexpected.values())}
    if not missing or unexpected or sum(missing.values()) > allowance:
        return row
    matched = expected & seen
    if matched and max(missing, key=float) < min(matched, key=float):
        row['prestart_drops'] = row['missing']
        row['missing'] = 0
    return row


def reconcile_rows(tracker: 'CallbackTracker', imu_topic: str, allowance: int) -> dict:
    """Summary rows with the bounded IMU-prestart reconciliation applied once."""
    rows = tracker.summary()
    imu_row = rows[imu_topic]
    reconciled = reconcile_imu(tracker.observed[imu_topic], tracker.expected[imu_topic],
                               allowance)
    imu_row.update(prestart_allowance=allowance, **reconciled)
    if reconciled['prestart_drops'] and not reconciled['missing']:
        imu_row['missing_stamp_examples'] = []
    return rows


def terminal_message_gap(rows: dict, lidar_topic: str) -> dict:
    """Return the one end-of-bag loss that provably cannot reach any VIO frame.

    The player exits at EOF and can leave the bag's final sample unacknowledged.
    Only that sample is inert: it postdates the last LiDAR callback, and VIO runs
    per scan, so no frame can consume it. Every other shape -- an earlier gap, a
    second missing message, any duplicate, or an incomplete LiDAR stream -- stays
    a coverage failure. Returns the recorded allowance, or None when not met.
    """
    if not isinstance(rows, dict) or lidar_topic not in rows:
        return None
    lidar = rows[lidar_topic]
    if not isinstance(lidar, dict) or any(key not in lidar
                                          for key in ('missing', 'unexpected',
                                                      'last_callback_stamp')):
        return None
    if lidar['missing'] or lidar['unexpected'] or lidar['last_callback_stamp'] is None:
        return None
    gap = None
    for name, row in rows.items():
        if not isinstance(row, dict) or any(key not in row
                                            for key in ('missing', 'unexpected',
                                                        'expected_last_stamp')):
            return None
        if row['unexpected']:
            return None
        if name == lidar_topic or not row['missing']:
            continue
        if (gap is not None or row['missing'] != 1 or row['expected_last_stamp'] is None
                or row.get('missing_stamp_examples') != [row['expected_last_stamp']]):
            return None
        after = float(row['expected_last_stamp']) - float(lidar['last_callback_stamp'])
        if not after > 0:
            return None
        gap = {'topic': name, 'stamp': row['expected_last_stamp'],
               'seconds_after_last_lidar': round(after, 6)}
    return gap


CLOUD_DIAG = re.compile(r'\[T35_DIAG_CLOUD\] source_points=(\d+) coloured_points=(\d+)')


def parse_cloud_diag(lines) -> dict:
    """Summarise the mapper's own per-VIO-frame coloured-cloud log lines."""
    frames, zero_sources = 0, []
    for line in lines:
        match = CLOUD_DIAG.search(line)
        if match:
            frames += 1
            if int(match.group(2)) == 0:
                zero_sources.append(int(match.group(1)))
    return {'frames': frames, 'zero_coloured': len(zero_sources),
            'zero_source_min': min(zero_sources, default=None),
            'zero_source_max': max(zero_sources, default=None)}


def coloured_empty_allowance(harness_count: int, diag, require_visual: bool) -> tuple:
    """Record zero-point coloured clouds only when the mapper's log accounts for each.

    Stock publish_frame_world publishes a fielded, zero-point cloud on a VIO frame
    where no source point projects into the image. That is a legitimate "nothing
    in view" frame, not corruption, but only when the mapper itself logged exactly
    the same number of such frames and every one had source points. Returns
    (record, error); (None, None) when the monitor saw none.
    """
    if not harness_count:
        return None, None
    if not require_visual:
        return None, 'coloured empty cloud seen without visual mode'
    if not diag or not diag.get('frames'):
        return None, 'coloured empty cloud without mapper cloud diagnostic evidence'
    if diag['zero_coloured'] != harness_count:
        return None, (f"coloured empty cloud count {harness_count} does not match "
                      f"mapper log {diag['zero_coloured']}")
    if not diag['zero_source_min'] or diag['zero_source_min'] <= 0:
        return None, 'coloured empty cloud from a frame with no source points'
    return ({'count': harness_count, 'mapper_logged': diag['zero_coloured'],
             'source_points_min': diag['zero_source_min'],
             'source_points_max': diag['zero_source_max']}, None)


def rgb_bound_error(rgb_count: int, diag):
    """The best-effort monitor may miss RGB frames but can never see more than the mapper published."""
    if not diag or not diag.get('frames'):
        return None
    if rgb_count > diag['frames']:
        return (f"rgb count {rgb_count} exceeds the {diag['frames']} publishes "
                "the mapper logged")
    return None

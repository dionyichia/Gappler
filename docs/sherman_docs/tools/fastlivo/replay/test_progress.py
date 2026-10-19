"""Callback accounting and bounded replay controls; no ROS or Docker."""
from collections import Counter
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import sqlite3
import struct
import tempfile
import unittest

import replay

# The reviewed public raw bag's inputs, kept explicit here so the accountant is
# never tested against its own derivation (T3.5c parameterisation).
PUBLIC_INPUTS = {'/livox/lidar': 'livox_ros_driver2/msg/CustomMsg',
                 '/livox/imu': 'sensor_msgs/msg/Imu',
                 '/left_camera/image': 'sensor_msgs/msg/Image'}
OUR_PARAMS = {'common.lid_topic': '/livox/lidar', 'common.imu_topic': '/livox/imu',
              'common.img_topic': '/camera/camera/color/image_raw', 'common.img_en': 1}


def coverage_rows(camera=(0, 0, '100.600000'), imu=(0, 0, '101.500000'),
                  lidar=(0, 0, '101.500000')):
    """Summary rows for the reviewed topics as (missing, unexpected, last stamp)."""
    def row(expected_last, spec):
        missing, unexpected, last = spec
        return {'expected_last_stamp': expected_last, 'last_callback_stamp': last,
                'missing': missing, 'unexpected': unexpected,
                'missing_stamp_examples': [expected_last] if missing == 1 else []}
    return {'/livox/lidar': row('101.500000', lidar),
            '/livox/imu': row('101.500000', imu),
            '/left_camera/image': row('101.600000', camera)}


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def progress(self):
        # Import here so a missing implementation produces test failures.
        self.assertTrue((Path(__file__).parent / 'replay_progress.py').exists(),
                        'callback accounting module has not been implemented')
        import replay_progress
        return replay_progress

    def bag(self, topics=None, extra=()):
        path = self.root / 'bag.db3'
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript('CREATE TABLE topics(id INTEGER,name TEXT,type TEXT,serialization_format TEXT);'
                             'CREATE TABLE messages(id INTEGER,topic_id INTEGER,timestamp INTEGER,data BLOB);')
            for topic_id, (name, typ) in enumerate(list((topics or PUBLIC_INPUTS).items()) + list(extra), 1):
                db.execute('INSERT INTO topics VALUES(?,?,?,?)', (topic_id, name, typ, 'cdr'))
                for sec in (100, 101):
                    data = b'\x00\x01\x00\x00' + struct.pack('<iI', sec, 500000000) + b'payload'
                    db.execute('INSERT INTO messages VALUES(NULL,?,?,?)', (topic_id, sec * 10**9, data))
        return path

    def test_expected_headers_are_read_only_and_apply_image_offset(self):
        module = self.progress()
        bag = self.bag()
        before = bag.read_bytes()
        expected = module.expected_callbacks(bag, PUBLIC_INPUTS, image_offset=0.1)
        self.assertEqual(expected['/left_camera/image'], Counter({'100.600000': 1, '101.600000': 1}))
        self.assertEqual(expected['/livox/imu'], Counter({'100.500000': 1, '101.500000': 1}))
        self.assertEqual(before, bag.read_bytes())

    def test_unplayed_bag_topics_are_recorded_not_parsed_or_rejected(self):
        module = self.progress()
        bag = self.bag(extra=[('/camera/camera/color/camera_info', 'sensor_msgs/msg/CameraInfo')])
        expected = module.expected_callbacks(bag, PUBLIC_INPUTS, image_offset=0.0)
        self.assertEqual(set(expected), set(PUBLIC_INPUTS))
        with self.assertRaises(ValueError):
            module.expected_callbacks(bag, dict(PUBLIC_INPUTS, **{'/absent': 'sensor_msgs/msg/Image'}), 0.0)
        with self.assertRaises(ValueError):
            module.expected_callbacks(bag, dict(PUBLIC_INPUTS, **{'/livox/imu': 'sensor_msgs/msg/Image'}), 0.0)

    def test_callback_patterns_follow_the_staged_config_topics(self):
        module = self.progress()
        patterns = module.callback_patterns(OUR_PARAMS)
        self.assertEqual(set(patterns), {'/livox/lidar', '/livox/imu',
                                         '/camera/camera/color/image_raw'})
        self.assertEqual(set(module.callback_patterns(dict(OUR_PARAMS, **{'common.img_en': 0}))),
                         {'/livox/lidar', '/livox/imu'})
        tracker = module.CallbackTracker({name: Counter() for name in patterns}, patterns)
        log = self.root / 'mapper.stdout.log'
        log.write_text('Get image, its header time: 123.456789\n'
                       'Get LiDAR, its header time: 123.466666\n'
                       'get imu at time: 123.466700\n')
        tracker.update(log)
        self.assertEqual(tracker.observed['/camera/camera/color/image_raw'],
                         Counter({'123.456789': 1}))
        self.assertNotIn('/left_camera/image', tracker.observed)
        lio = module.CallbackTracker(
            {name: Counter() for name in module.callback_patterns(dict(OUR_PARAMS, **{'common.img_en': 0}))},
            module.callback_patterns(dict(OUR_PARAMS, **{'common.img_en': 0})))
        lio.update(log)
        self.assertEqual(sum(sum(counts.values()) for counts in lio.observed.values()), 2)

    def test_wrong_type_or_cdr_header_is_rejected(self):
        module = self.progress()
        path = self.bag()
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("UPDATE topics SET type='wrong' WHERE name='/livox/imu'")
        with self.assertRaises(ValueError):
            module.expected_callbacks(path, PUBLIC_INPUTS, 0.1)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('UPDATE topics SET type=? WHERE name=?', (PUBLIC_INPUTS['/livox/imu'], '/livox/imu'))
            db.execute("UPDATE messages SET data=x'00010000'")
        with self.assertRaises(ValueError):
            module.expected_callbacks(path, PUBLIC_INPUTS, 0.1)

    def test_epoch_stamp_rounding_matches_humble_chrono_conversion(self):
        module = self.progress()
        path = self.bag()
        # Real recording value: split sec/nsec arithmetic rounds one us lower.
        with closing(sqlite3.connect(path)) as db, db:
            topic_id = db.execute("SELECT id FROM topics WHERE name='/livox/imu'").fetchone()[0]
            data = b'\x00\x01\x00\x00' + struct.pack('<iI', 1661405852, 103121281)
            db.execute('UPDATE messages SET data=? WHERE topic_id=?', (data, topic_id))
        expected = module.expected_callbacks(path, PUBLIC_INPUTS, 0.1)
        self.assertEqual(expected['/livox/imu'], Counter({'1661405852.103122': 2}))

    def test_incremental_logs_preserve_partial_lines_and_detect_gaps(self):
        module = self.progress()
        log = self.root / 'mapper.stderr.log'
        log.write_text('get imu at time: 100.500000\nget imu at time: 101.')
        tracker = module.CallbackTracker({'/livox/imu': Counter({'100.500000': 1, '101.500000': 1})})
        tracker.update(log)
        self.assertEqual(tracker.summary()['/livox/imu']['missing'], 1)
        with log.open('a') as out:
            out.write('500000\n')
        tracker.update(log)
        tracker.update(log)  # Must not count already-read bytes twice.
        self.assertTrue(tracker.tails_seen())
        self.assertEqual(tracker.summary()['/livox/imu']['matched'], 2)
        self.assertEqual(tracker.summary()['/livox/imu']['unexpected'], 0)

    def test_terminal_stamp_does_not_hide_missing_prefix_or_duplicate(self):
        module = self.progress()
        log = self.root / 'stderr.log'
        log.write_text('get imu at time: 101.500000\nget imu at time: 101.500000\n')
        tracker = module.CallbackTracker({'/livox/imu': Counter({'100.500000': 1, '101.500000': 1})})
        tracker.update(log)
        self.assertTrue(tracker.tails_seen())
        row = tracker.summary()['/livox/imu']
        self.assertEqual((row['missing'], row['unexpected']), (1, 1))

    def test_drain_waits_for_tails_and_quiet_but_never_exceeds_deadline(self):
        module = self.progress()
        self.assertEqual(module.drain_state(10, 30, 9, False), 'waiting')
        self.assertEqual(module.drain_state(10, 30, 9, True), 'waiting')
        self.assertEqual(module.drain_state(15, 30, 9, True), 'callbacks_quiet')
        self.assertEqual(module.drain_state(30, 30, 29, False), 'timeout')
        self.assertEqual(module.drain_state(30, 30, 0, True), 'timeout')

    def test_rate_cannot_silently_extend_the_custody_window(self):
        module = self.progress()
        self.assertEqual(module.playback_rate('0.2', 66.7), 0.2)
        self.assertEqual(module.playback_rate('0.25', 66.7), 0.25)
        for rate in ('0', '-1', 'nan', 'inf', 'oops', '0.1', '1'):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                module.playback_rate(rate, 66.7)
        with self.assertRaises(ValueError):
            module.playback_rate('0.24', 100)  # Must reserve cleanup as well.

    def test_final_supervisor_verdict_rejects_gaps_and_budget_overrun(self):
        self.assertTrue(hasattr(replay, 'finalize_report'), 'final supervisor accounting is not extracted yet')
        for missing, unexpected, elapsed, expected in ((0, 0, 599, 'PASS'),
                                                      (1, 0, 599, 'FAIL'),
                                                      (0, 1, 599, 'FAIL'),
                                                      (0, 0, 601, 'FAIL')):
            report = {'mode': 'replay', 'errors': [], 'eof': True,
                      'positive_visual_retrievals': 2,
                      'streams': {key: {'count': 10, 'first': 1, 'last': 6, 'invalid': 0}
                                  for key in replay.OUTPUTS},
                      'input_callbacks': {'/livox/imu': {'missing': missing, 'unexpected': unexpected}}}
            with self.subTest(missing=missing, unexpected=unexpected, elapsed=elapsed), \
                 patch.object(replay.time, 'monotonic', return_value=elapsed):
                replay.finalize_report(report, started=0, diagnostic_captured=False)
                self.assertEqual(report['verdict'], expected)
                self.assertEqual(report['elapsed_wall_seconds'], elapsed)

    def test_supervisor_uses_sensor_logs_not_two_second_eof_assumption(self):
        text = Path(replay.__file__).read_text()
        self.assertIn('CallbackTracker', text)
        self.assertIn('input_callbacks', text)
        self.assertIn('estimator_completion_proven', text)
        self.assertIn('drain_state(', text)
        self.assertNotIn('time.monotonic() + 2)', text)
        self.assertIn('"--rate", str(rate)', text)
        self.assertIn('flush=True', text)
        self.assertIn('reconcile_rows(', text)
        self.assertIn('prestart_allowance(', text)
        self.assertIn("missing_stamp_examples'] = []",
                      Path(replay.__file__).with_name('replay_progress.py').read_text())

    def test_wrapper_stages_accountant_streams_progress_and_avoids_sudo_prompts(self):
        text = Path(replay.__file__).with_name('run_replay.sh').read_text()
        self.assertIn('T35_REPLAY_RATE', text)
        self.assertIn('replay_progress.py', text)
        self.assertIn('docker logs --follow', text)
        self.assertNotIn('sudo docker', text)
        self.assertIn('sudo -v', text)

    def test_prestart_imu_prefix_is_bounded_but_midstream_gaps_fail(self):
        module = self.progress()
        # Pinned early-return drops IMU before the first lidar callback; the
        # allowance covers at most one 10 Hz lidar period of 200 Hz-class IMU.
        self.assertEqual(module.prestart_allowance(13515, 66.681504412), 21)
        self.assertEqual(module.prestart_allowance(200, 1.0), 20)
        expected = Counter({'1.000000': 1, '1.005000': 1, '1.010000': 1})
        # Strict startup prefix within allowance is reconciled, not missing.
        row = module.reconcile_imu(Counter({'1.005000': 1, '1.010000': 1}), expected, 21)
        self.assertEqual((row['prestart_drops'], row['missing']), (1, 0))
        # Mid-stream gap is not a startup prefix.
        row = module.reconcile_imu(Counter({'1.000000': 1, '1.010000': 1}), expected, 21)
        self.assertEqual((row['prestart_drops'], row['missing']), (0, 1))
        # Oversized prefix exceeds the race window.
        row = module.reconcile_imu(Counter(), expected, 1)
        self.assertEqual((row['prestart_drops'], row['missing']), (0, 3))
        # Duplicates are never prestart drops.
        row = module.reconcile_imu(Counter({'1.000000': 2, '1.005000': 1, '1.010000': 1}), expected, 21)
        self.assertEqual((row['prestart_drops'], row['missing'], row['unexpected']), (0, 0, 1))
        # Allowance validation rejects non-counts and non-durations.
        for count, duration in ((True, 1.0), (0, 1.0), (-5, 1.0), (200, 0.0),
                                (200, float('nan')), (200, float('inf'))):
            with self.subTest(count=count, duration=duration), self.assertRaises(ValueError):
                module.prestart_allowance(count, duration)


    def test_terminal_message_loss_is_allowed_only_when_single_and_inert(self):
        module = self.progress()
        allowed = module.terminal_message_gap(coverage_rows(camera=(1, 0, '100.600000')),
                                              '/livox/lidar')
        # The bag's own last image is the only stamp this may excuse: it comes
        # 0.1 s after the final LiDAR callback, so no VIO frame can consume it.
        self.assertEqual(allowed, {'topic': '/left_camera/image', 'stamp': '101.600000',
                                   'seconds_after_last_lidar': 0.1})
        # A terminal IMU sample is equally inert when it postdates the last scan.
        imu_rows = coverage_rows(imu=(1, 0, '101.400000'))
        imu_rows['/livox/imu'].update(expected_last_stamp='101.550000',
                                      missing_stamp_examples=['101.550000'])
        self.assertEqual(module.terminal_message_gap(imu_rows, '/livox/lidar')['topic'],
                         '/livox/imu')
        # A stamp at exactly the last LiDAR time could still join that scan.
        self.assertIsNone(module.terminal_message_gap(coverage_rows(imu=(1, 0, '101.400000')),
                                                      '/livox/lidar'))
        rejected = {}
        rejected['earlier stamp'] = coverage_rows(camera=(1, 0, '101.600000'))
        rejected['earlier stamp']['/left_camera/image']['missing_stamp_examples'] = ['100.600000']
        rejected['two missing'] = coverage_rows(camera=(2, 0, '100.600000'))
        rejected['duplicate'] = coverage_rows(camera=(1, 1, '100.600000'))
        rejected['lidar gap'] = coverage_rows(lidar=(1, 0, '100.500000'))
        rejected['two topics'] = coverage_rows(camera=(1, 0, '100.600000'),
                                               imu=(1, 0, '101.400000'))
        rejected['not after lidar'] = coverage_rows(camera=(1, 0, '100.600000'))
        rejected['not after lidar']['/left_camera/image']['expected_last_stamp'] = '101.500000'
        rejected['not after lidar']['/left_camera/image']['missing_stamp_examples'] = ['101.500000']
        rejected['no lidar row'] = {name: row for name, row in coverage_rows().items()
                                    if name != '/livox/lidar'}
        rejected['malformed row'] = coverage_rows(camera=(1, 0, '100.600000'))
        del rejected['malformed row']['/livox/imu']['missing']
        for label, rows in rejected.items():
            with self.subTest(label=label):
                self.assertIsNone(module.terminal_message_gap(rows, '/livox/lidar'))

    def test_reconciled_rows_apply_the_imu_prestart_allowance_once(self):
        module = self.progress()
        tracker = module.CallbackTracker({'/livox/lidar': Counter({'1.000000': 1}),
                                          '/livox/imu': Counter({'1.000000': 1,
                                                                 '1.100000': 1})})
        tracker.observed['/livox/lidar'].update({'1.000000': 1})
        tracker.observed['/livox/imu'].update({'1.100000': 1})
        rows = module.reconcile_rows(tracker, '/livox/imu', 2)
        self.assertEqual((rows['/livox/imu']['prestart_drops'], rows['/livox/imu']['missing']),
                         (1, 0))
        self.assertEqual(rows['/livox/imu']['missing_stamp_examples'], [])
        self.assertEqual(sum(sum(seen.values()) for seen in tracker.observed.values()), 2)

    def test_supervisor_records_the_inert_terminal_gap_instead_of_failing(self):
        self.assertTrue(hasattr(replay, 'finalize_report'))
        streams = {key: {'count': 10, 'first': 1, 'last': 6, 'invalid': 0}
                   for key in replay.OUTPUTS}
        report = {'mode': 'replay', 'errors': [], 'eof': True,
                  'positive_visual_retrievals': 2, 'streams': streams,
                  'input_lidar_topic': '/livox/lidar',
                  'input_callbacks': coverage_rows(camera=(1, 0, '100.600000'))}
        with patch.object(replay.time, 'monotonic', return_value=0):
            replay.finalize_report(report, started=0, diagnostic_captured=False)
        self.assertEqual(report['verdict'], 'PASS')
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['terminal_message_lost']['stamp'], '101.600000')
        for label, rows in (('earlier stamp', coverage_rows(camera=(1, 0, '101.600000'))),
                            ('lidar gap', coverage_rows(lidar=(1, 0, '100.500000'))),
                            ('duplicate', coverage_rows(camera=(0, 1, '100.600000')))):
            if label == 'earlier stamp':
                rows['/left_camera/image']['missing_stamp_examples'] = ['100.600000']
            with self.subTest(label=label):
                failed = {'mode': 'replay', 'errors': [], 'eof': True,
                          'positive_visual_retrievals': 2, 'streams': streams,
                          'input_lidar_topic': '/livox/lidar', 'input_callbacks': rows}
                with patch.object(replay.time, 'monotonic', return_value=0):
                    replay.finalize_report(failed, started=0, diagnostic_captured=False)
                self.assertEqual(failed['verdict'], 'FAIL')
                self.assertTrue(any('input callback coverage' in e for e in failed['errors']))
                self.assertNotIn('terminal_message_lost', failed)
        # Without a declared lidar topic the allowance stays closed.
        strict = {'mode': 'replay', 'errors': [], 'eof': True,
                  'positive_visual_retrievals': 2, 'streams': streams,
                  'input_callbacks': coverage_rows(camera=(1, 0, '100.600000'))}
        with patch.object(replay.time, 'monotonic', return_value=0):
            replay.finalize_report(strict, started=0, diagnostic_captured=False)
        self.assertEqual(strict['verdict'], 'FAIL')

    def test_supervisor_uses_the_allowance_for_drain_and_coverage(self):
        text = Path(replay.__file__).read_text()
        self.assertIn('terminal_message_gap(', text)
        self.assertIn('reconcile_rows(', text)
        self.assertIn("input_lidar_topic", text)
        self.assertIn('terminal_message_lost', text)

    def test_mapper_cloud_diagnostic_lines_are_summarised(self):
        module = self.progress()
        lines = ['noise',
                 '[T35_DIAG_CLOUD] source_points=208 coloured_points=0 pub_scan_num=1',
                 '[T35_DIAG_CLOUD] source_points=900 coloured_points=500 pub_scan_num=1',
                 '[T35_DIAG_CLOUD] source_points=12 coloured_points=0 pub_scan_num=1']
        self.assertEqual(module.parse_cloud_diag(lines),
                         {'frames': 3, 'zero_coloured': 2,
                          'zero_source_min': 12, 'zero_source_max': 208})
        self.assertEqual(module.parse_cloud_diag(['noise']),
                         {'frames': 0, 'zero_coloured': 0,
                          'zero_source_min': None, 'zero_source_max': None})

    def test_coloured_empty_clouds_are_allowed_only_with_matching_mapper_evidence(self):
        module = self.progress()
        diag = {'frames': 10, 'zero_coloured': 3, 'zero_source_min': 5, 'zero_source_max': 90}
        record, error = module.coloured_empty_allowance(3, diag, True)
        self.assertIsNone(error)
        self.assertEqual(record, {'count': 3, 'mapper_logged': 3,
                                  'source_points_min': 5, 'source_points_max': 90})
        # Nothing observed means nothing to allow and nothing to report.
        self.assertEqual(module.coloured_empty_allowance(0, diag, True), (None, None))
        rejected = {
            'harness saw more': (4, diag, True),
            'harness saw fewer': (2, diag, True),
            'no mapper evidence': (3, None, True),
            'no diagnostic frames': (3, dict(diag, frames=0, zero_coloured=0,
                                             zero_source_min=None, zero_source_max=None), True),
            'empty source': (3, dict(diag, zero_source_min=0), True),
            'not visual mode': (3, diag, False),
        }
        for label, (count, evidence, visual) in rejected.items():
            with self.subTest(label=label):
                record, error = module.coloured_empty_allowance(count, evidence, visual)
                self.assertIsNone(record)
                self.assertIn('coloured empty cloud', error)

    def test_supervisor_records_matching_coloured_empty_clouds_instead_of_failing(self):
        streams = {key: {'count': 10, 'first': 1, 'last': 6, 'invalid': 0}
                   for key in replay.OUTPUTS}

        def run(empties, diag):
            report = {'mode': 'replay', 'errors': [], 'eof': True,
                      'positive_visual_retrievals': 2, 'streams': streams,
                      'input_lidar_topic': '/livox/lidar',
                      'input_callbacks': coverage_rows(),
                      'monitor': {'cloud_coloured_empty': empties},
                      'mapper_cloud_diag': diag}
            with patch.object(replay.time, 'monotonic', return_value=0):
                replay.finalize_report(report, started=0, diagnostic_captured=False)
            return report

        diag = {'frames': 10, 'zero_coloured': 3, 'zero_source_min': 5, 'zero_source_max': 90}
        report = run(3, diag)
        self.assertEqual((report['verdict'], report['errors']), ('PASS', []))
        self.assertEqual(report['coloured_empty_clouds']['count'], 3)
        for label, empties, evidence in (('count mismatch', 4, diag),
                                         ('no evidence', 3, None),
                                         ('empty source', 3, dict(diag, zero_source_min=0))):
            with self.subTest(label=label):
                failed = run(empties, evidence)
                self.assertEqual(failed['verdict'], 'FAIL')
                self.assertTrue(any('coloured empty cloud' in e for e in failed['errors']))
                self.assertNotIn('coloured_empty_clouds', failed)
        clean = run(0, None)
        self.assertEqual(clean['verdict'], 'PASS')
        self.assertNotIn('coloured_empty_clouds', clean)

    def test_supervisor_counts_fielded_empty_clouds_and_reads_mapper_evidence(self):
        text = Path(replay.__file__).read_text()
        self.assertIn('cloud_coloured_empty', text)
        self.assertIn('len(message.fields) > 0', text)
        self.assertIn('parse_cloud_diag(', text)
        self.assertIn('mapper_cloud_diag', text)

    def test_rgb_count_is_bounded_by_mapper_publishes_not_matched_to_a_target(self):
        module = self.progress()
        diag = {'frames': 1482, 'zero_coloured': 118, 'zero_source_min': 1, 'zero_source_max': 9}
        # Any count up to the mapper's own publishes is fine: the monitor is best-effort.
        for seen in (10, 384, 606, 1264, 1482):
            with self.subTest(seen=seen):
                self.assertIsNone(module.rgb_bound_error(seen, diag))
        self.assertIn('exceeds', module.rgb_bound_error(1483, diag))
        # Without mapper evidence (unpatched binary, img_en 0) there is nothing to bound against.
        self.assertIsNone(module.rgb_bound_error(5000, None))
        self.assertIsNone(module.rgb_bound_error(5000, dict(diag, frames=0)))

    def test_supervisor_fails_an_rgb_count_above_what_the_mapper_published(self):
        def run(rgb_count):
            streams = {key: {'count': 10, 'first': 1, 'last': 6, 'invalid': 0}
                       for key in replay.OUTPUTS}
            streams['rgb']['count'] = rgb_count
            report = {'mode': 'replay', 'errors': [], 'eof': True,
                      'positive_visual_retrievals': 2, 'streams': streams,
                      'input_lidar_topic': '/livox/lidar',
                      'input_callbacks': coverage_rows(),
                      'mapper_cloud_diag': {'frames': 20, 'zero_coloured': 0,
                                            'zero_source_min': None, 'zero_source_max': None}}
            with patch.object(replay.time, 'monotonic', return_value=0):
                replay.finalize_report(report, started=0, diagnostic_captured=False)
            return report
        self.assertEqual(run(20)['verdict'], 'PASS')
        over = run(21)
        self.assertEqual(over['verdict'], 'FAIL')
        self.assertTrue(any('exceeds' in e for e in over['errors']))


if __name__ == '__main__':
    unittest.main()

const { C, ST } = require('./lib');

module.exports = function (pres, H) {
  const SEC = 'Appendix (backup for questions)';
  const hd = t => ({ text: t, options: { bold: true, color: C.SLATE, fill: { color: C.TINT } } });
  const table = (s, rows, o) => {
    const data = rows.map((r, i) => i === 0 ? r.map(hd) : r.map(c => (typeof c === 'string' ? { text: c } : c)));
    s.addTable(data, Object.assign({ fontFace: 'Calibri', fontSize: o.fs || 12, color: C.INK, border: { type: 'solid', color: C.LINE, pt: 0.75 }, valign: 'middle', margin: [0.03, 0.07, 0.03, 0.07] }, o));
  };
  const src = (s, t) => H.text(s, 'Source: ' + t, { x: 0.5, y: 7.08, w: 11, h: 0.25, fontSize: 10, color: C.MUTED });
  const slide = (title, q) => {
    const s = pres.addSlide({ masterName: 'APPENDIX', sectionTitle: SEC });
    H.title(s, title);
    H.text(s, [{ text: 'Answers: ', options: { bold: true } }, { text: q }], { x: 0.5, y: 1.0, w: 12.33, h: 0.3, fontSize: 13, italic: true, color: C.SLATE });
    s.addNotes('BACKUP SLIDE, not in the 20 minutes. Answers: ' + q);
    return s;
  };
  const red = t => ({ text: t, options: { color: C.RED } });

  // divider
  {
    const s = pres.addSlide({ masterName: 'TITLE', sectionTitle: SEC });
    H.rect(s, 0, 0, 13.333, 7.5, { fill: C.NAVY, line: null });
    H.text(s, 'Appendix', { x: 0.8, y: 2.5, w: 11, h: 0.9, fontSize: 40, bold: true, color: C.WHITE });
    H.text(s, 'Backup slides for questions. Not part of the 20 minutes', { x: 0.8, y: 3.45, w: 11, h: 0.5, fontSize: 20, color: 'D6DEEC' });
    const idx = ['A1 Topic-level wiring today', 'A2 Coordinate frames', 'A3 Matching rule and thresholds', 'A4 Grasp filters and the five options', 'A5 FAST-LIVO2 port defects and mid-route accuracy',
      'A6 Limitations, risks and observed failures', 'A7 September plan vs now', 'A8 Why gaze, not just a class name', 'A9 End-to-end evaluation plan', 'A10 Milestone tests'];
    H.text(s, idx.map((t, i) => ({ text: t, options: { breakLine: i < idx.length - 1 } })), { x: 0.8, y: 4.3, w: 11.5, h: 2.6, fontSize: 14, color: 'D6DEEC', paraSpaceAfter: 2 });
    s.addNotes('Appendix divider. Backup slides for questions only.');
  }

  // A1 topic wiring
  {
    const s = slide('A1  Topic-level wiring today', '"What exactly is connected?" Only links that exist in code. Grey rows exist in code but have not run');
    const g = t => ({ text: t, options: { color: C.MUTED } });
    table(s, [
      ['From', 'To', 'Channel', 'State'],
      ['Voice: Silero VAD, faster-whisper, Qwen2.5-0.5B', 'aria_segmentation_client', '/aria/audio/prompt (String)', 'Ran (replay)'],
      ['Eye model', 'aria_segmentation_client', '/aria/eye_tracking/gaze_estimate (PointStamped)', 'Ran (recording)'],
      ['aria_segmentation_client, grasp_segmentation_client', 'SAM 3 service (one copy on GPU)', '/segmentation/segment', 'Ran'],
      ['aria_segmentation_client', 'grasp_segmentation_client', '/grasp/target: word, then word plus reference crop', 'Ran on replay (T8.9a)'],
      ['aria_segmentation_client', 'grasp_state_machine', '/manipulator/grasp_request', 'Ran'],
      ['grasp_segmentation_client', 'grasp_state_machine', '/object_centroid_2d (pixel plus depth)', 'Ran'],
      ['anygrasp_detection_node', 'grasp_state_machine', '/grasp_candidates (state machine sends /pipeline_state back)', 'Ran'],
      ['grasp_state_machine', 'MoveIt and rm_driver', 'real arm', 'Ran on the real arm'],
      ['Livox MID-360, base D455', 'FAST-LIVO2 (container) then fastlivo_odom_bridge', 'odom to robot_base_link', 'Ran live'],
      ['fastlivo_odom_bridge', 'SLAM Toolbox, mapping mode', 'map to odom, /map', 'Ran live'],
      [g('SLAM Toolbox'), g('Nav2'), g('frame tree'), g('Never run on this')],
      [g('object_recognition_pipeline'), g('object_approach_node'), g('/manipulation/goal_pose (call site commented out)'), g('Not run')],
      [g('object_approach_node'), g('Nav2'), g('/goal_pose'), g('Not run')],
      [g('Recorded drive handdriven1'), g('Memory graph S0 to S13, then TargetFinder'), g('offline'), g('Graph built. Query not run on the drive')],
    ], { x: 0.5, y: 1.4, w: 12.33, colW: [3.35, 3.3, 3.95, 1.73], fs: 11, rowH: 0.32 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §3.3');
  }

  // A2 frames
  {
    const s = slide('A2  Coordinate frames', '"How do grasp poses reach the arm?"');
    const ch = ['map', 'odom', 'robot_base_link', 'base_link', 'Link1 to Link6', 'camera_link', 'camera_color_optical_frame'];
    const w = [0.95, 0.95, 1.7, 1.25, 1.55, 1.35, 2.75], g = 0.3;
    let x = 0.5;
    ch.forEach((c, i) => {
      H.rect(s, x, 1.5, w[i], 0.5, { fill: C.NAVY_T, line: C.NAVY });
      H.text(s, c, { x, y: 1.5, w: w[i], h: 0.5, fontSize: 12.5, bold: true, color: C.NAVY, align: 'center', valign: 'middle' });
      if (i < ch.length - 1) H.seg(s, x + w[i] + 0.02, 1.75, x + w[i] + g - 0.02, 1.75, { color: C.INK, w: 1.25, arrow: true });
      if (i === 2) { H.seg(s, x + w[i] / 2, 2.0, x + w[i] / 2, 2.35, { color: C.INK, w: 1.25, arrow: true }); H.rect(s, x, 2.35, w[i], 0.42, { fill: C.WHITE, line: C.NAVY }); H.text(s, 'livox_frame', { x, y: 2.35, w: w[i], h: 0.42, fontSize: 12, color: C.NAVY, align: 'center', valign: 'middle' }); }
      x += w[i] + g;
    });
    table(s, [
      ['Parent to child', 'Published by', 'Value or note'],
      ['map to odom', 'SLAM Toolbox', 'Nav2 plans in this map frame'],
      ['odom to robot_base_link', 'Wheel driver, or the FAST-LIVO2 bridge (odom_source:=fastlivo)', 'Bridge: T_odom_base(t) = Tb x P0^-1 x P(t) x Tb^-1, Tb = (0.191, 0.02329, 0.15588) m. Refuses to start above 2 deg start tilt'],
      ['robot_base_link to base_link', 'Static (arm mount)', '(0.18, 0, 0.48) m, yaw 180 deg. Measured, tf2_echo matched'],
      ['robot_base_link to livox_frame', 'Static', 'LiDAR mount'],
      ['base_link through Link1..6 to camera_link', 'URDF', 'Wrist camera to arm calibrated (Dion, 2026-10-24)'],
      ['camera_link to camera_color_optical_frame', 'RealSense driver', 'AnyGrasp candidates arrive in this frame'],
    ], { x: 0.5, y: 3.0, w: 12.33, colW: [3.2, 3.6, 5.53], fs: 12, rowH: 0.42 });
    H.text(s, [
      { text: 'Frame question for later: ', options: { bold: true } },
      { text: 'FAST-LIVO2 publishes in camera_init and aft_mapped (its own TF is remapped to /fastlivo/tf). The memory graph stores positions in camera_init, Nav2 drives in SLAM Toolbox’s map. How graph positions reach map at run time is a design question for P2 and T7.1, not a defect' },
    ], { x: 0.5, y: 6.25, w: 12.33, h: 0.75, fontSize: 12.5 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §6.7, §5.4');
  }

  // A3 matching rule
  {
    const s = slide('A3  Matching rule and thresholds', '"Why 0.56? Is CLIP cosine a probability?"');
    H.text(s, [
      { text: 'The rule (cross_camera_mask_match_rule.py)', options: { bold: true, color: C.NAVY, breakLine: true } },
      { text: 'Cosine of all pairs between each wrist mask crop (box plus 20 px) and the reference crop. Cutoff 0.56, tuned on 20 pairs (T8.7). Keep masks within 0.01 of the best. A wrist-side tie returns no match', options: { breakLine: true } },
      { text: 'Same model in both places: open_clip ViT-B-32 laion2b_s34b_b79k, 512-dimensional, L2-normalised' },
    ], { x: 0.5, y: 1.45, w: 6.0, h: 2.0, fontSize: 13.5, paraSpaceAfter: 6 });
    H.text(s, [
      { text: 'Not a probability', options: { bold: true, color: C.NAVY, breakLine: true } },
      { text: 'CLIP cosine is not a calibrated probability. Thresholds are empirical: 0.56 for the matcher, 0.6 on the graph’s combined score 1.5 x overlap + 0.5 x appearance (upstream weights)', options: { breakLine: true } },
      { text: 'float16 on the GPU shifts a vector by up to 0.0039 when batch size changes. Small against 0.56, but exact scores do not reproduce across batch sizes', options: { breakLine: true } },
      { text: 'Crop padding differs: glasses and wrist use box plus a fixed 20 px, the graph pads relative to the box' },
    ], { x: 6.83, y: 1.45, w: 6.0, h: 2.6, fontSize: 13.5, paraSpaceAfter: 6 });
    table(s, [
      ['Where', 'Method', 'Confidence handling'],
      ['Glasses mask', 'Gaze vote', 'Winner needs half the votes, else word only'],
      ['Wrist mask (matcher)', 'CLIP cosine', 'Cutoff 0.56, wrist tie returns no match'],
      ['Wrist mask (grasp)', 'CLIP cosine when a reference exists (T8.9a), else SAM 3 score', 'Cutoff 0.56 and no tie, else nothing published'],
      ['Graph association', '3D overlap plus CLIP', 'Score over 0.6, greedy'],
      ['Graph query', 'CLIP text vs image', 'Ranking only'],
    ], { x: 0.5, y: 4.2, w: 12.33, colW: [2.6, 5.0, 4.73], fs: 12.5, rowH: 0.36 });
    H.text(s, 'No stage carries a confidence forward to the next (see A6)', { x: 0.5, y: 6.55, w: 12.33, h: 0.3, fontSize: 12.5, italic: true, color: C.SLATE });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §5.4, §6.4, §6.6');
  }

  // A4 grasp filters and options
  {
    const s = slide('A4  Grasp filters and the five options', '"Why not just lower the score floor?"');
    H.text(s, 'Filters on every AnyGrasp candidate (EXECUTING state)', { x: 0.5, y: 1.45, w: 6, h: 0.3, fontSize: 14, bold: true, color: C.NAVY });
    const f = ['On the SAM 3 mask', 'Inside the approach cone', 'Score at least 0.3', 'Width under 68 mm', 'Fingertips at most 45 mm past the near face', 'Pose stable for 5 frames', 'Of the 180 deg symmetric twins, the smaller wrist turn (T1.33)'];
    H.text(s, f.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < f.length - 1 } })), { x: 0.5, y: 1.8, w: 5.8, h: 2.4, fontSize: 13, paraSpaceAfter: 3 });
    H.rect(s, 0.5, 4.3, 5.8, 1.95, { fill: C.AMBER_T, line: ST.built.c });
    H.text(s, [
      { text: 'Why the floor is not the fix: ', options: { bold: true } },
      { text: 'the top-down grasp scores at most 0.25, but the problem is the view. The 30 deg cone around the camera axis dropped every top-down grasp, because the camera axis is 44 deg from vertical. AnyGrasp was also used against its README: masked points only instead of the whole scene, 0.10 m width instead of the real one' },
    ], { x: 0.65, y: 4.3, w: 5.5, h: 1.95, fontSize: 12.5, valign: 'middle' });
    table(s, [
      ['Option', 'Idea', 'Cost'],
      ['A. Grasp from the view pose', 'AnyGrasp once at 0.4 to 0.5 m with the whole box in view, one planned motion. Steps only as a fallback', 'Small. The pieces exist'],
      ['B. Fused views (T1.47)', 'Several views in one cloud, grasp on that', 'Built, retest owed'],
      ['C. New AnyGrasp SDK (T1.45)', 'Native mask and angle steering', 'Waiting on licence'],
      ['D. Closed-loop tracking', 'AnyGrasp’s tracking mode updates the grasp while the arm moves', 'Medium. Old tracker node parked'],
      ['E. Two-phase (shelved, T1.33)', 'Move to just before the depth blind zone, set the angle, then a straight move in and close', 'Small'],
    ], { x: 6.7, y: 1.45, w: 6.13, colW: [1.75, 3.08, 1.3], fs: 11.5 });
    H.ph(s, 6.7, 5.55, 6.13, 0.9, 'OPTIONAL: RVIZ GRASP RECORDING', 'rviz_grasp_<date>.mp4, if Dion records it', 'Dion', { fs: 11, fs2: 10 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §5.5. Options: DION_PROGRESS_REPORT_2026-10.md §7 (options marked [inferred])');
  }

  // A5 FAST-LIVO2 defects
  {
    const s = slide('A5  FAST-LIVO2 port defects and mid-route accuracy', '"How do you know the map is right?"');
    table(s, [
      ['Defect (found by reading the source, confirmed against a control run)', 'Before', 'After the fix'],
      ['Range gate cannot act (F2): blind_sqr never assigned, the port dropped upstream’s line', 'Median 19,968 points per scan, the full packet', 'Median 9,607. Removed fraction 0.5206 against 51.84 % audited zero-range points'],
      ['LiDAR to IMU offset has the wrong sign (F3)', 'About 10.2 cm of geometric inconsistency in every replay before 19 Oct', 'Configs carry (-0.011, -0.02329, 0.04412) m. handdriven1 recorded after the fix'],
      ['Voxel key mismatch: insertion and retrieval used different arithmetic for negative coordinates', 'Key hits 1,392,458 against 1,878,707 shadow hits', 'Hits match, 1,855,269. Accepted retrieval points 112,980 to 128,385'],
    ], { x: 0.5, y: 1.45, w: 12.33, colW: [4.9, 3.5, 3.93], fs: 12 });
    H.text(s, [
      { text: 'Mid-route accuracy (T3.5f)', options: { bold: true, color: C.NAVY, breakLine: true } },
      { text: 'Against the handdriven1 map as an independent reference, with the 0.15 s lag removed: within 6.7 cm (run 1) and 6.5 cm (run 2) for the whole route. Uncorrected 12.7 and 11.3 cm. The reference carries about 7 cm of its own error, so 6.7 cm is at the floor', options: { bullet: true, breakLine: true } },
      { text: 'The mapper stamps its pose about 0.15 s after the scan. Surfaces smear by speed x 0.15 s, about 4 cm at 0.28 m/s. Fix prepared, off by default (stamp_offset_s)', options: { bullet: true, breakLine: true } },
      { text: 'Floor marks did not close as ground truth (AB +0.264 m, BC 0.33 m too long). A tape-measured check is owed', options: { bullet: true } },
    ], { x: 0.5, y: 4.05, w: 7.4, h: 2.9, fontSize: 12.5, paraSpaceAfter: 5 });
    H.ph(s, 8.2, 4.1, 4.63, 2.8, 'DRIFT PLOT: ERROR VS TIME', 'nav_t35f_drift_step3_error_vs_time_2026-10-21.png', 'Sherman', { fs: 12, fs2: 10 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §8.4. SHERMAN_PROGRESS_REPORT_2026-10.md §9.3, §11.4, §11.5');
  }

  // A6 (1/3) limitations
  {
    const s = slide('A6  Limitations (1 of 3): confirmed in the implementation', '"What fails today?" Most are links the plan schedules for later milestones');
    table(s, [
      ['Limitation', 'End-to-end implication'],
      ['A wrong gaze pick becomes a confident reference (T8.9a replay: at 1.5 m the reference was the mat, the other box scored just over 0.56 twice)', 'The arm would go for the wrong box if a grasp request were open. T2.24 refuses weak gaze picks'],
      ['/manipulation/goal_pose has no live publisher (inherited)', 'Nothing can start navigation to an object yet. T7.1 will publish it'],
      ['No graph query service, no T7.1 node', 'The graph cannot drive the robot'],
      ['No gaze-target trigger on graph objects', 'The exploring robot cannot yet tell it has found the target. Glasses crop vs base-camera features is untested'],
      ['Graph built offline from a hand-pushed recording', 'No live graph. No depth camera data'],
      ['No calibration between any cameras', 'Graph positions and the gaze ray carry unknown rotation error. About 6.7 px per degree on the base camera'],
      ['Software-only stops on arm and base', 'Every hardware test needs two people and the power button'],
      ['No automatic grasp success check', 'Outcome must be judged by people. A retry loop cannot know when to retry'],
    ], { x: 0.5, y: 1.45, w: 12.33, colW: [6.2, 6.13], fs: 12.5 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §9.1');
  }
  // A6 (2/3) risks
  {
    const s = slide('A6  Limitations (2 of 3): architectural risks to test', '"What could break when the parts join?"');
    const r = [
      ['No confidence crosses a stage boundary', 'A wrong gaze pick gives a confident reference, a wrong graph hit gives a goal, a wrong wrist mask gives a grasp. The matcher caught one wrong reference by luck of score (0.51 vs 0.56)'],
      ['Crop mismatch', 'Fixed 20 px glasses crop against the graph’s relative padding, when the gaze match (P3) lands'],
      ['Frame of graph positions', 'camera_init against Nav2’s map frame, to settle when P2 and T7.1 are built'],
      ['Standoff vs reach', '0.6 m camera standoff against the 35 to 46 cm tested grasp band, to check at the first nav-to-object test'],
      ['GPU contention', 'SAM 3 service, batched graph SAM 3 (up to 10.3 GiB), AnyGrasp, CLIP, Whisper, two Qwen models on one 16 GB card. Never run together'],
      ['0.15 s pose lag', 'Anything pairing a scan with a pose by stamp, including graph depth if rendered that way'],
      ['Viewpoint change between graph and wrist', 'Graph features from the base camera at knee height, reference from the glasses, confirmation from the wrist. Glasses to base camera is untested'],
    ];
    table(s, [['Risk', 'What to watch']].concat(r), { x: 0.5, y: 1.45, w: 12.33, colW: [3.4, 8.93], fs: 12.5 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §9.3');
  }
  // A6 (3/3) observed failures
  {
    const s = slide('A6  Limitations (3 of 3): observed failures', '"What has gone wrong on hardware or data?"');
    table(s, [
      ['Failure', 'Where', 'Source'],
      ['AnyGrasp’s confident grasps are across the too-wide face. Fit check passes edge slices', 'Wrist, 0.21 m', 'T1.44'],
      ['Live OK-Robot trials 0 of 4: one pushed the box, two stuck in EXECUTING, one found nothing in 3 s', 'Real arm', 'T1.44'],
      ['Wrist spun 180 deg and knocked the box off (fixed)', 'First AnyGrasp grasp', 'T1.33'],
      ['Wide wrist twist (j4 146, j5 29, j6 274 deg)', 'AnyGrasp grasp B', 'T1.40'],
      ['Look-alike boxes: 148 of 180, 6 of 12', 'Matcher', 'T8.5, T8.8'],
      ['Gaze landed on the mat stack at 1.5 m', 'Glasses', 'T8.5'],
      ['Keypoint matching 0 of 15', 'Cross camera', 'T8.4'],
      ['Mapper teardown aborts 2 of 4. LiDAR driver SIGBUS', 'Base', 'S§10.3'],
      ['Ethernet flap caused 8.1 s and 15.1 s IMU time jumps', 'Base, live', 'T3.5d'],
      ['Lab box silent hangs (2026-10-06, 2026-10-20)', 'Shared box', 'S§15'],
      ['Glass walls: about 42 % of 5 cm map points are ghosts outside the glass box', 'Map', 'S§15'],
      ['Glass door and both computer towers missed in every graph setting', 'Graph', 'Z§3.5'],
    ], { x: 0.5, y: 1.45, w: 12.33, colW: [8.2, 2.6, 1.53], fs: 12 });
    H.text(s, 'Lab visitors’ faces appear in Sherman’s coloured map. Cleared for this internal presentation. Re-render before any external showing', { x: 0.5, y: 6.65, w: 12.33, h: 0.3, fontSize: 11.5, italic: true, color: C.SLATE });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §9.2. 148 of 180 (T8.5, matcher on display) is not the same count as 266 of 268 on slide 12 (T8.9a, published targets only)');
  }

  // A7 September plan vs now
  {
    const s = slide('A7  September plan vs now', '"How does this compare with your original plan?"');
    const rows = [
      ['Milestone', 'September plan window', 'Now (actual to 24 Oct, forecast end)', 'Change'],
      ['M0 Everyone can build and run', '14 to 27 Sep 2026', 'Done 24 Sep', 'On time'],
      ['M1 The arm picks something up', '5 Oct to 1 Nov 2026', 'Started 21 Sep. Forecast 8 Nov', 'About one week later (AnyGrasp)'],
      ['M2 Voice and gaze reach the arm', '26 Oct 2026 to 3 Jan 2027', 'Started 8 Oct. Forecast 10 Jan', 'Started early, ends about one week later'],
      ['M3 The base navigates', '12 Oct to 27 Dec 2026', 'Started 14 Sep. Forecast 10 Jan', 'Two weeks later'],
      ['M4 Closed loop', '28 Dec 2026 to 17 Jan 2027', 'Forecast 11 to 31 Jan', 'Two weeks later'],
      ['M5 Calibrated base camera', '5 Oct 2026 to 17 Jan 2027', 'Started 16 Sep. Forecast 24 Jan', 'One week later'],
      ['M6 Memory graph offline', '28 Dec 2026 to 7 Feb 2027', 'Started 21 Sep. Forecast 31 Jan', 'One week earlier'],
      ['M7 The graph drives the robot', '1 to 28 Feb 2027', 'Forecast 18 Jan to 28 Feb', 'Can start earlier, end unchanged'],
      ['M8 Gaze picks the instance', '8 Feb to 14 Mar 2027', 'Started 19 Oct. Forecast 14 Mar', 'Started early, end unchanged'],
      ['M9 Frontier scoring (optional)', '2 Nov 2026 to 21 Feb 2027', 'Not started. 18 Jan to 21 Feb if kept', 'First on the cut list'],
      ['M10 Demonstration and paper', '1 to 21 Mar 2027', 'Forecast 1 to 21 Mar', 'Unchanged'],
    ];
    table(s, rows, { x: 0.5, y: 1.45, w: 12.33, colW: [3.2, 2.9, 3.4, 2.83], fs: 12.5, rowH: 0.4 });
    H.text(s, 'September plan windows from the milestone headings of the plan in git at 1cde0ec:docs/PROJECT_PLAN.md. Its §6.6 heading gives M4 as 28 Dec to 17 Jan, while PROJECT_PLAN.md:414 forecasts 11 to 31 Jan', { x: 0.5, y: 6.45, w: 12.33, h: 0.5, fontSize: 11.5, italic: true, color: C.SLATE });
    src(s, '1cde0ec:docs/PROJECT_PLAN.md §5 and §6 headings. COMBINED_PROGRESS_REPORT_2026-10.md §0.2, §0.6');
  }

  // A8 why gaze
  {
    const s = slide('A8  Why gaze, not just a class name', '"Isn’t identical-object picking niche?"');
    H.text(s, [
      { text: 'Two truly identical objects are the hardest test case, not the pitch.', options: { bold: true, breakLine: true } },
      { text: 'The capability is knowing where the user is looking in the robot’s own 3D space' },
    ], { x: 0.5, y: 1.5, w: 12.33, h: 0.8, fontSize: 18 });
    const it = [
      ['Similar objects', 'Two chairs of the same model score 0.81 to 0.85 in CLIP, close to the same chair at 0.93'],
      ['Partly hidden objects', 'The robot may see only part of the object the user sees'],
      ['Uncertain image features', 'Appearance alone is not a reliable identity'],
      ['A robot that does not see what the user sees', 'The base camera is at knee height, the glasses at eye level'],
      ['Assistive use', 'A user who can look but cannot easily point or speak, in a scene full of mugs, pill bottles and cans'],
    ];
    it.forEach((r, i) => {
      const y = 2.55 + i * 0.82;
      H.rect(s, 0.5, y, 12.33, 0.7, { fill: i % 2 ? C.WHITE : C.TINT, line: null });
      H.text(s, r[0], { x: 0.7, y, w: 4.2, h: 0.7, fontSize: 16, bold: true, color: C.NAVY, valign: 'middle' });
      H.text(s, r[1], { x: 5.0, y, w: 7.7, h: 0.7, fontSize: 15, valign: 'middle' });
    });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §0.3 (D§5.5). CLIP values: §8.5');
  }

  // A9 evaluation plan
  {
    const s = slide('A9  End-to-end evaluation plan', '"How will you measure the final system?" Today every measurement is per stage, none end to end');
    table(s, [
      ['Metric', 'Definition', 'Needs', 'Milestone'],
      ['Glasses target accuracy', 'Reference crop is the intended object, per spoken command, scenes with 2 to 4 objects at 1 to 3 m', 'Live glasses', 'M2'],
      ['Wrist confirmation accuracy', 'Matcher picks the intended object, with and without look-alikes. Refusals counted apart from wrong picks', 'P0 item 1', 'M2'],
      ['False acceptance rate', 'Wrong object accepted, per stage (glasses, graph, wrist)', 'Labelled trials', 'M2, M8'],
      ['Graph target retrieval', 'First hit lands on the intended marked object, and distance to it', 'T6.8', 'M6'],
      ['Gaze-target trigger accuracy', 'The robot stops exploring at the intended object. Wrong stops and wrist rejects counted', 'T8.2', 'M8'],
      ['User discovery and search distance', 'User found, and distance driven before the target is matched', 'T7.5, T7.6', 'M7'],
      ['Without gaze (stretch)', 'Same trials, voice only', 'T8.11', 'M8'],
      ['Drive-to-point repeatability', 'Ten drives, landing error, 10 cm circle', 'T3.6, T5.8 fixture', 'M3'],
      ['Handover success', 'Base stops with the object inside the grasp band', 'T3.7', 'M4'],
      ['Grasp success', '12-trial grid, pass bar 9 of 12', 'T1.35', 'M1'],
      ['End-to-end success', 'Speak, look, drive, grasp. Counted only when the intended object is lifted', 'All above', 'M4, M10'],
      ['Per-stage timing', '99th percentile per stage', 'T4.2', 'M4'],
      ['Recovery', 'Share of failures that end safely (refusal, ask, reject and retry) instead of a wrong grasp', 'P1 items', 'M4'],
    ], { x: 0.5, y: 1.45, w: 12.33, colW: [2.8, 6.6, 1.75, 1.18], fs: 11.5, rowH: 0.38 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §11');
  }

  // A10 milestones
  {
    const s = slide('A10  Milestone tests', '"How do you know a milestone is done?"');
    table(s, [
      ['', 'Milestone', 'Done means', 'Lead'],
      ['M0', 'Everyone can build and run', 'Two people other than Dion clone, build and pass the bench', 'Zongzhe'],
      ['M1', 'Arm picks something up', '5 grasp attempts on a box, success rate recorded, stop verified first', 'Dion'],
      ['M2', 'Voice and gaze reach the arm', 'Two boxes, the arm picks the one you looked at, 3 times in 4', 'Dion'],
      ['M3', 'Base navigates', 'Map, localisation, ten drives to a point with error recorded', 'Sherman'],
      ['M4', 'Closed loop', 'One recorded run: speak, look, drive, grasp, per-stage timing', 'Dion'],
      ['M5', 'Calibrated base camera', 'LiDAR points land on the right objects in the camera image, pose error as a number', 'Sherman mount, Dion calibration'],
      ['M6', 'Memory graph offline', 'Objects from a recorded drive, no duplicates, a sentence query returns the right one', 'Zongzhe'],
      ['M7', 'Graph drives the robot', 'Object out of view: the robot explores, finds the user, builds the graph live, drives to the object', 'Dion'],
      ['M8', 'Gaze picks the instance', 'A gaze match ends exploration. N end-to-end trials, success per phase', 'Dion'],
      ['M9', 'Smarter exploration order (optional)', 'The paper’s exploration order beats our nearest-first exploration', 'Zongzhe'],
      ['M10', 'Demonstration and paper', 'Recorded end-to-end run, paper whose central table is the end-to-end trials', 'All'],
    ], { x: 0.5, y: 1.45, w: 12.33, colW: [0.6, 3.0, 6.83, 1.9], fs: 12.5, rowH: 0.43 });
    src(s, 'COMBINED_PROGRESS_REPORT_2026-10.md §0.2');
  }
};

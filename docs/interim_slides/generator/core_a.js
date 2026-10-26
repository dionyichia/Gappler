const { C, ST } = require('./lib');
const IMG = __dirname + '/img/';

module.exports = function (pres, H, notes) {
  // ---------------- Slide 1: title ----------------
  {
    const s = pres.addSlide({ masterName: 'TITLE', sectionTitle: '1. Problem and objectives' });
    H.ph(s, 0, 0, 6.2, 7.5, 'PHOTO: full robot with the Aria glasses beside it',
      'RealMan RM65 arm on the Hexman ECHO-PLUS base, Livox LiDAR and front D455 visible. Half-bleed, crop to fill', 'any member, take at the lab', { fs: 16, fs2: 12 });
    H.rect(s, 6.2, 0, 7.133, 7.5, { fill: C.NAVY, line: null });
    H.text(s, 'High-Readiness Mobile Manipulation via Gaze-Speech Interaction and Continuous Pre-Alignment',
      { x: 6.8, y: 1.35, w: 6.0, h: 2.55, fontSize: 32, bold: true, color: C.WHITE, valign: 'bottom' });
    H.text(s, 'Look at it, name it, and the robot fetches that one',
      { x: 6.8, y: 4.1, w: 6.0, h: 0.5, fontSize: 20, italic: true, color: 'D6DEEC' });
    H.text(s, [
      { text: 'Dion, Sherman, Zongzhe', options: { fontSize: 18, bold: true, color: C.WHITE, breakLine: true } },
      { text: 'Supervisors: Prof Yuan Shenghai, Prof Xie Lihua', options: { fontSize: 16, color: 'D6DEEC', breakLine: true } },
      { text: 'Interim assessment, 28 October 2026', options: { fontSize: 16, color: 'D6DEEC' } },
    ], { x: 6.8, y: 5.2, w: 6.0, h: 1.2, paraSpaceAfter: 4 });
    s.addNotes(notes(1));
  }

  // ---------------- Slide 2: the problem ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '1. Problem and objectives' });
    H.title(s, 'The user can see the object. The robot sees neither the user nor the object');
    const panels = [
      { cap: "User's glasses", sub: '1 to 3 m away, front on', img: 'glasses_crop.jpg' },
      { cap: 'Robot base camera', sub: 'knee height', ph: true },
      { cap: 'Robot wrist camera', sub: '0.2 to 0.5 m, from above', img: 'wrist_crop.jpg' },
    ];
    const sz = 3.2, colw = 4.11;
    panels.forEach((p, i) => {
      const cx = 0.5 + i * colw + (colw - sz) / 2 - (i === 2 ? 0 : 0);
      const x = 0.5 + i * colw + (colw - 0.22 - sz) / 2;
      if (p.img) {
        s.addImage({ path: IMG + p.img, x, y: 1.6, w: sz, h: sz, altText: p.cap + ' view of the box' });
        H.rect(s, x, 1.6, sz, sz, { line: C.LINE, lw: 0.75 });
      } else {
        H.ph(s, x, 1.6, sz, sz, 'BASE-CAMERA FRAME FROM KNEE HEIGHT',
          'Ideally the same box seen by the D455. Else a frame from mg_handdriven1_survey_every_100th_frame_2026-10-21.jpg or nav_camera_frames_along_t35f_run1_2026-10-21.jpg, captioned "the lab from the base camera"', 'Sherman or Zongzhe', { fs: 13, fs2: 10.5 });
      }
      H.text(s, [
        { text: p.cap, options: { bold: true, fontSize: 18, breakLine: true } },
        { text: p.sub, options: { fontSize: 16, color: C.SLATE } },
      ], { x, y: 4.92, w: sz, h: 0.65, align: 'center' });
    });
    H.rect(s, 0.5, 5.75, 12.33, 0.55, { fill: C.NAVY_T, line: null });
    H.text(s, 'Same object, three viewpoints, almost nothing in common pixel for pixel',
      { x: 0.5, y: 5.75, w: 12.33, h: 0.55, fontSize: 20, bold: true, color: C.NAVY, align: 'center', valign: 'middle' });
    H.text(s, [
      { text: 'Why it matters: ', options: { bold: true } },
      { text: 'assistive use, where a user can look but cannot easily point or speak, in a scene full of similar mugs, pill bottles and cans' },
    ], { x: 0.5, y: 6.42, w: 12.33, h: 0.5, fontSize: 16, color: C.INK });
    H.text(s, 'Glasses and wrist crops: clip_glasses_vs_wrist_crops_2026-10-20.jpg (T8.7 pairs)', { x: 6.8, y: 7.08, w: 5.4, h: 0.25, fontSize: 10, color: C.MUTED, align: 'right' });
    H.footer(s, 'Dion');
    s.addNotes(notes(2));
  }

  // ---------------- Slide 3: objective and the two papers ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '1. Problem and objectives' });
    H.title(s, "Objective: join FAM-HRI's gaze and speech with HiCo-Nav's exploration and memory");
    H.text(s, [
      { text: 'Main objective: ', options: { bold: true, color: C.NAVY } },
      { text: 'a mobile manipulator that takes a spoken command and the user’s gaze, explores a room it cannot see at the start, finds the object the user looked at, drives to it and grasps it' },
    ], { x: 0.5, y: 1.5, w: 12.33, h: 0.7, fontSize: 18 });
    const blocks = [
      { x: 0.5, name: 'FAM-HRI', cite: 'Lai et al., 2025',
        does: 'Meta Aria glasses: gaze and speech tell a robot arm which object to pick',
        take: 'Speech to an object word, gaze to pick the object, the arm grasp',
        limit: 'The object must already be in front of the arm' },
      { x: 6.93, name: 'HiCo-Nav', cite: 'Xu et al., ICRA 2026',
        does: 'A robot explores an unseen room, builds a memory graph of every object it sees, and answers language queries',
        take: '3D pose from FAST-LIVO2, the memory graph (3D position and CLIP image feature per object), sentence to object classes, exploration',
        notTaken: 'Not taken: its own motion planner (we send goals to Nav2). Its smarter exploration order is optional (M9)',
        limit: 'It finds a class ("a box"), not the one you mean' },
    ];
    const by = 2.28, bh = 3.72, bw = 5.9;
    blocks.forEach(b => {
      H.rect(s, b.x, by, bw, bh, { fill: C.WHITE, line: C.LINE, lw: 1 });
      const ix = b.x + 0.22, iw = bw - 0.44;
      H.text(s, [
        { text: b.name + '  ', options: { bold: true, fontSize: 22, color: C.INK } },
        { text: b.cite, options: { fontSize: 14, color: C.SLATE } },
      ], { x: ix, y: by + 0.12, w: iw, h: 0.42, valign: 'middle' });
      H.text(s, 'What it does', { x: ix, y: by + 0.58, w: iw, h: 0.25, fontSize: 13, bold: true, color: C.SLATE });
      H.text(s, b.does, { x: ix, y: by + 0.82, w: iw, h: 0.55, fontSize: 16 });
      H.text(s, 'What we take', { x: ix, y: by + 1.42, w: iw, h: 0.25, fontSize: 13, bold: true, color: C.NAVY });
      H.rect(s, ix, by + 1.67, iw, 0.84, { fill: C.NAVY_T, line: null });
      H.text(s, b.take, { x: ix + 0.12, y: by + 1.67, w: iw - 0.24, h: 0.84, fontSize: 16, color: C.INK, valign: 'middle' });
      if (b.notTaken) H.text(s, b.notTaken, { x: ix, y: by + 2.55, w: iw, h: 0.48, fontSize: 13.5, color: C.MUTED, italic: true });
      H.text(s, 'What it cannot do for us', { x: ix, y: by + 3.05, w: iw, h: 0.25, fontSize: 13, bold: true, color: C.RED });
      H.text(s, b.limit, { x: ix, y: by + 3.3, w: iw, h: 0.32, fontSize: 16.5, bold: true, color: C.INK, valign: 'middle' });
    });
    // the bridge: what we add
    const bry = 6.1;
    H.seg(s, 3.45, by + bh, 3.45, bry, { color: C.NAVY, w: 2, arrow: true });
    H.seg(s, 9.88, by + bh, 9.88, bry, { color: C.NAVY, w: 2, arrow: true });
    H.rect(s, 0.5, bry, 12.33, 0.6, { fill: C.NAVY, line: null });
    H.text(s, [
      { text: 'What we add to join them: ', options: { bold: true } },
      { text: 'the robot compares each object it finds with the object the user looked at, drives to the match, and confirms it with the wrist camera before grasping' },
    ], { x: 0.7, y: bry, w: 11.93, h: 0.6, fontSize: 16, color: C.WHITE, valign: 'middle' });
    H.text(s, [{ text: 'Evaluation: ', options: { bold: true } }, { text: 'end-to-end trials, success counted per phase' }],
      { x: 0.5, y: 6.78, w: 8, h: 0.28, fontSize: 15, color: C.INK });
    H.footer(s, 'Dion');
    s.addNotes(notes(3));
  }

  // ---------------- Slide 4: five phases ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '2. Intended system' });
    H.title(s, 'The target system works in five phases');
    const ph = [
      { n: '1', name: 'Intent capture', job: 'Speech gives the word, gaze picks the object, crop it', b: [['tested', 'Tested on replay']], own: 'Dion' },
      { n: '2', name: 'Explore and find the user', job: 'Explores, maps the room and remembers objects with 3D position and image feature. Looks for the user first', b: [['tested', 'Map tested live (pushed by hand)'], ['isolated', 'Memory graph tested offline'], ['planned', 'Exploration and finding the user planned']], own: 'Sherman, Zongzhe, Dion' },
      { n: '3', name: 'Search', job: 'Compare each object with the gaze target. A match ends exploration', b: [['built', 'Graph search built for sentences'], ['planned', 'Gaze match planned (T8.2)']], own: 'Zongzhe, Dion' },
      { n: '4', name: 'Approach and confirm', job: 'Drive to the object. The wrist camera confirms it is the same one', b: [['tested', 'Confirm tested on replay, now steers the grasp'], ['planned', 'Driving planned']], own: 'Dion, Sherman' },
      { n: '5', name: 'Grasp', job: 'Grasp candidates on the wrist point cloud, plan, execute', b: [['tested', 'Tested on the real arm']], own: 'Dion' },
    ];
    const bw = 2.25, gap = 0.27, by = 1.55, bh = 3.85;
    ph.forEach((p, i) => {
      const x = 0.5 + i * (bw + gap);
      H.rect(s, x, by, bw, bh, { fill: C.WHITE, line: C.INK, lw: 1.25 });
      H.text(s, [{ text: p.n + '  ', options: { color: C.NAVY } }, { text: p.name }],
        { x: x + 0.14, y: by + 0.12, w: bw - 0.28, h: 0.62, fontSize: 17, bold: true, valign: 'top' });
      H.text(s, p.job, { x: x + 0.14, y: by + 0.74, w: bw - 0.28, h: 1.35, fontSize: 13.5, color: C.INK });
      // badges stacked from the bottom up
      const bhh = 0.5, bg = 0.07;
      p.b.forEach((bb, j) => {
        const yy = by + bh - 0.12 - (p.b.length - j) * bhh - (p.b.length - 1 - j) * bg;
        H.badge(s, x + 0.12, yy, bw - 0.24, bhh, bb[0], bb[1], { fs: 12 });
      });
      H.text(s, p.own, { x, y: by + bh + 0.06, w: bw, h: 0.28, fontSize: 13, color: C.SLATE, align: 'center' });
      if (i < 4) H.seg(s, x + bw + 0.03, by + 0.95, x + bw + gap - 0.03, by + 0.95, { color: C.INK, w: 1.75, arrow: true });
    });
    H.legend(s, 0.5, 5.76, ['tested', 'built', 'isolated', 'planned']);
    H.text(s, 'Owner under each phase', { x: 9.83, y: 5.76, w: 3.0, h: 0.25, fontSize: 11, color: C.MUTED, align: 'right', valign: 'middle' });
    // scope decisions
    const sy = 6.08;
    H.rect(s, 0.5, sy, 12.33, 0.92, { fill: C.TINT, line: null });
    H.text(s, 'Scope decisions', { x: 0.68, y: sy + 0.08, w: 2.0, h: 0.3, fontSize: 14, bold: true, color: C.NAVY });
    const items = [
      [{ text: 'Exploration is the core of the search. The paper’s smarter exploration order (M9) is cut first if time runs short' }],
      [{ text: 'Finding the user speeds up exploration: the object is somewhere the user can see' }],
      [{ text: 'Out of scope: bringing the object back to the user' }],
      [{ text: 'Final demonstration target: ' }, { text: 'March 2027 (M10)', options: { bold: true } }],
    ];
    const cw = [4.6, 3.3, 2.05, 2.2];
    let cx = 0.68;
    items.forEach((it, i) => {
      H.text(s, it, { x: cx, y: sy + 0.36, w: cw[i] - 0.2, h: 0.54, fontSize: 12.5, color: C.INK });
      cx += cw[i] + 0.05;
    });
    H.footer(s, 'Zongzhe');
    s.addNotes(notes(4));
  }

  // ---------------- Slide 5: starting point and approach ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '3. Starting point and approach' });
    H.title(s, 'We inherited code that did not run, so we built a test bench and a contract first');
    // before card
    H.rect(s, 0.5, 1.6, 4.45, 4.8, { fill: C.WHITE, line: C.RED, lw: 1.75 });
    H.text(s, 'September 2026 starting point', { x: 0.7, y: 1.72, w: 4.1, h: 0.4, fontSize: 18, bold: true, color: C.RED });
    const before = [
      'A year of code from an earlier team. No tests, no CI',
      'One program moved the real arm within seconds of starting, unprompted',
      'The AnyGrasp path was unreachable',
      'Navigation ran only from another user’s private workspace, and the repo copy did not build',
      'No memory graph code',
    ];
    H.text(s, before.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < before.length - 1 } })),
      { x: 0.7, y: 2.25, w: 4.05, h: 4.0, fontSize: 18, color: C.INK, paraSpaceAfter: 12 });
    // three people
    const people = [
      { n: 'Dion', own: 'Glasses, cross-camera matching, arm and grasp, test bench and CI', on: 'Aria SDK, SAM 3, AnyGrasp, MoveIt 2', ms: 'M1, M2, M4, M7, M8' },
      { n: 'Sherman', own: 'Mobile base, LiDAR, camera mount, mapping and localisation', on: 'FAST-LIVO2, Nav2, SLAM Toolbox', ms: 'M3, M5 (mount)' },
      { n: 'Zongzhe', own: 'Memory graph, sentence reasoning, navigation goal nodes', on: 'HiCo-Nav method, open_clip, Qwen2.5', ms: 'M0, M6, M9' },
    ];
    const px = 5.3, pw = 2.39, pg = 0.13;
    people.forEach((p, i) => {
      const x = px + i * (pw + pg);
      H.rect(s, x, 1.6, pw, 3.3, { fill: C.TINT, line: null });
      H.text(s, p.n, { x: x + 0.15, y: 1.7, w: pw - 0.3, h: 0.4, fontSize: 19, bold: true, color: C.NAVY });
      H.text(s, p.own, { x: x + 0.15, y: 2.12, w: pw - 0.3, h: 1.0, fontSize: 14.5 });
      H.text(s, [
        { text: 'Builds on', options: { bold: true, color: C.SLATE, fontSize: 12, breakLine: true } },
        { text: p.on, options: { fontSize: 13.5, color: C.INK } },
      ], { x: x + 0.15, y: 3.2, w: pw - 0.3, h: 0.8 });
      H.text(s, [
        { text: 'Leads', options: { bold: true, color: C.SLATE, fontSize: 12, breakLine: true } },
        { text: p.ms, options: { fontSize: 13.5, color: C.INK } },
      ], { x: x + 0.15, y: 4.08, w: pw - 0.3, h: 0.7 });
    });
    // shared base band
    H.rect(s, px, 5.02, 3 * pw + 2 * pg, 0.82, { fill: C.NAVY, line: null });
    H.text(s, [
      { text: 'Shared base: ', options: { bold: true } },
      { text: 'channel contract naming the owner of every topic and frame + 7-level test bench (L0 static checks to L6 real robot) + CI on every PR, plus a GPU runner on the lab machine' },
    ], { x: px + 0.18, y: 5.02, w: 3 * pw + 2 * pg - 0.36, h: 0.82, fontSize: 14.5, color: C.WHITE, valign: 'middle' });
    H.text(s, [
      { text: 'Baseline first, then replace: ', options: { bold: true } },
      { text: 'keypoint matching measured before CLIP replaced it' },
    ], { x: px, y: 6.0, w: 3.55, h: 0.85, fontSize: 14.5 });
    H.text(s, [
      { text: 'Hardware one step at a time: ', options: { bold: true } },
      { text: 'written pass rule, saved log, two people present' },
    ], { x: px + 3.8, y: 6.0, w: 3.6, h: 0.85, fontSize: 14.5 });
    H.footer(s, 'Sherman');
    s.addNotes(notes(5));
  }

  // ---------------- Slide 6: intent capture ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '4. Phase 1: intent capture' });
    H.phase(s, 1);
    H.title(s, 'Speech gives the word, gaze picks the object');
    const steps = [
      ['Voice', 'Speech detector, Whisper, small language model returns one object word ("box"). One message per sentence, down from 31'],
      ['Pick the moment', 'The glasses frame from when you spoke (gaze window of 1.0 s)'],
      ['Segment', 'SAM 3 finds every "box" in that frame'],
      ['Gaze vote', 'Each gaze sample votes for the mask under it. Winner needs half the votes. Crop its box plus 20 px: the reference crop goes to the robot'],
    ];
    const sw = 2.9, sg = 0.243, sy = 1.5, sh = 1.5;
    steps.forEach((st, i) => {
      const x = 0.5 + i * (sw + sg);
      H.rect(s, x, sy, sw, sh, { fill: i === 3 ? C.NAVY_T : C.TINT, line: null });
      H.text(s, [{ text: (i + 1) + '  ', options: { color: C.NAVY } }, { text: st[0] }], { x: x + 0.12, y: sy + 0.08, w: sw - 0.24, h: 0.32, fontSize: 16, bold: true });
      H.text(s, st[1], { x: x + 0.12, y: sy + 0.42, w: sw - 0.24, h: sh - 0.48, fontSize: 13 });
      if (i < 3) H.seg(s, x + sw + 0.02, sy + sh / 2, x + sw + sg - 0.02, sy + sh / 2, { color: C.INK, w: 1.5, arrow: true });
    });
    // two real gaze picks
    const iy = 3.15, iw = 3.1, ih = iw * 590 / 645;
    s.addImage({ path: IMG + 'gaze_1m.jpg', x: 0.5, y: iy, w: iw, h: ih, altText: 'Glasses frame at 1 m, gaze on the box' });
    s.addImage({ path: IMG + 'gaze_15m.jpg', x: 3.75, y: iy, w: iw, h: ih, altText: 'Glasses frame at 1.5 m, gaze on the mats' });
    H.rect(s, 3.75, iy, iw, ih, { line: C.RED, lw: 2 });
    H.text(s, [{ text: '1.0 m: ', options: { bold: true } }, { text: 'gaze on the box, box picked' }], { x: 0.5, y: iy + ih + 0.06, w: iw, h: 0.3, fontSize: 13, color: ST.tested.d });
    H.text(s, [{ text: '1.5 m: ', options: { bold: true } }, { text: 'gaze landed on the mats' }], { x: 3.75, y: iy + ih + 0.06, w: iw, h: 0.3, fontSize: 13, color: C.RED });
    // callout on the miss: gaze circle sits at about (0.53, 0.37) of the crop
    const gx = 3.75 + 0.53 * iw, gy = iy + 0.37 * ih;
    H.rect(s, 4.95, iy + ih - 0.62, 1.8, 0.48, { fill: C.WHITE, line: C.RED, lw: 1 });
    H.text(s, 'gaze landed on the mats', { x: 4.95, y: iy + ih - 0.62, w: 1.8, h: 0.48, fontSize: 12, bold: true, color: C.RED, align: 'center', valign: 'middle' });
    H.seg(s, 5.85, iy + ih - 0.62, gx + 0.1, gy + 0.42, { color: C.RED, w: 1.5, arrow: true });
    H.text(s, 'Blue ring: gaze. Box outline: masks SAM 3 found. Frames from aria_gaze_pick_vs_distance_2026-10-20.jpg', { x: 0.5, y: iy + ih + 0.36, w: 6.35, h: 0.25, fontSize: 10, color: C.MUTED });
    // results
    const rx = 7.25, rw = 5.58;
    H.text(s, [
      { text: '60 of 61', options: { fontSize: 40, bold: true, color: C.NAVY, breakLine: true } },
      { text: 'frames, right box', options: { fontSize: 17, bold: true, breakLine: true } },
      { text: 'recording, 1.4 to 2.4 m, steady stare', options: { fontSize: 14, color: C.SLATE } },
    ], { x: rx, y: 3.15, w: rw / 2 - 0.1, h: 1.55 });
    H.text(s, [
      { text: '4 of 4', options: { fontSize: 40, bold: true, color: C.NAVY, breakLine: true } },
      { text: 'spoken words produced a reference crop', options: { fontSize: 17, bold: true, breakLine: true } },
      { text: 'full chain on replay', options: { fontSize: 14, color: C.SLATE } },
    ], { x: rx + rw / 2 + 0.1, y: 3.15, w: rw / 2 - 0.1, h: 1.55 });
    H.text(s, 'Word ready about 1.1 s after speech ends', { x: rx, y: 4.75, w: rw, h: 0.32, fontSize: 15 });
    H.rect(s, rx, 5.17, rw, 0.95, { fill: C.AMBER_T, line: ST.built.c, lw: 1 });
    H.text(s, [
      { text: 'Limit: ', options: { bold: true, color: ST.built.d } },
      { text: 'gaze is off by about 5.6 degrees (60 px at 1.4 m), about 15 cm at 1.5 m. At 1.5 m it landed on a stack of mats' },
    ], { x: rx + 0.15, y: 5.17, w: rw - 0.3, h: 0.95, fontSize: 14.5, valign: 'middle' });
    H.badge(s, rx, 6.33, 1.3, 0.34, 'tested', 'Tested', { fs: 12, bold: true });
    H.text(s, 'on recordings and replay. Live glasses stream still throttled on the lab machine', { x: rx + 1.4, y: 6.25, w: rw - 1.4, h: 0.5, fontSize: 13, color: C.SLATE, valign: 'middle' });
    H.footer(s, 'Dion');
    s.addNotes(notes(6));
  }

  // ---------------- Slide 7: FAST-LIVO2 map ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '5. Phase 2: map and frames' });
    H.phase(s, 2);
    H.title(s, 'The base builds a coloured 3D map that closes within 12 mm over a 26 m loop');
    H.ph(s, 0.5, 1.58, 5.1, 3.25, 'MAP BUILD-UP ANIMATION',
      'nav_fastlivo_map_buildup_clean_handdriven1_2026-10-24.gif (10 s, about 12x). Alt: ..._map_orbit_clean_... .gif. Still fallback: ..._map_iso_clean_... .png. Orange line = path, green dot = start, white square = end', 'Sherman', { fs: 14, fs2: 10.5 });
    H.ph(s, 5.75, 1.58, 1.9, 1.9, 'CLOSURE ZOOM', 'nav_fastlivo_path_closure_zoom_clean_handdriven1_2026-10-24.png', 'Sherman', { fs: 11, fs2: 9 });
    H.text(s, '10 cm zoom, bar = 2 cm, start to end 12 mm', { x: 5.75, y: 3.52, w: 1.9, h: 0.5, fontSize: 11, color: C.SLATE });
    // what it is + why 3D
    H.text(s, [
      { text: 'What it is: ', options: { bold: true } },
      { text: 'FAST-LIVO2 fuses the Livox MID-360 LiDAR, its IMU and the base D455 colour camera into a pose and a coloured map. The HiCo-Nav paper uses it for its camera poses, with the same LiDAR' },
    ], { x: 0.5, y: 4.95, w: 3.55, h: 1.15, fontSize: 12.5 });
    H.text(s, [
      { text: 'Why 3D, not 2D SLAM: ', options: { bold: true } },
      { text: 'the memory graph places every object in 3D from the camera pose, so it also needs height, pitch and roll (1 degree of pitch moves an object 4 m away by about 7 cm). Nav2 still drives on a 2D grid, fed by this pose' },
    ], { x: 4.2, y: 4.95, w: 3.45, h: 1.15, fontSize: 12.5 });
    // 2D vs 3D chips
    H.rect(s, 5.75, 4.07, 0.92, 0.6, { fill: C.WHITE, line: C.MUTED });
    H.text(s, [{ text: '2D', options: { bold: true, breakLine: true } }, { text: 'x, y, heading' }], { x: 5.75, y: 4.07, w: 0.92, h: 0.6, fontSize: 10, align: 'center', valign: 'middle', color: C.SLATE });
    H.rect(s, 6.73, 4.07, 0.92, 0.6, { fill: C.NAVY_T, line: C.NAVY });
    H.text(s, [{ text: '3D', options: { bold: true, breakLine: true } }, { text: 'full pose' }], { x: 6.73, y: 4.07, w: 0.92, h: 0.6, fontSize: 10, align: 'center', valign: 'middle', color: C.NAVY });
    // results
    const rx = 8.0, rw = 4.83;
    H.text(s, 'Hand-pushed loop, recording handdriven1, 20 Oct', { x: rx, y: 1.58, w: rw, h: 0.28, fontSize: 12.5, color: C.SLATE, italic: true });
    const res = [
      ['12 mm', '26.05 m loop, back to start within 12 mm', '4 mm LiDAR-only, 7 mm odometry error, 0.03 %'],
      ['6.7 cm', 'mid-route error at most', 'at the floor of our reference (about 7 cm)'],
      ['11 to 14 ms', 'per frame on the CPU', 'inside the 100 ms scan period'],
    ];
    res.forEach((r, i) => {
      const y = 1.92 + i * 0.98;
      H.text(s, r[0], { x: rx, y, w: 1.95, h: 0.85, fontSize: 28, bold: true, color: C.NAVY, valign: 'middle' });
      H.text(s, [{ text: r[1], options: { bold: true, breakLine: true } }, { text: r[2], options: { color: C.SLATE } }], { x: rx + 2.0, y, w: rw - 2.0, h: 0.85, fontSize: 13, valign: 'middle' });
    });
    H.rect(s, rx, 4.95, rw, 0.72, { fill: C.AMBER_T, line: ST.built.c });
    H.text(s, [{ text: 'Limit: ', options: { bold: true, color: ST.built.d } }, { text: 'pushed by hand, not driven. Nav2 has never driven the base' }],
      { x: rx + 0.15, y: 4.95, w: rw - 0.3, h: 0.72, fontSize: 14, valign: 'middle' });
    // six-step port strip
    const fy = 6.22, fh = 0.68;
    H.rect(s, 0.5, fy, 1.45, fh, { fill: C.NAVY, line: null });
    H.text(s, [{ text: 'ROS 1 to ROS 2 port', options: { bold: true, breakLine: true } }, { text: '15 to 22 Oct' }], { x: 0.55, y: fy, w: 1.35, h: fh, fontSize: 11, color: C.WHITE, valign: 'middle', align: 'center' });
    const fsx = 2.1, fsw = 1.66, fsg = 0.12;
    const fsteps = [['1 Build', 'sealed container'], ['2 Authors’ data', '14,850 / 14,850'], ['3 Our sensors', 'every message audited'], ['4 Silent defects', '3 found, fixed'], ['5 Live', '26 m loop'], ['6 Hand to Nav2', 'tilt under 0.5 deg']];
    fsteps.forEach((f, i) => {
      const x = fsx + i * (fsw + fsg);
      H.rect(s, x, fy, fsw, fh, { fill: C.TINT, line: null });
      H.text(s, [{ text: f[0], options: { bold: true, breakLine: true } }, { text: f[1], options: { color: C.SLATE } }], { x: x + 0.06, y: fy, w: fsw - 0.12, h: fh, fontSize: 12, align: 'center', valign: 'middle' });
      if (i < 5) H.seg(s, x + fsw + 0.01, fy + fh / 2, x + fsw + fsg - 0.01, fy + fh / 2, { color: C.INK, w: 1, arrow: true });
    });
    H.footer(s, 'Sherman');
    s.addNotes(notes(7));
  }

  // ---------------- Slide 8: four camera relationships ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '5. Phase 2: map and frames' });
    H.phase(s, 2, 'frames also serve phases 4 and 5');
    H.title(s, 'Four camera relationships, four different states of calibration');
    const G = ST.tested.c, A = ST.built.c, P = ST.planned.c;
    // inset placeholder
    H.ph(s, 0.5, 1.58, 2.0, 1.5, 'LIDAR-ON-CAMERA OVERLAY', 'nav_lidar_on_camera_overlay_stationary02_t0s_2026-10-19.png', 'Sherman', { fs: 10.5, fs2: 8.5 });
    H.text(s, 'before calibration: LiDAR points over the camera image', { x: 0.5, y: 3.12, w: 2.0, h: 0.42, fontSize: 10.5, color: C.SLATE });
    // schematic robot, side view, facing right
    const fl = 5.95;
    H.seg(s, 0.6, fl, 6.85, fl, { color: C.MUTED, w: 1 });
    H.rect(s, 1.3, 5.0, 2.8, 0.66, { fill: 'EEF1F5', line: C.SLATE, lw: 1.25 }); // base
    H.text(s, 'Base', { x: 1.35, y: 5.05, w: 0.9, h: 0.3, fontSize: 11, color: C.SLATE });
    H.oval(s, 1.5, 5.6, 0.36, 0.36, { fill: C.SLATE, line: C.SLATE });
    H.oval(s, 3.5, 5.6, 0.36, 0.36, { fill: C.SLATE, line: C.SLATE });
    H.rect(s, 1.9, 3.75, 0.07, 1.25, { fill: 'B8C0CC', line: null }); // frame posts
    H.rect(s, 3.5, 3.75, 0.07, 1.25, { fill: 'B8C0CC', line: null });
    H.rect(s, 1.9, 3.68, 1.75, 0.09, { fill: 'B8C0CC', line: null }); // platform
    H.rect(s, 3.6, 3.55, 0.42, 0.2, { fill: C.INK, line: null }); // D455
    H.text(s, 'D455', { x: 4.07, y: 3.5, w: 0.6, h: 0.28, fontSize: 11, bold: true });
    H.rect(s, 3.05, 4.62, 0.5, 0.38, { fill: C.INK, line: null }); // LiDAR on base top, front
    H.text(s, 'LiDAR', { x: 2.35, y: 4.62, w: 0.68, h: 0.36, fontSize: 11, bold: true, align: 'right', valign: 'middle' });
    // arm: root on platform
    const ac = 'A8B1BF';
    H.seg(s, 2.75, 3.68, 2.75, 2.55, { color: ac, w: 9 });
    H.seg(s, 2.75, 2.55, 4.3, 2.1, { color: ac, w: 9 });
    H.seg(s, 4.3, 2.1, 4.95, 2.55, { color: ac, w: 7 });
    H.rect(s, 2.6, 3.5, 0.3, 0.2, { fill: C.SLATE, line: null }); // arm root
    H.text(s, 'Arm', { x: 2.88, y: 2.8, w: 0.6, h: 0.28, fontSize: 11, bold: true, color: C.SLATE });
    H.rect(s, 4.95, 2.48, 0.34, 0.16, { fill: C.INK, line: null }); // wrist D435i
    H.seg(s, 5.05, 2.64, 5.05, 2.92, { color: C.SLATE, w: 2.5 }); // gripper
    H.seg(s, 5.2, 2.64, 5.2, 2.92, { color: C.SLATE, w: 2.5 });
    H.text(s, 'Wrist D435i', { x: 5.35, y: 2.38, w: 1.1, h: 0.28, fontSize: 11, bold: true });
    // user with glasses
    const ux = 6.25;
    H.oval(s, ux - 0.2, 1.7, 0.4, 0.4, { fill: C.WHITE, line: C.INK, lw: 1.5 });
    H.rect(s, ux - 0.24, 1.82, 0.48, 0.09, { fill: C.INK, line: null });
    H.seg(s, ux, 2.1, ux, 3.9, { color: C.INK, w: 2 });
    H.seg(s, ux, 2.5, ux - 0.35, 3.2, { color: C.INK, w: 2 });
    H.seg(s, ux, 2.5, ux + 0.35, 3.2, { color: C.INK, w: 2 });
    H.seg(s, ux, 3.9, ux - 0.3, fl, { color: C.INK, w: 2 });
    H.seg(s, ux, 3.9, ux + 0.3, fl, { color: C.INK, w: 2 });
    H.text(s, 'User + Aria glasses', { x: 5.5, y: 1.35, w: 1.5, h: 0.3, fontSize: 11, bold: true, align: 'center' });
    // links
    H.seg(s, 2.45, 4.98, 2.7, 3.75, { color: G, w: 3, both: true }); // 1 base-arm
    H.num(s, 2.15, 4.15, 1, G);
    H.seg(s, 3.82, 3.8, 3.4, 4.6, { color: A, w: 3, both: true }); // 2 D455-LiDAR
    H.num(s, 3.85, 4.1, 2, A);
    H.seg(s, 4.62, 2.3, 4.97, 2.5, { color: G, w: 3, both: true }); // 3 wrist-arm
    H.num(s, 4.5, 2.62, 3, G);
    H.seg(s, ux - 0.26, 1.95, 4.15, 5.0, { color: P, w: 2.25, dash: 'dash', both: true }); // 4 glasses-robot
    H.num(s, 5.0, 3.62, 4, P);
    H.text(s, 'Schematic side view, not to scale', { x: 0.5, y: 6.0, w: 3, h: 0.25, fontSize: 10, color: C.MUTED });
    // right: four cards
    const cx = 7.15, cw = 5.68;
    const cards = [
      { n: 1, col: G, st: 'tested', name: 'Base to arm', state: 'Measured', use: 'Arm grasps in the base’s map',
        d: '(0.18, 0, 0.48) m, yaw 180 degrees, matched on the robot. Base origin (floor, under the drive axle) checked against the vendor manual', h: 1.2 },
      { n: 2, col: A, st: 'built', name: 'Base camera to LiDAR', state: 'Mount measured, not calibrated', use: 'Object positions and depth in the memory graph',
        d: 'Measured to the camera’s mounting hole, Intel’s published dimensions from there. Rotation set by construction (flush on vertical aluminium extrusions), not measured with a tool. Mount values wired and unit-tested (12 software checks). Not yet calibrated to the LiDAR: about 6.7 px of error per degree. Rig planned (T5.5)', h: 1.82 },
      { n: 3, col: G, st: 'tested', name: 'Wrist camera to arm', state: 'Calibrated', use: 'Turning a grasp seen by the camera into an arm goal', d: '', h: 0.74 },
      { n: 4, col: P, st: 'planned', name: 'Glasses to robot', state: 'Planned (T8.8)', use: 'A gaze ray in the robot’s own 3D frame, for look-alike objects', d: 'Three methods ranked', h: 0.97 },
    ];
    let y = 1.55;
    cards.forEach(c => {
      H.rect(s, cx, y, cw, c.h, { fill: C.WHITE, line: C.LINE });
      H.num(s, cx + 0.12, y + 0.1, c.n, c.col, 0.3);
      H.text(s, c.name, { x: cx + 0.52, y: y + 0.08, w: 2.6, h: 0.34, fontSize: 15, bold: true, valign: 'middle' });
      const bw = 0.085 * c.state.length + 0.3;
      H.badge(s, cx + cw - bw - 0.1, y + 0.1, bw, 0.3, c.st, c.state, { fs: 11.5, bold: true });
      H.text(s, [{ text: 'Used for: ', options: { bold: true, color: C.SLATE } }, { text: c.use, options: { color: C.SLATE } }], { x: cx + 0.52, y: y + 0.44, w: cw - 0.65, h: 0.28, fontSize: 12.5 });
      if (c.d) H.text(s, c.d, { x: cx + 0.52, y: y + 0.72, w: cw - 0.65, h: c.h - 0.76, fontSize: 12.5 });
      y += c.h + 0.06;
    });
    H.text(s, [
      { text: 'Line key: ', options: { bold: true } },
      { text: 'green, measured or calibrated. Amber, measured, not calibrated. Grey dashed, planned' },
    ], { x: 0.5, y: 6.28, w: 6.5, h: 0.25, fontSize: 11, color: C.SLATE });
    H.text(s, 'Camera calibration (where is one camera relative to another) is a separate problem from the robot’s frame tree (where each part is relative to the base)',
      { x: 0.5, y: 6.62, w: 12.33, h: 0.38, fontSize: 13.5, italic: true, color: C.INK });
    H.footer(s, 'Sherman');
    s.addNotes(notes(8));
  }

  // ---------------- Slide 9: memory graph ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '6. Phases 2 and 3: memory graph and search' });
    H.phase(s, 2);
    H.title(s, 'The memory graph turns a drive into objects with a position and an image feature');
    const lw = 7.75;
    H.text(s, [
      { text: 'Objects: ', options: { bold: true, color: C.NAVY } }, { text: 'merged 3D points, a box, an averaged CLIP image feature, a class label', options: { breakLine: true } },
      { text: 'Anchors: ', options: { bold: true, color: C.NAVY } }, { text: 'kept photos with the camera pose, linked to the objects they show' },
    ], { x: 0.5, y: 1.55, w: lw, h: 0.72, fontSize: 16, paraSpaceAfter: 4 });
    H.text(s, 'How it is built, in 14 tested stages', { x: 0.5, y: 2.35, w: lw, h: 0.26, fontSize: 13, bold: true, color: C.SLATE });
    const chips = ['Keep a photo every 1 m or 45 deg', 'SAM 3 finds all 30 classes', 'LiDAR gives depth', 'Lift to 3D', 'CLIP feature per object', 'Merge repeat sightings'];
    const chw = 1.17, chg = 0.146;
    chips.forEach((c, i) => {
      const x = 0.5 + i * (chw + chg);
      H.rect(s, x, 2.65, chw, 0.58, { fill: C.TINT, line: null });
      H.text(s, c, { x: x + 0.04, y: 2.65, w: chw - 0.08, h: 0.58, fontSize: 11, align: 'center', valign: 'middle' });
      if (i < 5) H.seg(s, x + chw + 0.01, 2.94, x + chw + chg - 0.01, 2.94, { color: C.INK, w: 1, arrow: true });
    });
    H.ph(s, 0.5, 3.38, lw, 2.2, 'RERUN 3D VIEW OF THE GRAPH',
      'Grey LiDAR room, each object a labelled box, each anchor a small camera at its pose, lines from cameras to the objects they saw. Screenshot from mg_t6.3_four_photos_rerun_3d_2026-10-21.rrd, or the flythrough video', 'Zongzhe', { fs: 14, fs2: 11 });
    H.ph(s, 0.5, 5.68, lw, 0.8, 'FRAME 700: PHOTO | SAM 3 MASKS | 3D BOXES', 'mg_frame700_masks_and_3d_objects_2026-10-21.png', 'Zongzhe', { fs: 12, fs2: 10 });
    H.badge(s, 0.5, 6.6, 1.15, 0.32, 'isolated', 'Isolated', { fs: 12, bold: true });
    H.text(s, 'Built offline from a recorded drive. Not yet built live while driving', { x: 1.75, y: 6.6, w: 6.5, h: 0.32, fontSize: 13, color: C.SLATE, valign: 'middle' });
    // numbers column
    const rx = 8.65, rw = 4.18;
    H.text(s, 'Recording handdriven1, 3536 frames', { x: rx, y: 1.55, w: rw, h: 0.3, fontSize: 12.5, italic: true, color: C.SLATE });
    const nums = [
      ['29 photos kept', '99.2 % of segmentation time saved'],
      ['1.69 s vs 9.70 s', 'batched SAM 3: 40 phrases, 5.7 times faster than one at a time'],
      ['399 tests pass', 'on the lab GPU'],
      ['9 upstream problems', 'fixed or avoided, for example the language model call had no timeout, and the task score was never set'],
    ];
    nums.forEach((n, i) => {
      const y = 1.95 + i * 1.22;
      H.rect(s, rx, y, rw, 1.12, { fill: i % 2 ? C.WHITE : C.TINT, line: null });
      H.text(s, [{ text: n[0], options: { fontSize: 22, bold: true, color: C.NAVY, breakLine: true } }, { text: n[1], options: { fontSize: 12.5, color: C.INK } }],
        { x: rx + 0.15, y: y + 0.06, w: rw - 0.3, h: 1.0, valign: 'middle' });
    });
    H.footer(s, 'Zongzhe');
    s.addNotes(notes(9));
  }
};

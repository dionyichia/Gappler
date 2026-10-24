const { C, ST } = require('./lib');
const IMG = __dirname + '/img/';

module.exports = function (pres, H, notes) {
  // ---------------- Slide 10: merge radius ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '6. Phases 2 and 3: memory graph and search' });
    H.phase(s, 2);
    H.title(s, 'A 10 cm merge radius cut duplicates from 8 to 3 with no false merges');
    // native scatter so the x axis keeps real radius spacing. Drive 2 sits on separate x slots with gaps so its 3 points are never joined
    const X = [1, 2.5, 5, 7.5, 10, 15, 20, 2.5, 6, 10, 12, 15];
    const N = null;
    const cx = 0.5, cy = 1.55, cw = 7.35, ch = 3.65;
    const L = { x: 0.1, y: 0.05, w: 0.86, h: 0.8 };
    s.addChart(pres.charts.SCATTER, [
      { name: 'X', values: X },
      { name: 'Duplicates, drive 1', values: [31, 8, 4, 4, 3, 3, 2, N, N, N, N, N] },
      { name: 'False merges, drive 1', values: [1, 0, 0, 0, 0, 0, 0, N, N, N, N, N] },
      { name: 'Duplicates, drive 2 (run at 2.5, 10, 15 cm only)', values: [N, N, N, N, N, N, N, 2, N, 1, N, 1] },
    ], {
      x: cx, y: cy, w: cw, h: ch, layout: L, displayBlanksAs: 'gap',
      chartColors: [C.NAVY, 'A9B4C6', ST.isolated.c], lineSize: 2.25, lineDataSymbol: 'circle', lineDataSymbolSize: 8,
      valAxisMinVal: 0, valAxisMaxVal: 32, valAxisMajorUnit: 8, catAxisMinVal: 0, catAxisMaxVal: 21, catAxisMajorUnit: 5,
      valAxisLabelFontSize: 12, catAxisLabelFontSize: 12, valAxisLabelColor: C.SLATE, catAxisLabelColor: C.SLATE,
      valAxisLabelFontFace: '+mn-lt', catAxisLabelFontFace: '+mn-lt',
      showValAxisTitle: true, valAxisTitle: 'Count', valAxisTitleFontSize: 12, valAxisTitleColor: C.SLATE,
      showCatAxisTitle: true, catAxisTitle: 'Match radius (cm)', catAxisTitleFontSize: 12, catAxisTitleColor: C.SLATE,
      valGridLine: { color: 'E3E7EE', size: 0.5 }, catGridLine: { style: 'none' },
      showLegend: false,
    });
    const lgy = cy + ch + 0.02;
    [[C.NAVY, 'Duplicates, drive 1'], ['A9B4C6', 'False merges, drive 1'], [ST.isolated.c, 'Duplicates, drive 2 (run at 2.5, 10, 15 cm only)']].forEach((l, i) => {
      const lx = [0.75, 2.7, 4.65][i];
      H.seg(s, lx, lgy + 0.13, lx + 0.3, lgy + 0.13, { color: l[0], w: i === 2 ? 0.01 : 2.25 });
      H.oval(s, lx + 0.09, lgy + 0.06, 0.13, 0.13, { fill: l[0], line: l[0] });
      H.text(s, l[1], { x: lx + 0.36, y: lgy, w: i === 2 ? 3.3 : 1.75, h: 0.26, fontSize: 11, color: C.INK, valign: 'middle' });
    });
    // vertical "chosen" marker at 10 cm, positioned from the fixed plot layout
    const px = r => cx + cw * (L.x + L.w * r / 21);
    const py = v => cy + ch * (L.y + L.h * (1 - v / 32));
    H.seg(s, px(10), py(32), px(10), py(0), { color: ST.tested.c, w: 1.75, dash: 'dash' });
    H.text(s, 'chosen: 10 cm', { x: px(10) + 0.06, y: py(31.5), w: 1.4, h: 0.28, fontSize: 12, bold: true, color: ST.tested.d });
    H.text(s, 'drive 1: 8 at 2.5 cm, 3 at 10 cm', { x: px(2.5) + 0.12, y: py(12.5), w: 2.4, h: 0.28, fontSize: 11, color: C.NAVY });
    H.text(s, '15 cm: chair merges into desk (drive 2)', { x: px(15) - 1.0, y: py(16.5), w: 2.1, h: 0.5, fontSize: 11, color: C.RED, align: 'center' });
    H.seg(s, px(15), py(12.0), px(15), py(3.8), { color: C.RED, w: 1, arrow: true });
    // CLIP similarity bars
    const by = 5.6;
    H.text(s, [{ text: 'Why not appearance: ', options: { bold: true } }, { text: 'CLIP similarity' }], { x: 0.5, y: by, w: 4, h: 0.28, fontSize: 13 });
    const bars = [['Same chair', 0.934, null, '0.934'], ['Two chairs, same model', 0.81, 0.85, '0.81 to 0.85'], ['Other objects', 0.56, null, '0.56']];
    const bx = 2.55, bwid = 3.6;
    bars.forEach((b, i) => {
      const y = by + 0.34 + i * 0.32;
      H.text(s, b[0], { x: 0.5, y, w: 2.0, h: 0.26, fontSize: 11.5, color: C.SLATE, align: 'right', valign: 'middle' });
      H.rect(s, bx, y + 0.04, bwid * b[1], 0.18, { fill: i === 1 ? C.RED : C.MUTED, line: null });
      if (b[2]) H.rect(s, bx + bwid * b[1], y + 0.04, bwid * (b[2] - b[1]), 0.18, { fill: 'E7A49E', line: null });
      H.text(s, b[3], { x: bx + bwid * (b[2] || b[1]) + 0.08, y, w: 1.1, h: 0.26, fontSize: 11.5, bold: i === 1, valign: 'middle' });
    });
    // right column
    const rx = 8.2, rw = 4.63;
    H.text(s, [
      { text: 'Method', options: { bold: true, color: C.NAVY, fontSize: 14, breakLine: true } },
      { text: 'A hand-made answer key of 16 real objects marked on the LiDAR map (7 chairs, 2 tables, 2 TVs, 2 computer towers, shelf, sofa, door). Independent of the code under test', options: { fontSize: 13.5 } },
    ], { x: rx, y: 1.55, w: rw, h: 1.15 });
    H.text(s, [
      { text: 'Why the radius', options: { bold: true, color: C.NAVY, fontSize: 14, breakLine: true } },
      { text: 'Two views of one object land 4 to 9 cm apart with sparse LiDAR depth. Upstream’s 2.5 cm was too tight', options: { fontSize: 13.5 } },
    ], { x: rx, y: 2.78, w: rw, h: 0.85 });
    H.rect(s, rx, 3.72, rw, 1.05, { fill: ST.tested.t, line: ST.tested.c });
    H.text(s, [
      { text: 'Result at 10 cm: duplicates 8 to 3, 0 false merges, misses unchanged at 3 ', options: { bold: true } },
      { text: '(first drive). Second drive: 2 to 1' },
    ], { x: rx + 0.15, y: 3.72, w: rw - 0.3, h: 1.05, fontSize: 14, valign: 'middle' });
    H.text(s, [
      { text: 'Trade-off', options: { bold: true, color: C.NAVY, fontSize: 14, breakLine: true } },
      { text: 'At 15 cm a chair merges into its desk on the second drive, so 10 cm, not 15', options: { fontSize: 13.5 } },
    ], { x: rx, y: 4.88, w: rw, h: 0.75 });
    H.text(s, [
      { text: 'Appearance alone', options: { bold: true, color: C.NAVY, fontSize: 14, breakLine: true } },
      { text: 'Two chairs of the same model score 0.81 to 0.85. Merging on appearance alone removes duplicates by merging everything (10 to 14 of 16 objects missed)', options: { fontSize: 13.5 } },
    ], { x: rx, y: 5.7, w: rw, h: 1.0 });
    H.text(s, 'Two drives, 16 objects. A difference of one is noise', { x: rx, y: 6.72, w: rw, h: 0.26, fontSize: 11.5, italic: true, color: C.SLATE });
    H.footer(s, 'Zongzhe');
    s.addNotes(notes(10));
  }

  // ---------------- Slide 11: search ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '6. Phases 2 and 3: memory graph and search' });
    H.phase(s, 3);
    H.title(s, 'A sentence becomes a ranked list of objects with 3D positions');
    const fy = 1.55, fh = 2.4;
    const bx = [0.5, 4.75, 9.0], bw = 3.83;
    const head = ['1  Sentence to classes', '2  Score', '3  Rank'];
    bx.forEach((x, i) => {
      H.rect(s, x, fy, bw, fh, { fill: C.WHITE, line: i === 2 ? ST.planned.c : C.LINE, lw: 1.25 });
      H.text(s, head[i], { x: x + 0.18, y: fy + 0.1, w: bw - 0.36, h: 0.34, fontSize: 16, bold: true, color: C.NAVY });
      if (i < 2) H.seg(s, x + bw + 0.03, fy + fh / 2, bx[i + 1] - 0.03, fy + fh / 2, { color: C.INK, w: 1.75, arrow: true });
    });
    // box 1 content
    H.text(s, '"Find the chair"', { x: 0.68, y: fy + 0.5, w: 3.5, h: 0.45, fontSize: 22, italic: true, bold: true });
    H.text(s, 'A local language model (Qwen2.5, 1.5B) returns target and related classes', { x: 0.68, y: fy + 0.98, w: 3.5, h: 0.55, fontSize: 12.5, color: C.SLATE });
    H.rect(s, 0.68, fy + 1.65, 1.45, 0.38, { fill: C.NAVY, line: null });
    H.text(s, 'target: chair', { x: 0.68, y: fy + 1.65, w: 1.45, h: 0.38, fontSize: 13, bold: true, color: C.WHITE, align: 'center', valign: 'middle' });
    H.rect(s, 2.23, fy + 1.65, 1.95, 0.38, { fill: C.WHITE, line: C.NAVY });
    H.text(s, 'related: table, desk', { x: 2.23, y: fy + 1.65, w: 1.95, h: 0.38, fontSize: 13, color: C.NAVY, align: 'center', valign: 'middle' });
    // box 2 content
    H.text(s, 'Each object’s CLIP image feature against the sentence’s CLIP text vector', { x: 4.93, y: fy + 0.5, w: 3.47, h: 0.8, fontSize: 14 });
    const chip = (x, y, w, t, fill) => { H.rect(s, x, y, w, 0.42, { fill, line: null }); H.text(s, t, { x, y, w, h: 0.42, fontSize: 12, align: 'center', valign: 'middle' }); };
    chip(4.93, fy + 1.5, 1.45, 'object image feature', C.TINT);
    H.text(s, 'vs', { x: 6.43, y: fy + 1.5, w: 0.45, h: 0.42, fontSize: 13, align: 'center', valign: 'middle', color: C.SLATE });
    chip(6.93, fy + 1.5, 1.47, 'sentence text vector', C.TINT);
    // box 3 content
    H.text(s, [
      { text: 'Target classes first, then related, each by score', options: { breakLine: true } },
      { text: 'Each hit: object id, 3D centre, best photo', options: { breakLine: true } },
      { text: 'A wrong hit can be rejected and skipped next time' },
    ], { x: 9.18, y: fy + 0.5, w: 3.47, h: 1.35, fontSize: 13.5, paraSpaceAfter: 5 });
    H.rect(s, 9.18, fy + 1.84, 3.47, 0.44, { fill: C.WHITE, line: ST.planned.c, dash: 'dash' });
    H.text(s, 'Acceptance run pending (T6.8)', { x: 9.18, y: fy + 1.84, w: 3.47, h: 0.44, fontSize: 13, bold: true, color: ST.planned.d, align: 'center', valign: 'middle' });
    // results: sentence to classes, 22 instructions
    const ry = 4.15;
    H.text(s, 'Sentence to classes, 22 test instructions (checked by hand)', { x: 0.5, y: ry, w: 7, h: 0.3, fontSize: 14, bold: true });
    const rows = [['Qwen2.5 1.5B (used)', 20], ['Fallback without the model', 15], ['Smaller 0.5B model', 12]];
    const lx = 0.5, labw = 2.6, barx = 3.15, barw = 3.9;
    rows.forEach((r, i) => {
      const y = ry + 0.4 + i * 0.4;
      H.text(s, r[0], { x: lx, y, w: labw, h: 0.32, fontSize: 13, color: i === 0 ? C.INK : C.SLATE, bold: i === 0, align: 'right', valign: 'middle' });
      H.rect(s, barx, y + 0.04, barw, 0.24, { fill: C.TINT, line: null });
      H.rect(s, barx, y + 0.04, barw * r[1] / 22, 0.24, { fill: i === 0 ? C.NAVY : C.MUTED, line: null });
      H.text(s, r[1] + ' of 22', { x: barx + barw + 0.1, y, w: 1.0, h: 0.32, fontSize: 13, bold: i === 0, valign: 'middle' });
    });
    H.text(s, [{ text: '0.28 to 0.32 s', options: { fontSize: 26, bold: true, color: C.NAVY, breakLine: true } }, { text: 'a reply, running locally', options: { fontSize: 13, color: C.SLATE } }],
      { x: 9.0, y: ry + 0.35, w: 3.83, h: 0.95 });
    // status and note
    H.badge(s, 0.5, 6.0, 1.5, 0.34, 'built', 'Built', { fs: 12, bold: true });
    H.text(s, [{ text: 'Steps 2 and 3 tested on stand-ins and a few photos. ' }, { text: 'The full query on the recorded drive is the acceptance test, scheduled weeks 7 to 8 (T6.8)', options: { bold: true } }],
      { x: 2.1, y: 5.95, w: 10.73, h: 0.45, fontSize: 13.5, valign: 'middle' });
    H.text(s, 'Today the query is a sentence. In the full system each object is matched against the gaze crop’s feature, and a match ends exploration (M8)',
      { x: 0.5, y: 6.5, w: 12.33, h: 0.45, fontSize: 13.5, italic: true, color: C.SLATE });
    H.footer(s, 'Zongzhe');
    s.addNotes(notes(11));
  }

  // ---------------- Slide 12: cross-camera match ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '7. Phases 4 and 5: cross-camera match and grasp' });
    H.phase(s, 4);
    H.title(s, 'CLIP finds the looked-at box across cameras, and now steers the grasp');
    H.text(s, [{ text: 'The question: ', options: { bold: true } }, { text: 'which wrist-camera mask is the object in the glasses crop?' }], { x: 0.5, y: 1.52, w: 12.33, h: 0.32, fontSize: 16 });
    // left panel
    const lx = 0.5, lw = 5.95, py0 = 1.98;
    H.text(s, '1  Choose the method', { x: lx, y: py0, w: lw, h: 0.34, fontSize: 17, bold: true, color: C.NAVY });
    H.text(s, '25 glasses-wrist pairs with 2 to 12 decoys, unless noted. Share of pairs with the box ranked first', { x: lx, y: py0 + 0.34, w: lw, h: 0.45, fontSize: 11.5, color: C.SLATE });
    const m = [['SuperPoint + LightGlue keypoints (baseline, 15 pairs)', 0, '0 of 15'], ['SAM 3 decoder vector', 0.28, '7 of 25'], ['SAM 3 image features', 0.6, '15 of 25'], ['CLIP whole-object feature', 1, '25 of 25']];
    const labw = 2.35, bx = lx + 2.45, bw = 2.5;
    m.forEach((r, i) => {
      const y = py0 + 0.85 + i * 0.5;
      H.text(s, r[0], { x: lx, y, w: labw, h: 0.44, fontSize: 12, align: 'right', valign: 'middle', bold: i === 3, color: i === 3 ? C.INK : C.SLATE });
      H.rect(s, bx, y + 0.1, bw, 0.24, { fill: C.TINT, line: null });
      if (r[1] > 0) H.rect(s, bx, y + 0.1, bw * r[1], 0.24, { fill: i === 3 ? C.NAVY : C.MUTED, line: null });
      H.text(s, r[2], { x: bx + bw + 0.08, y, w: 0.95, h: 0.44, fontSize: 12.5, bold: true, valign: 'middle', color: i === 0 ? C.RED : C.INK });
    });
    const ty = py0 + 2.95, tw = 3.4, th = tw * 686 / 1600;
    s.addImage({ path: IMG + 'lightglue.jpg', x: lx, y: ty, w: tw, h: th, altText: 'LightGlue baseline: wrong keypoint matches' });
    H.text(s, 'Baseline: keypoints match the ceiling and floor, not the box', { x: lx + tw + 0.15, y: ty, w: lw - tw - 0.15, h: th, fontSize: 12, color: C.SLATE, valign: 'middle' });
    // right panel
    const rx = 6.85, rw = 5.98;
    H.text(s, '2  In the grasp loop (T8.9a)', { x: rx, y: py0, w: rw, h: 0.34, fontSize: 17, bold: true, color: C.NAVY });
    H.text(s, 'The grasp client compares every wrist mask with the glasses crop and takes the closest. Below 0.56, or a tie within 0.01, it publishes nothing and the arm waits',
      { x: rx, y: py0 + 0.38, w: rw - 1.15, h: 0.95, fontSize: 13 });
    s.addImage({ path: IMG + 'pair.jpg', x: rx + rw - 0.68, y: py0, w: 0.68, h: 1.36, altText: 'Glasses crop above, wrist crop below' });
    H.text(s, 'glasses above, wrist below', { x: rx + rw - 1.05, y: py0 + 1.38, w: 1.05, h: 0.4, fontSize: 9.5, color: C.SLATE, align: 'right' });
    H.text(s, 'Wrist targets on the box the user looked at (recordings replayed, arm not moved)', { x: rx, y: py0 + 1.4, w: rw - 1.15, h: 0.45, fontSize: 11.5, color: C.SLATE, italic: true });
    const scenes = [
      ['Three different boxes', [['Old pick (most confident SAM 3 mask)', 105 / 115, '105 of 115'], ['With the glasses crop', 1, '334 of 334']]],
      ['Two cardboard boxes, 0.4 to 1.6 m', [['Old pick (most confident SAM 3 mask)', 0, '0 of 114'], ['With the glasses crop', 266 / 268, '266 of 268']]],
    ];
    const sbx = rx + 2.55, sbw = 2.2;
    scenes.forEach((sc, i) => {
      const y = py0 + 1.9 + i * 1.05;
      H.text(s, sc[0], { x: rx, y, w: rw, h: 0.28, fontSize: 13, bold: true });
      sc[1].forEach((b, j) => {
        const yy = y + 0.3 + j * 0.32;
        H.text(s, b[0], { x: rx, y: yy, w: 2.45, h: 0.3, fontSize: 11, color: C.SLATE, align: 'right', valign: 'middle' });
        H.rect(s, sbx, yy + 0.04, sbw, 0.22, { fill: C.TINT, line: null });
        if (b[1] > 0) H.rect(s, sbx, yy + 0.04, sbw * b[1], 0.22, { fill: j ? C.NAVY : C.MUTED, line: null });
        const pct = Math.round(b[1] * 100) + ' %';
        H.text(s, [{ text: pct + '  ', options: { bold: true } }, { text: b[2], options: { color: C.SLATE } }], { x: sbx + sbw + 0.08, y: yy, w: 1.3, h: 0.3, fontSize: 11.5, valign: 'middle', color: (j === 0 && b[1] === 0) ? C.RED : C.INK });
      });
    });
    H.text(s, 'Replayed recordings, counted per published target. Not yet run on the real arm', { x: rx, y: py0 + 4.0, w: rw, h: 0.28, fontSize: 11.5, italic: true, color: C.SLATE });
    // callouts
    const cy = 6.38;
    H.rect(s, rx, cy, 2.9, 0.58, { fill: C.AMBER_T, line: ST.built.c });
    H.text(s, [{ text: 'The 2 misses: ', options: { bold: true } }, { text: 'wrong gaze pick at 1.5 m (the mat). Fix next: T2.24' }], { x: rx + 0.1, y: cy, w: 2.7, h: 0.58, fontSize: 11.5, valign: 'middle' });
    H.rect(s, rx + 3.05, cy, 2.93, 0.58, { fill: C.RED_T, line: C.RED });
    H.text(s, [{ text: 'Limit: ', options: { bold: true, color: C.RED } }, { text: 'same-colour boxes 6 of 12. Needs the gaze ray in the robot frame (T8.8)' }], { x: rx + 3.15, y: cy, w: 2.73, h: 0.58, fontSize: 11.5, valign: 'middle' });
    H.footer(s, 'Dion');
    s.addNotes(notes(12));
  }

  // ---------------- Slide 13: real arm grasp ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '7. Phases 4 and 5: cross-camera match and grasp' });
    H.phase(s, 5);
    H.title(s, 'The real arm grasps on a spoken command: 5 of 6 within reach');
    // state machine
    const sy = 2.35, sw = 0.98, sh = 0.62, gap = 0.72;
    const names = ['Idle', 'Approach', 'Grasp', 'Hold'];
    const xs = names.map((_, i) => 0.6 + i * (sw + gap));
    names.forEach((n, i) => {
      H.rect(s, xs[i], sy, sw, sh, { fill: i === 0 ? C.TINT : C.NAVY_T, line: C.NAVY, lw: 1.25 });
      H.text(s, n, { x: xs[i], y: sy, w: sw, h: sh, fontSize: 15, bold: true, align: 'center', valign: 'middle', color: C.NAVY });
    });
    const tl = ['grasp request + mask', 'wrist camera at 0.21 m', 'lift, return home'];
    for (let i = 0; i < 3; i++) {
      H.seg(s, xs[i] + sw, sy + sh / 2, xs[i + 1], sy + sh / 2, { color: C.INK, w: 1.5, arrow: true });
      H.text(s, tl[i], { x: xs[i] + sw + 0.02, y: sy + sh / 2 + 0.05, w: gap - 0.04, h: 0.62, fontSize: 10, color: C.SLATE, align: 'center' });
    }
    // Hold -> Idle via top lane
    const ly = sy - 0.42;
    H.path(s, [[xs[3] + sw / 2, sy], [xs[3] + sw / 2, ly], [xs[0] + sw / 2, ly], [xs[0] + sw / 2, sy]], { color: C.INK, w: 1.5, arrow: true });
    H.text(s, '"release"', { x: xs[1], y: ly - 0.3, w: 2.5, h: 0.28, fontSize: 12, color: C.SLATE, align: 'center' });
    // Stopped
    const stx = (xs[1] + xs[2] + sw) / 2 - 0.6, sty = sy + 1.35;
    H.rect(s, stx, sty, 1.2, 0.55, { fill: C.RED_T, line: C.RED, lw: 1.25 });
    H.text(s, 'Stopped', { x: stx, y: sty, w: 1.2, h: 0.55, fontSize: 14, bold: true, color: C.RED, align: 'center', valign: 'middle' });
    H.seg(s, xs[1] + sw / 2, sy + sh, stx + 0.25, sty, { color: C.RED, w: 1.25, arrow: true });
    H.seg(s, xs[2] + sw / 2, sy + sh, stx + 0.95, sty, { color: C.RED, w: 1.25, arrow: true });
    H.text(s, 'stop key', { x: stx + 1.25, y: sty - 0.32, w: 1.0, h: 0.26, fontSize: 11, color: C.RED });
    H.path(s, [[stx, sty + 0.28], [xs[0] + sw / 2, sty + 0.28], [xs[0] + sw / 2, sy + sh]], { color: C.RED, w: 1.25, arrow: true, dash: 'dash' });
    H.text(s, 'reset, no motion', { x: xs[0] + sw / 2 + 0.08, y: sty + 0.3, w: 1.6, h: 0.26, fontSize: 11, color: C.RED });
    H.text(s, [
      { text: 'Approach: ', options: { bold: true } }, { text: 'the wrist camera steps 2 cm towards the mask centre until 0.21 m', options: { breakLine: true } },
      { text: 'Hold: ', options: { bold: true } }, { text: 'until the user says "release"' },
    ], { x: 0.5, y: 4.3, w: 6.2, h: 0.55, fontSize: 12.5, color: C.INK });
    // video placeholder
    H.ph(s, 6.95, 1.6, 5.88, 3.3, 'VIDEO OF THE REAL GRASP',
      'grasp_real_arm_<date>.mp4 (Dion’s phone), trimmed to 15 s or less. Or three stills: approach, close, lift. Keep a still as backup if playback fails', 'Dion', { fs: 15, fs2: 11.5 });
    // distance chart (attempts by box distance)
    const gx = 0.75, gy = 5.3, gh = 1.08, unit = gh / 4, colw = 0.55;
    const dist = [['44.5 cm', 4, 0], ['49.5 cm', 1, 1], ['54.5 cm', 0, 2]];
    H.text(s, 'Grasps by box distance', { x: 0.5, y: 4.98, w: 3, h: 0.25, fontSize: 12, bold: true });
    dist.forEach((d, i) => {
      const x = gx + 0.2 + i * 1.05;
      let top = gy + 0.28 + gh;
      if (d[1]) { H.rect(s, x, top - d[1] * unit, colw, d[1] * unit, { fill: ST.tested.c, line: null }); top -= d[1] * unit; }
      if (d[2]) { H.rect(s, x, top - d[2] * unit, colw, d[2] * unit, { fill: 'D5D9E0', line: null }); top -= d[2] * unit; }
      H.text(s, d[1] + ' of ' + (d[1] + d[2]), { x: x - 0.2, y: top - 0.27, w: colw + 0.4, h: 0.25, fontSize: 11.5, bold: true, align: 'center' });
      H.text(s, d[0], { x: x - 0.2, y: gy + 0.3 + gh, w: colw + 0.4, h: 0.25, fontSize: 11, color: C.SLATE, align: 'center' });
    });
    H.seg(s, gx, gy + 0.28 + gh, gx + 3.3, gy + 0.28 + gh, { color: C.MUTED, w: 0.75 });
    const rl = gx + 0.2 + 1.05 + colw + 0.25;
    H.seg(s, rl, gy + 0.22, rl, gy + 0.28 + gh, { color: C.RED, w: 1.25, dash: 'dash' });
    H.text(s, 'reach limit', { x: rl - 0.5, y: gy - 0.02, w: 1.0, h: 0.22, fontSize: 10.5, color: C.RED, align: 'center' });
    H.text(s, [{ text: '■ ', options: { color: ST.tested.c } }, { text: 'grasped   ' }, { text: '■ ', options: { color: 'D5D9E0' } }, { text: 'failed' }], { x: 4.15, y: 5.4, w: 1.4, h: 0.5, fontSize: 11, color: C.SLATE });
    // results
    const rx = 5.75;
    H.text(s, 'Real RM65 arm, simple grasp path, command from a recorded voice file', { x: rx, y: 5.05, w: 7.08, h: 0.26, fontSize: 12, italic: true, color: C.SLATE });
    H.text(s, [
      { text: '5 of 6', options: { fontSize: 32, bold: true, color: C.NAVY, breakLine: true } },
      { text: 'within reach (5 of 8 grasps)', options: { fontSize: 13, bold: true } },
    ], { x: rx, y: 5.35, w: 2.25, h: 0.95 });
    H.text(s, [
      { text: 'First real grasp 13 Oct 2026', options: { bold: true, breakLine: true } },
      { text: 'Grasp, hold, refuse two requests while busy, release, grasp again, in one run' },
    ], { x: rx + 2.35, y: 5.38, w: 2.3, h: 1.0, fontSize: 12.5 });
    H.rect(s, rx + 4.8, 5.38, 2.28, 0.92, { fill: ST.tested.t, line: ST.tested.c });
    H.text(s, [{ text: 'Software stop: ', options: { bold: true } }, { text: 'arm stopped at two test points, motion cancelled within 1 ms' }], { x: rx + 4.9, y: 5.38, w: 2.1, h: 0.92, fontSize: 12, valign: 'middle', color: ST.tested.d });
    H.text(s, [{ text: 'Conditions and limits: ', options: { bold: true } }, { text: 'voice from a recorded file, not live glasses. Box in a narrow band of positions. Success judged by the people at the robot, no automatic check yet. Hardware e-stop is rejected by the arm controller, so every test has two people and a hand on the power button' }],
      { x: rx, y: 6.38, w: 7.08, h: 0.62, fontSize: 11, color: C.SLATE });
    H.footer(s, 'Dion');
    s.addNotes(notes(13));
  }

  // ---------------- Slide 14: AnyGrasp blocker ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '7. Phases 4 and 5: cross-camera match and grasp' });
    H.phase(s, 5);
    H.title(s, 'AnyGrasp works at one ideal spot because, up close, the camera sees only one face');
    H.text(s, [
      { text: 'AnyGrasp: ', options: { bold: true } }, { text: 'a learned model that proposes 6-DoF grasps on a point cloud.  ' },
      { text: 'Result: ', options: { bold: true } }, { text: '2 of 3 at the ideal spot', options: { bold: true, color: C.NAVY } }, { text: ' (44.5 cm, centred, square). Fails elsewhere: a recipe from OK-Robot gave more grasps offline (132 vs 97) but ' },
      { text: '0 of 4 live', options: { bold: true, color: C.RED } },
    ], { x: 0.5, y: 1.52, w: 12.33, h: 0.68, fontSize: 15 });
    // fit-check figure
    const iw = 4.35, ih = iw * 547 / 678, iy = 2.35;
    s.addImage({ path: IMG + 'fitcheck.png', x: 0.5, y: iy, w: iw, h: ih, altText: 'Fit check passes an edge grasp wrongly' });
    H.text(s, 'A 75 mm face measured as 56 mm: the check passes a grasp the gripper cannot make', { x: 0.5, y: iy + ih + 0.06, w: iw, h: 0.48, fontSize: 12, color: C.SLATE });
    // dimension sketch: gripper opening against each face
    const dx = 5.15, sc = 0.03;
    H.text(s, 'Gripper opening against each face', { x: dx, y: iy, w: 2.8, h: 0.28, fontSize: 13, bold: true });
    const faces = [['Side face', 75, false], ['Top', 60, true]];
    faces.forEach((f, i) => {
      const y = iy + 0.45 + i * 1.55;
      const fw = f[1] * sc;
      H.rect(s, dx, y + 0.42, fw, 0.5, { fill: 'C9A97A', line: '8C6D45' });
      H.text(s, f[0] + ' ' + f[1] + ' mm', { x: dx, y: y + 0.42, w: fw, h: 0.5, fontSize: 12, bold: true, align: 'center', valign: 'middle', color: C.INK });
      // 71 mm opening bracket
      const gw = 71 * sc;
      H.seg(s, dx, y + 0.22, dx + gw, y + 0.22, { color: C.INK, w: 1.5, both: true });
      H.text(s, 'gripper 71 mm', { x: dx, y: y - 0.05, w: gw, h: 0.25, fontSize: 11, align: 'center', color: C.SLATE });
      const mx = dx + Math.max(fw, gw) + 0.15;
      H.text(s, f[2] ? '✓' : '✗', { x: mx, y: y + 0.32, w: 0.45, h: 0.6, fontSize: 30, bold: true, color: f[2] ? ST.tested.c : C.RED, valign: 'middle' });
      H.text(s, f[2] ? 'fits' : 'too wide', { x: mx - 0.05, y: y + 0.88, w: 0.9, h: 0.25, fontSize: 11, color: f[2] ? ST.tested.d : C.RED });
    });
    H.text(s, 'Box 75 x 60 x 143 mm', { x: dx, y: iy + 3.3, w: 2.8, h: 0.26, fontSize: 11.5, color: C.SLATE });
    // cause
    const cx = 8.35, cw = 4.48;
    H.text(s, 'Cause, diagnosed', { x: cx, y: iy, w: cw, h: 0.3, fontSize: 15, bold: true, color: C.NAVY });
    const cause = [
      'At 0.21 m the wrist camera sees mostly one face of the 75 x 60 x 143 mm box',
      'The confident grasps go across the 75 mm face, wider than the 71 mm gripper',
      'Our fit check measures width from visible points, so edge and corner grasps pass it wrongly (369 of 369 passed on replay)',
      'The good top-down grasp is proposed in 49 of 75 frames but scores at most 0.25, under our 0.3 floor',
    ];
    H.text(s, cause.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < cause.length - 1 } })), { x: cx, y: iy + 0.36, w: cw, h: 3.3, fontSize: 13.5, paraSpaceAfter: 8 });
    // options
    const oy = 6.12;
    H.text(s, 'Next, cheapest first', { x: dx, y: oy - 0.02, w: 2.2, h: 0.3, fontSize: 13, bold: true, color: C.NAVY });
    const opts = [['A', 'Grasp once from 0.4 to 0.5 m with the whole box in view'], ['B', 'Grasp on several fused views (retest owed)'], ['C', 'New AnyGrasp SDK (waiting on a licence)']];
    const ow = 2.48, og = 0.08;
    opts.forEach((o, i) => {
      const x = dx + i * (ow + og);
      H.rect(s, x, oy + 0.3, ow, 0.6, { fill: i === 0 ? C.NAVY_T : C.TINT, line: null });
      H.text(s, [{ text: o[0] + '  ', options: { bold: true, color: C.NAVY, fontSize: 15 } }, { text: o[1] }], { x: x + 0.1, y: oy + 0.3, w: ow - 0.2, h: 0.6, fontSize: 11.5, valign: 'middle' });
    });
    H.footer(s, 'Dion');
    s.addNotes(notes(14));
  }

  // ---------------- Slide 15: full flow and links still to join ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '8. Full flow, links still to join, schedule' });
    H.title(s, 'Where each part sits in the full flow, and the links still to join');
    const X0 = [0.5, 3.02, 5.54, 8.06, 10.58], BW = 1.75, RH = 0.72;
    const R = [2.5, 3.56, 4.62, 5.68];
    const hdr = ['1 Intent capture', '2 Explore and find the user', '3 Search', '4 Approach and confirm', '5 Grasp'];
    hdr.forEach((h, i) => {
      H.rect(s, X0[i], 1.98, BW, 0.42, { fill: C.TINT, line: null });
      H.text(s, h, { x: X0[i] + 0.06, y: 1.98, w: BW - 0.12, h: 0.42, fontSize: 11, bold: true, color: C.SLATE, valign: 'middle' });
    });
    const parts = {
      A: [0, 1, 'Voice and gaze to a reference crop', 'Tested on replay', 'tested'],
      B: [1, 3, 'FAST-LIVO2 map and pose', 'Tested, pushed by hand', 'tested'],
      C: [1, 1, 'Nav2 drives the base', 'Built, never driven', 'built'],
      D: [1, 2, 'Memory graph', 'Works alone, offline', 'isolated'],
      E: [1, 0, 'Find the user', 'Planned', 'planned'],
      F: [2, 2, 'Gaze match against graph objects', 'Planned', 'planned'],
      G: [3, 2, 'Drive to the object, hand over to the arm', 'Planned', 'planned'],
      H: [3, 1, 'Wrist camera confirms the object', 'Tested on replay', 'tested'],
      I: [4, 1, 'Grasp on the real arm', 'Tested on the real arm', 'tested'],
    };
    const P = {};
    Object.entries(parts).forEach(([k, p]) => {
      const x = X0[p[0]], y = R[p[1]], st = ST[p[4]];
      P[k] = { x, y, r: x + BW, b: y + RH, cx: x + BW / 2, cy: y + RH / 2 };
      H.rect(s, x, y, BW, RH, { fill: st.t, line: st.c, lw: 1.5 });
      H.text(s, [{ text: p[2], options: { bold: true, fontSize: 11.5, color: C.INK, breakLine: true } }, { text: p[3], options: { fontSize: 10.5, color: st.d } }],
        { x: x + 0.07, y, w: BW - 0.14, h: RH, valign: 'middle' });
    });
    const ok = { color: C.INK, w: 1.75, arrow: true };
    const miss = { color: C.RED, w: 1.75, arrow: true, dash: 'dash' };
    const lab = (t, x, y, w, h, o = {}) => H.text(s, t, Object.assign({ x, y, w, h, fontSize: 10, color: C.INK }, o));
    const labR = (t, x, y, w, h, o = {}) => lab(t, x, y, w, h, Object.assign({ color: C.RED }, o));
    // 1 A -> I, recorded voice word, top lane
    H.path(s, [[P.A.r, P.A.y + 0.14], [2.45, P.A.y + 0.14], [2.45, 1.5], [12.6, 1.5], [12.6, P.I.y + 0.2], [P.I.r, P.I.y + 0.2]], ok);
    lab('1  recorded voice word (real arm)', 5.6, 1.26, 3.2, 0.24, { align: 'center' });
    // 2 A -> H, gaze reference crop, second lane
    H.path(s, [[P.A.r, P.A.y + 0.4], [2.65, P.A.y + 0.4], [2.65, 1.8], [10.2, 1.8], [10.2, P.H.y + 0.16], [P.H.r, P.H.y + 0.16]], ok);
    lab('2  gaze reference crop (replay)', 5.6, 1.56, 3.2, 0.24, { align: 'center' });
    // 3 H -> I
    H.seg(s, P.H.r, P.H.y + 0.55, P.I.x, P.H.y + 0.55, ok);
    lab('3  target mask, 600 of 602', P.H.r + 0.02, P.H.y + 0.6, 0.74, 0.5, { align: 'center' });
    // 4 B -> C via gap left of column 2
    H.path(s, [[P.B.x, P.B.cy], [2.85, P.B.cy], [2.85, P.C.y + 0.5], [P.C.x, P.C.y + 0.5]], ok);
    lab('4  pose and 2D map, checked live', 1.25, 5.05, 1.5, 0.36, { align: 'right' });
    // 5 B -> D
    H.seg(s, 4.5, P.B.y, 4.5, P.D.b, ok);
    lab('5  recorded drive, offline', 3.05, P.D.b + 0.02, 1.4, 0.32, { align: 'right' });
    // 6 C -> D (missing)
    H.seg(s, 4.5, P.C.b, 4.5, P.D.y, miss);
    labR('6  explore, graph grows live (T3.6, T7.5, T7.2)', 3.0, P.C.b + 0.0, 1.45, 0.34, { align: 'right', fontSize: 9.5 });
    // 7 C -> E
    H.seg(s, 4.5, P.C.y, 4.5, P.E.b, miss);
    labR('7  find the user (T7.6)', 3.05, P.E.b + 0.02, 1.4, 0.32, { align: 'right' });
    // 8 A -> F, bottom lane
    H.path(s, [[1.1, P.A.b], [1.1, 6.53], [6.4, 6.53], [6.4, P.F.b]], miss);
    labR('8  gaze target (T8.2)', 1.2, 6.25, 1.55, 0.26);
    // 9 D -> F
    H.seg(s, P.D.r, P.D.cy, P.F.x, P.D.cy, miss);
    labR('9  each new object (T8.2)', P.D.r + 0.02, P.D.cy + 0.06, 0.74, 0.5, { align: 'center' });
    // 10 F -> G
    H.seg(s, P.F.r, P.F.cy, P.G.x, P.F.cy, miss);
    labR('10  match becomes the goal (T7.1, T6.8)', P.F.r + 0.02, P.F.cy + 0.06, 0.74, 0.68, { align: 'center' });
    // 11 G -> H
    H.seg(s, 9.45, P.G.y, 9.45, P.H.b, miss);
    labR('11  arrive, hand over (T3.7)', 8.08, P.H.b + 0.0, 1.32, 0.34, { align: 'right' });
    // 12 H -> C, reject
    H.seg(s, P.H.x, P.H.cy + 0.06, P.C.r, P.H.cy + 0.06, miss);
    labR('12  reject: explore again (no task yet)', 5.3, P.H.cy - 0.22, 2.6, 0.24, { align: 'center' });
    // legend in the empty top-right area
    const lgx = 5.6, lgy = 2.55;
    H.text(s, 'Key', { x: lgx, y: lgy, w: 1, h: 0.24, fontSize: 11, bold: true, color: C.SLATE });
    H.legend(s, lgx, lgy + 0.27, ['tested', 'built', 'isolated', 'planned'], { fs: 10.5 });
    H.seg(s, lgx, lgy + 0.68, lgx + 0.45, lgy + 0.68, ok);
    H.text(s, 'works today', { x: lgx + 0.52, y: lgy + 0.56, w: 1.1, h: 0.24, fontSize: 10.5, color: C.SLATE });
    H.seg(s, lgx + 1.75, lgy + 0.68, lgx + 2.2, lgy + 0.68, miss);
    H.text(s, 'still to join, with task IDs', { x: lgx + 2.27, y: lgy + 0.56, w: 2.2, h: 0.24, fontSize: 10.5, color: C.SLATE });
    // footer message
    H.text(s, [
      { text: 'No end-to-end run yet, as planned. ', options: { bold: true } },
      { text: 'First full run (speak, look, drive, grasp) is M4, January 2027. The plan’s target for this interim was "M0 done, M1 and M3 under way"' },
    ], { x: 0.5, y: 6.68, w: 12.33, h: 0.36, fontSize: 13, valign: 'middle' });
    H.footer(s, 'Sherman');
    s.addNotes(notes(15));
  }

  // ---------------- Slide 16: schedule ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '8. Full flow, links still to join, schedule' });
    H.title(s, 'Ahead on memory and gaze, behind on calibration and driving, final dates unchanged');
    const gx = 3.0, gw = 9.83, nW = 31, ww = gw / nW;
    const wx = w => gx + (w - 1) * ww; // left edge of week w
    const top = 1.5, monY = top, wkY = top + 0.26, rowY = top + 0.56, rh = 0.265;
    const ms = [
      ['M0 Build and run', [1, 2], null, 'done 24 Sep'],
      ['M1 Arm picks something up', [2, 6], [7, 8], '8 Nov'],
      ['M2 Voice and gaze to arm', [4, 6], [7, 17], '10 Jan'],
      ['M3 Base navigates', [1, 6], [7, 17], '10 Jan'],
      ['M4 Closed loop', null, [18, 20], '31 Jan'],
      ['M5 Calibrated base camera', [1, 6], [7, 19], '24 Jan'],
      ['M6 Memory graph offline', [2, 6], [7, 20], '31 Jan'],
      ['M7 Graph drives the robot', null, [19, 24], '28 Feb'],
      ['M8 Gaze picks the instance', [6, 6], [7, 26], '14 Mar'],
      ['M9 Frontier scoring (optional)', null, [19, 23], '21 Feb, if kept'],
      ['M10 Demo and paper', null, [25, 27], '21 Mar'],
    ];
    const gh = ms.length * rh;
    // non-working bands
    const bands = [[3, 3, 'recess', 'DDE2EA'], [9, 12, 'exams, early Dec', 'DDE2EA'], [13, 14, 'break', 'DDE2EA'], [15, 16, 'buffer', 'EDF0F4']];
    bands.forEach(b => {
      H.rect(s, wx(b[0]), wkY, (b[1] - b[0] + 1) * ww, 0.3 + gh, { fill: b[3], line: null });
      H.text(s, b[2], { x: wx(b[0]) - 0.2, y: rowY + gh + 0.03, w: (b[1] - b[0] + 1) * ww + 0.4, h: 0.22, fontSize: 9, color: C.SLATE, align: 'center' });
    });
    // oral weeks
    H.rect(s, wx(30), wkY, 2 * ww, 0.3 + gh, { fill: 'E6ECF6', line: null });
    H.text(s, 'oral', { x: wx(30), y: rowY + gh + 0.03, w: 2 * ww, h: 0.22, fontSize: 9, color: C.NAVY, align: 'center' });
    // months: week 1 starts Mon 14 Sep 2026
    const d0 = Date.UTC(2026, 8, 14);
    const dayX = d => gx + ((d - d0) / 864e5) / 7 * ww;
    const months = [['Sep', 2026, 8], ['Oct', 2026, 9], ['Nov', 2026, 10], ['Dec', 2026, 11], ['Jan', 2027, 0], ['Feb', 2027, 1], ['Mar', 2027, 2], ['Apr', 2027, 3], ['May', 2027, 4]];
    for (let i = 0; i < months.length - 1; i++) {
      const a = Math.max(gx, dayX(Date.UTC(months[i][1], months[i][2], 1)));
      const b = Math.min(gx + gw, dayX(Date.UTC(months[i + 1][1], months[i + 1][2], 1)));
      if (b - a < 0.2) continue;
      H.text(s, months[i][0], { x: a, y: monY, w: b - a, h: 0.24, fontSize: 11, bold: true, color: C.SLATE, align: 'center' });
      if (i > 0) H.seg(s, a, monY, a, monY + 0.24, { color: C.LINE, w: 0.75 });
    }
    for (let w = 1; w <= nW; w++) H.text(s, String(w), { x: wx(w), y: wkY, w: ww, h: 0.26, fontSize: 8.5, color: C.SLATE, align: 'center', valign: 'middle' });
    H.text(s, 'Week (week 1 = 14 Sep 2026)', { x: 0.5, y: wkY, w: 2.45, h: 0.26, fontSize: 10, color: C.SLATE, valign: 'middle' });
    ms.forEach((m, i) => {
      const y = rowY + i * rh;
      H.text(s, m[0], { x: 0.5, y, w: 2.45, h: rh, fontSize: 11, color: C.INK, valign: 'middle', bold: i === 8 });
      H.seg(s, gx, y + rh, gx + gw, y + rh, { color: 'E8EBF0', w: 0.5 });
      const opt = i === 9;
      let end = 0;
      if (m[1]) { H.rect(s, wx(m[1][0]), y + 0.06, (m[1][1] - m[1][0] + 1) * ww, rh - 0.12, { fill: C.NAVY, line: null }); end = m[1][1]; }
      if (m[2]) {
        H.rect(s, wx(m[2][0]), y + 0.06, (m[2][1] - m[2][0] + 1) * ww, rh - 0.12, opt ? { fill: C.WHITE, line: C.MUTED, dash: 'dash', lw: 1 } : { fill: 'AFC0DD', line: null });
        end = m[2][1];
      }
      H.text(s, m[3], { x: wx(end + 1) + 0.05, y, w: 1.6, h: rh, fontSize: 10, color: opt ? C.MUTED : C.SLATE, valign: 'middle', italic: opt });
    });
    // today line: interim, Wed 28 Oct, week 7
    const tx = dayX(Date.UTC(2026, 9, 28));
    H.seg(s, tx, wkY - 0.02, tx, rowY + gh, { color: C.RED, w: 1.5 });
    H.text(s, 'today: interim 28 Oct', { x: tx + 0.06, y: rowY, w: 1.6, h: rh, fontSize: 10, bold: true, color: C.RED, valign: 'middle' });
    const fr = wx(29);
    H.seg(s, fr, wkY - 0.02, fr, rowY + gh, { color: C.INK, w: 1.25, dash: 'dash' });
    H.text(s, 'final report 28 Mar', { x: fr - 1.5, y: rowY, w: 1.44, h: rh, fontSize: 10, bold: true, color: C.INK, align: 'right', valign: 'middle' });
    // bar key
    const ky = rowY + gh + 0.3;
    H.rect(s, 0.5, ky + 0.05, 0.3, 0.14, { fill: C.NAVY, line: null });
    H.text(s, 'actual to 24 Oct', { x: 0.86, y: ky, w: 1.3, h: 0.24, fontSize: 10, color: C.SLATE });
    H.rect(s, 2.15, ky + 0.05, 0.3, 0.14, { fill: 'AFC0DD', line: null });
    H.text(s, 'forecast', { x: 2.51, y: ky, w: 0.8, h: 0.24, fontSize: 10, color: C.SLATE });
    H.rect(s, 3.3, ky + 0.05, 0.3, 0.14, { fill: C.WHITE, line: C.MUTED, dash: 'dash' });
    H.text(s, 'optional, likely cut', { x: 3.66, y: ky, w: 1.5, h: 0.24, fontSize: 10, color: C.SLATE });
    H.text(s, 'Grey bands: no work or half speed. Bars that cross them are calendar time, not working time. Forecasts re-estimated on 24 Oct: estimates, not commitments', { x: 5.25, y: ky, w: 7.58, h: 0.24, fontSize: 10, color: C.SLATE, italic: true });
    // text columns
    const ty = ky + 0.36, tcw = 3.98;
    H.text(s, [
      { text: 'Against the September plan at week 7', options: { bold: true, color: C.NAVY, breakLine: true } },
      { text: 'Planned: M0 done, M1 and M3 under way', options: { breakLine: true } },
      { text: 'Actual: M0 done. M1 met on the simple path. M3 map and localisation done', options: { bold: true } },
    ], { x: 0.5, y: ty, w: tcw, h: 1.3, fontSize: 13, paraSpaceAfter: 3 });
    H.text(s, [
      { text: 'Started early: ', options: { bold: true, color: ST.tested.d } }, { text: 'M2 (voice and gaze to arm), M6 (memory graph), M8 (gaze picks the instance)', options: { breakLine: true } },
      { text: 'Behind: ', options: { bold: true, color: ST.built.d } }, { text: 'base camera calibration (M5) and drive-to-point (M3), one to two weeks' },
    ], { x: 0.5 + tcw + 0.2, y: ty, w: tcw, h: 1.3, fontSize: 13, paraSpaceAfter: 3 });
    H.text(s, [
      { text: 'Each milestone has a written test, ', options: {} }, { text: 'for example M2: two boxes, the arm picks the one you looked at, 3 times in 4', options: { bold: true } }, { text: '. Full list in A10', options: { breakLine: true } },
      { text: 'Progress: 97 of 171 task rows done', options: { breakLine: true } },
      { text: 'Final report 28 Mar 2027 (week 28), oral weeks 30 and 31' },
    ], { x: 0.5 + 2 * (tcw + 0.2), y: ty, w: tcw - 0.03, h: 1.3, fontSize: 12.5, paraSpaceAfter: 2 });
    H.footer(s, 'Sherman');
    s.addNotes(notes(16));
  }

  // ---------------- Slide 17: budget and risks ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '9. Budget, risks, next steps' });
    H.title(s, 'Budget: SGD 1,500 for compute, approved. Risks are mostly schedule and shared hardware');
    const lx = 0.5, lw = 5.95;
    H.text(s, 'Budget in SGD, approved, dated 5 Oct 2026', { x: lx, y: 1.6, w: 4.4, h: 0.34, fontSize: 16, bold: true, color: C.NAVY, valign: 'middle' });
    H.rect(s, lx + 4.65, 1.62, 1.3, 0.3, { fill: ST.tested.t, line: ST.tested.c });
    H.text(s, 'Approved', { x: lx + 4.65, y: 1.62, w: 1.3, h: 0.3, fontSize: 12, bold: true, color: ST.tested.d, align: 'center', valign: 'middle' });
    const hd = o => Object.assign({ bold: true, color: C.SLATE, fill: { color: C.TINT }, fontSize: 12 }, o || {});
    const rows = [
      [{ text: 'No.', options: hd() }, { text: 'Item', options: hd() }, { text: 'Cost per unit', options: hd({ align: 'right' }) }, { text: 'Units', options: hd({ align: 'right' }) }, { text: 'Total', options: hd({ align: 'right' }) }, { text: 'Purpose', options: hd() }],
      ['1', 'Hardware GPU', { text: '1,000.00', options: { align: 'right' } }, { text: '1', options: { align: 'right' } }, { text: '1,000.00', options: { align: 'right' } }, 'Compute requirement'],
      ['2', 'API credits', { text: '500.00', options: { align: 'right' } }, { text: '1', options: { align: 'right' } }, { text: '500.00', options: { align: 'right' } }, 'Compute requirement (AI services)'],
      ['', { text: 'Total', options: { bold: true } }, '', '', { text: '1,500.00', options: { bold: true, align: 'right' } }, ''],
    ];
    s.addTable(rows, { x: lx, y: 2.1, w: lw, colW: [0.45, 1.3, 1.05, 0.55, 0.9, 1.7], fontFace: 'Calibri', fontSize: 13, color: C.INK, border: { type: 'solid', color: C.LINE, pt: 0.75 }, rowH: 0.42, valign: 'middle', margin: [0.04, 0.08, 0.04, 0.08] });
    H.text(s, [
      { text: 'Why compute: ', options: { bold: true } },
      { text: 'one shared 16 GB GPU runs SAM 3, AnyGrasp, CLIP, Whisper and two language models for three people and CI. Batched SAM 3 alone peaks at 10.3 GiB. The full set has never run together' },
    ], { x: lx, y: 4.6, w: lw, h: 1.3, fontSize: 15 });
    // risks
    const rx = 6.85, rw = 5.98;
    H.text(s, 'Risks and status', { x: rx, y: 1.6, w: rw, h: 0.34, fontSize: 16, bold: true, color: C.NAVY, valign: 'middle' });
    const dot = c => ({ text: '●', options: { color: c, fontSize: 16, align: 'center' } });
    const A = ST.built.c, G = ST.tested.c;
    const rr = [
      [{ text: '', options: hd() }, { text: 'Risk', options: hd() }, { text: 'Status', options: hd() }],
      [dot(A), 'AnyGrasp licence bound to a hardware ID', 'New licence requested, network ID pinned'],
      [dot(A), 'Shared, throttled lab machine', 'Ongoing: CPU throttling, two silent hangs, disk 89 % full'],
      [dot(A), 'No hardware stop on arm or base', 'Software stop tested, two people and the power button at every test'],
      [dot(G), 'Graph duplicates from poor camera poses', 'Controlled: 8 to 3 duplicates, 0 false merges'],
    ];
    s.addTable(rr, { x: rx, y: 2.1, w: rw, colW: [0.4, 2.45, 3.13], fontFace: 'Calibri', fontSize: 13, color: C.INK, border: { type: 'solid', color: C.LINE, pt: 0.75 }, rowH: [0.4, 0.72, 0.72, 0.72, 0.72], valign: 'middle', margin: [0.04, 0.08, 0.04, 0.08] });
    H.text(s, [{ text: '● ', options: { color: A } }, { text: 'ongoing   ' }, { text: '● ', options: { color: G } }, { text: 'controlled' }], { x: rx, y: 5.55, w: 3, h: 0.26, fontSize: 11.5, color: C.SLATE });
    H.rect(s, 0.5, 6.1, 12.33, 0.75, { fill: C.TINT, line: null });
    H.text(s, [{ text: 'Cut order if late: ', options: { bold: true } }, { text: 'M9 (smarter exploration order), without-gaze comparison, reasoning layer, graph pruning, two-stage trigger, fewer end-to-end trials' }],
      { x: 0.7, y: 6.1, w: 11.93, h: 0.75, fontSize: 14.5, valign: 'middle' });
    H.footer(s, 'Zongzhe');
    s.addNotes(notes(17));
  }

  // ---------------- Slide 18: next steps and takeaways ----------------
  {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: '9. Budget, risks, next steps' });
    H.title(s, 'Next: close the grasp, drive the base, query the graph. Then explore with gaze');
    const lx = 0.5, lw = 7.85;
    const blocks = [
      ['Weeks 7 to 8, before exams', [
        ['Refuse weak gaze picks at the glasses, then the gaze-matched grasp on the real arm', 'T2.24, T8.9a'],
        ['New AnyGrasp SDK, fused-view retest, then a 12-trial grasp validation. M1 closes (target 8 Nov)', 'T1.45, T1.47, T1.35'],
        ['Nav2 prerequisites and the first drives to a point', 'T3.6'],
        ['Memory graph query acceptance run on the recorded drive', 'T6.8'],
      ]],
      ['After the break, January to March 2027', [
        ['Two-box gaze grasp on hardware (M2), camera calibration (M5)', 'T2.5, T5.5, T5.6'],
        ['Closed loop (M4, January)', 'M4'],
        ['The robot explores and finds the user (M7, February)', 'T7.2, T7.5, T7.6, T7.1'],
        ['A gaze match ends exploration, end-to-end trials (M8, March)', 'T8.2, T8.3', true],
      ]],
    ];
    let y = 1.6;
    blocks.forEach((b, bi) => {
      H.oval(s, lx, y + 0.06, 0.22, 0.22, { fill: C.NAVY, line: C.NAVY });
      H.text(s, b[0], { x: lx + 0.35, y, w: lw - 0.35, h: 0.34, fontSize: 16, bold: true, color: C.NAVY });
      y += 0.4;
      b[1].forEach(it => {
        H.text(s, [{ text: it[0], options: { bold: !!it[2] } }, { text: '   ' + it[1], options: { color: C.MUTED, fontSize: 11 } }], { x: lx + 0.35, y, w: lw - 0.35, h: 0.5, fontSize: 13.5 });
        y += 0.46;
      });
      if (bi === 0) { H.seg(s, lx + 0.11, 1.95, lx + 0.11, y + 0.1, { color: C.NAVY, w: 1.5 }); y += 0.15; }
    });
    // takeaways
    const tx = 8.75, tw = 4.08;
    H.text(s, 'Three takeaways', { x: tx, y: 1.6, w: tw, h: 0.34, fontSize: 16, bold: true, color: C.NAVY });
    const tk = [
      'The hard part is identity across viewpoints. CLIP does it for different objects and now steers the grasp. Gaze geometry is needed for look-alikes',
      'Every subsystem has measured results on real hardware or real recordings',
      'The links are scheduled, with a cut list fixed in advance',
    ];
    let ty = 2.02;
    const th = [1.55, 1.0, 1.0];
    tk.forEach((t, i) => {
      H.rect(s, tx, ty, tw, th[i], { fill: C.NAVY_T, line: null });
      H.text(s, String(i + 1), { x: tx + 0.12, y: ty + 0.08, w: 0.4, h: 0.5, fontSize: 26, bold: true, color: C.NAVY });
      H.text(s, t, { x: tx + 0.6, y: ty + 0.1, w: tw - 0.75, h: th[i] - 0.2, fontSize: 14, valign: 'middle' });
      ty += th[i] + 0.12;
    });
    // closing strip
    const sy = 6.35, names = ['1 Intent', '2 Explore and map', '3 Search', '4 Approach and confirm', '5 Grasp'];
    const w = 1.6, g = 0.18;
    names.forEach((n, i) => {
      const x = 0.5 + i * (w + g);
      H.rect(s, x, sy, w, 0.4, { fill: C.WHITE, line: C.NAVY, lw: 1.25 });
      H.text(s, n, { x, y: sy, w, h: 0.4, fontSize: 11, bold: true, color: C.NAVY, align: 'center', valign: 'middle' });
      if (i < 4) H.seg(s, x + w + 0.02, sy + 0.2, x + w + g - 0.02, sy + 0.2, { color: C.NAVY, w: 1.25, arrow: true });
    });
    H.text(s, 'March 2027: end-to-end demonstration', { x: 9.4, y: sy, w: 3.43, h: 0.4, fontSize: 15, bold: true, color: C.NAVY, valign: 'middle' });
    H.footer(s, 'Zongzhe');
    s.addNotes(notes(18));
  }
};

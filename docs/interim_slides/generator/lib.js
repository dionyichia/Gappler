// Shared helpers and design tokens for the interim deck
const C = {
  INK: '1B2333', SLATE: '5B6577', MUTED: '8A93A3', LINE: 'CDD3DD', TINT: 'F2F4F8',
  NAVY: '1F3B73', NAVY_T: 'E6ECF6', RED: 'B3392F', RED_T: 'FBEAE8', WHITE: 'FFFFFF',
  AMBER_T: 'FDF4E3',
};
// One status colour scale everywhere (spec rule 3)
const ST = {
  tested:   { c: '2E7D4F', t: 'E3F1E8', d: '1F5C39', label: 'Tested' },
  built:    { c: 'B7791F', t: 'FBF1DC', d: '7A4E0B', label: 'Built, not validated' },
  isolated: { c: '2B6CB0', t: 'E2ECF7', d: '1D4E85', label: 'Isolated (works alone)' },
  inprog:   { c: 'D9622B', t: 'FCEADF', d: '8F3A12', label: 'In progress' },
  planned:  { c: '8A93A3', t: 'FFFFFF', d: '4B5363', label: 'Planned' },
};
const FONT = 'Calibri';

function mk(pres) {
  const S = pres.shapes;
  const H = {};
  H.text = (s, text, o = {}) => s.addText(text, Object.assign({ isTextBox: true, fontFace: FONT, fontSize: 18, color: C.INK, margin: 0, valign: 'top' }, o));
  H.rect = (s, x, y, w, h, o = {}) => s.addShape(S.RECTANGLE, {
    x, y, w, h, fill: o.fill ? { color: o.fill } : { type: 'none' },
    line: o.line === null ? { type: 'none' } : { color: o.line || C.LINE, width: o.lw || 1, dashType: o.dash || 'solid' },
    objectName: o.name,
  });
  H.round = (s, x, y, w, h, o = {}) => s.addShape(S.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: o.r || 0.06, fill: o.fill ? { color: o.fill } : { type: 'none' },
    line: o.line === null ? { type: 'none' } : { color: o.line || C.LINE, width: o.lw || 1, dashType: o.dash || 'solid' },
  });
  H.oval = (s, x, y, w, h, o = {}) => s.addShape(S.OVAL, {
    x, y, w, h, fill: o.fill ? { color: o.fill } : { type: 'none' },
    line: o.line === null ? { type: 'none' } : { color: o.line || C.LINE, width: o.lw || 1, dashType: o.dash || 'solid' },
  });
  // straight segment, optional arrowheads
  H.seg = (s, x1, y1, x2, y2, o = {}) => {
    const line = { color: o.color || C.INK, width: o.w || 1.5, dashType: o.dash || 'solid' };
    if (o.end !== false && o.arrow) line.endArrowType = 'triangle';
    if (o.both) { line.endArrowType = 'triangle'; line.beginArrowType = 'triangle'; }
    s.addShape(S.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipH: x2 < x1, flipV: y2 < y1, line });
  };
  // polyline through points, arrowhead on the last segment only
  H.path = (s, pts, o = {}) => {
    for (let i = 0; i < pts.length - 1; i++) {
      H.seg(s, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], Object.assign({}, o, { arrow: o.arrow && i === pts.length - 2 }));
    }
  };
  H.title = (s, t) => s.addText(t, { placeholder: 'title' });
  H.footer = (s, presenter) => {
    if (presenter) H.text(s, presenter, { x: 0.5, y: 7.08, w: 4, h: 0.25, fontSize: 11, color: C.MUTED });
  };
  // "you are here" phase strip, spec rule 2
  H.phase = (s, active, extra) => {
    const names = ['1 Intent', '2 Explore and map', '3 Search', '4 Approach and confirm', '5 Grasp'];
    const w = 1.92, g = 0.06, y = 0.2, h = 0.3;
    names.forEach((n, i) => {
      const x = 0.5 + i * (w + g), on = i + 1 === active;
      H.rect(s, x, y, w, h, { fill: on ? C.NAVY : C.TINT, line: on ? C.NAVY : C.LINE, lw: 0.75 });
      H.text(s, n, { x, y, w, h, fontSize: 11, bold: on, color: on ? C.WHITE : C.SLATE, align: 'center', valign: 'middle' });
    });
    if (extra) H.text(s, extra, { x: 0.5 + 5 * (w + g) + 0.1, y, w: 2.6, h, fontSize: 11, italic: true, color: C.SLATE, valign: 'middle' });
  };
  H.badge = (s, x, y, w, h, st, text, o = {}) => {
    const k = ST[st];
    H.rect(s, x, y, w, h, { fill: k.t, line: k.c, lw: 1 });
    H.text(s, text, { x: x + 0.08, y, w: w - 0.16, h, fontSize: o.fs || 12, color: k.d, valign: 'middle', bold: o.bold });
  };
  H.legend = (s, x, y, keys, o = {}) => {
    let cx = x;
    const fs = o.fs || 11;
    keys.forEach(k => {
      const st = ST[k];
      H.rect(s, cx, y + 0.04, 0.2, 0.17, { fill: st.t, line: st.c, lw: 1 });
      const lw = fs * 0.0078 * st.label.length + 0.12;
      H.text(s, st.label, { x: cx + 0.26, y, w: lw, h: 0.25, fontSize: fs, color: C.SLATE, valign: 'middle' });
      cx += 0.26 + lw + 0.15;
    });
    return cx;
  };
  // clearly labelled placeholder for an artefact a teammate supplies
  H.ph = (s, x, y, w, h, what, file, owner, o = {}) => {
    H.rect(s, x, y, w, h, { fill: 'F7F8FA', line: '9AA3B2', lw: 1.25, dash: 'dash' });
    const parts = [{ text: '[INSERT ' + what + ']', options: { bold: true, color: C.SLATE, fontSize: o.fs || 14, breakLine: true } }];
    if (file) parts.push({ text: file, options: { color: C.MUTED, fontSize: o.fs2 || 11, breakLine: true } });
    if (owner) parts.push({ text: 'Owner: ' + owner, options: { color: C.MUTED, fontSize: o.fs2 || 11 } });
    H.text(s, parts, { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2, align: 'center', valign: 'middle' });
  };
  H.num = (s, x, y, n, color, d = 0.32) => {
    H.oval(s, x, y, d, d, { fill: color, line: color });
    H.text(s, String(n), { x, y, w: d, h: d, fontSize: 13, bold: true, color: C.WHITE, align: 'center', valign: 'middle' });
  };
  return H;
}
module.exports = { C, ST, FONT, mk };

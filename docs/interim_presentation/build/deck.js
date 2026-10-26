// Gappler interim deck, 28 Oct 2026. Style: 2WO boxes and colour + full-width underline tracker.
// Content from Gappler/docs/INTERIM_PRESENTATION_SLIDE_CONTENT_2026-10.md and the appendix of the 24 Oct deck.
const pptxgen = require("pptxgenjs");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const MD = require("react-icons/md");

const LOCAL_MEDIA = __dirname + "/media/";
const SHERMAN = __dirname + "/../../sherman_docs/local/report_media/";
const MAP_ISO = SHERMAN + "nav_fastlivo_map_iso_clean_handdriven1_2026-10-24.png";
const OUT = process.argv[2];

const FONT = "Calibri";
const NAVY = "16213A", BLUE = "0068B5", TINT = "EEF2F7", SLATE = "4B5563", MUTED = "6B7280", RULE = "D7DEE8",
  GREY = "C5CDD8", SKY = "7DD3FC", PALE = "CBD5E1", SIGNAL = "FF7A3A", EMBER = "C2410C", WHITE = "FFFFFF", HILITE = "DBEAFE";
// one status scale, used on slides 4, 8 and 15
const ST = {
  tested: { fill: "DCFCE7", text: "15803D", dot: "16A34A", name: "tested" },
  built: { fill: "FEF3C7", text: "B45309", dot: "D97706", name: "built, not validated" },
  alone: { fill: "CFFAFE", text: "0E7490", dot: "0891B2", name: "works alone" },
  planned: { fill: WHITE, text: MUTED, dot: "9CA3AF", name: "planned", dash: true },
};
const SECTIONS = ["Problem", "System", "Intent", "Explore", "Search", "Confirm", "Grasp", "Plan"];
const L = 0.6, W = 12.13, R = { x: 9.2, w: 3.53 }, C = { x: 2.95, w: 6.0 };

const iconCache = {};
async function icon(name, color = WHITE) {
  const key = name + color;
  if (!iconCache[key]) {
    const svg = renderToStaticMarkup(React.createElement(MD[name], { color: "#" + color, size: 256 }));
    iconCache[key] = "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
  }
  return iconCache[key];
}

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.title = "Gappler interim presentation";
let page = 0;

function kit(s) {
  const T = (t, o) => s.addText(t, { fontFace: FONT, margin: 0, isTextBox: true, ...o });
  const RR = (o) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.1, line: { type: "none" }, ...o });
  const line = (x1, y1, x2, y2, o = {}) => s.addShape(pres.shapes.LINE, {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipH: x2 < x1, flipV: y2 < y1,
    line: { color: NAVY, width: 1.5, ...o } });
  const k = {
    T, RR, line,
    async circleIcon(x, y, d, name, fill = BLUE, color = WHITE) {
      s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" } });
      const p = d * 0.22;
      s.addImage({ data: await icon(name, color), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p });
    },
    num(x, y, d, n, fill = BLUE, color = WHITE, size = 12) {
      s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" } });
      T(String(n), { x, y, w: d, h: d, fontSize: size, bold: true, color, align: "center", valign: "middle" });
    },
    header(presenter, pill, title, sub) {
      T(`GAPPLER  ·  ${presenter}`, { x: L, y: 0.45, w: 6, h: 0.25, fontSize: 11, bold: true, color: BLUE, charSpacing: 1.5 });
      const pw = Math.max(2.4, pill.length * 0.105 + 0.6);
      RR({ x: L + W - pw, y: 0.38, w: pw, h: 0.38, rectRadius: 0.19, fill: { color: NAVY } });
      T(pill, { x: L + W - pw, y: 0.38, w: pw, h: 0.38, fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", charSpacing: 1 });
      T(title, { x: L, y: 0.85, w: W, h: 0.6, fontSize: 30, bold: true, color: NAVY });
      if (sub) T(sub, { x: L, y: 1.45, w: W, h: 0.35, fontSize: 17, color: SLATE });
    },
    // left rail: the presenter's topics in this part, current one filled; LIMIT card at the bottom
    rail(items, active, limit) {
      T("THIS PART", { x: L, y: 2.05, w: 2, h: 0.25, fontSize: 11, bold: true, color: MUTED, charSpacing: 1.5 });
      items.forEach((label, i) => {
        const y = 2.4 + i * 0.7, on = i === active;
        RR({ x: L, y, w: 2.1, h: 0.58, fill: { color: on ? NAVY : TINT } });
        s.addShape(pres.shapes.OVAL, { x: L + 0.15, y: y + 0.12, w: 0.34, h: 0.34, fill: { color: on ? WHITE : TINT }, line: { color: on ? WHITE : MUTED, width: 1 } });
        T(String(i + 1), { x: L + 0.15, y: y + 0.12, w: 0.34, h: 0.34, fontSize: 13, bold: true, color: on ? NAVY : MUTED, align: "center", valign: "middle" });
        T(label, { x: L + 0.62, y, w: 1.45, h: 0.58, fontSize: 14, bold: on, color: on ? WHITE : SLATE, valign: "middle" });
      });
      if (limit) k.limitCard(L, 4.85, 2.1, 1.6, limit);
    },
    limitCard(x, y, w, h, text, label = "LIMIT") {
      RR({ x, y, w, h, fill: { color: TINT } });
      T(label, { x: x + 0.18, y: y + 0.15, w: w - 0.3, h: 0.22, fontSize: 11, bold: true, color: EMBER, charSpacing: 1.5 });
      T(text, { x: x + 0.18, y: y + 0.42, w: w - 0.3, h: h - 0.5, fontSize: 13, color: NAVY, valign: "top" });
    },
    // navy card: the one number to remember
    hero({ x = R.x, y = 2.05, w = R.w, h = 1.9, label, big, unit = "", sub }) {
      RR({ x, y, w, h, fill: { color: NAVY } });
      T(label, { x: x + 0.25, y: y + 0.2, w: w - 0.4, h: 0.25, fontSize: 11, bold: true, color: SKY, charSpacing: 1.5 });
      T([{ text: big, options: { fontSize: 50, bold: true, color: WHITE } }, { text: unit, options: { fontSize: 22, bold: true, color: SIGNAL } }],
        { x: x + 0.25, y: y + 0.45, w: w - 0.4, h: 0.85, valign: "bottom" });
      T(sub, { x: x + 0.25, y: y + 1.35, w: w - 0.4, h: h - 1.45, fontSize: 13, color: PALE, valign: "top" });
    },
    async stat({ x = R.x, y, w = R.w, h = 0.95, ic, num, label }) {
      RR({ x, y, w, h, fill: { color: TINT } });
      const d = Math.min(0.5, h - 0.25);
      await k.circleIcon(x + 0.18, y + (h - d) / 2, d, ic);
      T(num, { x: x + 0.85, y: y + h / 2 - 0.36, w: w - 1, h: 0.36, fontSize: 20, bold: true, color: NAVY, valign: "bottom" });
      T(label, { x: x + 0.85, y: y + h / 2 + 0.02, w: w - 1, h: 0.3, fontSize: 12, color: SLATE, valign: "top" });
    },
    label(text, x, y, w, color = MUTED) {
      T(text, { x, y, w, h: 0.25, fontSize: 11, bold: true, color, charSpacing: 1.5 });
    },
    caption(text, x, y, w) { T(text, { x, y, w, h: 0.25, fontSize: 11, color: MUTED }); },
    photo(path, box, cap, alt) {
      s.addImage({ path, ...box, sizing: { type: "cover", w: box.w, h: box.h }, altText: alt || cap || "photo" });
      if (cap) {
        s.addShape(pres.shapes.RECTANGLE, { x: box.x, y: box.y + box.h - 0.36, w: box.w, h: 0.36, fill: { color: NAVY, transparency: 20 }, line: { type: "none" } });
        T(cap, { x: box.x + 0.15, y: box.y + box.h - 0.36, w: box.w - 0.3, h: 0.36, fontSize: 11, bold: true, color: WHITE, charSpacing: 1, valign: "middle" });
      }
    },
    chip(x, y, w, text, st) {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.26, rectRadius: 0.13, fill: { color: st.fill },
        line: st.dash ? { color: "9CA3AF", width: 0.75, dashType: "dash" } : { type: "none" } });
      T(text, { x, y, w, h: 0.26, fontSize: 11, bold: true, color: st.text, align: "center", valign: "middle" });
    },
    // full-width underline tracker over the eight sections of the talk
    tracker(active) {
      const tw = W / SECTIONS.length;
      SECTIONS.forEach((p, i) => {
        const on = i === active;
        s.addShape(pres.shapes.RECTANGLE, { x: L + i * tw + 0.05, y: 7.0, w: tw - 0.1, h: on ? 0.04 : 0.015, fill: { color: on ? BLUE : RULE }, line: { type: "none" } });
        T(p, { x: L + i * tw, y: 7.08, w: tw, h: 0.22, fontSize: 11, bold: on, color: on ? NAVY : MUTED, align: "center" });
      });
      T(String(page), { x: L + W - 0.6, y: 6.6, w: 0.6, h: 0.25, fontSize: 11, color: MUTED, align: "right" });
    },
  };
  return k;
}

function slide(section) {
  page += 1;
  const s = pres.addSlide({ sectionTitle: section });
  s.background = { color: WHITE };
  return s;
}

// ---------- dark slides: cover, part dividers, Q&A ----------
// Robot's-eye viewfinder: a real sensor frame with corner brackets, a detection-style label chip
// and the orange gaze reticle on the target (target given in source-image pixels).
function viewfinder(s, k, { path, iw, ih, tx, ty, chip, caption }) {
  const v = { x: 6.95, y: 0.95, w: 5.78, h: 4.95 };
  s.addImage({ path, ...v, sizing: { type: "cover", w: v.w, h: v.h }, altText: caption });
  const sc = Math.max(v.w / iw, v.h / ih);
  const mx = v.x + tx * sc - (iw * sc - v.w) / 2, my = v.y + ty * sc - (ih * sc - v.h) / 2;
  // corner brackets, just outside the frame
  const o = 0.14, len = 0.5, br = { color: SKY, width: 2.5 };
  [[v.x - o, v.y - o, 1, 1], [v.x + v.w + o, v.y - o, -1, 1], [v.x - o, v.y + v.h + o, 1, -1], [v.x + v.w + o, v.y + v.h + o, -1, -1]].forEach(([x, y, dx, dy]) => {
    k.line(x, y, x + dx * len, y, br); k.line(x, y, x, y + dy * len, br);
  });
  // reticle: ring, centre dot and four ticks
  const r = 0.34;
  s.addShape(pres.shapes.OVAL, { x: mx - r, y: my - r, w: 2 * r, h: 2 * r, fill: { type: "none" }, line: { color: SIGNAL, width: 2.5 } });
  s.addShape(pres.shapes.OVAL, { x: mx - 0.05, y: my - 0.05, w: 0.1, h: 0.1, fill: { color: SIGNAL }, line: { type: "none" } });
  const tick = { color: SIGNAL, width: 2.5 };
  k.line(mx - r - 0.18, my, mx - r + 0.06, my, tick); k.line(mx + r - 0.06, my, mx + r + 0.18, my, tick);
  k.line(mx, my - r - 0.18, mx, my - r + 0.06, tick); k.line(mx, my + r - 0.06, mx, my + r + 0.18, tick);
  // detection label chip on the frame's top edge
  const cw = chip.length * 0.088 + 0.4;
  k.RR({ x: v.x, y: v.y - 0.5, w: cw, h: 0.32, rectRadius: 0.05, fill: { color: SIGNAL } });
  k.T(chip, { x: v.x, y: v.y - 0.5, w: cw, h: 0.32, fontSize: 11, bold: true, color: NAVY, align: "center", valign: "middle", charSpacing: 1 });
  k.T(caption, { x: v.x, y: v.y + v.h + 0.28, w: v.w, h: 0.3, fontSize: 12, color: PALE });
}

const PARTS = ["Problem and plan", "Results", "Where we stand"];
function partBar(k, current) {
  const w = 1.75;
  PARTS.forEach((t, i) => {
    const x = L + i * (w + 0.12), col = i === current ? SIGNAL : i < current ? "64748B" : "334155";
    k.RR({ x, y: 6.55, w, h: 0.07, rectRadius: 0.03, fill: { color: col } });
    k.T(t, { x, y: 6.68, w, h: 0.25, fontSize: 11, bold: i === current, color: i === current ? WHITE : "94A3B8" });
  });
}

function divider(section, part, title, sub, who, view) {
  page += 1;
  const s = pres.addSlide({ sectionTitle: section });
  s.background = { color: NAVY };
  const k = kit(s);
  viewfinder(s, k, view);
  k.T(`PART ${part} / 3`, { x: L, y: 1.15, w: 5, h: 0.3, fontSize: 12, bold: true, color: SIGNAL, charSpacing: 2 });
  const lines = title.length > 23 ? 2 : 1, subY = 1.55 + lines * 0.68;
  k.T(title, { x: L, y: 1.5, w: 5.9, h: lines * 0.7, fontSize: 40, bold: true, color: WHITE, valign: "top" });
  k.T(sub, { x: L, y: subY, w: 5.9, h: 0.4, fontSize: 17, color: PALE, valign: "top" });
  // presenters as tracked objects, like the #ids on SAM 3 masks
  who.forEach(([name, topic], i) => {
    const y = subY + 0.85 + i * 0.52;
    s.addShape(pres.shapes.RECTANGLE, { x: L, y: y + 0.03, w: 0.52, h: 0.32, fill: { type: "none" }, line: { color: SKY, width: 1.25 } });
    k.T(`#${i + 1}`, { x: L, y: y + 0.03, w: 0.52, h: 0.32, fontSize: 12, bold: true, color: SKY, align: "center", valign: "middle" });
    k.T([{ text: name, options: { bold: true, color: WHITE } }, { text: "   " + topic, options: { color: PALE } }], { x: L + 0.7, y, w: 5.4, h: 0.38, fontSize: 15, valign: "middle" });
  });
  partBar(k, part - 1);
  return s;
}

function tableRows(rows, o = {}) {
  return rows.map((r, i) => r.map((c) => {
    const cell = typeof c === "object" ? c : { text: String(c) };
    const head = i === 0;
    return { text: cell.text, options: {
      bold: head || cell.bold, color: head ? WHITE : (cell.color || NAVY),
      fill: { color: head ? NAVY : (cell.fill || (o.hi && o.hi.includes(i) ? HILITE : (i % 2 ? WHITE : TINT))) } } };
  }));
}
function table(s, rows, { x = L, y, w = W, colW, fontSize = 12, hi, rowH } = {}) {
  s.addTable(tableRows(rows, { hi }), { x, y, w, colW, fontFace: FONT, fontSize, valign: "middle", margin: [3, 6, 3, 6],
    border: { type: "solid", pt: 0.5, color: RULE }, ...(rowH ? { rowH } : {}) });
}

// appendix frame
function appendix(id, title, answers, source) {
  page += 1;
  const s = pres.addSlide({ sectionTitle: "Appendix" });
  s.background = { color: WHITE };
  const k = kit(s);
  k.header("APPENDIX", `BACKUP  ·  ${id}`, `${id}  ${title}`, answers);
  k.T(source, { x: L, y: 6.95, w: 9, h: 0.3, fontSize: 11, color: MUTED });
  k.T(String(page), { x: L + W - 0.6, y: 6.95, w: 0.6, h: 0.3, fontSize: 11, color: MUTED, align: "right" });
  s.addNotes(`BACKUP SLIDE, not in the 20 minutes. ${answers}`);
  return { s, k };
}

(async () => {
  // ================= COVER =================
  {
    page += 1;
    pres.addSection({ title: "Opening" });
    const s = pres.addSlide({ sectionTitle: "Opening" });
    s.background = { color: NAVY };
    const k = kit(s);
    s.addImage({ path: MAP_ISO, x: 0, y: 0, w: 13.333, h: 7.5, altText: "FAST-LIVO2 coloured map of the lab with the 26 m path in orange" });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: NAVY, transparency: 55 }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 6.4, h: 7.5, fill: { color: NAVY, transparency: 12 }, line: { type: "none" } });
    const mx = 1038 * 13.333 / 1920, my = 645 * 7.5 / 1080;
    s.addShape(pres.shapes.OVAL, { x: mx - 0.35, y: my - 0.35, w: 0.7, h: 0.7, fill: { type: "none" }, line: { color: SIGNAL, width: 2.5 } });
    k.T("INTERIM ASSESSMENT  ·  28 OCTOBER 2026", { x: L, y: 1.0, w: 6, h: 0.3, fontSize: 12, bold: true, color: SKY, charSpacing: 2 });
    k.T("GAPPLER", { x: L, y: 1.35, w: 6, h: 1.0, fontSize: 66, bold: true, color: WHITE, charSpacing: 2 });
    k.T("High-Readiness Mobile Manipulation via Gaze-Speech Interaction and Continuous Pre-Alignment", { x: L, y: 2.5, w: 5.5, h: 1.0, fontSize: 20, color: WHITE, valign: "top" });
    k.T("Look at it, name it, and the robot fetches that one.", { x: L, y: 3.65, w: 5.5, h: 0.4, fontSize: 18, italic: true, color: SIGNAL });
    k.T("Dion  ·  Sherman  ·  Zongzhe", { x: L, y: 4.9, w: 5.5, h: 0.4, fontSize: 18, bold: true, color: WHITE });
    k.T("Supervisors: Prof Yuan Shenghai, Prof Xie Lihua", { x: L, y: 5.35, w: 5.5, h: 0.3, fontSize: 13, color: PALE });
    k.T("FAST-LIVO2 map of the lab  ·  26 m loop  ·  20 Oct", { x: 8.5, y: 6.95, w: 4.3, h: 0.3, fontSize: 11, color: PALE, align: "right" });
    s.addNotes("Good afternoon. We are Dion, Sherman and Zongzhe. Our project is a mobile robot that fetches the specific object a person looked at and named, even when the robot cannot see that object at the start.\n\n(Presenter: Dion. Transition: \"Here is the situation we want the robot to handle.\")");
  }

  // ================= PART 1 =================
  pres.addSection({ title: "1 Problem and plan" });
  divider("1 Problem and plan", 1, "The problem and our plan", "Why this is hard, what we build, how we work",
    [["Dion", "the problem and the objective"], ["Zongzhe", "the five-phase system"], ["Sherman", "where we started and how we work"]],
    { path: LOCAL_MEDIA + "image-6-1.jpg", iw: 645, ih: 590, tx: 340, ty: 191, chip: "ARIA GLASSES  ·  WHAT THE USER SEES", caption: "The user looks and speaks. The robot has to find that one object." });

  // ---- 2: the problem ----
  {
    const s = slide("1 Problem and plan"), k = kit(s);
    k.header("DION", "THE PROBLEM", "The user sees the object. The robot does not", "Same box, three viewpoints, almost nothing in common pixel for pixel");
    const iw = (W - 0.4) / 3, ih = 2.55;
    [[LOCAL_MEDIA + "image-2-1.jpg", "USER'S GLASSES  ·  1 TO 3 M, FRONT ON"],
     [LOCAL_MEDIA + "base_cam_frame.jpg", "ROBOT BASE CAMERA  ·  KNEE HEIGHT"],
     [LOCAL_MEDIA + "image-2-2.jpg", "ROBOT WRIST CAMERA  ·  0.2 TO 0.5 M"]].forEach(([p, cap], i) =>
      k.photo(p, { x: L + i * (iw + 0.2), y: 2.05, w: iw, h: ih }, cap));
    const cy = 4.85, ch = 1.35;
    [["FAM-HRI  ·  LAI ET AL., 2025", "Gaze and speech pick an object, ", "if it is already in front of the arm"],
     ["HICO-NAV  ·  XU ET AL., ICRA 2026", "Searches a room by memory, ", "for a class, not the one you mean"]].forEach(([lab, a, b], i) => {
      const x = L + i * (iw + 0.2);
      k.RR({ x, y: cy, w: iw, h: ch, fill: { color: TINT } });
      k.label(lab, x + 0.2, cy + 0.17, iw - 0.4, BLUE);
      k.T([{ text: a, options: { color: NAVY } }, { text: b, options: { color: NAVY, bold: true } }], { x: x + 0.2, y: cy + 0.47, w: iw - 0.4, h: 0.8, fontSize: 15, valign: "top" });
    });
    const x3 = L + 2 * (iw + 0.2);
    k.RR({ x: x3, y: cy, w: iw, h: ch, fill: { color: NAVY } });
    k.label("WHY IT MATTERS", x3 + 0.2, cy + 0.17, iw - 0.4, SKY);
    k.T("Users who can look but not easily point or speak", { x: x3 + 0.2, y: cy + 0.47, w: iw - 0.4, h: 0.8, fontSize: 14, color: WHITE, valign: "top" });
    k.caption("Base camera: the lab from knee height. A frame of the box is still to be taken.", L, 6.28, W);
    k.tracker(0);
    s.addNotes("Picture a user wearing Meta's Aria glasses. They look at a box on a table and say 'find the box'. The robot is somewhere else in the room. It has never seen the user's view.\n\nThese three images show why that is hard. On the left is what the glasses see: the box from a metre or two away, front on. In the middle, the robot's base camera, at knee height. On the right, the wrist camera on the arm, looking down from twenty centimetres. Same object, but the images have almost nothing in common.\n\nTwo published systems each solve half of this. FAM-HRI uses gaze and speech from the same glasses to tell an arm what to pick, but it assumes the object is already in front of the arm. HiCo-Nav lets a robot search a room using a memory of what it has seen, but it finds a class, any box, not the one you looked at. Our project joins the two: the robot explores like HiCo-Nav, and the user's gaze tells it which object to stop for.\n\nTransition: \"So what exactly are we building, and how will we know it works?\"");
  }

  // ---- 3: objective ----
  {
    const s = slide("1 Problem and plan"), k = kit(s);
    k.header("DION", "THE OBJECTIVE", "Find, reach and grasp the object the user looked at", "In a room the robot cannot see at the start");
    const cw = (W - 0.6) / 3, ch = 1.55;
    const cards = [["MdMap", "HICO-NAV  ·  WE TAKE", "Explore a room, remember every object in 3D", TINT],
      ["MdGpsFixed", "WHAT WE ADD", "The gaze target tells the robot when to stop", NAVY],
      ["MdVisibility", "FAM-HRI  ·  WE TAKE", "Gaze and speech from the glasses pick the object", TINT]];
    for (const [i, [ic, lab, t, fill]] of cards.entries()) {
      const x = L + i * (cw + 0.3), dark = fill === NAVY;
      k.RR({ x, y: 2.05, w: cw, h: ch, fill: { color: fill } });
      await k.circleIcon(x + 0.22, 2.25, 0.5, ic, dark ? SIGNAL : BLUE);
      k.label(lab, x + 0.9, 2.37, cw - 1, dark ? SKY : BLUE);
      k.T(t, { x: x + 0.22, y: 2.9, w: cw - 0.4, h: 0.6, fontSize: 16, bold: dark, color: dark ? WHITE : NAVY, valign: "top" });
      if (i < 2) k.T("+", { x: x + cw, y: 2.5, w: 0.3, h: 0.6, fontSize: 22, bold: true, color: MUTED, align: "center", valign: "middle" });
    }
    k.label("MILESTONES, EACH WITH A WRITTEN TEST (APPENDIX A10)", L, 3.9, 8);
    const ms = [["M1", "Arm picks something up"], ["M2", "Voice and gaze reach the arm"], ["M3", "Base navigates"], ["M6", "Memory graph"],
      ["M7", "Graph drives the robot"], ["M8", "Gaze picks the instance"], ["M10", "Demo and paper"]];
    const step = (W - 1.6) / 6, ly = 5.0, d = 0.72;
    k.line(L + 0.8, ly, L + W - 0.8, ly, { color: GREY, width: 2 });
    const x7 = L + 0.8 + 4 * step, x8 = L + 0.8 + 5 * step;
    k.RR({ x: x7 - 0.85, y: 4.4, w: x8 - x7 + 1.7, h: 1.75, fill: { type: "none" }, line: { color: SIGNAL, width: 1.25, dashType: "dash" } });
    k.T("where the two systems meet", { x: x7 - 0.85, y: 4.13, w: x8 - x7 + 1.7, h: 0.22, fontSize: 11, bold: true, color: EMBER, align: "center" });
    ms.forEach(([m, t], i) => {
      const cx = L + 0.8 + i * step, hot = i === 4 || i === 5;
      k.num(cx - d / 2, ly - d / 2, d, m, hot ? NAVY : BLUE, WHITE, 14);
      k.T(t, { x: cx - 0.8, y: ly + 0.48, w: 1.6, h: 0.6, fontSize: 13, bold: hot, color: NAVY, align: "center", valign: "top" });
    });
    k.caption("Evaluation: end-to-end trials, success per phase. Without gaze is a stretch goal. Also M0, M4, M5 and M9.", L, 6.25, W);
    k.tracker(0);
    s.addNotes("Our main objective is a mobile manipulator that takes what the user says and where they look, explores a room it cannot see at the start, finds the user and then the object they looked at, drives to it, checks it with the wrist camera and grasps it.\n\nGaze is what ties this together. From the glasses we cut out the object the user looked at and turn it into a CLIP image feature. While the robot explores, it compares every object it sees with that feature. A good enough match is the signal to stop exploring and go to that object. Without it, the robot has no way to know it has found the right one. We will measure the whole pipeline end to end, with gaze, phase by phase. A comparison without gaze is a stretch goal.\n\nTo make progress measurable we broke the project into eleven milestones. Each has a written test. For example, M2 is done when, with two boxes on the table, the arm picks the one you looked at three times out of four.\n\nHandover: \"Here is the full behaviour we are building towards. Zongzhe will walk through it.\"");
  }

  // ---- 4: five phases ----
  {
    const s = slide("1 Problem and plan"), k = kit(s);
    k.header("ZONGZHE", "THE SYSTEM", "The target system works in five phases", "From a spoken word and a glance to a grasp, in a room the robot has not seen");
    const gap = 0.25, cw = (W - 4 * gap) / 5, ch = 3.2;
    const phases = [
      ["MdMic", "Intent capture", "Word from speech, object from gaze", [["Tested on replay", ST.tested]], "Dion"],
      ["MdMap", "Explore and find the user", "Map the room, remember objects, find the user", [["Map tested live", ST.tested], ["Graph offline", ST.alone], ["Exploring planned", ST.planned]], "Sherman, Zongzhe, Dion"],
      ["MdSearch", "Search", "Match objects to the gaze target", [["Sentence search built", ST.built], ["Gaze match planned", ST.planned]], "Zongzhe, Dion"],
      ["MdCenterFocusStrong", "Approach and confirm", "Drive close, wrist camera confirms", [["Confirm on replay", ST.tested], ["Driving planned", ST.planned]], "Dion, Sherman"],
      ["MdPanTool", "Grasp", "Choose, plan and execute the grasp", [["Tested on real arm", ST.tested]], "Dion"],
    ];
    for (const [i, [ic, name, job, chips, who]] of phases.entries()) {
      const x = L + i * (cw + gap), y = 2.05;
      k.RR({ x, y, w: cw, h: ch, fill: { color: TINT } });
      await k.circleIcon(x + 0.18, y + 0.2, 0.5, ic);
      k.T(String(i + 1), { x: x + cw - 0.7, y: y + 0.12, w: 0.55, h: 0.6, fontSize: 30, bold: true, color: GREY, align: "right" });
      k.T(name, { x: x + 0.18, y: y + 0.8, w: cw - 0.3, h: 0.55, fontSize: 15, bold: true, color: NAVY, valign: "top" });
      k.T(job, { x: x + 0.18, y: y + 1.38, w: cw - 0.3, h: 0.7, fontSize: 12, color: SLATE, valign: "top" });
      chips.forEach(([t, st], j) => k.chip(x + 0.15, y + 2.07 + j * 0.31, cw - 0.3, t, st));
      k.caption(who, x, y + ch + 0.07, cw);
      if (i < 4) k.T("›", { x: x + cw, y: y + 1.0, w: gap, h: 0.5, fontSize: 24, bold: true, color: MUTED, align: "center", valign: "middle" });
    }
    const sy = 5.7, sh = 0.75, nw = 3.1;
    const scope = [["MdSearch", "Exploration is the core"], ["MdBlock", "M9 cut first if late"], ["MdClose", "Not in scope: bringing it back"]];
    const scw = (W - nw - 0.2 - 0.4) / 3;
    for (const [i, [ic, t]] of scope.entries()) {
      const x = L + i * (scw + 0.2);
      k.RR({ x, y: sy, w: scw, h: sh, fill: { color: TINT } });
      await k.circleIcon(x + 0.18, sy + 0.15, 0.45, ic, BLUE);
      k.T(t, { x: x + 0.78, y: sy, w: scw - 0.85, h: sh, fontSize: 13, bold: true, color: NAVY, valign: "middle" });
    }
    k.RR({ x: L + W - nw, y: sy, w: nw, h: sh, fill: { color: NAVY } });
    k.T([{ text: "March 2027  ", options: { bold: true, color: WHITE, fontSize: 16 } }, { text: "final demonstration (M10)", options: { color: PALE, fontSize: 12 } }],
      { x: L + W - nw + 0.2, y: sy, w: nw - 0.3, h: sh, valign: "middle" });
    k.tracker(1);
    s.addNotes("The finished system works in five phases. First, the user speaks and looks. Speech gives us the word, gaze tells us which object, and we cut an image crop of it and turn it into a CLIP feature. Second, the robot explores. It maps the room and builds a memory of the objects it sees, each with a 3D position and an image feature. It looks for the user first, because the object is somewhere the user can see. Third, it compares what it sees with the user's target. A good match tells it to stop exploring. Fourth, it drives close and the camera on the arm confirms that this is the object the user meant. If not, it goes back to exploring. Fifth, it grasps.\n\nExploration is the core of the search. HiCo-Nav also has a smarter way to choose where to explore next. That part is optional and the first thing we cut if time runs short. Bringing the object back to the user is out of scope.\n\nThe badges show where each phase stands seven weeks in. The next eleven minutes go through them in order.\n\nHandover: \"Before the results, Sherman covers where we started and how we work.\"");
  }

  // ---- 5: starting point and approach ----
  {
    const s = slide("1 Problem and plan"), k = kit(s);
    k.header("SHERMAN", "OUR APPROACH", "The inherited code did not run, so we built a test bench first", "Rebuilt from tested open-source parts, with a baseline measured before every change");
    const lw = 3.7;
    k.RR({ x: L, y: 2.05, w: lw, h: 4.4, fill: { color: TINT } });
    k.label("SEPTEMBER 2026  ·  WHERE WE STARTED", L + 0.2, 2.22, lw - 0.3, EMBER);
    const probs = ["No tests, no CI", "Arm moved on its own at start-up", "AnyGrasp path unreachable", "Navigation ran only from another user's folder", "No memory graph code"];
    for (const [i, p] of probs.entries()) {
      const y = 2.65 + i * 0.75;
      await k.circleIcon(L + 0.2, y + 0.04, 0.32, "MdClose", "DC2626");
      k.T(p, { x: L + 0.65, y, w: lw - 0.8, h: 0.6, fontSize: 13, color: NAVY, valign: "top" });
    }
    const px = L + lw + 0.25, pw = W - lw - 0.25, gap = 0.2, cw = (pw - 2 * gap) / 3, ch = 2.9;
    const people = [
      ["D", "Dion", ["Glasses", "Matching", "Arm, grasp", "Bench, CI"], "Aria SDK, SAM 3, AnyGrasp, MoveIt 2", "Leads M1 M2 M4 M7 M8"],
      ["S", "Sherman", ["Base", "LiDAR", "Mount", "Mapping"], "FAST-LIVO2, Nav2, SLAM Toolbox", "Leads M3, M5 mount"],
      ["Z", "Zongzhe", ["Memory graph", "Reasoning", "Nav goals"], "HiCo-Nav method, open_clip, Qwen2.5", "Leads M0 M6 M9"],
    ];
    people.forEach(([ini, name, tags, base, leads], i) => {
      const x = px + i * (cw + gap), y = 2.05;
      k.RR({ x, y, w: cw, h: ch, fill: { color: TINT } });
      k.num(x + 0.2, y + 0.2, 0.55, ini, NAVY, WHITE, 18);
      k.T(name, { x: x + 0.9, y: y + 0.2, w: cw - 1, h: 0.55, fontSize: 18, bold: true, color: NAVY, valign: "middle" });
      let tx = x + 0.2, ty = y + 0.95;
      tags.forEach((t) => {
        const tw = t.length * 0.075 + 0.25;
        if (tx + tw > x + cw - 0.15) { tx = x + 0.2; ty += 0.36; }
        k.chip(tx, ty, tw, t, { fill: WHITE, text: NAVY });
        tx += tw + 0.08;
      });
      k.label("BUILDS ON", x + 0.2, y + 1.78, cw - 0.3);
      k.T(base, { x: x + 0.2, y: y + 2.02, w: cw - 0.35, h: 0.45, fontSize: 12, color: SLATE, valign: "top" });
      k.chip(x + 0.2, y + 2.5, cw - 0.4, leads, { fill: HILITE, text: BLUE });
    });
    const by = 5.15, bh = 1.3;
    k.RR({ x: px, y: by, w: pw, h: bh, fill: { color: NAVY } });
    k.label("SHARED BASE", px + 0.25, by + 0.13, 3, SKY);
    const iw3 = (pw - 0.5) / 3;
    for (const [i, [ic, t, d]] of [["MdHub", "Channel contract", "an owner for every topic"], ["MdLayers", "7-level test bench", "L0 static to L6 robot"], ["MdCheckCircle", "CI on every PR", "plus a GPU runner"]].entries()) {
      const x = px + 0.25 + i * iw3;
      await k.circleIcon(x, by + 0.48, 0.55, ic, BLUE);
      k.T(t, { x: x + 0.68, y: by + 0.45, w: iw3 - 0.75, h: 0.3, fontSize: 14, bold: true, color: WHITE });
      k.T(d, { x: x + 0.68, y: by + 0.76, w: iw3 - 0.75, h: 0.3, fontSize: 12, color: PALE });
    }
    k.tracker(1);
    s.addNotes("We did not start from a working system. The inherited code had no tests and no CI, and none of it ran from a fresh copy. One program homed the real arm within seconds, with no prompt. Navigation ran only from another user's workspace, and our copy did not build. There was no memory graph.\n\nSo we built foundations first. Dion took the glasses and the arm, I took the base and mapping, and Zongzhe the memory graph. A channel contract says who owns every message and frame, and a seven-level test bench runs on every pull request. We measure a baseline before replacing anything, and on the real robot we move one step at a time, with two people present.\n\nHandover: \"Phase one: turning a sentence and a glance into a target. Over to Dion.\"");
  }

  // ================= PART 2 =================
  pres.addSection({ title: "2 Results" });
  divider("2 Results", 2, "Results, phase by phase", "Every stage measured on real hardware or real recordings",
    [["Dion", "intent capture"], ["Sherman", "the 3D map and the camera frames"], ["Zongzhe", "the memory graph and search"], ["Dion", "confirm and grasp"]],
    { path: SHERMAN + "nav_fastlivo_map_inside_clean_handdriven1_2026-10-24.png", iw: 1920, ih: 1080, tx: 805, ty: 885, chip: "MOBILE BASE  ·  FAST-LIVO2 MAP", caption: "Inside the lab map. Orange: the 26 m hand-pushed path." });

  // ---- 6: intent capture ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("DION", "PHASE 1  ·  INTENT CAPTURE", "Speech gives the word, gaze picks the object", "A one-second gaze vote over SAM 3 masks makes the reference crop sent to the robot");
    const lw = R.x - 0.25 - L, gap = 0.15, sw = (lw - 3 * gap) / 4;
    const steps = [["MdMic", "Voice", "one word per sentence"], ["MdAccessTime", "Moment", "the frame from when you spoke"],
      ["MdCropFree", "Segment", "SAM 3 finds every “box”"], ["MdVisibility", "Vote", "gaze picks a mask, then crop it"]];
    for (const [i, [ic, t, d]] of steps.entries()) {
      const x = L + i * (sw + gap);
      k.RR({ x, y: 2.05, w: sw, h: 0.85, fill: { color: TINT } });
      await k.circleIcon(x + 0.12, 2.2, 0.42, ic);
      k.T(t, { x: x + 0.65, y: 2.12, w: sw - 0.7, h: 0.3, fontSize: 14, bold: true, color: NAVY });
      k.T(d, { x: x + 0.65, y: 2.42, w: sw - 0.72, h: 0.45, fontSize: 11, color: SLATE, valign: "top" });
    }
    const pw = (lw - 0.2) / 2;
    k.photo(LOCAL_MEDIA + "image-6-1.jpg", { x: L, y: 3.1, w: pw, h: 3.1 }, "1.0 M  ·  GAZE ON THE BOX, BOX PICKED");
    k.photo(LOCAL_MEDIA + "image-6-2.jpg", { x: L + pw + 0.2, y: 3.1, w: pw, h: 3.1 }, "1.5 M  ·  GAZE LANDED ON THE MATS");
    k.hero({ label: "RIGHT BOX, STEADY STARE", big: "60", unit: " of 61", sub: "recorded frames, at 1.4 to 2.4 m" });
    await k.stat({ y: 4.1, h: 0.9, ic: "MdCheckCircle", num: "4 of 4", label: "spoken words gave a crop (replay)" });
    k.limitCard(R.x, 5.15, R.w, 1.05, "Gaze is off by about 5.6 degrees: about 15 cm at 1.5 m");
    k.caption("Blue ring: gaze vote window. Tested on recordings and replay; live stream still throttled.", L, 6.28, W);
    k.tracker(2);
    s.addNotes("The user says 'find the box'. A speech detector waits for the sentence to finish, Whisper turns it into text, and a small language model pulls out the object word. Before this, the old pipeline produced thirty-one messages per phrase. Now it produces one.\n\nGaze runs at the same time. We keep the last twenty seconds of glasses images and gaze points, so we can go back to the moment the user was speaking. SAM 3, a segmentation model you prompt with a word, finds every box in that one frame. Then gaze votes. Each gaze sample in a one-second window votes for the mask it lands on, and the winner needs half the votes. We crop that mask with a small margin. That crop is what we send to the robot.\n\nOn a recording at 1.4 to 2.4 metres, this picked the right box in 60 of 61 frames. On a full replay, all four spoken words produced a crop.\n\nThe limit is gaze accuracy. The eye model is off by about five and a half degrees, roughly 15 centimetres at 1.5 metres. Here, at 1.5 metres, it landed on a stack of mats that SAM 3 also called a box. Keep that case in mind. It comes back on the CLIP slide.\n\nHandover: \"That crop now has to be found by a robot that has never seen this view. Sherman will show how the robot knows where it is.\"");
  }

  // ---- 7: map ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("SHERMAN", "PHASE 2  ·  EXPLORE AND MAP", "A 3D map that closes within 12 mm", "FAST-LIVO2 fuses LiDAR, IMU and colour camera into one 3D pose");
    k.rail(["3D map", "Camera frames"], 0, "Pushed by hand, not yet driven by Nav2");
    const box = { x: C.x, y: 2.05, w: C.w, h: 4.15 };
    k.photo(MAP_ISO, box, null, "FAST-LIVO2 coloured point-cloud map of the lab with the 26 m path in orange");
    const sc = Math.max(box.w / 1920, box.h / 1080);
    const mx = box.x + 1038 * sc - (1920 * sc - box.w) / 2, my = box.y + 645 * sc - (1080 * sc - box.h) / 2;
    s.addShape(pres.shapes.OVAL, { x: mx - 0.24, y: my - 0.24, w: 0.48, h: 0.48, fill: { type: "none" }, line: { color: SIGNAL, width: 2 } });
    k.caption("Hand-pushed 26 m loop, 20 Oct. Orange = path, ring = start and end.", box.x, 6.28, box.w);
    k.hero({ label: "LOOP CLOSURE", big: "12", unit: " mm", sub: "back to start after 26 m" });
    await k.stat({ y: 4.15, ic: "MdTimeline", num: "6.7 cm", label: "worst error mid-route" });
    await k.stat({ y: 5.25, ic: "MdSpeed", num: "11–14 ms", label: "per frame on CPU (budget 100)" });
    k.tracker(3);
    s.addNotes("Before the robot can remember where objects are, it needs to know where it is. We use FAST-LIVO2, the method the HiCo-Nav paper uses, from the University of Hong Kong. It fuses the LiDAR, its motion sensor and the colour camera into one pose, and paints a coloured 3D map.\n\nWhy 3D? 2D SLAM knows only where the base is on the floor and which way it faces. The memory graph places each object in 3D from the camera's pose, so an unmeasured tilt moves objects by centimetres. Nav2 still drives on a 2D grid built from this pose.\n\nFAST-LIVO2 is published for ROS 1. We run a community ROS 2 port, and getting it to work was most of the effort. I proved it on the authors' own recording first, then on our sensors with every message checked. I found three defects that fail silently: no crash, just a wrong map. Each was found by reading the source and confirmed against a control run.\n\nThe result: I pushed the base by hand around a 26-metre loop. The path returns to its start within 12 millimetres, and the mid-route error is within about 7 centimetres, the limit of our reference. The pose now feeds Nav2's frame tree. Nav2 driving the base is the next test.\n\nSource: recording handdriven1, 20 Oct 2026. Closure 4 mm LiDAR-only, 7 mm odometry (0.03 %). CR 8.4.\n\nTransition: \"A map is only useful to the arm and the memory if every camera's position on the robot is known.\"");
  }

  // ---- 8: camera frames ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("SHERMAN", "PHASE 2  ·  EXPLORE AND MAP", "Four camera links, four states of calibration", "Each missing calibration blocks a specific later step");
    k.rail(["3D map", "Camera frames"], 1, "Base camera not yet calibrated: about 6.7 px of error per degree");
    // side-view sketch of the robot and the user
    k.RR({ x: C.x, y: 2.05, w: C.w, h: 4.15, fill: { color: "F8FAFC" } });
    const g = "64748B";
    k.line(C.x + 0.2, 5.95, C.x + C.w - 0.2, 5.95, { color: GREY, width: 1 });
    k.RR({ x: 3.25, y: 4.9, w: 3.3, h: 0.72, fill: { color: "334155" } });
    k.T("Mobile base", { x: 3.25, y: 4.9, w: 2.2, h: 0.72, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle" });
    [3.55, 5.85].forEach((x) => s.addShape(pres.shapes.OVAL, { x, y: 5.6, w: 0.36, h: 0.36, fill: { color: NAVY }, line: { type: "none" } }));
    k.RR({ x: 5.6, y: 4.5, w: 0.65, h: 0.4, rectRadius: 0.05, fill: { color: g } });
    k.T("LiDAR", { x: 5.6, y: 4.5, w: 0.65, h: 0.4, fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle" });
    k.RR({ x: 6.55, y: 5.05, w: 0.28, h: 0.3, rectRadius: 0.04, fill: { color: g } });
    k.T("Base camera", { x: 6.9, y: 5.08, w: 1.2, h: 0.25, fontSize: 11, color: NAVY });
    k.line(3.95, 4.9, 3.95, 3.55, { color: g, width: 7 });
    k.line(3.95, 3.55, 5.0, 2.85, { color: g, width: 7 });
    k.line(5.0, 2.85, 5.3, 3.2, { color: g, width: 5 });
    k.RR({ x: 5.2, y: 3.2, w: 0.38, h: 0.26, rectRadius: 0.04, fill: { color: g } });
    k.T("Wrist camera", { x: 5.65, y: 3.2, w: 1.3, h: 0.25, fontSize: 11, color: NAVY });
    k.T("Arm", { x: 3.3, y: 3.75, w: 0.55, h: 0.25, fontSize: 11, color: NAVY, align: "right" });
    // user with glasses
    const ux = 8.3;
    s.addShape(pres.shapes.OVAL, { x: ux - 0.2, y: 3.0, w: 0.4, h: 0.4, fill: { type: "none" }, line: { color: NAVY, width: 1.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: ux - 0.2, y: 3.14, w: 0.3, h: 0.08, fill: { color: SIGNAL }, line: { type: "none" } });
    k.line(ux, 3.4, ux, 4.8); k.line(ux, 3.7, ux - 0.3, 4.25); k.line(ux, 3.7, ux + 0.3, 4.25);
    k.line(ux, 4.8, ux - 0.25, 5.95); k.line(ux, 4.8, ux + 0.25, 5.95);
    k.T("User + glasses", { x: ux - 0.65, y: 2.65, w: 1.3, h: 0.25, fontSize: 11, color: NAVY, align: "center" });
    // the four links, coloured by status
    k.line(6.17, 4.7, 6.82, 4.45, { color: ST.built.dot, width: 2 });
    k.line(6.82, 4.45, 6.7, 5.05, { color: ST.built.dot, width: 2 });
    k.line(ux - 0.22, 3.2, 6.25, 4.45, { color: ST.planned.dot, width: 2, dashType: "dash" });
    const marks = [[3.42, 4.38, 1, ST.tested], [6.72, 4.2, 2, ST.built], [4.48, 3.45, 3, ST.tested], [7.05, 3.62, 4, ST.planned]];
    marks.forEach(([x, y, n, st]) => k.num(x, y, 0.36, n, st.dot, WHITE, 13));
    k.caption("Camera calibration is a separate problem from the robot's frame tree (appendix A2).", C.x, 6.28, C.w);
    const cards = [
      [1, "Base to arm", ST.tested, "Measured", "Arm grasps in the base's map"],
      [2, "Base camera to LiDAR", ST.built, "Mount measured, not calibrated", "Graph objects. Rig planned (T5.5)"],
      [3, "Wrist camera to arm", ST.tested, "Calibrated", "Camera grasp becomes an arm goal"],
      [4, "Glasses to robot", ST.planned, "Planned (T8.8)", "Gaze ray in robot frame, look-alikes"],
    ];
    cards.forEach(([n, t, st, state, use], i) => {
      const y = 2.05 + i * 1.07;
      k.RR({ x: R.x, y, w: R.w, h: 0.95, fill: { color: TINT } });
      k.num(R.x + 0.15, y + 0.15, 0.36, n, st.dot, WHITE, 13);
      k.T(t, { x: R.x + 0.62, y: y + 0.1, w: R.w - 0.75, h: 0.28, fontSize: 14, bold: true, color: NAVY });
      k.T(state, { x: R.x + 0.62, y: y + 0.37, w: R.w - 0.75, h: 0.22, fontSize: 11, bold: true, color: st.text });
      k.T(use, { x: R.x + 0.62, y: y + 0.58, w: R.w - 0.75, h: 0.35, fontSize: 11, color: SLATE, valign: "top" });
    });
    k.tracker(3);
    s.addNotes("There are four places where we need to know how one part of the robot sits relative to another.\n\nThe arm on the base is measured. We set the transform from the mount drawings and checked it on the robot. The base's own origin, on the floor under the drive axle, matches the vendor's manual.\n\nThe base camera relative to the LiDAR is measured but not calibrated. I designed and fitted the mount, measured to the camera's mounting hole, and took the rest from Intel's published camera dimensions. It sits flush on vertical aluminium extrusions, so it points straight by construction. What is left is a calibration against the LiDAR itself, because one degree of error moves a point by about seven pixels. The rig for that is planned.\n\nThe wrist camera relative to the arm is calibrated, so a grasp it sees becomes an arm goal.\n\nThe last one is different in kind. To use gaze to separate two identical objects, the robot needs the user's gaze ray in its own frame, which means locating the glasses relative to the robot. That is planned for January.\n\nNone of these blocks today's results, but each one blocks a specific later step.\n\nHandover: \"With poses and camera images from that drive, Zongzhe builds the robot's memory of the room.\"");
  }

  // ---- 9: memory graph ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("ZONGZHE", "PHASE 2  ·  EXPLORE AND MAP", "The memory graph turns a drive into a map of objects", "Each object gets a 3D position and a CLIP image feature, built from the recorded drive");
    k.rail(["Memory graph", "Merge tuning", "Search"], 0, "Built offline from a recorded drive. Not yet live while driving");
    k.label("HOW IT IS BUILT  ·  14 TESTED STAGES", C.x, 2.05, C.w);
    const stages = ["Keep a photo every 1 m or 45°", "SAM 3 finds all 30 classes", "LiDAR gives depth", "Lift each mask to 3D", "CLIP feature per object", "Merge repeat sightings"];
    const sw = (C.w - 0.3) / 3;
    stages.forEach((t, i) => {
      const x = C.x + (i % 3) * (sw + 0.15), y = 2.4 + Math.floor(i / 3) * 0.95;
      k.RR({ x, y, w: sw, h: 0.8, fill: { color: TINT } });
      k.num(x + 0.12, y + 0.22, 0.36, i + 1, BLUE, WHITE, 12);
      k.T(t, { x: x + 0.58, y: y + 0.05, w: sw - 0.65, h: 0.7, fontSize: 13, color: NAVY, valign: "middle" });
    });
    k.label("WHAT IT STORES", C.x, 4.4, C.w);
    k.RR({ x: C.x, y: 4.75, w: C.w, h: 1.7, fill: { color: TINT } });
    const an = [[C.x + 0.55, 5.1], [C.x + 0.55, 5.85]], ob = [[C.x + 2.35, 4.98, "chair"], [C.x + 2.35, 5.48, "table"], [C.x + 2.35, 5.98, "box"]];
    [[0, 0], [0, 1], [1, 1], [1, 2]].forEach(([i, j]) => k.line(an[i][0] + 0.25, an[i][1] + 0.25, ob[j][0] + 0.17, ob[j][1] + 0.17, { color: GREY, width: 1.5 }));
    for (const [x, y] of an) await k.circleIcon(x, y, 0.5, "MdPhotoCamera", NAVY);
    ob.forEach(([x, y, t]) => {
      s.addShape(pres.shapes.OVAL, { x, y, w: 0.34, h: 0.34, fill: { color: BLUE }, line: { color: WHITE, width: 1.5 } });
      k.T(t, { x: x + 0.42, y, w: 0.8, h: 0.34, fontSize: 12, color: NAVY, valign: "middle" });
    });
    const lx = C.x + 3.65;
    for (const [i, [t, d]] of [["Anchor", "kept photo + camera pose"], ["Object", "3D box, CLIP feature, class"]].entries()) {
      const y = 5.0 + i * 0.68;
      if (i === 0) await k.circleIcon(lx, y + 0.02, 0.36, "MdPhotoCamera", NAVY);
      else s.addShape(pres.shapes.OVAL, { x: lx + 0.03, y: y + 0.05, w: 0.3, h: 0.3, fill: { color: BLUE }, line: { type: "none" } });
      k.T(t, { x: lx + 0.48, y: y - 0.03, w: 1.8, h: 0.25, fontSize: 13, bold: true, color: NAVY });
      k.T(d, { x: lx + 0.48, y: y + 0.21, w: 1.85, h: 0.25, fontSize: 11, color: SLATE });
    }
    k.hero({ h: 1.75, label: "PHOTOS KEPT", big: "29", unit: " of 3,536", sub: "99.2 % less segmentation time" });
    await k.stat({ y: 3.92, h: 0.78, ic: "MdBolt", num: "1.69 s vs 9.70 s", label: "batched SAM 3, 5.7 times faster" });
    await k.stat({ y: 4.78, h: 0.78, ic: "MdCheckCircle", num: "399 tests", label: "pass on the lab GPU" });
    await k.stat({ y: 5.66, h: 0.78, ic: "MdBuild", num: "9 problems", label: "in upstream code, fixed or avoided" });
    k.tracker(3);
    s.addNotes("The memory graph is HiCo-Nav's idea. As the robot moves, it keeps a photo now and then, finds the objects in it, and stores each object with its position in 3D and a CLIP image feature. CLIP is a model that turns an image into a vector, so that similar-looking things get similar vectors. The photos are kept too, linked to the objects they show. That link is the 'graph'.\n\nHiCo-Nav published code, but with no licence, so I read it and wrote a fresh implementation as fourteen separate stages, each with its own tests. Reading it also turned up nine problems, such as a language-model call with no timeout, which we fixed or avoided.\n\nHere is the graph built from Sherman's hand-pushed drive. Two choices keep it fast. A photo is kept only after the robot moves a metre or turns 45 degrees, so 29 of 3,536 frames go to segmentation, which saves over 99 % of that time. And all thirty object classes go through SAM 3 in one batch, 5.7 times faster than one at a time.\n\nIt is built offline from a recording. Building it live while the robot explores is next (T7.2, T7.5).\n\n[Artefact owed by Zongzhe: a Rerun 3D screenshot of the graph can replace the 'What it stores' cards.]\n\nTransition: \"The hardest part of building it is deciding when two sightings are the same object.\"");
  }

  // ---- 10: merge radius ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("ZONGZHE", "PHASE 2  ·  EXPLORE AND MAP", "A 10 cm merge radius removes duplicates safely", "Tuned against a hand-made answer key: 16 real objects marked on the LiDAR map");
    k.rail(["Memory graph", "Merge tuning", "Search"], 1, "Two drives, 16 objects: a difference of one is noise");
    k.T("Duplicates left, by match radius (cm)", { x: C.x, y: 2.05, w: C.w, h: 0.3, fontSize: 14, bold: true, color: NAVY });
    s.addChart(pres.charts.BAR, [{ name: "Duplicates, drive 1", labels: ["2.5", "5", "7.5", "10", "15", "20"], values: [8, 4, 4, 3, 3, 2] }], {
      x: 2.85, y: 2.4, w: 6.2, h: 3.6, barDir: "col", barGapWidthPct: 55,
      chartColors: [GREY, GREY, GREY, BLUE, GREY, GREY],
      showValue: true, dataLabelPosition: "outEnd", dataLabelColor: NAVY, dataLabelFontSize: 14, dataLabelFontBold: true, dataLabelFontFace: "+mn-lt",
      catAxisLabelColor: SLATE, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt", catAxisLineShow: false,
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    });
    const note = (t, cx, o = {}) => k.T(t, { x: cx - 0.6, y: 6.03, w: 1.2, h: 0.45, fontSize: 11, color: MUTED, align: "center", valign: "top", ...o });
    note("upstream", 3.47); note("chosen", 6.44, { bold: true, color: BLUE }); note("chair merges\ninto desk", 7.44);
    k.hero({ label: "DUPLICATES AT 10 CM", big: "8→3", sub: "with no false merges" });
    k.RR({ x: R.x, y: 4.15, w: R.w, h: 2.05, fill: { color: TINT } });
    await k.circleIcon(R.x + 0.18, 4.32, 0.4, "MdCompareArrows");
    k.T("Why not merge by look?", { x: R.x + 0.72, y: 4.32, w: 2.7, h: 0.4, fontSize: 14, bold: true, color: NAVY, valign: "middle" });
    [["Same chair", 0.934, "0.93", NAVY], ["Same-model chairs", 0.85, "0.81–0.85", BLUE], ["Other objects", 0.56, "0.56", GREY]].forEach(([lab, v, txt, col], i) => {
      const y = 4.95 + i * 0.4;
      k.T(lab, { x: R.x + 0.18, y, w: 1.4, h: 0.28, fontSize: 11, color: SLATE, valign: "middle" });
      s.addShape(pres.shapes.RECTANGLE, { x: R.x + 1.6, y: y + 0.07, w: 1.0 * v, h: 0.14, fill: { color: col }, line: { type: "none" } });
      k.T(txt, { x: R.x + 1.65 + 1.0 * v, y, w: 0.85, h: 0.28, fontSize: 11, bold: true, color: NAVY, valign: "middle" });
    });
    k.caption("CLIP image similarity, 0 to 1", R.x, 6.28, R.w);
    k.tracker(3);
    s.addNotes("The robot sees the same chair from many places. Each sighting must merge into one object, and two chairs side by side must stay two.\n\nTo measure that, I made an answer key by hand: sixteen real objects marked on the LiDAR map, without using any of the code being tested. Then I swept the settings.\n\nThe lever is the match radius, how close two sightings' points must be. With our sparse LiDAR depth, two views of one object land 4 to 9 centimetres apart, so upstream's 2.5 centimetres split objects. At 10 centimetres duplicates fall from 8 to 3 with no false merges. On a second drive, 2 to 1. At 15, a chair merges into the desk next to it, so we chose 10.\n\nWhy not just merge things that look alike? Because look-alikes are exactly the problem. CLIP scores two chairs of the same model at 0.81 to 0.85, close to the same chair at 0.93. Merging on appearance removes every duplicate by merging nearly everything. That is also why the class alone cannot find the user's object.\n\nChart: drive 1. The 1 cm setting (31 duplicates) is left off the chart.\n\nTransition: \"Once the objects are in the graph, the robot has to find the right one from a sentence.\"");
  }

  // ---- 11: search ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("ZONGZHE", "PHASE 3  ·  SEARCH", "A sentence becomes a ranked list of objects", "Today the query is a sentence. In the full system, the gaze crop is the query (M8)");
    k.rail(["Memory graph", "Merge tuning", "Search"], 2, "Full query on the recorded drive not run yet: T6.8, weeks 7 to 8");
    const sh = 1.33;
    const card = (i, title) => {
      const y = 2.05 + i * (sh + 0.2);
      k.RR({ x: C.x, y, w: C.w, h: sh, fill: { color: TINT } });
      k.num(C.x + 0.18, y + 0.17, 0.38, i + 1, BLUE, WHITE, 13);
      k.T(title, { x: C.x + 0.7, y: y + 0.15, w: C.w - 0.9, h: 0.42, fontSize: 15, bold: true, color: NAVY, valign: "middle" });
      return y;
    };
    let y = card(0, "Sentence to classes");
    k.RR({ x: C.x + 0.7, y: y + 0.68, w: 1.7, h: 0.38, rectRadius: 0.19, fill: { color: WHITE }, line: { color: GREY, width: 0.75 } });
    k.T("“Find the chair”", { x: C.x + 0.7, y: y + 0.68, w: 1.7, h: 0.38, fontSize: 13, italic: true, color: NAVY, align: "center", valign: "middle" });
    k.T("›", { x: C.x + 2.45, y: y + 0.62, w: 0.3, h: 0.45, fontSize: 22, bold: true, color: MUTED, align: "center" });
    [["chair", true], ["table", false], ["desk", false]].forEach(([t, on], j) => {
      const x = C.x + 2.85 + j * 0.95;
      k.RR({ x, y: y + 0.7, w: 0.85, h: 0.34, rectRadius: 0.17, fill: { color: on ? NAVY : WHITE }, line: on ? { type: "none" } : { color: GREY, width: 0.75 } });
      k.T(t, { x, y: y + 0.7, w: 0.85, h: 0.34, fontSize: 12, bold: on, color: on ? WHITE : SLATE, align: "center", valign: "middle" });
    });
    y = card(1, "Score each object");
    k.T("Its CLIP image feature against the sentence's CLIP text vector", { x: C.x + 0.7, y: y + 0.6, w: C.w - 0.9, h: 0.55, fontSize: 13, color: SLATE, valign: "top" });
    y = card(2, "Rank the hits");
    k.T("Target classes first, then related, each by score. Each hit has a 3D centre and its best photo. A wrong hit can be rejected.", { x: C.x + 0.7, y: y + 0.6, w: C.w - 0.9, h: 0.6, fontSize: 13, color: SLATE, valign: "top" });
    k.hero({ label: "SENTENCE TO CLASSES", big: "20", unit: " of 22", sub: "test instructions, checked by hand" });
    k.RR({ x: R.x, y: 4.15, w: R.w, h: 2.3, fill: { color: TINT } });
    k.label("BY LANGUAGE MODEL", R.x + 0.18, 4.3, R.w - 0.3);
    [["Qwen2.5 1.5B (used)", 20, BLUE], ["No model, fallback", 15, GREY], ["Qwen2.5 0.5B", 12, GREY]].forEach(([lab, v, col], i) => {
      const yy = 4.7 + i * 0.48;
      k.T(lab, { x: R.x + 0.18, y: yy, w: 1.55, h: 0.3, fontSize: 11, color: SLATE, valign: "middle" });
      s.addShape(pres.shapes.RECTANGLE, { x: R.x + 1.75, y: yy + 0.08, w: 1.2 * v / 22, h: 0.15, fill: { color: col }, line: { type: "none" } });
      k.T(`${v}/22`, { x: R.x + 1.8 + 1.2 * v / 22, y: yy, w: 0.6, h: 0.3, fontSize: 11, bold: true, color: NAVY, valign: "middle" });
    });
    k.T("0.28 to 0.32 s per reply, on the lab machine", { x: R.x + 0.18, y: 6.1, w: R.w - 0.3, h: 0.25, fontSize: 11, color: SLATE });
    k.tracker(4);
    s.addNotes("To search the graph, the robot first turns the sentence into classes. A small language model, running locally, returns the target class and some related ones. 'Find the chair' gives chair, plus table and desk, because chairs are usually near them. The 1.5 billion parameter model got 20 of 22 test instructions right and answers in about a third of a second.\n\nThen every object is scored by comparing its stored image feature with the sentence, using CLIP again. Target classes rank first, related ones after. Each hit comes with a 3D position and the best photo of it, and a wrong hit can be rejected so the robot tries the next one.\n\nThe ranking has been tested on stand-in data and a few photos. Running the full query on the recorded drive, checked against the answer key, is the next milestone, in the next two weeks.\n\nToday the query is a sentence. In the full system, the robot matches each object against the gaze crop, and a good match tells it to stop exploring and go to the user's chair, not just any chair.\n\n[VERIFY: Zongzhe to confirm the 'table, desk' example against check_reasoning.json.]\n\nHandover: \"Dion now picks up the object at close range.\"");
  }

  // ---- 12: CLIP cross-camera match ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("DION", "PHASE 4  ·  APPROACH AND CONFIRM", "CLIP finds the looked-at box, and now steers the grasp", "Which wrist-camera mask is the object in the glasses crop?");
    const lw = 4.9;
    k.RR({ x: L, y: 2.05, w: lw, h: 4.15, fill: { color: TINT } });
    k.label("1  ·  CHOOSE THE METHOD", L + 0.2, 2.2, lw - 0.3, BLUE);
    k.T("Box ranked first, glasses vs wrist pairs", { x: L + 0.2, y: 2.47, w: lw - 0.3, h: 0.3, fontSize: 14, bold: true, color: NAVY });
    s.addChart(pres.charts.BAR, [{ name: "Box ranked first (%)", labels: ["CLIP whole object  25/25", "SAM 3 image  15/25", "SAM 3 decoder  7/25", "Keypoints, baseline  0/15"], values: [100, 60, 28, 0] }], {
      x: L + 0.05, y: 2.8, w: lw - 0.15, h: 2.05, barDir: "bar", barGapWidthPct: 45,
      chartColors: [BLUE, GREY, GREY, GREY], valAxisMaxVal: 115, valAxisMinVal: 0,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"', dataLabelColor: NAVY, dataLabelFontSize: 12, dataLabelFontBold: true, dataLabelFontFace: "+mn-lt",
      catAxisLabelColor: NAVY, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catAxisLineShow: false,
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    });
    s.addImage({ path: LOCAL_MEDIA + "image-12-1.jpg", x: L + 0.2, y: 5.0, w: 2.3, h: 0.99, altText: "Keypoint matches between glasses and wrist views land on the ceiling and floor" });
    k.T("Keypoints match the ceiling and floor, not the box", { x: L + 2.65, y: 5.0, w: lw - 2.85, h: 0.99, fontSize: 12, color: SLATE, valign: "middle" });
    const mx = L + lw + 0.25, mw = R.x - 0.25 - mx, ih = 1.98;
    k.photo(LOCAL_MEDIA + "image-2-1.jpg", { x: mx, y: 2.05, w: mw, h: ih }, "GLASSES CROP");
    s.addShape(pres.shapes.OVAL, { x: mx + mw / 2 - 0.55, y: 2.05 + ih / 2 - 0.65, w: 1.1, h: 1.1, fill: { type: "none" }, line: { color: SIGNAL, width: 2 } });
    k.photo(LOCAL_MEDIA + "image-2-2.jpg", { x: mx, y: 2.05 + ih + 0.19, w: mw, h: ih }, "WRIST VIEW");
    k.hero({ label: "2  ·  IN THE GRASP LOOP", big: "600", unit: " of 602", sub: "wrist targets on the box the user looked at" });
    k.RR({ x: R.x, y: 4.1, w: R.w, h: 1.0, fill: { color: TINT } });
    k.label("TWO LOOK-ALIKE CARDBOARD BOXES", R.x + 0.18, 4.2, R.w - 0.3);
    [["Old pick", 0, "0 of 114", GREY], ["Glasses crop", 0.99, "266 of 268", BLUE]].forEach(([lab, v, txt, col], i) => {
      const yy = 4.47 + i * 0.3;
      k.T(lab, { x: R.x + 0.18, y: yy, w: 1.05, h: 0.26, fontSize: 11, color: SLATE, valign: "middle" });
      s.addShape(pres.shapes.RECTANGLE, { x: R.x + 1.25, y: yy + 0.07, w: Math.max(0.03, 1.2 * v), h: 0.13, fill: { color: col }, line: { type: "none" } });
      k.T(txt, { x: R.x + 1.3 + 1.2 * v, y: yy, w: 0.95, h: 0.26, fontSize: 11, bold: true, color: NAVY, valign: "middle" });
    });
    k.limitCard(R.x, 5.25, R.w, 0.95, "Same-colour boxes: 6 of 12. Needs the gaze ray in the robot's frame (T8.8)");
    k.caption("Replayed recordings, arm not moved. Below 0.56, or a tie, the arm waits.", L, 6.28, W);
    k.tracker(5);
    s.addNotes("This is the central perception problem. We have the glasses crop from the intent slide, and the wrist camera sees several objects. Which one is it?\n\nThe obvious approach is keypoint matching: find distinctive points in both images and pair them. We measured that first. It ranked the box first in none of 15 pairs. The viewpoints differ too much. So we compared whole-object features, and CLIP ranked the right box first in all 25.\n\nThis week we put it where it matters, inside the grasp client. The arm now goes for the box you looked at, not the box SAM 3 is most confident about. On a scene with two cardboard boxes, the old pick took the wrong box in every one of 114 frames. With the glasses crop, 266 of 268 targets were the right box. With three boxes, 334 of 334. If nothing matches well enough, the arm waits.\n\nThe two misses are instructive. They came at 1.5 metres, where gaze landed on the mat. The crop was wrong before the matcher ever saw it. So the next step is to refuse weak gaze picks at the glasses (T2.24).\n\nThe real limit is identical objects: two boxes of the same colour, 6 of 12. Appearance cannot separate them. That needs the gaze ray in the robot's frame, the glasses calibration from the camera-frames slide.\n\nAll of this is on replayed recordings. The real arm run comes next.\n\nTransition: \"Once the target mask is chosen, the arm has to pick it up.\"");
  }

  // ---- 13: grasp on the real arm ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("DION", "PHASE 5  ·  GRASP", "The real arm grasps on a spoken command", "First real grasp on 13 Oct 2026, with a tested software stop");
    const lw = R.x - 0.25 - L, gap = 0.3, sw = (lw - 3 * gap) / 4;
    [["Idle", "at home"], ["Approach", "wrist camera steps 2 cm to 0.21 m"], ["Grasp", "choose and execute"], ["Hold", "until “release”"]].forEach(([t, d], i) => {
      const x = L + i * (sw + gap);
      k.RR({ x, y: 2.05, w: sw, h: 0.8, fill: { color: i === 2 ? NAVY : TINT } });
      k.T(t, { x: x + 0.15, y: 2.1, w: sw - 0.25, h: 0.32, fontSize: 14, bold: true, color: i === 2 ? WHITE : NAVY });
      k.T(d, { x: x + 0.15, y: 2.42, w: sw - 0.25, h: 0.4, fontSize: 11, color: i === 2 ? PALE : SLATE, valign: "top" });
      if (i < 3) k.T("›", { x: x + sw, y: 2.15, w: gap, h: 0.5, fontSize: 22, bold: true, color: MUTED, align: "center", valign: "middle" });
    });
    const vw = 4.0, vy = 3.05, vh = 3.4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: L, y: vy, w: vw, h: vh, rectRadius: 0.1, fill: { color: "F8FAFC" }, line: { color: GREY, width: 1, dashType: "dash" } });
    await k.circleIcon(L + vw / 2 - 0.35, vy + 0.9, 0.7, "MdVideocam", GREY);
    k.T("Video of the first real grasp", { x: L, y: vy + 1.75, w: vw, h: 0.35, fontSize: 15, bold: true, color: NAVY, align: "center" });
    k.T("Dion: drop in grasp_real_arm.mp4 (15 s or less)", { x: L, y: vy + 2.1, w: vw, h: 0.3, fontSize: 11, color: MUTED, align: "center" });
    const cx = L + vw + 0.25, cw = lw - vw - 0.25;
    k.T("Grasps by distance", { x: cx, y: vy, w: cw, h: 0.3, fontSize: 14, bold: true, color: NAVY });
    s.addChart(pres.charts.BAR, [
      { name: "Grasped", labels: ["44.5 cm: 4/4", "49.5 cm: 1/2", "54.5 cm: 0/2"], values: [4, 1, 0] },
      { name: "Failed", labels: ["44.5 cm: 4/4", "49.5 cm: 1/2", "54.5 cm: 0/2"], values: [0, 1, 2] }], {
      x: cx - 0.1, y: vy + 0.35, w: cw + 0.1, h: 2.7, barDir: "col", barGrouping: "stacked", barGapWidthPct: 50,
      chartColors: [BLUE, GREY], showValue: false,
      catAxisLabelColor: SLATE, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catAxisLineShow: false,
      valAxisHidden: true, valAxisMaxVal: 4, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt", legendColor: SLATE,
    });
    k.T("54.5 cm is out of reach", { x: cx, y: vy + 3.12, w: cw, h: 0.25, fontSize: 11, color: MUTED });
    k.hero({ label: "WITHIN REACH", big: "5", unit: " of 6", sub: "grasps (5 of 8 overall), started by a recorded voice command" });
    await k.stat({ y: 4.1, h: 0.9, ic: "MdBlock", num: "< 1 ms", label: "software stop cancels motion" });
    k.limitCard(R.x, 5.15, R.w, 1.3, "Narrow band of positions. Two people and a hand on the power button");
    k.tracker(6);
    s.addNotes("Grasping is a state machine. A grasp request opens a short gate. The arm then steps the wrist camera towards the target mask, two centimetres at a time, re-checking at each step, until it is 21 centimetres away. This is a simple form of visual servoing: small corrections absorb calibration and depth errors. Then it grasps, lifts, returns home, and holds the object until the user says 'release'.\n\nOur first real grasp was on 13 October. Started from a recorded spoken command, the arm made 5 of 8 grasps. Both failures at 54.5 centimetres were out of reach, so within reach it was 5 of 6. In one run it grasped, held, refused two requests while busy, released, and grasped again.\n\nSafety came first. The arm's hardware stop is rejected by its controller, so we wrote a software stop. On the real arm it cancels motion within a millisecond. Every motion test still has two people and a hand on the power button.\n\nThese grasps used a simple path, one blind step and close. The learned grasp model is the harder part.\n\nTransition: \"The learned grasp model, AnyGrasp, is where the current blocker sits.\"");
  }

  // ---- 14: AnyGrasp ----
  {
    const s = slide("2 Results"), k = kit(s);
    k.header("DION", "PHASE 5  ·  GRASP", "AnyGrasp works at only one ideal spot", "Up close, the wrist camera sees only one face of the box");
    const iw = 3.85, ih = 3.05;
    s.addImage({ path: LOCAL_MEDIA + "image-14-1.png", x: L, y: 2.05, w: iw, h: ih, sizing: { type: "contain", w: iw, h: ih }, altText: "Fit check: an edge grasp on the 75 mm face measured as 56 mm passes wrongly" });
    s.addShape(pres.shapes.RECTANGLE, { x: L, y: 2.05, w: iw, h: ih, fill: { type: "none" }, line: { color: RULE, width: 0.75 } });
    const dx = L + iw + 0.25, dw = R.x - 0.25 - dx;
    k.RR({ x: dx, y: 2.05, w: dw, h: ih, fill: { color: TINT } });
    k.label("WHY IT FAILS UP CLOSE", dx + 0.2, 2.2, dw - 0.3, BLUE);
    const sc = 0.028, gx = dx + 1.2;
    for (const [i, [face, mm, ok]] of [["Side face", 75, false], ["Top", 60, true]].entries()) {
      const y = 2.65 + i * 0.85;
      k.T(face, { x: dx + 0.2, y, w: 0.95, h: 0.45, fontSize: 13, bold: true, color: NAVY, valign: "middle" });
      s.addShape(pres.shapes.RECTANGLE, { x: gx, y: y + 0.05, w: mm * sc, h: 0.35, fill: { color: ok ? BLUE : GREY }, line: { type: "none" } });
      k.T(`${mm} mm`, { x: gx, y: y + 0.05, w: mm * sc, h: 0.35, fontSize: 12, bold: true, color: ok ? WHITE : NAVY, align: "center", valign: "middle" });
      s.addShape(pres.shapes.RECTANGLE, { x: gx, y: y - 0.02, w: 71 * sc, h: 0.49, fill: { type: "none" }, line: { color: NAVY, width: 1.25, dashType: "dash" } });
      await k.circleIcon(gx + 75 * sc + 0.15, y + 0.05, 0.36, ok ? "MdCheck" : "MdClose", ok ? ST.tested.dot : "DC2626");
    }
    k.T("Dashed: gripper opens to 71 mm", { x: gx, y: 4.15, w: dw - 1.3, h: 0.25, fontSize: 11, color: MUTED });
    k.T("Top grasp: proposed in 49 of 75 frames, but scores ≤ 0.25, under the 0.3 floor", { x: dx + 0.2, y: 4.45, w: dw - 0.35, h: 0.6, fontSize: 12, color: NAVY, valign: "top" });
    k.hero({ label: "AT THE IDEAL SPOT", big: "2", unit: " of 3", sub: "grasps at 44.5 cm, centred and square" });
    await k.stat({ y: 4.1, h: 1.0, ic: "MdBlock", num: "0 of 4", label: "live, with the OK-Robot recipe" });
    k.caption("Fit check reads the 75 mm face as 56 mm, so it passes (369 of 369 on replay)", L, 5.13, 8.4);
    const oy = 5.45, oh = 1.0;
    k.T("NEXT, CHEAPEST FIRST", { x: L, y: oy, w: 1.6, h: oh, fontSize: 11, bold: true, color: MUTED, charSpacing: 1.5, valign: "middle" });
    const ow = (W - 1.7 - 0.4) / 3;
    [["A", "Grasp from 0.4 to 0.5 m, whole box in view"], ["B", "Fused views: built, retest owed"], ["C", "New SDK: licence pending"]].forEach(([n, t], i) => {
      const x = L + 1.7 + i * (ow + 0.2);
      k.RR({ x, y: oy, w: ow, h: oh, fill: { color: i === 0 ? NAVY : TINT } });
      k.num(x + 0.15, oy + 0.19, 0.38, n, i === 0 ? WHITE : BLUE, i === 0 ? NAVY : WHITE, 13);
      k.T(t, { x: x + 0.65, y: oy, w: ow - 0.75, h: oh, fontSize: 13, color: i === 0 ? WHITE : NAVY, valign: "middle" });
    });
    k.tracker(6);
    s.addNotes("AnyGrasp is a learned model that looks at a point cloud and proposes grasps: where to put the gripper and at what angle. At the ideal spot it worked twice in three tries. Anywhere else it failed.\n\nWe traced why. The arm runs AnyGrasp when the camera is 21 centimetres from the box, and from there it sees mostly one face. AnyGrasp's most confident grasps go across the 75-millimetre face, but our gripper opens to 71. Our own fit check should catch that, but it measures width from the points it can see, so a grasp on an edge looks narrow enough and passes. On replay every one of 369 grasps passed it. The grasp we want, from the top across 60 millimetres, is proposed in most frames, but scores 0.25, under our floor.\n\nSo the problem is not the model. It is where we ask it. The cheapest fix is to run AnyGrasp once from further back, 40 to 50 centimetres, with the whole box in view, then make one planned move. The second is to fuse several views into one cloud, which is built and needs a retest. This decides when M1 closes.\n\nHandover: \"Sherman will now step back from the parts and show what is connected today.\"");
  }

  // ================= PART 3 =================
  pres.addSection({ title: "3 Where we stand" });
  divider("3 Where we stand", 3, "Where we stand", "Joins, schedule, budget and next steps",
    [["Sherman", "the full flow and the schedule"], ["Zongzhe", "budget, risks and next steps"]],
    { path: SHERMAN + "nav_lidar_on_camera_overlay_stationary02_t0s_2026-10-19.png", iw: 640, ih: 480, tx: 352, ty: 247, chip: "BASE CAMERA + LIDAR  ·  NOT YET CALIBRATED", caption: "Two sensors, one scene: the parts work, the joins come next." });

  // ---- 15: full flow ----
  {
    const s = slide("3 Where we stand"), k = kit(s);
    k.header("SHERMAN", "THE FULL FLOW", "Every phase has a working part. Two links are still to join", "No end-to-end run yet, as planned: the first full run is M4, January 2027");
    const cw = W / 5, bw = 2.1, bh = 0.6, cx = (i) => L + (i + 0.5) * cw;
    const rowY = [2.55, 3.65, 4.75, 5.75];
    ["1 Intent", "2 Explore, find the user", "3 Search", "4 Approach, confirm", "5 Grasp"].forEach((h, i) => {
      k.RR({ x: cx(i) - bw / 2, y: 2.05, w: bw, h: 0.34, rectRadius: 0.17, fill: { color: NAVY } });
      k.T(h, { x: cx(i) - bw / 2, y: 2.05, w: bw, h: 0.34, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle" });
    });
    // parts: [col, row, label, status]
    const P = {
      A: [0, 0, "Voice and gaze to a crop", "tested on replay", ST.tested],
      H: [3, 0, "Wrist camera confirms", "600 / 602 on replay", ST.tested],
      I: [4, 0, "Grasp on the real arm", "tested on the real arm", ST.tested],
      D: [1, 1, "Memory graph", "works alone, offline", ST.alone],
      F: [2, 1, "Gaze match on graph", "planned (T8.2)", ST.planned],
      G: [3, 1, "Drive and hand over", "planned (T7.1)", ST.planned],
      C: [1, 2, "Nav2 drives the base", "built, never driven (T3.6)", ST.built],
      E: [2, 2, "Find the user", "planned (T7.6)", ST.planned],
      B: [1, 3, "FAST-LIVO2 map and pose", "tested, pushed by hand", ST.tested],
    };
    const box = (id) => { const [c, r] = P[id]; return { l: cx(c) - bw / 2, r: cx(c) + bw / 2, t: rowY[r], b: rowY[r] + bh, cx: cx(c), cy: rowY[r] + bh / 2 }; };
    // links first, so boxes sit on top of line ends
    const ok = { color: ST.tested.dot, width: 2.25 }, todo = { color: EMBER, width: 2, dashType: "dash" };
    const arrow = (x1, y1, x2, y2, st) => k.line(x1, y1, x2, y2, { ...st, endArrowType: "triangle" });
    const lab = (t, x, y, w, col, align = "center") => k.T(t, { x, y, w, h: 0.22, fontSize: 11, bold: true, color: col, align });
    let A = box("A"), H = box("H"), I = box("I"), D = box("D"), F = box("F"), G = box("G"), C = box("C"), E = box("E"), B = box("B");
    arrow(A.r, A.cy, H.l, H.cy, ok); lab("gaze reference crop (replay)", A.r, A.cy - 0.27, H.l - A.r, ST.tested.text);
    arrow(H.r, H.cy, I.l, I.cy, ok);
    arrow(B.cx, B.t, C.cx, C.b, ok); lab("pose, checked live", B.cx + 0.08, C.b + 0.08, 1.6, ST.tested.text, "left");
    const lane = L + cw - 0.06;
    k.line(B.l, B.cy, lane, B.cy, ok); k.line(lane, B.cy, lane, D.cy, ok); arrow(lane, D.cy, D.l, D.cy, ok);
    lab("recorded drive, offline", L, 5.85, lane - L - 0.1, ST.tested.text, "right");
    arrow(C.cx, C.t, D.cx, D.b, todo); lab("graph grows live (T7.5)", C.cx + 0.1, D.b + 0.13, 2.2, EMBER, "left");
    arrow(C.r, C.cy, E.l, E.cy, todo);
    arrow(A.r - 0.2, A.b, F.cx - 0.3, F.t, todo); lab("gaze target", L + 0.3, A.b + 0.08, 1.7, EMBER, "right");
    arrow(D.r, D.cy, F.l, F.cy, todo);
    arrow(F.r, F.cy, G.l, G.cy, todo);
    arrow(G.cx, G.t, H.cx, H.b, todo); lab("arrive, hand over (T3.7)", G.cx + 0.1, H.b + 0.13, 2.2, EMBER, "left");
    Object.entries(P).forEach(([id, [c, r, label, stat, st]]) => {
      const x = cx(c) - bw / 2, y = rowY[r];
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: bh, rectRadius: 0.08, fill: { color: st.dash ? WHITE : st.fill },
        line: st.dash ? { color: "9CA3AF", width: 1, dashType: "dash" } : { type: "none" } });
      k.T(label, { x: x + 0.12, y: y + 0.04, w: bw - 0.2, h: 0.3, fontSize: 12, bold: true, color: NAVY, valign: "middle" });
      k.T(stat, { x: x + 0.12, y: y + 0.31, w: bw - 0.2, h: 0.24, fontSize: 11, color: st.text, valign: "middle" });
    });
    // what comes next on this path
    const nx = cx(3) - bw / 2, nw = cx(4) + bw / 2 - nx;
    k.RR({ x: nx, y: rowY[2], w: nw, h: rowY[3] + bh - rowY[2], fill: { color: NAVY } });
    k.label("NEXT ON THIS PATH", nx + 0.25, rowY[2] + 0.17, nw - 0.4, SKY);
    [["Nav2 drives the base", "starts after this presentation (T3.6)"], ["First full run, speak to grasp", "M4, January 2027"]].forEach(([t, d], i) => {
      const y = rowY[2] + 0.48 + i * 0.55;
      k.num(nx + 0.25, y + 0.05, 0.36, i + 1, SIGNAL, NAVY, 13);
      k.T(t, { x: nx + 0.75, y: y - 0.02, w: nw - 0.95, h: 0.28, fontSize: 14, bold: true, color: WHITE });
      k.T(d, { x: nx + 0.75, y: y + 0.25, w: nw - 0.95, h: 0.24, fontSize: 12, color: PALE });
    });
    // legend
    const gy = 6.55;
    k.line(L, gy + 0.11, L + 0.5, gy + 0.11, ok); k.T("works today", { x: L + 0.6, y: gy, w: 1.3, h: 0.22, fontSize: 11, color: SLATE });
    k.line(L + 1.9, gy + 0.11, L + 2.4, gy + 0.11, todo); k.T("still to join", { x: L + 2.5, y: gy, w: 1.3, h: 0.22, fontSize: 11, color: SLATE });
    ["tested", "built", "alone", "planned"].forEach((key, i) => k.chip(L + 4.0 + i * 1.85, gy - 0.02, 1.7, ST[key].name, ST[key]));
    k.tracker(7);
    s.addNotes("Here is the full flow from the five-phase slide again, with each part we have just shown placed where it sits.\n\nBuilt and connected today: a recorded voice command starts a real grasp on the real arm, and since this week the glasses crop also chooses which object the arm goes for, on replayed recordings. My map feeds the navigation frame tree, and the memory graph is built from my recorded drive.\n\nTwo links are still to join. The robot has to explore with a live memory graph, match what it sees against the gaze target, and turn a match into a navigation goal. Nav2 has to drive the base, which I start right after this presentation.\n\nSo there is no end-to-end run yet. That matches the plan: the first closed-loop run is milestone M4, in January. Here is how we stand against that schedule.\n\n(Phases 2 and 3 form a loop: Nav2 explores, the graph grows, a gaze match becomes the next goal; a wrist-camera reject sends the robot back to exploring. Topic-level wiring is in appendix A1.)");
  }

  // ---- 16: schedule ----
  {
    const s = slide("3 Where we stand"), k = kit(s);
    k.header("SHERMAN", "SCHEDULE", "Ahead on memory and gaze, behind on driving", "Final dates unchanged. Forecasts re-estimated on 24 Oct, weeks counted from 14 Sep 2026");
    const lx = L, lw = 2.75, gx = L + lw + 0.1, gw = W - lw - 0.1, wk = gw / 31, top = 2.4, rh = 0.29;
    const day0 = Date.UTC(2026, 8, 14), wx = (w) => gx + (w - 1) * wk, dx = (d) => gx + (d - day0) / (7 * 864e5) * wk;
    const rows = [["M0 Build and run", [1, 2], null], ["M1 Arm picks something up", [2, 6], [7, 8]], ["M2 Voice and gaze to arm", [4, 6], [7, 17]],
      ["M3 Base navigates", [1, 6], [7, 17]], ["M4 Closed loop", null, [18, 20]], ["M5 Calibrated base camera", [1, 6], [7, 19]],
      ["M6 Memory graph offline", [2, 6], [7, 20]], ["M7 Graph drives the robot", null, [19, 24]], ["M8 Gaze picks the instance", [6, 6], [7, 26]],
      ["M9 Exploration order (optional)", null, [19, 23], true], ["M10 Demo and paper", null, [25, 27]]];
    const bottom = top + rows.length * rh;
    // non-working weeks: recess, exams, winter break (solid), half-speed buffer (lighter)
    [[3, 3, "E5E7EB"], [9, 14, "E5E7EB"], [15, 16, "F1F5F9"]].forEach(([a, b, col]) =>
      s.addShape(pres.shapes.RECTANGLE, { x: wx(a), y: top - 0.05, w: (b - a + 1) * wk, h: bottom - top + 0.05, fill: { color: col }, line: { type: "none" } }));
    ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"].forEach((m, i) => {
      const d = Date.UTC(2026, 9 + i, 1);
      k.line(dx(d), 2.05, dx(d), bottom, { color: RULE, width: 0.5 });
      k.T(m, { x: dx(d) + 0.04, y: 2.05, w: 0.6, h: 0.25, fontSize: 11, bold: true, color: SLATE });
    });
    k.T("Sep", { x: gx + 0.04, y: 2.05, w: 0.6, h: 0.25, fontSize: 11, bold: true, color: SLATE });
    rows.forEach(([lab, act, fc, opt], i) => {
      const y = top + i * rh;
      k.T(lab, { x: lx, y, w: lw, h: rh, fontSize: 12, color: NAVY, valign: "middle" });
      if (fc) s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: wx(fc[0]), y: y + 0.06, w: (fc[1] - fc[0] + 1) * wk, h: rh - 0.12, rectRadius: 0.05,
        fill: { color: opt ? WHITE : "93C5FD" }, line: opt ? { color: MUTED, width: 0.75, dashType: "dash" } : { type: "none" } });
      if (act) s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: wx(act[0]), y: y + 0.06, w: (act[1] - act[0] + 1) * wk, h: rh - 0.12, rectRadius: 0.05, fill: { color: NAVY }, line: { type: "none" } });
    });
    const today = dx(Date.UTC(2026, 9, 24));
    k.line(today, 2.3, today, bottom + 0.05, { color: EMBER, width: 2 });
    k.T("today", { x: today - 0.5, y: bottom + 0.05, w: 1.0, h: 0.22, fontSize: 11, bold: true, color: EMBER, align: "center" });
    [[28, "report"], [30.5, "oral"]].forEach(([w, t]) => {
      const x = wx(w) + wk / 2;
      s.addShape(pres.shapes.DIAMOND, { x: x - 0.09, y: bottom + 0.08, w: 0.18, h: 0.18, fill: { color: NAVY }, line: { type: "none" } });
      k.T(t, { x: x - 0.5, y: bottom + 0.27, w: 1.0, h: 0.22, fontSize: 11, color: NAVY, align: "center" });
    });
    // legend
    const ly = bottom + 0.1;
    [["done", NAVY, null], ["forecast", "93C5FD", null], ["optional", WHITE, MUTED], ["no work", "E5E7EB", null]].forEach(([t, col, dash], i) => {
      const x = lx + i * 0.95;
      s.addShape(pres.shapes.RECTANGLE, { x, y: ly + 0.04, w: 0.22, h: 0.15, fill: { color: col }, line: dash ? { color: dash, width: 0.75, dashType: "dash" } : { type: "none" } });
      k.T(t, { x: x + 0.27, y: ly, w: 0.7, h: 0.22, fontSize: 11, color: SLATE });
    });
    const cy = 6.1, chh = 0.4, cwid = (W - 0.4) / 3;
    [["Started early", "M2 voice and gaze, M6 memory graph, M8 gaze instance", ST.tested],
     ["Behind 1 to 2 weeks", "M5 camera calibration, M3 drive-to-point", ST.built],
     ["Progress", "97 of 171 task rows done", { fill: HILITE, text: BLUE }]].forEach(([t, d, st], i) => {
      const x = L + i * (cwid + 0.2);
      k.RR({ x, y: cy, w: cwid, h: chh, rectRadius: 0.2, fill: { color: st.fill } });
      k.T([{ text: t + ":  ", options: { bold: true, color: st.text } }, { text: d, options: { color: NAVY } }], { x: x + 0.18, y: cy, w: cwid - 0.3, h: chh, fontSize: 12, valign: "middle" });
    });
    k.tracker(7);
    s.addNotes("This chart shows every milestone by week. Solid bars are work done so far, light bars are our forecast, and the grey bands are recess, exams and the winter break, when we are not working.\n\nOur September plan expected, at this point, only the build milestone finished and the arm and base under way. We have that. The build milestone closed in week two. The arm picks up a box on the simple path. My map and localisation are done.\n\nThree milestones started well ahead of their windows: voice and gaze to the arm, the memory graph, and the gaze-instance work. The memory graph should finish a week early.\n\nTwo things are behind, and both are mine: calibrating the base camera, because the rig is not built yet, and the test drives, because bring-up has taken twice my estimates. They slip one to two weeks into January. M8 and the final dates do not move.\n\nThe weeks after the break carry most of the integration: closed loop in January, the robot exploring in February, and the end-to-end trials in March.\n\n(Bars that cross exam and break weeks are calendar time, not working time. Key dates: interim 28 Oct, final report 28 Mar 2027 (week 28), oral weeks 30 and 31.)\n\nHandover: \"Zongzhe will cover what the plan costs and what could go wrong.\"");
  }

  // ---- 17: budget and risks ----
  {
    const s = slide("3 Where we stand"), k = kit(s);
    k.header("ZONGZHE", "BUDGET AND RISKS", "SGD 1,500 for compute, approved", "Risks are mostly schedule and shared hardware");
    const lw = 4.0;
    k.hero({ x: L, w: lw, h: 1.7, label: "APPROVED  ·  5 OCT 2026", big: "1,500", unit: " SGD", sub: "both items for compute" });
    k.RR({ x: L, y: 3.9, w: lw, h: 0.95, fill: { color: TINT } });
    const bx = L + 0.2, bwid = lw - 0.4;
    s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 4.05, w: bwid * 2 / 3, h: 0.3, fill: { color: BLUE }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x: bx + bwid * 2 / 3, y: 4.05, w: bwid / 3, h: 0.3, fill: { color: "93C5FD" }, line: { type: "none" } });
    k.T("1,000", { x: bx, y: 4.05, w: bwid * 2 / 3, h: 0.3, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle" });
    k.T("500", { x: bx + bwid * 2 / 3, y: 4.05, w: bwid / 3, h: 0.3, fontSize: 12, bold: true, color: NAVY, align: "center", valign: "middle" });
    k.T("Hardware GPU", { x: bx, y: 4.4, w: bwid * 2 / 3, h: 0.3, fontSize: 12, color: SLATE, align: "center" });
    k.T("API credits", { x: bx + bwid * 2 / 3, y: 4.4, w: bwid / 3, h: 0.3, fontSize: 12, color: SLATE, align: "center" });
    k.RR({ x: L, y: 5.0, w: lw, h: 1.45, fill: { color: TINT } });
    k.label("WHY: ONE SHARED 16 GB GPU", L + 0.2, 5.12, lw - 0.3, BLUE);
    s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 5.45, w: bwid, h: 0.32, fill: { color: WHITE }, line: { color: GREY, width: 0.75 } });
    s.addShape(pres.shapes.RECTANGLE, { x: bx, y: 5.45, w: bwid * 10.3 / 16, h: 0.32, fill: { color: BLUE }, line: { type: "none" } });
    k.T("10.3 GiB: batched SAM 3 alone", { x: bx + 0.1, y: 5.45, w: bwid * 10.3 / 16, h: 0.32, fontSize: 11, bold: true, color: WHITE, valign: "middle" });
    k.T("16 GB", { x: bx + bwid - 0.7, y: 5.45, w: 0.62, h: 0.32, fontSize: 11, color: SLATE, align: "right", valign: "middle" });
    k.T("Also AnyGrasp, CLIP, Whisper, 2 language models: 3 people + CI", { x: bx, y: 5.85, w: bwid, h: 0.5, fontSize: 12, color: NAVY, valign: "top" });
    const rx = L + lw + 0.3, rw = W - lw - 0.3;
    k.label("RISKS AND STATUS", rx, 2.05, 3);
    [["controlled", ST.tested.dot], ["ongoing", ST.built.dot]].forEach(([t, col], i) => {
      const x = rx + rw - 2.4 + i * 1.25;
      s.addShape(pres.shapes.OVAL, { x, y: 2.1, w: 0.16, h: 0.16, fill: { color: col }, line: { type: "none" } });
      k.T(t, { x: x + 0.22, y: 2.05, w: 1.0, h: 0.25, fontSize: 11, color: SLATE });
    });
    const risks = [
      ["Critical path runs through one person", "Cut list fixed in advance", ST.built.dot],
      ["AnyGrasp licence tied to a hardware ID", "New licence requested", ST.built.dot],
      ["Shared, throttled lab machine", "Throttling, 2 hangs, disk 89 % full", ST.built.dot],
      ["No hardware stop on arm or base", "Software stop, two people at every test", ST.tested.dot],
      ["Duplicate objects in the graph", "8 → 3, no false merges", ST.tested.dot]];
    risks.forEach(([r, st, col], i) => {
      const y = 2.4 + i * 0.73;
      k.RR({ x: rx, y, w: rw, h: 0.63, fill: { color: TINT } });
      s.addShape(pres.shapes.OVAL, { x: rx + 0.2, y: y + 0.22, w: 0.18, h: 0.18, fill: { color: col }, line: { type: "none" } });
      k.T(r, { x: rx + 0.55, y, w: 3.55, h: 0.63, fontSize: 13, bold: true, color: NAVY, valign: "middle" });
      k.T(st, { x: rx + 4.2, y, w: rw - 4.35, h: 0.63, fontSize: 12, color: SLATE, valign: "middle" });
    });
    k.caption("Cut order if late: M9 exploration order, without-gaze comparison, reasoning layer, graph pruning, two-stage trigger, fewer trials.", rx, 6.1, rw);
    k.tracker(7);
    s.addNotes("Our budget is small and approved: a thousand Singapore dollars for a GPU and five hundred for API credits for AI services, both for compute. The reason is concrete. Everything runs on one 16 gigabyte GPU in the lab, shared by the three of us and by the CI runner. Segmentation, grasping, CLIP, speech and two language models all need it, and the memory graph's segmentation alone peaks at over 10 gigabytes. We have never run them all at once.\n\nThe main risks are about schedule and shared hardware. The critical path runs almost entirely through one person, so we fixed a cut list in advance. The paper's smarter exploration order goes first. Exploration itself and the gaze match stay, because the system does not work without them. The grasp model's licence is tied to a machine ID, and a new one is requested. The lab machine is shared and has hung twice. And neither the arm nor the base has a working hardware stop, so every motion test has two people and a hand on the power button.\n\n[TEAM INPUT: whether the GPU has been bought yet and any spend to date, in case an examiner asks.]\n\nTransition: \"To close, what happens next and what we want you to remember.\"");
  }

  // ---- 18: next steps ----
  {
    const s = slide("3 Where we stand"), k = kit(s);
    k.header("ZONGZHE", "NEXT STEPS", "Next: close the grasp, drive the base, query the graph", "Then explore with gaze, to end-to-end trials in March 2027");
    const lw = R.x - 0.25 - L;
    k.RR({ x: L, y: 2.05, w: lw, h: 2.45, fill: { color: TINT } });
    k.label("WEEKS 7 TO 8  ·  BEFORE EXAMS", L + 0.2, 2.2, lw - 0.3, BLUE);
    [["Refuse weak gaze picks, gaze grasp on the real arm", "T2.24, T8.9"],
     ["New SDK, 12-trial validation: M1 by 8 Nov", "T1.45, T1.35"],
     ["Nav2: first drives to a point", "T3.6"],
     ["Graph query on the recorded drive", "T6.8"]].forEach(([t, id], i) => {
      const y = 2.55 + i * 0.45;
      k.num(L + 0.2, y + 0.06, 0.3, i + 1, BLUE, WHITE, 11);
      k.T([{ text: t + "  ", options: { color: NAVY } }, { text: id, options: { color: MUTED, fontSize: 11 } }], { x: L + 0.62, y, w: lw - 0.8, h: 0.42, fontSize: 13, valign: "middle" });
    });
    k.label("AFTER THE BREAK", L, 4.7, 3);
    const steps = [["Jan", "M2 two-box gaze grasp, M5 calibration, M4 closed loop"], ["Feb", "M7 the robot explores and finds the user"], ["Mar", "M8 a gaze match ends exploration: end-to-end trials"]];
    const sw = (lw - 0.4) / 3;
    k.line(L + 0.2, 5.42, L + lw - 0.2, 5.42, { color: GREY, width: 2 });
    steps.forEach(([m, t], i) => {
      const x = L + i * (sw + 0.2), last = i === 2;
      s.addShape(pres.shapes.OVAL, { x: x + 0.12, y: 5.3, w: 0.24, h: 0.24, fill: { color: last ? SIGNAL : NAVY }, line: { color: WHITE, width: 2 } });
      k.T(m, { x: x + 0.12, y: 4.97, w: 1, h: 0.3, fontSize: 15, bold: true, color: NAVY, valign: "middle" });
      k.T(t, { x: x + 0.12, y: 5.65, w: sw - 0.15, h: 0.75, fontSize: 12, color: last ? NAVY : SLATE, bold: last, valign: "top" });
    });
    k.RR({ x: R.x, y: 2.05, w: R.w, h: 4.4, fill: { color: NAVY } });
    k.label("THREE TAKEAWAYS", R.x + 0.25, 2.25, R.w - 0.4, SKY);
    ["Identity across viewpoints is the hard part",
     "Every subsystem is measured on real hardware or data",
     "The links are scheduled, with a cut list ready"].forEach((t, i) => {
      const y = 2.7 + i * 1.22;
      s.addShape(pres.shapes.OVAL, { x: R.x + 0.25, y, w: 0.4, h: 0.4, fill: { type: "none" }, line: { color: SKY, width: 1.5 } });
      k.T(String(i + 1), { x: R.x + 0.25, y, w: 0.4, h: 0.4, fontSize: 14, bold: true, color: SKY, align: "center", valign: "middle" });
      k.T(t, { x: R.x + 0.8, y: y - 0.04, w: R.w - 1.0, h: 1.05, fontSize: 16, bold: true, color: WHITE, valign: "top" });
    });
    k.tracker(7);
    s.addNotes("In the next two weeks, before exams, we close four specific gaps. The glasses learn to refuse a weak gaze pick, and the gaze-matched grasp runs on the real arm. The new AnyGrasp version and the fused views are tested, then a twelve-trial validation closes the grasp milestone. Sherman starts driving the base with Nav2. And I run the full memory graph query on the recorded drive, checked against the answer key.\n\nAfter the break, the pieces join: the two-box gaze test on the real arm, the camera calibrations, the first closed-loop run in January, and the robot exploring on its own in February, with a gaze match telling it when to stop. In March we run the end-to-end trials.\n\nThree things to take away. The hard part of this problem is keeping the object's identity across very different viewpoints. Every subsystem now has measured results on real hardware or real data. And the remaining links are scheduled, with a cut list fixed in advance. Thank you. We are happy to take questions.");
  }

  // ================= Q&A =================
  {
    page += 1;
    const s = pres.addSlide({ sectionTitle: "3 Where we stand" });
    s.background = { color: NAVY };
    const k = kit(s);
    viewfinder(s, k, { path: SHERMAN + "nav_fastlivo_map_top_clean_handdriven1_2026-10-24.png", iw: 1920, ih: 1080, tx: 891, ty: 540, chip: "MOBILE BASE  ·  TOP VIEW OF THE LAB", caption: "Backup slides A1 to A10 follow." });
    k.T("THANK YOU", { x: L, y: 1.15, w: 5, h: 0.3, fontSize: 12, bold: true, color: SIGNAL, charSpacing: 2 });
    k.T("Questions", { x: L, y: 1.5, w: 5.9, h: 1.1, fontSize: 60, bold: true, color: WHITE });
    k.T("Look at it, name it, and the robot fetches that one.", { x: L, y: 2.75, w: 5.9, h: 0.4, fontSize: 18, italic: true, color: SIGNAL });
    k.T("Dion  ·  Sherman  ·  Zongzhe", { x: L, y: 3.6, w: 5.9, h: 0.4, fontSize: 18, bold: true, color: WHITE });
    k.T("Backup: wiring, frames, matching, grasp options, map accuracy, limitations, plan, evaluation.", { x: L, y: 4.1, w: 5.6, h: 0.7, fontSize: 13, color: PALE, valign: "top" });
    partBar(k, 3);
    s.addNotes("Questions. Backup slides A1 to A10 follow for detailed answers.");
  }

  // ================= APPENDIX =================
  pres.addSection({ title: "Appendix" });
  {
    page += 1;
    const s = pres.addSlide({ sectionTitle: "Appendix" });
    s.background = { color: NAVY };
    const k = kit(s);
    k.T("BACKUP  ·  NOT IN THE 20 MINUTES", { x: L, y: 1.2, w: 8, h: 0.3, fontSize: 12, bold: true, color: SKY, charSpacing: 2 });
    k.T("Appendix", { x: L, y: 1.55, w: 8, h: 0.95, fontSize: 44, bold: true, color: WHITE });
    const items = ["Topic-level wiring today", "Coordinate frames", "Matching rule and thresholds", "Grasp filters and the five options", "FAST-LIVO2 port defects and mid-route accuracy",
      "Limitations, risks and observed failures", "September plan vs now", "Why gaze, not just a class name", "End-to-end evaluation plan", "Milestone tests"];
    items.forEach((t, i) => {
      const x = L + Math.floor(i / 5) * 6.1, y = 2.9 + (i % 5) * 0.62;
      k.T([{ text: `A${i + 1}   `, options: { bold: true, color: SKY } }, { text: t, options: { color: WHITE } }], { x, y, w: 5.9, h: 0.45, fontSize: 16, valign: "middle" });
    });
    s.addNotes("Appendix divider. Backup slides for questions only.");
  }

  // A1
  {
    const { s } = appendix("A1", "Topic-level wiring today", "Answers: “What exactly is connected?” Only links that exist in code. Grey rows exist but have not run", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §3.3");
    const g = (t) => ({ text: t, color: MUTED });
    table(s, [["From", "To", "Channel", "State"],
      ["Voice: Silero VAD, faster-whisper, Qwen2.5-0.5B", "aria_segmentation_client", "/aria/audio/prompt (String)", "Ran (replay)"],
      ["Eye model", "aria_segmentation_client", "/aria/eye_tracking/gaze_estimate", "Ran (recording)"],
      ["aria and grasp segmentation clients", "SAM 3 service (one copy on GPU)", "/segmentation/segment", "Ran"],
      ["aria_segmentation_client", "grasp_segmentation_client", "/grasp/target: word, then word plus reference crop", "Ran on replay (T8.9a)"],
      ["aria_segmentation_client", "grasp_state_machine", "/manipulator/grasp_request", "Ran"],
      ["grasp_segmentation_client", "grasp_state_machine", "/object_centroid_2d (pixel plus depth)", "Ran"],
      ["anygrasp_detection_node", "grasp_state_machine", "/grasp_candidates", "Ran"],
      ["grasp_state_machine", "MoveIt and rm_driver", "real arm", "Ran on the real arm"],
      ["Livox MID-360, base D455", "FAST-LIVO2, then fastlivo_odom_bridge", "odom to robot_base_link", "Ran live"],
      ["fastlivo_odom_bridge", "SLAM Toolbox, mapping mode", "map to odom, /map", "Ran live"],
      [g("SLAM Toolbox"), g("Nav2"), g("frame tree"), g("Never run on this")],
      [g("object_recognition_pipeline"), g("object_approach_node"), g("/manipulation/goal_pose (call commented out)"), g("Not run")],
      [g("object_approach_node"), g("Nav2"), g("/goal_pose"), g("Not run")],
      ["Recorded drive handdriven1", "Memory graph S0 to S13, then TargetFinder", "offline", "Graph built. Query not run"]],
      { y: 1.95, colW: [3.3, 3.2, 3.75, 1.88], fontSize: 11, rowH: 0.3 });
  }
  // A2
  {
    const { s, k } = appendix("A2", "Coordinate frames", "Answers: “How do grasp poses reach the arm?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §6.7, §5.4");
    const chain = ["map", "odom", "robot_base_link", "base_link", "Link1 to Link6", "camera_link", "camera_color_optical_frame"];
    let x = L;
    chain.forEach((t, i) => {
      const w = t.length * 0.085 + 0.4, on = t === "base_link";
      k.RR({ x, y: 1.95, w, h: 0.38, rectRadius: 0.19, fill: { color: on ? BLUE : NAVY } });
      k.T(t, { x, y: 1.95, w, h: 0.38, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle" });
      x += w;
      if (i < chain.length - 1) { k.T("›", { x, y: 1.92, w: 0.3, h: 0.42, fontSize: 18, bold: true, color: MUTED, align: "center", valign: "middle" }); x += 0.3; }
    });
    k.T("plus livox_frame under robot_base_link", { x: L, y: 2.42, w: 6, h: 0.25, fontSize: 11, color: MUTED });
    table(s, [["Parent to child", "Published by", "Value or note"],
      ["map to odom", "SLAM Toolbox", "Nav2 plans in this map frame"],
      ["odom to robot_base_link", "Wheel driver, or the FAST-LIVO2 bridge (odom_source:=fastlivo)", "Bridge: T_odom_base(t) = Tb x P0^-1 x P(t) x Tb^-1, Tb = (0.191, 0.02329, 0.15588) m. Refuses to start above 2° start tilt"],
      ["robot_base_link to base_link", "Static (arm mount)", "(0.18, 0, 0.48) m, yaw 180°. Measured, tf2_echo matched"],
      ["robot_base_link to livox_frame", "Static", "LiDAR mount"],
      ["base_link through Link1 to 6 to camera_link", "URDF", "Wrist camera to arm calibrated (Dion, 24 Oct)"],
      ["camera_link to camera_color_optical_frame", "RealSense driver", "AnyGrasp candidates arrive in this frame"]],
      { y: 2.8, colW: [3.2, 3.6, 5.33], fontSize: 12, rowH: 0.42 });
    k.T("Open question for P2 and T7.1: the memory graph stores positions in FAST-LIVO2's camera_init frame, while Nav2 drives in SLAM Toolbox's map frame. How graph positions reach map at run time is a design question, not a defect.",
      { x: L, y: 6.05, w: W, h: 0.55, fontSize: 12, color: SLATE, valign: "top" });
  }
  // A3
  {
    const { s, k } = appendix("A3", "Matching rule and thresholds", "Answers: “Why 0.56? Is CLIP cosine a probability?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §5.4, §6.4, §6.6");
    const hw = (W - 0.2) / 2;
    [["THE RULE", "Cosine between each wrist mask crop (box plus 20 px) and the reference crop. Cutoff 0.56, tuned on 20 pairs (T8.7). Masks within 0.01 of the best count as a tie, and a tie returns no match. Same model in both places: open_clip ViT-B-32 laion2b_s34b_b79k."],
     ["NOT A PROBABILITY", "CLIP cosine is not calibrated. Thresholds are empirical: 0.56 for the matcher, 0.6 on the graph's 1.5 x overlap + 0.5 x appearance score. float16 shifts a vector by up to 0.0039 across batch sizes. Crop padding differs between glasses, wrist and graph."]].forEach(([lab, t], i) => {
      const x = L + i * (hw + 0.2);
      k.RR({ x, y: 1.95, w: hw, h: 1.75, fill: { color: TINT } });
      k.label(lab, x + 0.2, 2.07, hw - 0.3, BLUE);
      k.T(t, { x: x + 0.2, y: 2.35, w: hw - 0.35, h: 1.3, fontSize: 13, color: NAVY, valign: "top" });
    });
    table(s, [["Where", "Method", "Confidence handling"],
      ["Glasses mask", "Gaze vote", "Winner needs half the votes, else word only"],
      ["Wrist mask (matcher)", "CLIP cosine", "Cutoff 0.56, wrist tie returns no match"],
      ["Wrist mask (grasp)", "CLIP cosine when a reference exists (T8.9a), else SAM 3 score", "Cutoff 0.56 and no tie, else nothing published"],
      ["Graph association", "3D overlap plus CLIP", "Score over 0.6, greedy"],
      ["Graph query", "CLIP text vs image", "Ranking only"]],
      { y: 3.9, colW: [2.7, 4.6, 4.83], fontSize: 12, rowH: 0.38 });
    k.T("No stage carries a confidence forward to the next (see A6).", { x: L, y: 6.35, w: W, h: 0.3, fontSize: 12, bold: true, color: EMBER });
  }
  // A4
  {
    const { s, k } = appendix("A4", "Grasp filters and the five options", "Answers: “Why not just lower the score floor?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §5.5. Options: DION_PROGRESS_REPORT_2026-10.md §7");
    const lw = 3.6;
    k.RR({ x: L, y: 1.95, w: lw, h: 4.7, fill: { color: TINT } });
    k.label("FILTERS ON EVERY CANDIDATE", L + 0.2, 2.07, lw - 0.3, BLUE);
    k.T(["On the SAM 3 mask", "Inside the approach cone", "Score at least 0.3", "Width under 68 mm", "Fingertips at most 45 mm past the near face", "Pose stable for 5 frames", "Of the 180° twins, the smaller wrist turn (T1.33)"]
      .map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
      { x: L + 0.2, y: 2.4, w: lw - 0.35, h: 4.1, fontSize: 13, color: NAVY, valign: "top", paraSpaceAfter: 6 });
    const tx = L + lw + 0.25, tw = W - lw - 0.25;
    table(s, [["Option", "Idea", "Cost"],
      [{ text: "A. Grasp from the view pose", bold: true }, "AnyGrasp once at 0.4 to 0.5 m with the whole box in view, one planned motion", "Small, the pieces exist"],
      ["B. Fused views (T1.47)", "Several views in one cloud, grasp on that", "Built, retest owed"],
      ["C. New AnyGrasp SDK (T1.45)", "Native mask and angle steering", "Waiting on licence"],
      ["D. Closed-loop tracking", "AnyGrasp's tracking mode updates the grasp while the arm moves", "Medium, old node parked"],
      ["E. Two-phase (shelved, T1.33)", "Stop just before the depth blind zone, set the angle, move straight in and close", "Small"]],
      { x: tx, y: 1.95, w: tw, colW: [2.55, 4.0, tw - 6.55], fontSize: 12, hi: [1], rowH: 0.5 });
    k.RR({ x: tx, y: 5.25, w: tw, h: 1.4, fill: { color: NAVY } });
    k.label("WHY THE FLOOR IS NOT THE FIX", tx + 0.2, 5.37, tw - 0.3, SKY);
    k.T("The top-down grasp scores at most 0.25, but the problem is the view. The 30° cone around the camera axis dropped every top-down grasp, because the camera axis is 44° from vertical. AnyGrasp was also used against its README: masked points only, 0.10 m width.",
      { x: tx + 0.2, y: 5.63, w: tw - 0.35, h: 0.95, fontSize: 12, color: WHITE, valign: "top" });
  }
  // A5
  {
    const { s, k } = appendix("A5", "FAST-LIVO2 port defects and mid-route accuracy", "Answers: “How do you know the map is right?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §8.4. SHERMAN_PROGRESS_REPORT_2026-10.md §9.3, §11.4, §11.5");
    table(s, [["Defect (found by reading the source, confirmed against a control run)", "Before", "After the fix"],
      ["Range gate cannot act (F2): blind_sqr never assigned, the port dropped upstream's line", "Median 19,968 points per scan, the full packet", "Median 9,607. Removed 52.06 % against 51.84 % audited zero-range points"],
      ["LiDAR to IMU offset has the wrong sign (F3)", "About 10.2 cm of geometric inconsistency in every replay before 19 Oct", "Configs carry (-0.011, -0.02329, 0.04412) m. handdriven1 recorded after the fix"],
      ["Voxel key mismatch: insertion and retrieval round negative coordinates differently", "Key hits 1,392,458 vs 1,878,707 shadow hits", "Hits match, 1,855,269. Retrieval points 112,980 to 128,385"]],
      { y: 1.95, colW: [4.6, 3.4, 4.13], fontSize: 11, rowH: 0.5 });
    const lw = 6.2;
    k.RR({ x: L, y: 4.25, w: lw, h: 2.4, fill: { color: TINT } });
    k.label("MID-ROUTE ACCURACY (T3.5F)", L + 0.2, 4.37, lw - 0.3, BLUE);
    k.T([{ text: "Within 6.7 cm (run 1) and 6.5 cm (run 2) for the whole route, against the handdriven1 map, 0.15 s lag removed. The reference carries about 7 cm of its own error.", options: { bullet: true, breakLine: true } },
      { text: "The mapper stamps its pose about 0.15 s late: surfaces smear about 4 cm at 0.28 m/s. Fix prepared, off by default.", options: { bullet: true, breakLine: true } },
      { text: "Floor marks did not close as ground truth. A tape-measured check is owed.", options: { bullet: true } }],
      { x: L + 0.2, y: 4.65, w: lw - 0.35, h: 1.95, fontSize: 12, color: NAVY, valign: "top", paraSpaceAfter: 4 });
    s.addImage({ path: SHERMAN + "nav_t35f_drift_step3_error_vs_time_2026-10-21.png", x: L + lw + 0.25, y: 4.25, w: W - lw - 0.25, h: 2.4, sizing: { type: "contain", w: W - lw - 0.25, h: 2.4 }, altText: "Mid-route position error against time for two runs" });
  }
  // A6 (three slides)
  {
    const { s } = appendix("A6", "Limitations (1 of 3): confirmed in the code", "Answers: “What fails today?” Most are links the plan schedules for later milestones", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §9.1");
    table(s, [["Limitation", "End-to-end implication"],
      ["A wrong gaze pick becomes a confident reference (at 1.5 m the reference was the mat)", "The arm would go for the wrong box. T2.24 refuses weak gaze picks"],
      ["/manipulation/goal_pose has no live publisher (inherited)", "Nothing can start navigation to an object yet. T7.1 will publish it"],
      ["No graph query service, no T7.1 node", "The graph cannot drive the robot"],
      ["No gaze-target trigger on graph objects", "The exploring robot cannot tell it has found the target. Glasses vs base-camera features untested"],
      ["Graph built offline from a hand-pushed recording", "No live graph. No depth camera data"],
      ["No calibration between any cameras", "Graph positions and the gaze ray carry unknown rotation error, about 6.7 px per degree"],
      ["Software-only stops on arm and base", "Every hardware test needs two people and the power button"],
      ["No automatic grasp success check", "Outcome judged by people. A retry loop cannot know when to retry"]],
      { y: 1.95, colW: [5.6, 6.53], fontSize: 12, rowH: 0.5 });
  }
  {
    const { s } = appendix("A6", "Limitations (2 of 3): risks when the parts join", "Answers: “What could break when the parts join?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §9.3");
    table(s, [["Risk", "What to watch"],
      ["No confidence crosses a stage boundary", "A wrong gaze pick gives a confident reference, a wrong graph hit a goal, a wrong wrist mask a grasp. The matcher caught one by luck of score (0.51 vs 0.56)"],
      ["Crop mismatch", "Fixed 20 px glasses crop against the graph's relative padding, when the gaze match (P3) lands"],
      ["Frame of graph positions", "camera_init against Nav2's map frame, to settle when P2 and T7.1 are built"],
      ["Standoff vs reach", "0.6 m camera standoff against the 35 to 46 cm tested grasp band"],
      ["GPU contention", "SAM 3 service, batched graph SAM 3 (up to 10.3 GiB), AnyGrasp, CLIP, Whisper, two Qwen models on one 16 GB card. Never run together"],
      ["0.15 s pose lag", "Anything pairing a scan with a pose by stamp, including graph depth"],
      ["Viewpoint change between graph and wrist", "Graph features from the base camera, reference from the glasses, confirmation from the wrist. Glasses to base camera untested"]],
      { y: 1.95, colW: [3.6, 8.53], fontSize: 12, rowH: 0.55 });
  }
  {
    const { s } = appendix("A6", "Limitations (3 of 3): observed failures", "Answers: “What has gone wrong on hardware or data?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §9.2. Lab visitors' faces appear in the coloured map: re-render before any external showing");
    table(s, [["Failure", "Where", "Source"],
      ["AnyGrasp's confident grasps go across the too-wide face. Fit check passes edge slices", "Wrist, 0.21 m", "T1.44"],
      ["Live OK-Robot trials 0 of 4: one pushed the box, two stuck, one found nothing in 3 s", "Real arm", "T1.44"],
      ["Wrist spun 180° and knocked the box off (fixed)", "First AnyGrasp grasp", "T1.33"],
      ["Wide wrist twist (j4 146°, j5 29°, j6 274°)", "AnyGrasp grasp B", "T1.40"],
      ["Look-alike boxes: 148 of 180, and 6 of 12", "Matcher", "T8.5, T8.8"],
      ["Gaze landed on the mat stack at 1.5 m", "Glasses", "T8.5"],
      ["Keypoint matching 0 of 15", "Cross camera", "T8.4"],
      ["Mapper teardown aborts 2 of 4. LiDAR driver SIGBUS", "Base", "S§10.3"],
      ["Ethernet flap caused 8.1 s and 15.1 s IMU time jumps", "Base, live", "T3.5d"],
      ["Lab box silent hangs (6 Oct, 20 Oct)", "Shared box", "S§15"],
      ["Glass walls: about 42 % of 5 cm map points are ghosts outside the glass box", "Map", "S§15"],
      ["Glass door and both computer towers missed in every graph setting", "Graph", "Z§3.5"]],
      { y: 1.95, colW: [7.6, 2.8, 1.73], fontSize: 11, rowH: 0.29 });
  }
  // A7
  {
    const { s } = appendix("A7", "September plan vs now", "Answers: “How does this compare with your original plan?”", "Source: 1cde0ec:docs/PROJECT_PLAN.md §5 and §6 headings. COMBINED_PROGRESS_REPORT_2026-10.md §0.2, §0.6");
    table(s, [["Milestone", "September plan window", "Now (actual to 24 Oct, forecast end)", "Change"],
      ["M0 Everyone can build and run", "14 to 27 Sep 2026", "Done 24 Sep", "On time"],
      ["M1 The arm picks something up", "5 Oct to 1 Nov 2026", "Started 21 Sep. Forecast 8 Nov", "About one week later (AnyGrasp)"],
      ["M2 Voice and gaze reach the arm", "26 Oct 2026 to 3 Jan 2027", "Started 8 Oct. Forecast 10 Jan", "Started early, ends about a week later"],
      ["M3 The base navigates", "12 Oct to 27 Dec 2026", "Started 14 Sep. Forecast 10 Jan", "Two weeks later"],
      ["M4 Closed loop", "28 Dec 2026 to 17 Jan 2027", "Forecast 11 to 31 Jan", "Two weeks later"],
      ["M5 Calibrated base camera", "5 Oct 2026 to 17 Jan 2027", "Started 16 Sep. Forecast 24 Jan", "One week later"],
      ["M6 Memory graph offline", "28 Dec 2026 to 7 Feb 2027", "Started 21 Sep. Forecast 31 Jan", "One week earlier"],
      ["M7 The graph drives the robot", "1 to 28 Feb 2027", "Forecast 18 Jan to 28 Feb", "Can start earlier, end unchanged"],
      ["M8 Gaze picks the instance", "8 Feb to 14 Mar 2027", "Started 19 Oct. Forecast 14 Mar", "Started early, end unchanged"],
      ["M9 Frontier scoring (optional)", "2 Nov 2026 to 21 Feb 2027", "Not started. 18 Jan to 21 Feb if kept", "First on the cut list"],
      ["M10 Demonstration and paper", "1 to 21 Mar 2027", "Forecast 1 to 21 Mar", "Unchanged"]],
      { y: 1.95, colW: [3.2, 2.85, 3.3, 2.78], fontSize: 12, rowH: 0.38 });
  }
  // A8
  {
    const { k } = appendix("A8", "Why gaze, not just a class name", "Answers: “Isn't identical-object picking niche?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §0.3 (D§5.5). CLIP values: §8.5");
    k.RR({ x: L, y: 1.95, w: W, h: 0.85, fill: { color: NAVY } });
    k.T([{ text: "Two identical objects are the hardest test case, not the pitch.  ", options: { bold: true, color: WHITE } }, { text: "The capability is knowing where the user is looking in the robot's own 3D space.", options: { color: PALE } }],
      { x: L + 0.25, y: 1.95, w: W - 0.5, h: 0.85, fontSize: 15, valign: "middle" });
    const rows = [["MdCompareArrows", "Similar objects", "Two chairs of the same model score 0.81 to 0.85 in CLIP, close to the same chair at 0.93"],
      ["MdVisibilityOff", "Partly hidden objects", "The robot may see only part of the object the user sees"],
      ["MdLayers", "Uncertain image features", "Appearance alone is not a reliable identity"],
      ["MdSmartToy", "A robot that does not see what the user sees", "The base camera is at knee height, the glasses at eye level"],
      ["MdTouchApp", "Assistive use", "A user who can look but cannot easily point or speak, among mugs, pill bottles and cans"]];
    for (const [i, [ic, t, d]] of rows.entries()) {
      const y = 3.0 + i * 0.73;
      k.RR({ x: L, y, w: W, h: 0.63, fill: { color: TINT } });
      await k.circleIcon(L + 0.15, y + 0.1, 0.43, ic);
      k.T(t, { x: L + 0.75, y, w: 4.2, h: 0.63, fontSize: 14, bold: true, color: NAVY, valign: "middle" });
      k.T(d, { x: L + 5.0, y, w: W - 5.15, h: 0.63, fontSize: 13, color: SLATE, valign: "middle" });
    }
  }
  // A9
  {
    const { s } = appendix("A9", "End-to-end evaluation plan", "Answers: “How will you measure the final system?” Today every measurement is per stage", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §11");
    table(s, [["Metric", "Definition", "Needs", "Milestone"],
      ["Glasses target accuracy", "Reference crop is the intended object, scenes with 2 to 4 objects at 1 to 3 m", "Live glasses", "M2"],
      ["Wrist confirmation accuracy", "Matcher picks the intended object, with and without look-alikes. Refusals counted apart", "P0 item 1", "M2"],
      ["False acceptance rate", "Wrong object accepted, per stage (glasses, graph, wrist)", "Labelled trials", "M2, M8"],
      ["Graph target retrieval", "First hit lands on the intended marked object, and distance to it", "T6.8", "M6"],
      ["Gaze-target trigger accuracy", "The robot stops exploring at the intended object. Wrong stops counted", "T8.2", "M8"],
      ["User discovery and search distance", "User found, and distance driven before the target is matched", "T7.5, T7.6", "M7"],
      ["Without gaze (stretch)", "Same trials, voice only", "T8.11", "M8"],
      ["Drive-to-point repeatability", "Ten drives, landing error, 10 cm circle", "T3.6, T5.8", "M3"],
      ["Handover success", "Base stops with the object inside the grasp band", "T3.7", "M4"],
      ["Grasp success", "12-trial grid, pass bar 9 of 12", "T1.35", "M1"],
      [{ text: "End-to-end success", bold: true }, { text: "Speak, look, drive, grasp. Counted only when the intended object is lifted", bold: true }, "All above", "M4, M10"],
      ["Per-stage timing", "99th percentile per stage", "T4.2", "M4"],
      ["Recovery", "Share of failures that end safely instead of a wrong grasp", "P1 items", "M4"]],
      { y: 1.95, colW: [3.1, 6.33, 1.6, 1.1], fontSize: 11, rowH: 0.33, hi: [11] });
  }
  // A10
  {
    const { s } = appendix("A10", "Milestone tests", "Answers: “How do you know a milestone is done?”", "Source: COMBINED_PROGRESS_REPORT_2026-10.md §0.2");
    table(s, [["", "Milestone", "Done means", "Lead"],
      ["M0", "Everyone can build and run", "Two people other than Dion clone, build and pass the bench", "Zongzhe"],
      ["M1", "Arm picks something up", "5 grasp attempts on a box, success rate recorded, stop verified first", "Dion"],
      ["M2", "Voice and gaze reach the arm", "Two boxes, the arm picks the one you looked at, 3 times in 4", "Dion"],
      ["M3", "Base navigates", "Map, localisation, ten drives to a point with error recorded", "Sherman"],
      ["M4", "Closed loop", "One recorded run: speak, look, drive, grasp, per-stage timing", "Dion"],
      ["M5", "Calibrated base camera", "LiDAR points land on the right objects in the camera image, pose error as a number", "Sherman mount, Dion calibration"],
      ["M6", "Memory graph offline", "Objects from a recorded drive, no duplicates, a sentence query returns the right one", "Zongzhe"],
      ["M7", "Graph drives the robot", "Object out of view: the robot explores, finds the user, builds the graph live, drives to it", "Dion"],
      ["M8", "Gaze picks the instance", "A gaze match ends exploration. N end-to-end trials, success per phase", "Dion"],
      ["M9", "Smarter exploration order (optional)", "The paper's exploration order beats our nearest-first exploration", "Zongzhe"],
      ["M10", "Demonstration and paper", "Recorded end-to-end run, paper whose central table is the end-to-end trials", "All"]],
      { y: 1.95, colW: [0.7, 3.0, 6.13, 2.3], fontSize: 12, rowH: 0.37 });
  }

  await pres.writeFile({ fileName: OUT });
  console.log("wrote", OUT, "slides:", page);
})();

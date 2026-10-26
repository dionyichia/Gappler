const pptxgen = require('pptxgenjs');
const { C, mk } = require('./lib');
const { slides, elapsed } = require('./spec');
const SK = '/root/.claude/skills/synced/6cdd37b7-5269-4c51-a14f-770104e29466_d0ec5a53-5510-46a5-8b3e-1559bbfaf8e6/pptx/scripts/';
const { applyTheme } = require(SK + 'apply_theme.js');

const THEME = {
  name: 'Gappler interim',
  headFontFace: 'Calibri', bodyFontFace: 'Calibri',
  colors: { dk1: C.INK, lt1: 'FFFFFF', dk2: C.NAVY, lt2: C.TINT, accent1: C.NAVY, accent2: '2E7D4F', accent3: 'B7791F', accent4: '2B6CB0', accent5: 'D9622B', accent6: '8A93A3', hlink: '2B6CB0', folHlink: '5B6577' },
};

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'High-Readiness Mobile Manipulation via Gaze-Speech Interaction and Continuous Pre-Alignment';
pres.subject = 'FYP interim assessment, 28 October 2026';
pres.author = 'Dion, Sherman, Zongzhe';
pres.theme = { headFontFace: 'Calibri', bodyFontFace: 'Calibri' };

pres.defineSlideMaster({
  title: 'CONTENT', background: { color: 'FFFFFF' },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.62, w: 12.33, h: 0.82, fontFace: 'Calibri', fontSize: 24, bold: true, color: C.INK, valign: 'top', align: 'left', margin: 0 }, text: '' } }],
  slideNumber: { x: 12.23, y: 7.05, w: 0.6, h: 0.28, fontFace: 'Calibri', fontSize: 11, color: C.MUTED, align: 'right' },
});
pres.defineSlideMaster({ title: 'TITLE', background: { color: 'FFFFFF' }, objects: [] });
pres.defineSlideMaster({
  title: 'APPENDIX', background: { color: 'FFFFFF' },
  objects: [{ placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.45, w: 12.33, h: 0.7, fontFace: 'Calibri', fontSize: 22, bold: true, color: C.INK, valign: 'top', align: 'left', margin: 0 }, text: '' } }],
  slideNumber: { x: 12.23, y: 7.05, w: 0.6, h: 0.28, fontFace: 'Calibri', fontSize: 11, color: C.MUTED, align: 'right' },
});

const H = mk(pres);
const _add = pres.addSlide.bind(pres), seen = new Set();
pres.addSlide = (o = {}) => { if (o.sectionTitle && !seen.has(o.sectionTitle)) { pres.addSection({ title: o.sectionTitle }); seen.add(o.sectionTitle); } return _add(o); };
const strip = t => t.replace(/`/g, '').trim();
const unwrap = t => t.replace(/([^\n])\n(?!\n)/g, '$1 ').replace(/[ \t]+/g, ' ').trim();

function notes(n) {
  const s = slides[n];
  const ph = strip(s.placeholders);
  let out = `PRESENTER: ${s.presenter}    SLOT: ${s.duration}    ELAPSED AT END OF SLIDE: ${elapsed[n]} of 20:00\n\n`;
  out += `SCRIPT (approved, from INTERIM_PRESENTATION_SLIDE_CONTENT_2026-10.md)\n${unwrap(s.script)}\n\n`;
  out += `TRANSITION\n${unwrap(strip(s.transition)).replace(/^"|"$/g, '')}\n`;
  if (ph && ph !== 'None.') out += `\nTEAM REVIEW BEFORE THE TALK (not shown on the slide)\n${unwrap(ph.replace(/\]\n\[/g, ']\n\n['))}\n`;
  return out;
}

require('./core_a')(pres, H, notes);
require('./core_b')(pres, H, notes);
if (!process.env.CORE_ONLY) require('./appendix')(pres, H);

const OUT = process.env.OUT || 'Gappler_Interim_2026-10-28.pptx';
pres.writeFile({ fileName: OUT }).then(async () => { await applyTheme(OUT, THEME); console.log('wrote', OUT); });

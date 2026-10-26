// Pull the approved scripts, timings, presenters, transitions and placeholders verbatim from the spec
const fs = require('fs');
const SRC = '/mnt/user-data/uploads/Gappler/docs/INTERIM_PRESENTATION_SLIDE_CONTENT_2026-10.md';
const md = fs.readFileSync(SRC, 'utf8');

function field(block, name) {
  const re = new RegExp('\\*\\*' + name + '\\.\\*\\*([\\s\\S]*?)(?=\\n\\*\\*[A-Z][^*]+\\.\\*\\*|\\n---|$)');
  const m = block.match(re);
  return m ? m[1].trim() : '';
}
const slides = {};
const parts = md.split(/\n## Slide (\d+): /).slice(1);
for (let i = 0; i < parts.length; i += 2) {
  const n = +parts[i];
  let block = parts[i + 1];
  block = block.split(/\n## [A-F]\. /)[0];
  const heading = block.split('\n')[0].trim();
  let script = field(block, 'Proposed speaker script').replace(/^"|"$/g, '').trim();
  slides[n] = {
    heading,
    script,
    duration: field(block, 'Estimated duration'),
    presenter: field(block, 'Presenter'),
    transition: field(block, 'Transition'),
    placeholders: field(block, 'Placeholders'),
  };
}
// elapsed times from section D
const elapsed = {};
const d = md.split('## D. Timing and team handover plan')[1].split('**Total')[0];
d.split('\n').forEach(l => {
  const m = l.match(/^\| (\d+) \| [^|]+\| [^|]+\| ([\d:]+) \| ([\d:]+) \|/);
  if (m) elapsed[+m[1]] = m[3];
});
module.exports = { slides, elapsed, md };
if (require.main === module) {
  for (const n of Object.keys(slides)) {
    const s = slides[n];
    console.log(n, '|', s.presenter, '|', s.duration, '|', elapsed[n], '| words', s.script.split(/\s+/).length, '|', s.script.slice(0, 60).replace(/\n/g, ' '));
  }
}

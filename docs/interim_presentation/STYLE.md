# Gappler deck style guide

The style of `Gappler_Interim_2026-10-28_v2.pptx`, for any agent or person adding or changing slides.
Follow it exactly so new slides look like the rest. When a choice is not covered here, copy the
nearest existing slide.

**Source of truth:** `build/deck.js` generates the whole deck. Change the deck by editing that
script and rebuilding (see "Build and check" at the end), never by hand in PowerPoint. A hand edit is
lost on the next rebuild. Slide content comes from
`docs/INTERIM_PRESENTATION_SLIDE_CONTENT_2026-10.md`. This file covers only how slides look.

**How the style was chosen (2026-10-25):** Sherman compared five previews. He chose the 2WO deck's
boxes and colours to split up the content, the Mary Barra deck's thin full-width tracker, and Apple
keynote restraint on words. He rejected these:
- Elon-style dark bars and rings: too close to the Elon deck.
- Half-page photos: they cut off the tracker.
- A box-free layout: too little separation between pieces of content.

---

## 1. Principles

1. **One message per slide.** The title states the claim and the subtitle gives one line of context.
2. **Visuals before words.** About 60–110 words on a core slide, counting the header and tracker.
   Detail goes in the speaker notes or the appendix, never in paragraphs on the slide.
3. **One number to remember per slide.** It goes in the navy hero card, at most one per slide.
4. **Boxes separate the content.** Tinted cards hold context and the navy card holds the result.
   No stripes, no edge bars, and no lines under titles.
5. **Orange means "the target".** Use it only for the gaze reticle in photos, the unit on the hero
   number, the dividers' label chips and the current part marker. Never use it for body text.
6. **Every content slide fills down to the tracker.** The body ends 0.45–0.5" above the tracker
   line (body bottom about 6.45", tracker at 7.0"). Large empty bands at the bottom are a defect.
7. **Honest status.** Claims carry their condition: replay or real, offline or live, tested or
   planned. Missing artefacts are shown as clearly labelled placeholders, never faked.

## 2. Canvas and grid

| Item | Value |
|---|---|
| Layout | `LAYOUT_WIDE`, 13.333 × 7.5 in |
| Side margins | 0.6 in. Content box x = 0.6, width W = 12.13 |
| Header zone | y 0.38–1.8 |
| Body zone | y 2.05 to about 6.45 (caption line at y 6.28 if used) |
| Page number | right edge, y 6.6 |
| Tracker | y 7.0 (line), labels y 7.08 |
| Default 3-column grid | rail x 0.6, w 2.1 · centre x 2.95, w 6.0 · right column x 9.2, w 3.53 |
| Gaps | 0.2–0.25 between cards, 0.15 between small chips |

The 3-column grid is the default, not a rule: change the layout to fit the content (Sherman's
instruction). Charts and diagrams can take the full width. Keep the header, the tracker and the
component styles the same on every slide.

## 3. Colour tokens

| Token | Hex | Use |
|---|---|---|
| NAVY | `16213A` | titles, body text, hero card, pills, dark slide background |
| BLUE | `0068B5` | kicker text, icon circles, the highlighted bar in a chart, active tracker line |
| TINT | `EEF2F7` | context cards, rail items, stat cards, limit card |
| SLATE | `4B5563` | subtitles, secondary text |
| MUTED | `6B7280` | captions, small labels, inactive tracker text |
| RULE | `D7DEE8` | hairlines, table borders, inactive tracker line |
| GREY | `C5CDD8` | non-highlighted chart bars |
| SKY | `7DD3FC` | labels on navy, viewfinder brackets, presenter #ids |
| PALE | `CBD5E1` | secondary text on navy |
| SIGNAL | `FF7A3A` | orange: reticle, hero unit, label chips on dividers. Fills and large text on navy only |
| EMBER | `C2410C` | orange text on white (LIMIT label, "today" line, "still to join" links) |
| HILITE | `DBEAFE` | highlighted table rows, "leads" chips |
| WHITE | `FFFFFF` | slide background |

**Status scale** (used on slides 4, 8 and 18, and in the legends):

| Status | Fill | Text | Dot | Name |
|---|---|---|---|---|
| tested | `DCFCE7` | `15803D` | `16A34A` | tested |
| built | `FEF3C7` | `B45309` | `D97706` | built, not validated |
| alone | `CFFAFE` | `0E7490` | `0891B2` | works alone |
| planned | white + dashed `9CA3AF` border | `6B7280` | `9CA3AF` | planned |

Contrast rules: SIGNAL on white fails contrast (2.6:1), so orange text on white is always EMBER
(5.2:1). Small text on white is SLATE or darker, never lighter than MUTED.

## 4. Type

Font: **Calibri** everywhere, including charts (`"+mn-lt"`). Do not use Aptos.

| Element | Size | Style |
|---|---|---|
| Kicker (`GAPPLER · PRESENTER`) | 11 | bold, BLUE, caps, charSpacing 1.5 |
| Pill text | 11 | bold, white on NAVY, caps |
| Title | 30 | bold, NAVY, one line, ≤ about 60 characters, no full stop |
| Subtitle | 17 | SLATE, one line |
| Card heading | 14–16 | bold, NAVY |
| Body / card text | 12–14 | NAVY or SLATE |
| Hero number | 50 | bold, white, unit 22 bold SIGNAL |
| Stat number | 20 | bold, NAVY |
| Small caps labels | 11 | bold, charSpacing 1.5 (MUTED, BLUE, EMBER or SKY) |
| Captions, sources, legends | 11 | MUTED |
| Divider title | 40 | bold, white |

**Floor:** nothing below 11 pt. If text does not fit, cut words or split the slide.
**Writing:** plain words, short fragments, no em dashes, no semicolons. Arrows (→) are fine on
slides to show flow.

## 5. Components (all in `kit()` in `build/deck.js`)

| Component | Function | Look |
|---|---|---|
| Header | `k.header(presenter, pill, title, sub)` | kicker top-left, navy pill top-right (phase or section, caps), title, subtitle |
| Section rail | `k.rail(items, active, limit)` | "THIS PART" label, one rounded item per topic in the presenter's run, current one filled NAVY, LIMIT card at the bottom (ends at y 6.45). Use only when the presenter has 2 or more slides in a row |
| Hero card | `k.hero({label, big, unit, sub})` | NAVY rounded card, SKY caps label, big white number, SIGNAL unit, PALE sub. Default x 9.2, y 2.05, 3.53 × 1.9 |
| Stat card | `k.stat({y, h, ic, num, label})` | TINT card, BLUE icon circle, 20 pt number, 12 pt label |
| Limit card | `k.limitCard(x, y, w, h, text)` | TINT card, EMBER "LIMIT" caps label, 13 pt NAVY text. Every results slide has one |
| Photo | `k.photo(path, box, caption)` | cover-cropped, with a NAVY 20 %-transparent caption strip at the bottom, 11 pt white caps |
| Chip | `k.chip(x, y, w, text, status)` | pill, 0.26 high, 11 pt bold, status colours (dashed border for planned) |
| Icon circle | `k.circleIcon(x, y, d, name, fill)` | filled circle with a white `react-icons/md` icon |
| Number circle | `k.num(x, y, d, n, fill)` | filled circle with a number or letter |
| Small caps label | `k.label(text, x, y, w, color)` | 11 pt bold caps |
| Caption | `k.caption(text, x, y, w)` | 11 pt MUTED, one line |
| Tracker | `k.tracker(section)` | 8 sections across the full width: Problem, System, Intent, Explore, Search, Confirm, Grasp, Plan. Thin RULE lines, active line BLUE 0.04 in thick, active label bold NAVY. Adds the page number |
| Table | `table(s, rows, {colW, fontSize, hi, rowH})` | NAVY header row, white text. Rows alternate white and TINT. 0.5 pt RULE borders. `hi` rows in HILITE |

Rounded corners: cards `rectRadius 0.1`, pills fully rounded. Card fills only, no outlines (except
dashed "planned" items and placeholders).

## 6. Slide types

**Cover.** The full-bleed FAST-LIVO2 map under a NAVY overlay at 55 % transparency, with a stronger
NAVY panel on the left 6.4 in. Orange reticle ring on the loop start. Left: kicker (SKY), "GAPPLER"
at 66 pt, the full project title at 20 pt, the tagline in italic SIGNAL, the names, the supervisors.

**Part divider (robot's-eye viewfinder).** NAVY background.
- Left column:
  - "PART n / 3" in SIGNAL caps, then the title at 40 pt and the subtitle at 17 pt PALE.
  - Presenters listed as tracked objects: an SKY-outlined "#1" box, the name in bold white, the
    topic in PALE.
  - A 3-part progress bar at y 6.55: current part SIGNAL, past parts `64748B`, future parts
    `334155`.
- Right: a real sensor frame in a 5.78 × 4.95 viewfinder at x 6.95, y 0.95:
  - SKY corner brackets just outside the frame.
  - An orange label chip on the top edge: `SOURCE · WHAT IT SHOWS`, caps.
  - The orange reticle (ring, centre dot, 4 ticks) on the target, given in source pixels.
  - A one-line PALE caption below.
- `viewfinder()` places all of this. Each part uses a different sensor: Aria glasses, FAST-LIVO2
  map, LiDAR on the camera image. Do not reuse concentric rings or big outlined numerals: they read
  as the Elon deck.

**Content slide.** Header, body in the grid, tracker. Typical body: a centre visual (photo, chart or
diagram), the right column with one hero card and one or two stat or limit cards, and an optional
caption at y 6.28.

**Q&A.** Same as a part divider, with the top-down map in the viewfinder. Left: "THANK YOU" in
SIGNAL caps, "Questions" at 60 pt, the tagline, the names and a short list of backup topics. All
three part-bar segments are marked as past.

**Appendix.**
- Divider: NAVY background with A1–A10 in two columns.
- Appendix slides use the header with kicker `GAPPLER · APPENDIX`, pill `BACKUP · An`, title
  `An  Topic`, and subtitle `Answers: "the question it answers"`.
- The body is tables, 11–12 pt. No tracker.
- The source line goes at the bottom left, y 6.95, 11 pt MUTED, with the page number on the right.
- Tables must end above y 6.9.

## 7. Charts and diagrams

- Native PowerPoint charts only (`addChart`), never images of charts.
- Bars are GREY, with the chosen or key value in BLUE. Value labels on: 12–14 pt bold NAVY. Hide
  the value axis, and remove gridlines and the legend unless there are two series. Category labels
  are 11–13 pt SLATE.
- Short notes under key bars ("upstream", "chosen") in 11 pt, the chosen one in BLUE bold.
- Small comparison bars can be drawn with rectangles inside a TINT card: label, bar, bold value.
- Flow diagrams (slide 18):
  - Solid lines in the "tested" dot colour with arrowheads mean "works today".
  - EMBER dashed lines with arrowheads mean "still to join".
  - Task IDs go in the box status line or on the link label.
  - Route lines around boxes, never through them.
  - Add a legend row.
- Drawn schematics (slide 8): simple shapes in `64748B`, NAVY and `334155`. Number the links with
  status-coloured circles and explain them in cards beside the drawing.
- Gantt (slide 16): weeks as columns. Shade non-working weeks `E5E7EB`, and the half-speed weeks
  `F1F5F9`. Done bars are NAVY, forecast bars `93C5FD`, optional bars dashed and unfilled. Draw an
  EMBER "today" line and diamond markers for the key dates.

## 8. Images

- Use real project images only, cover-cropped into their box. Sherman's renders are in
  `docs/sherman_docs/local/report_media/`. Images taken from the old deck are in
  `build/media/`.
- The orange reticle ring marks the target or start point. Compute its position from the source
  pixel coordinates and the cover crop (see `viewfinder()` and slide 7's map code).
- A missing artefact gets a dashed GREY placeholder box with an icon and the name of who supplies
  it (slide 13). Never stretch an image or use an unrelated stock photo.
- The coloured map shows lab visitors' faces: cleared for this internal talk only. Re-render before
  any external showing.

## 9. Speaker notes

Every slide gets `s.addNotes()` with the speaking script from the content spec, then the handover
line, then any `[VERIFY: ...]` or `[TEAM INPUT: ...]` items. Numbers that are cut from the slide
stay in the notes.

## 10. Build and check

```bash
cd docs/interim_presentation/build
npm install pptxgenjs react-icons react react-dom sharp   # once
node deck.js "../Gappler_Interim_2026-10-28_v2.pptx"
```

Before handing over a change:

1. Validate with the pptx skill: `scripts/office/validate.py deck.pptx` must pass.
2. Render with `soffice --convert-to pdf`, then `pdftoppm -r 80`, and look at every changed slide.
   Check that no text overflows its box, no word breaks across lines, and nothing overlaps.
3. Check the bottom gap: the lowest content sits 0.45–0.5" above the tracker (y 6.95). Tables in
   the appendix end above their source line.
4. No text below 11 pt, and no orange text on white except EMBER.
5. Open each file with its own `open` command.

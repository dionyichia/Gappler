# Interim deck handoff, 28 Oct 2026

Deck: `Gappler_Interim_2026-10-28.pptx`. 31 slides: 18 core, 1 appendix divider, 12 backup slides (A1 to A10, with A6 split over 3 slides). Editable PowerPoint: native text, shapes, tables and one native chart (slide 10). Approved scripts are in each slide's speaker notes and in `SPEAKER_SCRIPTS_2026-10-28.md`.

## 1. Missing assets (dashed placeholder boxes on the slides)

Each placeholder names the file and the owner. To fill one: delete the dashed box, insert the picture at the same spot, keep its aspect ratio.

| Slide | What goes in | File | Owner |
|---|---|---|---|
| 1 | Photo of the full robot with the glasses beside it (left half of the slide) | take at the lab | Any member |
| 2 | Base-camera frame from knee height (middle panel) | a D455 frame of the box, or a frame from `mg_handdriven1_survey_every_100th_frame_2026-10-21.jpg` / `nav_camera_frames_along_t35f_run1_2026-10-21.jpg` captioned "the lab from the base camera" | Sherman or Zongzhe |
| 7 | Map build-up animation (main) | `nav_fastlivo_map_buildup_clean_handdriven1_2026-10-24.gif`, fallback `..._map_iso_clean_...png` | Sherman |
| 7 | Closure zoom inset | `nav_fastlivo_path_closure_zoom_clean_handdriven1_2026-10-24.png` | Sherman |
| 8 | LiDAR-on-camera overlay inset | `nav_lidar_on_camera_overlay_stationary02_t0s_2026-10-19.png` | Sherman |
| 9 | Rerun 3D view of the graph | screenshot from `mg_t6.3_four_photos_rerun_3d_2026-10-21.rrd` | Zongzhe |
| 9 | Frame 700 strip | `mg_frame700_masks_and_3d_objects_2026-10-21.png` | Zongzhe |
| 13 | Real grasp video (15 s or less) or three stills | `grasp_real_arm_<date>.mp4` | Dion |
| A4 | Optional RViz grasp recording | `rviz_grasp_<date>.mp4` | Dion |
| A5 | Drift plot | `nav_t35f_drift_step3_error_vs_time_2026-10-21.png` | Sherman |

Optional, not placeholders: slide 11 shows the 20 / 15 / 12 of 22 counts as bars because the 22-instruction grid (`check_reasoning.json`) is not in the repo. Zongzhe can swap in the grid. Slide 10's optional answer-key inset was left out for space.

## 2. Claims and items to verify before the talk

From the spec (unchanged, also in each slide's notes):

- **S3** FAM-HRI full title and author list (D§1.1 flags it unverified). Only "Lai et al., 2025" is on the slide.
- **S6** Has T2.21 (Whisper word timestamps, PR #91) merged? If yes, the script can say the word is time-stamped.
- **S7** Clean renders live on Sherman's machine only. Check the venue can play video.
- **S8** Optional phone inclinometer on the camera top. One phrase on how the wrist camera was calibrated. Who presents the glasses-to-robot row.
- **S11** Replace "related: table, desk" with the model's real output for "find the chair". If T6.8 runs before 28 Oct, replace the status line with its result.
- **S12** 148 of 180 (T8.5) vs 266 of 268 (T8.9a). The slide uses only 266 of 268. Dion confirms before anyone quotes both.
- **S13** Has any grasp run with the live glasses instead of a WAV file?
- **S14** Any result from the new SDK licence (T1.45) or the fusion retest (T1.47)?
- **S15** M4 dates disagree across sources. Slide says "January 2027".
- **S16** M1's 8 Nov forecast depends on the AnyGrasp licence reply.
- **S17** Has the GPU been bought, and any spend to date?

New flags from building the deck:

- **S2 image quality.** The glasses and wrist crops come from `clip_glasses_vs_wrist_crops_2026-10-20.jpg`, where each tile is 128 px. Upscaled, they look soft on a projector. Full-resolution frames would be better.
- **S6 caption.** The source image's header for the 1.5 m frame reads "TABLE picked". I cropped the header off and used the spec's wording, "gaze landed on the mats". Dion should confirm the caption matches what SAM 3 labelled.
- **S18 task IDs.** The IDs in grey (T2.24, T8.9a, T1.45, T1.47, T1.35, T3.6, T6.8, T2.5, T5.5, T5.6, T7.1, T7.2, T7.5, T7.6, T8.2, T8.3) come from CR§0.6 "Next on the schedule", not from the spec slide.
- **A7 "Change" column.** Each change comes from comparing the September plan window (milestone headings in `1cde0ec:docs/PROJECT_PLAN.md`) with the CR§0.6 forecast. Where CR gives a stated slip (M1, M3, M5, M6), it matches.
- **Privacy.** Lab visitors' faces in Sherman's map: cleared for this internal talk only. Re-render before any external showing (noted on A6, 3 of 3).

## 3. Where the layout departs from the spec's visual suggestions

The content and numbers follow the spec. The layout departs from its suggestions in these places:

- **S3** No glasses icon or map photo in the two paper blocks, since there are no project images for them and decorative icons were ruled out.
- **S4** The scope box sits under the five phases, not on the right, so the phase boxes stay readable. Box borders are neutral. Status shows as coloured badges, because phases 2 to 4 mix statuses.
- **S8** The four links are explained in cards beside a schematic robot drawn with shapes (labelled "not to scale"). Frame names stay in A2.
- **S11** The ranked-hits box shows the structure (id, 3D centre, best photo) with no score bars, because there are no measured scores for it yet.
- **S16** M9 is drawn as a dashed outline, not hatched, because hatch fills are not available in the generator. Week spans follow the spec table.
- **Text size.** Body text is 13 to 18 pt on most slides. Diagram and chart labels are 10 to 12 pt (slides 7, 8, 13, 15 and 16 are the densest). That is below the 24 to 28 pt target. Reaching it would mean moving vetted on-slide content into the notes, so I left that decision to the team. If you want larger text, trim on-slide lines first on 7, 8, 13 and 16.

## 4. Animation plan (not implemented)

The generator cannot write PowerPoint animations, so the deck has none. Every slide reads complete as a static slide. If you want them, add them in PowerPoint (Animations > Appear, On click):

| Slide | Reveal order | Why |
|---|---|---|
| 4 | Phase boxes 1 to 5 one at a time, then the scope band | Walks the pipeline in the order of the script |
| 6 | Steps 1 to 4, then the 1.0 m frame, then the 1.5 m frame and its callout, then the results | Sets up the miss before the numbers |
| 12 | Left panel (method choice), then each scene in the right panel, then the two callouts | Baseline, choice, result, limit |
| 13 | States Idle to Hold in order, then Stopped and its arrows | Follows the state machine |
| 15 | All part boxes, then solid links 1 to 5, then dashed links 6 to 11, then link 12 | The spec's reading order: built today, then still to join |

Video: nothing is embedded. For S7, an inserted GIF plays on its own in PowerPoint. For S13, use Insert > Video and keep a still on a duplicate slide as a backup.

## 5. Checks actually done

- Rendered all 31 slides to images (LibreOffice) and inspected each one. I fixed text overflow or overlap on slides 3, 4, 6, 8, 10, 11, 13, 16, 17, 18 and A1, then re-rendered them.
- File check: `validate.py` passed (schema, relationships, chart XML).
- Numbers: an automated check confirmed every number in the slide text appears in the spec or the three source reports. It found one mismatch (A5, "52.06 %"), which I corrected to the source's "removed fraction 0.5206".
- Style: no em dashes or semicolons in the slide text.
- Speaker notes: scripts were pulled from the spec by code, word for word, with only the hard line breaks joined. Each note also carries the presenter, slot, elapsed time, transition line and the slide's review flags.
- Timing: slot times sum to 20:00 including eight 5 s handovers. The scripts total about 3,170 words, so they need about 160 words a minute overall. At 140 words a minute they run about 22:40. Slides needing over 180 words a minute: 11 (236), 17 (213), 18 (208), 14 (195), 10 and 16 (181). This matches the spec's own audit (section F, row 10).
- Schedule (S16) and budget (S17) are included.
- **Not checked:** how it renders in PowerPoint itself, and legibility on the venue projector. Calibri was previewed with a metric-compatible substitute, so line breaks should match, but run through it once in PowerPoint before the talk.

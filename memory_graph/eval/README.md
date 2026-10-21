# Ground truth for scoring the memory graph (T6.4e)

The real furniture in the lab, one entry per physical object, with its outline on the floor and
its height. T6.4 scores the graph against it: duplicates (one real object, two graph objects),
false merges (two real objects, one graph object), misses and extras. T6.8 checks query answers
against the same positions.

## `lab_ground_truth_handdriven1.json`

**Drive:** `handdriven1`, the FAST-LIVO hand drive of 2026-10-20 (118 s, 3536 photos). The path to
the bag on the lab box is in the file.

**Frame:** FAST-LIVO's world frame for that drive (`camera_init`): z up, origin where the drive
started. The same frame `FastLivoBag` gives every photo's pose, so graph objects built from this
drive compare directly. Another drive has its own origin and needs its map lined up first.

**Each object:**

| Field | Meaning |
|---|---|
| `id` | its number. Gaps are boxes deleted while marking |
| `class` | one of the 13 classes in `classes` |
| `corners` | the outline on the floor, 4 corners in metres (x, y), a rectangle at any angle |
| `z_bottom_above_floor`, `z_top_above_floor` | height range in metres above the floor |
| `centre` | middle of the box in the world frame (x, y, z). z counts from the frame's origin, not the floor: the floor is at `floor_z` (-0.175) |
| `source` | `hand` drawn by Zongzhe, `proposal` a LiDAR proposal Zongzhe accepted |
| `clip_suggested` | for proposals, CLIP's class guess, kept to see how often it was changed |
| `many_parts` | present and true on the glass bookcase (2) only: the graph sees it as one "shelf" per cell, and no merge should be expected to join them, so the scorer counts those as parts, not duplicates (Zongzhe, 2026-10-21) |

**Counts:** 16 objects. 7 chair, 2 computer tower, 2 table, 2 tv_monitor, 1 each of shelf, sofa,
door. 12 drawn by hand, 4 accepted from proposals.

## How it was made

Marked by Zongzhe on 2026-10-21 on a top-down view of the drive's LiDAR map (2 cm cells, 10 cm
height bands above the floor), next to the photos along the path. Each mark was checked by drawing
its 3D box on the photos.

To save time, 55 outlines were proposed from the map by geometry only (connected blobs per height
band, walls stripped), each with a class guess from open_clip ViT-B-32 on the best photos. No SAM 3
and none of the memory graph's merging code was used, so the list does not depend on what T6.4
tests. Zongzhe reviewed all 55: 4 accepted (3 with the class changed from CLIP's guess), 44
rejected, 2 split, 9 already covered by hand marks. The tools and the map are in Zongzhe's local
folder (`docs/zongzhe_docs/local/t6.4e/`, not in git).

Classes counted: furniture-size things in the base vocabulary. Small or vague things (book, paper,
light, sign, cup, box, bag, cushion, clothes, power outlet) are not in the list and are not scored.

## Known limits

- **Coverage, second pass.** The first list (12 objects, 2026-10-21 22:48) left several blobs on
  the map unmarked. For a second pass the marking page showed 7 "look here" places: where the graph
  (T6.4 baseline) saw something 7 or more times with no box marked. Only the place and the count
  were shown, not the graph's label. Zongzhe checked each in the photos and added 4 objects: the
  wall TV (14), a chair by the sofa (15), a chair under a table (17) and a long divided table (19).
  The other places were judged not to be furniture in the list. Final list saved 2026-10-21 23:45.
  This pass used the graph's output to point at places, so objects the graph never saw at all can
  still be missing.
- **Heights are read from the map**, the highest 10 cm band with points inside the outline. A box
  can pick up something above the object: computer towers 10 and 12 read 2.3 m, likely a
  partition or shelf above them. T6.4 matches on the floor outline, so this matters little there.
- **No tape check yet.** The map's scale is FAST-LIVO's. Measuring 3 to 5 distances between marked
  objects in the lab would confirm it.
- **One drive.** Ground truth for a second drive (T6.4's check run) comes from lining up its map
  with this one.

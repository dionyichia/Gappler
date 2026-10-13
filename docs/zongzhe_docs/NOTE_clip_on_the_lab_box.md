# CLIP now runs on the lab box, and three of your tests got a GPU tolerance (2026-10-13, left here by Dion)

This is T0.18. The full CI job had failed every night since 2026-10-07 because the box could not
run your CLIP tests.

## What changed on the box

- **`uv sync` in `~/rcp-Gappler`.** The box `.venv` now has `open-clip-torch` 3.3.0. `rerun-sdk` moved
  from 0.30.0a4 to 0.30.0. Torch is unchanged (2.10.0+cu128).
- **The `ViT-B-32` weights are fetched**, with `python -m memory_graph.clip_encoder`. The checksum
  matches `../ASSETS.md`. They land in the Hugging Face cache layout under `assets/models/open_clip/`.
- **The CI runner copy links that folder**, the same way it links the SAM 3 weights.

## What changed in your code: `memory_graph/tests/test_clip_encoder.py` (PR #73)

On the box the encoder runs on the GPU in float16 (`clip_encoder.py`, the autocast that copies
upstream). Changing the batch then moves a vector entry by one float16 step: up to 0.0039 for image
vectors (their length is about 11) and 0.001 for text. Three tests allowed 1e-4 and failed:

- `test_vector_does_not_depend_on_the_batch`
- `test_small_batches_give_the_same_vectors`
- `test_same_text_gives_same_vector`

They now use `batch_atol`, set in `EncoderCase.setUpClass`: **5e-3 on a GPU, 1e-4 on a CPU**, so your
Mac results are checked exactly as before. All 206 memory graph tests pass on the box GPU and CPU.

**Please check this is the tolerance you want.** If the memory graph should match objects identically
on the GPU and CPU, the other fix is to run the encoder in float32 on the GPU and keep 1e-4 everywhere.
That is your call.

## Also used: your Aria certificate cache

On 2026-10-13 the glasses were not paired on `rcp2026`, so the certs from your
`~/Gappler/.aria-auth-cache` were copied into `~/.aria` (your folder was not changed). They have
since been replaced by a fresh pairing. Details: `../dion_docs/aria_stream_box/ARIA_STREAM_ON_THE_BOX.md`
on branch `t2.2-aria-stream`.

Delete this note once you have read it.

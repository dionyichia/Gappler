# Replay callback-drain implementation plan

**Goal:** expose replay progress and prevent player EOF from silently hiding unconsumed sensor callbacks.
**Architecture:** use stdlib SQLite to read only serialized header prefixes from the fixed raw bag; compare those timestamps and counts with the pinned mapper's existing callback logs. Keep estimator-completion and accuracy explicitly unproven. No image or mapper changes.
**Stack:** Python stdlib, existing unittest suite, Bash/Docker wrapper.

## Inline execution (requested by Sherman)

- [x] Add `test_progress.py` with synthetic SQLite/CDR headers and real log files. Cover image offset, duplicate/missing/unexpected callbacks, incomplete log lines, bounded drain, invalid rates and wall-budget refusal. Run it and observe failures before implementation.
- [x] Add `replay_progress.py` for expected/observed callback accounting, validated rate and bounded drain decisions. Tests use actual stdlib SQLite and temporary files, not ROS.
- [x] Wire it into `replay.py`: report progress every 10 seconds, pass rate to player, wait up to 120 seconds after EOF for terminal callbacks plus five seconds of stdout/stderr inactivity, then report all coverage gaps as errors. Reserve ten seconds of the 600-second overall limit for cleanup. Explicitly distinguish this heuristic from estimator completion.
- [x] Wire the module/rate into `run_replay.sh` staging and hashes, stream supervisor output to the terminal, keep sudo calls noninteractive after initial authentication, and preserve exact-name isolation/cleanup. No container launches during tests.
- [x] Run local pure tests plus shell syntax checks. Replay old saved normal/ASan logs through the new accountant read-only to verify it exposes the known shortfall.
- [x] Finish review follow-ups, copy final scratch files to the separate lab candidate, verify hashes and rerun tests there. No replay or rebuild. Independent follow-up review found no remaining important issue.

## Acceptance boundaries

- Player EOF alone is insufficient for PASS.
- Missing callbacks, including initial IMU omissions, remain visible failures; no inferred allowance.
- Terminal callback observation plus log inactivity is only a bounded shutdown heuristic, not estimator-completion proof.
- Fail closed if the requested playback time plus startup/drain allowances exceeds the existing wall budget.
- All evidence containers, images and previous run records remain untouched.

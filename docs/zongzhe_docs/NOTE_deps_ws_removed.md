# `deps_ws/` no longer exists (2026-09-21, left here by Dion)

Your [`BUILD_WORKSPACES.md`](BUILD_WORKSPACES.md) explains why `deps_ws` and
`ros2_robot_ws` are built separately. That changed in reorg step 3 (`NEXT_STEPS.md` §2.15):

- **MoveIt Task Constructor moved** from `deps_ws/src/` to `grasp/vendor/moveit_task_constructor/`.
  `deps_ws/` is deleted.
- **One build, one overlay.** `./build.sh` (moved from `bench/` to the repo root) builds `arm/` and
  `grasp/` together into the repo-root `install/`. `global_env.sh` (was `env.sh`) sources only that.
- **`ros2_robot_ws/install.sh` is deleted** (Dion, 2026-09-21). `./build.sh` replaces it.

Please update or retire `BUILD_WORKSPACES.md` when you next work in your folder.

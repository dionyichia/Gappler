# maps/

Empty on purpose. `CMakeLists.txt` installs this folder, so it has to exist for the build to pass.

No map is kept in git. Saved maps live in `$GAPPLER_MAP_DIR` (default `~/maps`), the same folder
`robot_slam` uses. `navigation.launch.py` defaults to `maps/my_map.yaml`, which does not exist, so
pass one in: `ros2 launch robot_navigation navigation.launch.py map:=$GAPPLER_MAP_DIR/current_map.yaml`.
See `docs/ASSETS.md` for where the lab's saved map is.

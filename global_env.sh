# Sets up every subsystem in this shell: aria, arm, grasp and nav. Source it in every terminal:
#   source <repo>/global_env.sh
# Replaced env.sh on 2026-09-22 (NEXT_STEPS 2.15 step 7). To set up one subsystem only, source
# its own file instead, for example nav/nav_env.sh.
#
# Overlays: ./build.sh builds arm/ and grasp/ into install/, ./build.sh nav builds nav/ into
# install_nav/. Do NOT also source an old deps_ws/install, which would add a second copy of the
# MoveIt Task Constructor packages.

_gappler_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _gappler_sub in aria arm grasp nav; do
  source "$_gappler_here/$_gappler_sub/${_gappler_sub}_env.sh" \
    || { echo "global_env.sh: ${_gappler_sub}_env.sh failed, see above." >&2; unset _gappler_here _gappler_sub; return 1 2>/dev/null || exit 1; }
done
unset _gappler_here _gappler_sub
echo "Gappler: aria, arm, grasp, nav set up from $GAPPLER_REPO   DISPLAY=$DISPLAY"

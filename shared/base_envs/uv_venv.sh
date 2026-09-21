# INTERNAL: do not source this yourself. Source global_env.sh, or one <subsystem>/<subsystem>_env.sh.
#
# Activates the repo's uv Python env (.venv at the repo root) once. Sourced by aria_env.sh and
# grasp_env.sh, the two subsystems whose Python runs in it (the Aria app, the SAM3 node).
if [ ! -f "$GAPPLER_REPO/.venv/bin/activate" ]; then
  echo "uv_venv.sh: no .venv in $GAPPLER_REPO. Run 'uv sync' there first." >&2
  return 1
fi
[ "${VIRTUAL_ENV:-}" = "$GAPPLER_REPO/.venv" ] || source "$GAPPLER_REPO/.venv/bin/activate"

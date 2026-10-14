#!/usr/bin/env bash
# Sends a command to a tmux pane named by its row and column on screen, not its pane number,
# which you can't see. Rows count from the top, columns from the left, both from 1.
#
#   ./tmux_pane_by_row_col.sh <session>[:<window>] map                   show the grid
#   ./tmux_pane_by_row_col.sh <session>[:<window>] <row> <col> run  '<cmd>'  type it and press Enter
#   ./tmux_pane_by_row_col.sh <session>[:<window>] <row> <col> type '<cmd>'  type it, no Enter
#
# Use "type" for anything that moves the arm, gripper or base: the user presses Enter.
# The session name is matched exactly ("=name"), never by prefix.
set -eu
TARGET="=${1:?usage: see the top of this file}"

# One line per pane: row col pane_id current_command, sorted top to bottom then left to right.
grid() {
  tmux list-panes -t "$TARGET" -F '#{pane_top} #{pane_left} #{pane_id} #{pane_current_command}' |
    sort -n -k1,1 -k2,2 |
    awk 'NR == 1 || $1 != top { row++; col = 0; top = $1 } { col++; print row, col, $3, $4 }'
}

if [ "${2:-}" = map ]; then
  grid | while read -r row col id cmd; do
    last=$(tmux capture-pane -p -t "$id" | grep -v '^\s*$' | tail -1 | cut -c1-70)
    printf 'row %s col %s  %-8s %s\n' "$row" "$col" "$cmd" "$last"
  done
  exit 0
fi

ROW="${2:?row}" COL="${3:?col}" MODE="${4:?run or type}" CMD="${5:?command}"
case "$MODE" in run|type) ;; *) echo "mode must be run or type" >&2; exit 2 ;; esac
ID=$(grid | awk -v r="$ROW" -v c="$COL" '$1 == r && $2 == c { print $3 }')
[ -n "$ID" ] || { echo "no pane at row $ROW col $COL. The grid:" >&2; grid >&2; exit 1; }
tmux send-keys -t "$ID" -l "$CMD"
case "$MODE" in
  run)  tmux send-keys -t "$ID" Enter ;;
  type) echo "typed into row $ROW col $COL, not sent: press Enter there" ;;
esac

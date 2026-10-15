#!/usr/bin/env python3
"""Claude Code PreToolUse hook for Bash: a backstop for the lab box safety rules in CLAUDE.md.

Reads the hook's JSON on stdin and looks at the command string, including anything sent over ssh.
  - pkill / killall: blocked. They also hit other people's processes on the shared box.
  - a command that moves the arm, gripper or base, if it would run: blocked. Typing it into a tmux
    pane without Enter is allowed, so the user can press Enter themselves.
  - tmux kill-session / kill-server / kill-window / kill-pane: asks the user first. kill-session
    without an exact "=name" target is blocked, because tmux matches -t by name prefix.

Self-test: python3 .claude/hooks/lab_safety_guard.py --selftest
"""
import json
import re
import sys

# ponytail: string matching, not a shell parser. A command built at runtime (variables, eval,
# a script that publishes) gets past it. The CLAUDE.md rules are the real control.
MOVING = re.compile(
    r"ros2\s+launch\s+grasp_state_machine"
    r"|ros2\s+topic\s+pub\b.*?(/rm_driver/\S*_cmd|/cmd_vel|/goal_pose|/manipulation/"
    r"|/manipulator/grasp_request|/object_centroid_2d)"
    r"|ros2\s+action\s+send_goal"
    r"|ros2\s+run\s+simple_teleop"
    r"|(python3?\s+|\./)\S*launchers/(start_camera_arm_grasp|grasp_orchestrator)\.py"
)
TYPE_ONLY = re.compile(r"tmux_pane_by_row_col\.sh\s+['\"]?[\w:.=-]+['\"]?\s+\d+\s+\d+\s+type\b")
TMUX_KILL = re.compile(r"tmux\s+(?:-\S+\s+)*kill-(session|server|window|pane)\b(.*)")


def check(cmd):
    """Return (decision, reason). decision is "allow", "ask" or "deny"."""
    if re.search(r"(^|[;&|('\"]|\bsudo\s|\bssh\b[^'\";|&]*\s)\s*(pkill|killall)\s", cmd):
        return "deny", ("No pkill/killall on the shared lab box: it also stops other people's work. "
                        "Stop only processes you started, by process group: kill -INT -<pgid>.")
    if MOVING.search(cmd):
        raw_type = "send-keys" in cmd and not re.search(r"\b(Enter|C-m|KPEnter)\b", cmd)
        if not (TYPE_ONLY.search(cmd) or raw_type):
            return "deny", ("This command moves the arm, gripper or base. Type it into its tmux pane "
                            "without Enter (tmux_pane_by_row_col.sh <session> <row> <col> type '<cmd>'), "
                            "then tell the user which row and column to press Enter in.")
    m = TMUX_KILL.search(cmd)
    if m:
        if m.group(1) == "session" and not re.search(r"-t\s*['\"]?=", m.group(2)):
            return "deny", ('tmux matches -t by name prefix. Use the exact name, -t "=name", '
                            "and ask the user before closing any session.")
        return "ask", ("Closing a tmux " + m.group(1) + " on a shared box. Confirm which one, "
                       "what runs in it, and that it is yours.")
    return "allow", ""


def selftest():
    cases = {
        "pkill -u rcp2026 -f rs_launch.py": "deny",
        "ssh box 'killall python3'": "deny",
        "ros2 topic pub --once /manipulator/grasp_request std_msgs/msg/Empty": "deny",
        "ssh box 'tmux send-keys -t %3 \"ros2 launch grasp_state_machine x.launch.py\" Enter'": "deny",
        "ssh box './tmux_pane_by_row_col.sh grasp 2 1 run \"ros2 run simple_teleop teleop\"'": "deny",
        "ssh box './tmux_pane_by_row_col.sh grasp 2 1 type \"ros2 launch grasp_state_machine g.launch.py\"'": "allow",
        "tmux send-keys -t %3 -l 'ros2 topic pub --once /rm_driver/set_gripper_position_cmd x'": "allow",
        "grep -rn grasp_state_machine docs/": "allow",
        "./bench/state_machine_sim.sh": "allow",
        "ros2 topic echo /pipeline_state": "allow",
        "tmux kill-session -t grasp": "deny",
        'tmux kill-session -t "=grasp"': "ask",
        "tmux kill-pane -t %4": "ask",
        "kill -INT -12345": "allow",
        "ssh -o HostKeyAlias=x rcp2026@box pkill -f rs_launch": "deny",
        "grep -rn pkill docs/": "allow",
    }
    bad = [(c, want, check(c)[0]) for c, want in cases.items() if check(c)[0] != want]
    for c, want, got in bad:
        print(f"FAIL want {want} got {got}: {c}")
    print("selftest", "FAIL" if bad else "PASS")
    return 1 if bad else 0


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    decision, reason = check(cmd)
    if decision == "deny":
        print(reason, file=sys.stderr)
        return 2
    if decision == "ask":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

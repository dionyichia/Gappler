"""Shared helpers for the bench tools. Stdlib-only, like the rest of bench/.

is_owned decides what counts as "our code" (findings fail the bench) as opposed to
vendored code (findings are informational). The rule: everything except what sits under
a folder named vendor/ (NEXT_STEPS 2.15 step 6, 2026-09-22). So moving or adding our code
needs no edit here. Third-party code goes under the vendor/ folder of its subsystem
(aria/vendor, arm/vendor, grasp/vendor, nav/vendor, assets/vendor).
"""


def is_owned(path: str) -> bool:
    """path is repo-relative, for example 'grasp/anygrasp_node/anygrasp_node.py'."""
    return "vendor" not in path.split("/")

"""Keyboard input handling utilities."""

import select
import sys

# Key codes and characters
ESC_KEY = 27
ESC_CHAR = "\x1b"
QUIT_KEY = "q"


def exit_keypress() -> bool:
    """
    Check if user pressed 'q' or ESC in terminal.

    Used for exiting the main program loop. Requires TerminalRawMode context.

    Returns:
        bool: True if exit key was pressed, False otherwise.
    """
    readable, _, _ = select.select([sys.stdin], [], [], 0)

    if readable:
        char = sys.stdin.read(1)
        return char in (QUIT_KEY, ESC_CHAR)

    return False

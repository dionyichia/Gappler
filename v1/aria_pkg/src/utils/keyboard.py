"""Keyboard input handling utilities."""

import sys
import select
import cv2

# Key codes and characters
ESC_KEY = 27
ESC_CHAR = "\x1b"
QUIT_KEY = "q"


def quit_keypress() -> bool:
    """
    Check if user pressed 'q' or ESC in OpenCV window.

    Used for exiting CV2 display loops.

    Returns:
        bool: True if exit key was pressed, False otherwise.
    """
    key = cv2.waitKey(1)
    return key == ESC_KEY or key == ord(QUIT_KEY)


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

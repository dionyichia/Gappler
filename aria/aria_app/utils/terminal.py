"""Terminal mode management utilities."""

import sys
import termios
import tty


class TerminalRawMode:
    """Context manager for terminal raw mode to capture individual keypresses."""

    def __enter__(self):
        """Enable raw mode by saving current settings and setting cbreak mode."""
        print("\nEntering Terminal Raw Mode\n")
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        """Restore original terminal settings."""
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        print("\nTerminal Raw Mode exited.")
        return False  # Don't suppress exceptions

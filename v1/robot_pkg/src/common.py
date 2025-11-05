import select
import sys
import termios
import tty

# quit whole program
def exit_keypress():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        ch = sys.stdin.read(1)
        return ch in ('q', '\x1b')
    return False


# fallback to handle exit_keypress
class TerminalRawMode:
    def __enter__(self):
        print("\nEnter Terminal Raw Mode\n")
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        print("\nTerminal zurückgesetzt.")
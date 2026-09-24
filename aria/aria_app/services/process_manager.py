import threading
from multiprocessing import Event, Process
from typing import List


class ProcessManager:
    """Manages multiprocessing processes and threads for the application."""

    def __init__(self):
        self.processes: List[Process] = []
        self.aria_streaming_started = Event()
        self.quit_event = Event()

    def add_process(self, target, args=()) -> Process:
        """Create and track a new process."""
        process = Process(
            target=target,
            args=(self.aria_streaming_started, self.quit_event, *args),
            daemon=True,
        )
        process.start()
        self.processes.append(process)
        return process

    def add_thread(self, target, args=()) -> threading.Thread:
        """Create and track a new thread."""
        thread = threading.Thread(
            target=target,
            args=(self.aria_streaming_started, self.quit_event, *args),
            daemon=True,
        )
        thread.start()
        return thread

    def cleanup(self):
        """Terminate any running processes."""
        self.quit_event.set()
        for process in self.processes:
            if process.is_alive():
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()  # force kill if still alive
                    process.join(timeout=5)

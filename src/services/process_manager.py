import multiprocessing
import threading


class ProcessManager:
    """Manages multiprocessing processes and threads for the application."""

    def __init__(self):
        self.processes = []
        self.threads = []
        self.quit_event = multiprocessing.Event()

    def add_process(self, target, args=(), daemon=True) -> multiprocessing.Process:
        """Create and track a new process."""
        process = multiprocessing.Process(
            target=target, args=(self.quit_event, *args), daemon=daemon
        )
        self.processes.append(process)
        return process

    def add_thread(self, target, args=(), daemon=True) -> threading.Thread:
        """Create and track a new thread."""
        thread = threading.Thread(
            target=target, args=(self.quit_event, *args), daemon=daemon
        )
        self.threads.append(thread)
        return thread

    def start_all(self):
        """Start all registered processes and threads."""
        for thread in self.threads:
            thread.start()
        for process in self.processes:
            process.start()

    def join_all(self):
        """Wait for all processes and threads to complete."""
        for item in self.threads + self.processes:
            if hasattr(item, "is_alive") and item.is_alive():
                item.join()

    def cleanup(self):
        """Terminate any running processes."""
        self.quit_event.set()
        for process in self.processes:
            if process.is_alive():
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()  # force kill if still alive
                    process.join(timeout=5)

    def quit(self):
        self.quit_event.set()

import csv
import threading
from pathlib import Path
from typing import List, Sequence, Union


class CSVWriter:

    def __init__(self, filepath: Union[str, Path], headers: Sequence[str] = None):
        """
        Initialize CSV writer.

        Args:
            filepath: Path to the CSV file
            headers: Optional headers to write. If provided, creates file with headers.
        """
        self.filepath = Path(filepath)
        self._lock = threading.Lock()

        if headers:
            self._initialize_file(headers)

    def _initialize_file(self, headers: Sequence[str]) -> None:
        """Create CSV file with headers."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def write_row(self, data: Sequence) -> None:
        """
        Append a row to the CSV file in a thread-safe manner.

        Args:
            data: Sequence of values to write as a row
        """
        with self._lock:
            with open(self.filepath, mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(data)

    def write_rows(self, data: List[Sequence]) -> None:
        """
        Append multiple rows to the CSV file in a thread-safe manner.

        Args:
            data: List of sequences to write as rows
        """
        with self._lock:
            with open(self.filepath, mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(data)

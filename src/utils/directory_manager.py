import os
import shutil


class DirectoryManager:
    """Handles directory creation and organization for Aria data storage."""

    @staticmethod
    def create_or_reset(path: str) -> None:
        """
        Create directory, removing it first if it exists.

        Args:
            path: Directory path to create
        """
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)
        print(f"Directory created: {path}")

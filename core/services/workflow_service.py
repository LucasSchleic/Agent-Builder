import json
import os
from typing import List

from core.domain.workflow import Workflow


class WorkflowService:
    """Handles persistence of Workflow objects: create, save, load, and list."""

    def create_workflow(self, name: str) -> Workflow:
        """Instantiate and return a new empty Workflow.

        Args:
            name: Display name for the new workflow.
        Returns:
            A fresh Workflow instance with no blocks or connections.
        """
        return Workflow(name=name)

    def save_workflow(self, workflow: Workflow, path: str) -> None:
        """Serialize a workflow to JSON and write it to disk.

        Args:
            workflow: The Workflow instance to persist.
            path: Absolute or relative path to the destination .json file.
        """
        data = workflow.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_as_workflow(self, workflow: Workflow, path: str) -> None:
        """Save a workflow to a new path (Save As).

        Identical to save_workflow at the service level — the distinction
        between Save and Save As is handled by the UI (new path chosen by user).

        Args:
            workflow: The Workflow instance to persist.
            path: New destination path for the .json file.
        """
        self.save_workflow(workflow, path)

    def load_workflow(self, path: str) -> Workflow:
        """Read a JSON file from disk and reconstruct a Workflow instance.

        Args:
            path: Path to the .json file to load.
        Returns:
            A fully reconstructed Workflow instance.
        Raises:
            FileNotFoundError: If the file does not exist.
            KeyError: If required fields are missing from the JSON.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Workflow.from_dict(data)

    def list_workflows(self, directory: str) -> List[str]:
        """Return the filenames of all saved workflows in a directory.

        Args:
            directory: Path to the folder containing .json workflow files.
        Returns:
            List of .json filenames (not full paths).
        """
        return [f for f in os.listdir(directory) if f.endswith(".json")]

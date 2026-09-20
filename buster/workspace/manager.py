"""Scoped workspace scaffolding for agents and capabilities.

Keeps agent-created files isolated under a per-workspace directory and
refuses path traversal outside the workspace root.
"""

import logging
import os
import uuid


class WorkspaceError(Exception):
    pass


class Workspace:
    def __init__(self, workspace_id: str, root: str):
        self.workspace_id = workspace_id
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        self.logger = logging.getLogger("buster.workspace")

    def resolve(self, rel_path: str) -> str:
        candidate = os.path.abspath(os.path.join(self.root, rel_path))
        if candidate != self.root and not candidate.startswith(self.root + os.sep):
            raise WorkspaceError(f"Path escapes workspace: {rel_path}")
        return candidate

    def write(self, rel_path: str, content: str) -> str:
        target = self.resolve(rel_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def read(self, rel_path: str) -> str:
        with open(self.resolve(rel_path), "r", encoding="utf-8") as f:
            return f.read()

    def list_files(self) -> list[str]:
        found = []
        for root, _dirs, files in os.walk(self.root):
            for name in files:
                full = os.path.join(root, name)
                found.append(os.path.relpath(full, self.root))
        return sorted(found)

    def remove(self, rel_path: str) -> None:
        os.remove(self.resolve(rel_path))


class WorkspaceManager:
    """Creates and tracks isolated workspaces."""

    def __init__(self, base_dir: str):
        self._base_dir = os.path.abspath(base_dir)
        os.makedirs(self._base_dir, exist_ok=True)
        self._workspaces: dict[str, Workspace] = {}
        self.logger = logging.getLogger("buster.workspace.manager")

    def create(self, name: str = "") -> Workspace:
        workspace_id = f"{name or 'ws'}-{uuid.uuid4().hex[:8]}"
        root = os.path.join(self._base_dir, workspace_id)
        workspace = Workspace(workspace_id, root)
        self._workspaces[workspace_id] = workspace
        return workspace

    def get(self, workspace_id: str) -> Workspace:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceError(f"Unknown workspace '{workspace_id}'")
        return workspace

    def list_workspaces(self) -> list[str]:
        return sorted(self._workspaces.keys())

    def destroy(self, workspace_id: str) -> None:
        workspace = self.get(workspace_id)
        import shutil
        shutil.rmtree(workspace.root, ignore_errors=True)
        del self._workspaces[workspace_id]
"""Tests for filesystem actions: copy, move, delete."""

from unittest.mock import MagicMock

import pytest
from fs.memoryfs import MemoryFS

from mediariver.actions.copy import CopyAction
from mediariver.actions.delete import DeleteAction
from mediariver.actions.move import MoveAction


@pytest.fixture
def mock_connections():
    source_fs = MemoryFS()
    dest_fs = MemoryFS()
    source_fs.writetext("input.mp4", "video data")
    return {"local": source_fs, "output": dest_fs}


class TestCopyAction:
    def test_copy_within_same_fs(self, mock_connections):
        action = CopyAction()
        ctx = {"_connections": mock_connections}
        params = action.params_model(**{"from": "local://input.mp4", "to": "local://copied.mp4"})
        result = action.run(ctx, params, MagicMock())
        assert result.status == "done"
        assert mock_connections["local"].exists("copied.mp4")

    def test_copy_across_connections(self, mock_connections):
        action = CopyAction()
        ctx = {"_connections": mock_connections}
        params = action.params_model(**{"from": "local://input.mp4", "to": "output://video/input.mp4"})
        result = action.run(ctx, params, MagicMock())
        assert result.status == "done"
        assert mock_connections["output"].exists("video/input.mp4")


class TestMoveAction:
    def test_move_removes_source(self, mock_connections):
        action = MoveAction()
        ctx = {"_connections": mock_connections}
        params = action.params_model(**{"from": "local://input.mp4", "to": "output://moved.mp4"})
        result = action.run(ctx, params, MagicMock())
        assert result.status == "done"
        assert mock_connections["output"].exists("moved.mp4")
        assert not mock_connections["local"].exists("input.mp4")


class TestDeleteAction:
    def test_delete_file(self, mock_connections):
        action = DeleteAction()
        ctx = {"_connections": mock_connections}
        params = action.params_model(**{"path": "local://input.mp4"})
        result = action.run(ctx, params, MagicMock())
        assert result.status == "done"
        assert not mock_connections["local"].exists("input.mp4")

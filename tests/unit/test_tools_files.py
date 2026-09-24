from pathlib import Path

import pytest

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.files import list_files

APP_ROOT = Path("sample_app/loopline/app")


def test_list_files_includes_known_files() -> None:
    files = list_files(root=APP_ROOT)
    assert "notifications.py" in files
    assert "routers/tickets.py" in files


def test_list_files_scoped_to_a_subdirectory() -> None:
    files = list_files("routers", root=APP_ROOT)
    assert all(f.startswith("routers/") for f in files)
    assert "routers/tickets.py" in files
    assert "routers/users.py" in files


def test_list_files_rejects_a_non_directory() -> None:
    with pytest.raises(ToolError, match="not a directory"):
        list_files("notifications.py", root=APP_ROOT)

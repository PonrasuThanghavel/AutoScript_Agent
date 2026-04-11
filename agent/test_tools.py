import pytest
from pathlib import Path
from agent.tools import ToolDispatcher
from agent.validator import ToolName


def test_resolve_path():
    dispatcher = ToolDispatcher("scripts")
    # Valid
    assert dispatcher._resolve_path("test.py").name == "test.py"
    assert dispatcher._resolve_path("sub/test.py").name == "test.py"

    # Valid: leading slash is stripped
    assert dispatcher._resolve_path("/test.py").name == "test.py"

    # Invalid: Traversal
    with pytest.raises(ValueError):
        dispatcher._resolve_path("../test.py")


def test_dispatch_missing_args():
    dispatcher = ToolDispatcher("scripts")
    res = dispatcher.dispatch(ToolName.WRITE_FILE, {"content": "print('hello')"})
    assert "❌ Tool argument error" in res
    assert "filename" in res


def test_timeout_none():
    dispatcher = ToolDispatcher("scripts")
    dispatcher._write_file("test_timeout.py", "print('hello')")

    # Should not crash if timeout is None
    res = dispatcher._execute_script("test_timeout.py", timeout=None)
    assert "hello" in res


def test_read_file_no_markdown():
    dispatcher = ToolDispatcher("scripts")
    dispatcher._write_file("test_read.py", "x = 1")
    res = dispatcher._read_file("test_read.py")
    assert "```python" not in res
    assert "x = 1" in res


def test_relative_path_error():
    dispatcher = ToolDispatcher("scripts")
    res = dispatcher._read_file("nonexistent.py")
    assert "nonexistent.py" in res
    # Ensure no absolute paths
    workspace_str = str(Path("scripts").resolve())
    assert workspace_str not in res


if __name__ == "__main__":
    pytest.main([__file__])

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` so that a crash leaves either the old or the new file, never a partial one.

    The text goes to a temporary file in the same directory first, which then
    replaces `path` in one step. The file gets the usual permissions (0666
    minus the umask) rather than the 0600 of a temporary file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, 0o666 & ~_current_umask())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask

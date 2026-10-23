import os
import stat
from pathlib import Path

from jaa.storage.db import create_db_engine


def test_sqlite_file_created_with_mode_0600(tmp_path: Path) -> None:
    db = tmp_path / "perm.sqlite3"
    create_db_engine(db)
    mode = stat.S_IMODE(os.stat(db).st_mode)
    assert mode == 0o600

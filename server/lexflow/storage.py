"""Where uploaded files live.

``Storage`` is the interface; ``LocalDiskStorage`` keeps files on the local disk.
A later phase can add object storage (e.g. S3) behind the same interface.

Files are stored under a generated key (``uuid4().hex``), never under the name
the user uploaded, so a crafted filename cannot choose where a file is written.
"""

from __future__ import annotations

import re
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from fastapi import Depends

from lexflow.config import Settings, get_settings

KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class Storage(Protocol):
    def new_key(self) -> str: ...

    def staging_file(self) -> AbstractContextManager[tuple[Path, BinaryIO]]:
        """A temporary file on the same volume, removed when the block exits."""
        ...

    def put(self, key: str, staged: Path) -> None:
        """Move a staged file into storage under ``key`` (atomic where possible)."""
        ...

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None:
        """Remove the file if it exists."""
        ...

    def exists(self, key: str) -> bool: ...


class LocalDiskStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.staging = root / ".staging"

    def new_key(self) -> str:
        return uuid.uuid4().hex

    def _path(self, key: str) -> Path:
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError("invalid storage key")
        return self.root / key[:2] / key

    @contextmanager
    def staging_file(self) -> Iterator[tuple[Path, BinaryIO]]:
        self.staging.mkdir(parents=True, exist_ok=True)
        handle = cast(
            BinaryIO,
            tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed in the finally block
                dir=self.staging, prefix="upload-", delete=False
            ),
        )
        path = Path(handle.name)
        try:
            yield path, handle
        finally:
            handle.close()
            path.unlink(missing_ok=True)

    def put(self, key: str, staged: Path) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(target)  # same volume: atomic rename

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def get_storage(settings: Settings = Depends(get_settings)) -> Storage:
    return LocalDiskStorage(settings.upload_dir)

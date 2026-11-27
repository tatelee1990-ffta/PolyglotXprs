"""Load models from an internal source instead of Hugging Face.

Implements upstream's internal model source proposal (#322, see
docs/internal-model-source.md): when the environment variable
ATRAIN_MODEL_SOURCE is set, aTrain fetches models only from there and never
contacts Hugging Face. The source is a plain file server (any
web server that serves files by URL) or a folder, for example a network share,
with the same layout as a local models folder:

    <source>/<model>/<file listed in models.json>

No API, directory listing or authentication is needed: aTrain requests only the
files that models.json lists for a model, and get_model() verifies every one of
them against the SHA-256 pinned in models.json afterwards. A wrong or
compromised source therefore cannot swap the weights; verification fails and
the files are removed.
"""

from __future__ import annotations

import os
from collections.abc import Callable, MutableMapping
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit

from aTrain_core.integrity import OPTIONAL_FILES

ENV_VAR = "ATRAIN_MODEL_SOURCE"
CHUNK_SIZE = 1024 * 1024
HTTP_TIMEOUT_SECONDS = 60.0
URL_SCHEMES = {"http", "https"}
INCOMPLETE_SUFFIX = ".incomplete"


class ModelSourceError(Exception):
    """The configured model source is invalid or does not hold a required file."""


def configured_source() -> str | None:
    """The configured model source, or None when models come from Hugging Face.

    Read on every call rather than at import, so a Group Policy change or a test
    takes effect without reloading modules.
    """
    value = os.environ.get(ENV_VAR, "").strip()
    return value or None


def is_url(source: str) -> bool:
    """True for an http(s) source, False for a path. Rejects other URL schemes."""
    scheme = urlsplit(source).scheme.lower()
    if scheme in URL_SCHEMES:
        return True
    # A Windows drive letter ("C:\\models") parses as a one-letter scheme.
    if "://" in source:
        raise ModelSourceError(
            f"{ENV_VAR} uses an unsupported scheme {scheme!r}. "
            "Use an http(s) URL or a folder path such as \\\\server\\share\\models."
        )
    return False


def _relative_path(name: str) -> PurePosixPath:
    """A manifest file name as a relative path that cannot leave the model folder."""
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ("", ".", "..") for p in path.parts):
        raise ModelSourceError(f"Refusing unsafe file name in models.json: {name!r}")
    if any("\\" in part or ":" in part for part in path.parts):
        raise ModelSourceError(f"Refusing unsafe file name in models.json: {name!r}")
    return path


def file_location(source: str, model: str, name: str) -> str:
    """Where a model file is expected at the source, as a URL or a path."""
    relative = _relative_path(name)
    if is_url(source):
        quoted = "/".join(quote(part) for part in (model, *relative.parts))
        return f"{source.rstrip('/')}/{quoted}"
    return str(Path(source, model, *relative.parts))


def model_location(source: str, model: str) -> str:
    """Where a model folder is expected at the source, for display."""
    if is_url(source):
        return f"{source.rstrip('/')}/{quote(model)}/"
    return str(Path(source, model))


def _copy_file(location: str, target: Path, on_bytes: Callable[[int], None]) -> bool:
    source_file = Path(location)
    if not source_file.is_file():
        return False
    with source_file.open("rb") as reader, target.open("wb") as writer:
        while chunk := reader.read(CHUNK_SIZE):
            writer.write(chunk)
            on_bytes(len(chunk))
    return True


def _get_file(location: str, target: Path, on_bytes: Callable[[int], None]) -> bool:
    # huggingface_hub's shared client carries the proxy and CA settings that the
    # rest of aTrain uses. It sends no token unless one is passed explicitly.
    from huggingface_hub.utils import get_session

    client = get_session()
    with client.stream(
        "GET", location, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True
    ) as response:
        if response.status_code == 404:
            return False
        response.raise_for_status()
        with target.open("wb") as writer:
            for chunk in response.iter_bytes(CHUNK_SIZE):
                writer.write(chunk)
                on_bytes(len(chunk))
    return True


def download_from_source(
    source: str,
    model: str,
    model_path: Path,
    manifest: dict[str, str],
    progress: MutableMapping | None = None,
    total_bytes: int | None = None,
) -> None:
    """Fetch every manifest file of a model from the source into model_path.

    Files are written under a temporary name and moved into place once complete,
    like huggingface_hub does, so an interrupted download leaves files missing
    rather than truncated and the next call resumes it. Files that are already in
    place are kept; get_model() verifies all of them afterwards. Optional files
    (see integrity.OPTIONAL_FILES) may be absent at the source.
    """
    fetch = _get_file if is_url(source) else _copy_file
    if progress is not None:
        progress["current"] = 0
        if total_bytes:
            progress["total"] = total_bytes

    def on_bytes(count: int) -> None:
        if progress is not None:
            progress["current"] = progress.get("current", 0) + count

    model_path.mkdir(parents=True, exist_ok=True)
    remove_incomplete_files(model_path)
    root = model_path.resolve()
    for name in sorted(manifest):
        target = model_path.joinpath(*_relative_path(name).parts)
        if not target.resolve().is_relative_to(root):
            raise ModelSourceError(f"Refusing file outside the model folder: {name!r}")
        if target.is_file():
            on_bytes(target.stat().st_size)  # counts toward the bar when resuming
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + INCOMPLETE_SUFFIX)
        location = file_location(source, model, name)
        try:
            found = fetch(location, partial, on_bytes)
            if not found:
                if name in OPTIONAL_FILES:
                    continue
                raise ModelSourceError(
                    f"Model '{model}' is incomplete at the internal source: {location} "
                    f"was not found. Ask your IT department to copy the complete "
                    f"model folder to {model_location(source, model)}."
                )
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)


def remove_incomplete_files(model_path: Path) -> None:
    """Remove temporary files that a killed process left behind."""
    if model_path.is_dir():
        for leftover in model_path.rglob(f"*{INCOMPLETE_SUFFIX}"):
            if leftover.is_file():
                leftover.unlink(missing_ok=True)

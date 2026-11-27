"""Tests for loading models from an internal source (ATRAIN_MODEL_SOURCE).

Covers both kinds of source in docs/internal-model-source.md: a
folder (a temp dir standing in for a network share) and a plain web server
(Python's http.server on localhost). Hugging Face is stubbed to fail, so any
attempt to contact it while a source is configured fails the test.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import threading
from pathlib import Path

import pytest
from aTrain_core import load_resources, model_source
from aTrain_core.integrity import ModelIntegrityError
from aTrain_core.model_source import ModelSourceError

MODEL = "test-model"
FILES = {
    ".gitattributes": b"*.bin filter=lfs\n",
    "config.json": b'{"name": "test"}\n',
    "model.bin": b"\x00\x01weights" * 1000,
    "embedding/pytorch_model.bin": b"nested weights" * 500,
}


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def fill_source(root: Path, files: dict[str, bytes] = FILES) -> Path:
    for name, data in files.items():
        path = root / MODEL / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    """A models.json with one test model, a temp models dir, and no Hugging Face."""
    config = {
        MODEL: {
            "repo_id": "aTrain-core/test-model",
            "revision": "0" * 40,
            "license": "MIT",
            "backend": "faster-whisper",
            "repo_size": sum(len(data) for data in FILES.values()),
            "files": {name: sha256(data) for name, data in FILES.items()},
        }
    }
    directory = tmp_path / "models"
    monkeypatch.setattr(load_resources, "load_model_config_file", lambda: config)
    monkeypatch.setattr(load_resources, "MODELS_DIR", directory)
    monkeypatch.setattr(load_resources, "REQUIRED_MODELS_DIR", directory)

    def no_hub(**kwargs):
        raise AssertionError("Hugging Face must not be contacted with a model source set")

    monkeypatch.setattr(load_resources, "snapshot_download", no_hub)
    return directory


@pytest.fixture
def web_source(tmp_path):
    """Serve a filled source folder over plain HTTP on localhost."""
    root = fill_source(tmp_path / "served")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


# --- configuration --------------------------------------------------------------


def test_no_source_by_default(monkeypatch):
    monkeypatch.delenv(model_source.ENV_VAR, raising=False)
    assert model_source.configured_source() is None


def test_blank_source_counts_as_unset(monkeypatch):
    monkeypatch.setenv(model_source.ENV_VAR, "   ")
    assert model_source.configured_source() is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("https://models.example.org/atrain/", True),
        ("http://models.internal/atrain", True),
        ("\\\\fileserver\\atrain\\models", False),
        ("C:\\aTrain\\models", False),
        ("/srv/atrain/models", False),
    ],
)
def test_is_url(source, expected):
    assert model_source.is_url(source) is expected


def test_other_schemes_are_rejected():
    with pytest.raises(ModelSourceError, match="unsupported scheme"):
        model_source.is_url("ftp://models.example.org/")


@pytest.mark.parametrize("name", ["../evil.bin", "/etc/passwd", "a/../../b", "dir\\file", "C:x"])
def test_unsafe_manifest_names_are_refused(name):
    with pytest.raises(ModelSourceError, match="unsafe"):
        model_source.file_location("https://models.example.org/", MODEL, name)


def test_url_parts_are_quoted():
    location = model_source.file_location("https://example.org/m/", "my model", "a b/c.bin")
    assert location == "https://example.org/m/my%20model/a%20b/c.bin"


# --- folder source --------------------------------------------------------------


def test_get_model_from_folder_source(tmp_path, models_dir, monkeypatch):
    monkeypatch.setenv(model_source.ENV_VAR, str(fill_source(tmp_path / "share")))
    progress = {"current": 0, "total": 999999}

    path = load_resources.get_model(MODEL, progress=progress)

    assert path == models_dir / MODEL
    for name, data in FILES.items():
        assert (path / name).read_bytes() == data
    assert progress["total"] == sum(len(data) for data in FILES.values())
    assert progress["current"] == progress["total"]
    assert not list(path.rglob("*.incomplete"))


def test_optional_files_may_be_absent_at_the_source(tmp_path, models_dir, monkeypatch):
    without_optional = {k: v for k, v in FILES.items() if k != ".gitattributes"}
    monkeypatch.setenv(model_source.ENV_VAR, str(fill_source(tmp_path / "share", without_optional)))

    path = load_resources.get_model(MODEL)

    assert (path / "model.bin").is_file()
    assert not (path / ".gitattributes").exists()


def test_missing_required_file_names_the_location(tmp_path, models_dir, monkeypatch):
    incomplete = {k: v for k, v in FILES.items() if k != "model.bin"}
    monkeypatch.setenv(model_source.ENV_VAR, str(fill_source(tmp_path / "share", incomplete)))

    with pytest.raises(ModelSourceError, match=r"model\.bin"):
        load_resources.get_model(MODEL)


def test_tampered_file_fails_verification_and_is_removed(tmp_path, models_dir, monkeypatch):
    tampered = {**FILES, "model.bin": b"swapped weights"}
    monkeypatch.setenv(model_source.ENV_VAR, str(fill_source(tmp_path / "share", tampered)))

    with pytest.raises(ModelIntegrityError, match=r"model\.bin"):
        load_resources.get_model(MODEL)
    assert not (models_dir / MODEL).exists()


def test_interrupted_download_resumes(tmp_path, models_dir, monkeypatch):
    monkeypatch.setenv(model_source.ENV_VAR, str(fill_source(tmp_path / "share")))
    # A killed process leaves complete files in place plus a temporary file.
    target = models_dir / MODEL
    target.mkdir(parents=True)
    (target / "config.json").write_bytes(FILES["config.json"])
    (target / "model.bin.incomplete").write_bytes(b"half")

    progress = {"current": 0, "total": 999999}

    path = load_resources.get_model(MODEL, progress=progress)

    assert (path / "model.bin").read_bytes() == FILES["model.bin"]
    assert not (path / "model.bin.incomplete").exists()
    assert progress["current"] == progress["total"]  # files already in place count


def test_model_already_present_needs_no_source(models_dir, monkeypatch):
    # Offline after setup: a complete model is used without touching any source.
    monkeypatch.setenv(model_source.ENV_VAR, "https://unreachable.invalid/")
    for name, data in FILES.items():
        path = models_dir / MODEL / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    assert load_resources.get_model(MODEL) == models_dir / MODEL


# --- web source -----------------------------------------------------------------


def test_get_model_from_web_source(web_source, models_dir, monkeypatch):
    monkeypatch.setenv(model_source.ENV_VAR, web_source)

    path = load_resources.get_model(MODEL)

    for name, data in FILES.items():
        assert (path / name).read_bytes() == data


def test_web_source_404_for_required_file(tmp_path, web_source, models_dir, monkeypatch):
    monkeypatch.setenv(model_source.ENV_VAR, web_source + "missing-subdir/")

    with pytest.raises(ModelSourceError, match="was not found"):
        load_resources.get_model(MODEL)


# --- Models page ----------------------------------------------------------------


def test_models_page_names_hugging_face_without_a_source(monkeypatch):
    from aTrain.utils.models import model_source_info

    monkeypatch.delenv(model_source.ENV_VAR, raising=False)
    info = model_source_info(MODEL, {"repo_id": "aTrain-core/test", "revision": "abc"})
    assert info == {
        "source": "Hugging Face",
        "source_url": "https://huggingface.co/aTrain-core/test/tree/abc",
    }


def test_models_page_names_the_internal_source(monkeypatch):
    from aTrain.utils.models import model_source_info

    monkeypatch.setenv(model_source.ENV_VAR, "https://models.example.org/atrain")
    info = model_source_info(MODEL, {"repo_id": "aTrain-core/test", "revision": "abc"})
    assert info["source_url"] == "https://models.example.org/atrain/test-model/"
    assert "huggingface" not in str(info).lower()


def test_models_page_links_no_folder_source(monkeypatch, tmp_path):
    from aTrain.utils.models import model_source_info

    monkeypatch.setenv(model_source.ENV_VAR, str(tmp_path))
    info = model_source_info(MODEL, {"repo_id": "aTrain-core/test", "revision": "abc"})
    assert "source_url" not in info
    assert str(tmp_path) in info["source"]


def test_models_page_shows_an_invalid_source_instead_of_failing(monkeypatch):
    from aTrain.utils.models import model_source_info

    monkeypatch.setenv(model_source.ENV_VAR, "ftp://models.example.org/")
    info = model_source_info(MODEL, {"repo_id": "aTrain-core/test", "revision": "abc"})
    assert info["source"].startswith("Invalid internal source")
    assert "source_url" not in info

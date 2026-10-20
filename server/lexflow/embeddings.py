"""Embeddings for document chunks: the local model and whether it can run.

Embeddings are off by default (``LEXFLOW_EMBEDDINGS=disabled``): chunks are
stored without vectors and their index status is "disabled". With
``LEXFLOW_EMBEDDINGS=local`` the worker embeds chunks with
``BAAI/bge-small-en-v1.5`` (384 dimensions, MIT licence) on this computer:
the official ONNX export run by onnxruntime on the CPU, with the model's own
tokenizer. Nothing is sent to another service.

The model files are pinned to one revision of the model repository and
checked by SHA-256 (``MANIFEST``). They are downloaded only by
``python -m lexflow.cli.models download``; loading reads local files only, so
the worker and the API can never download anything. The vectors are stored in
PostgreSQL with pgvector (migration 0009; ADR 0016).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from lexflow.config import Settings

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
DIMENSIONS = 384
MAX_TOKENS = 512
# The model's instruction for short queries that look for longer passages.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
SOURCE_URL = "https://huggingface.co/{name}/resolve/{revision}/{path}"


@dataclass(frozen=True)
class ModelFile:
    path: str
    size: int
    sha256: str


MANIFEST: tuple[ModelFile, ...] = (
    ModelFile(
        "onnx/model.onnx",
        133_093_490,
        "828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35",
    ),
    ModelFile(
        "tokenizer.json",
        711_396,
        "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    ),
    ModelFile(
        "config.json", 743, "094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750"
    ),
    ModelFile(
        "1_Pooling/config.json",
        190,
        "d1caf60c96f5fba2157c0c26b76d80818fad6cf0b8eb5e73ec372ff9818eba5c",
    ),
)

# Stored with every vector: vectors from different models are never compared.
MODEL_KEY = f"{MODEL_NAME}@{MODEL_REVISION[:12]}"

DOWNLOAD_HINT = "Download it with: python -m lexflow.cli.models download --confirm"


class EmbeddingsUnavailableError(Exception):
    """The configured embeddings cannot be produced or stored here."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turns texts into unit-length vectors, on this computer."""

    model: str
    dimensions: int

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per passage, in the same order."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """The vector of a search query."""
        ...


def model_path(settings: Settings) -> Path:
    """Where the pinned model files live (``<model_dir>/<name>/<revision>``)."""
    return settings.model_dir / MODEL_NAME / MODEL_REVISION


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_files(root: Path) -> list[str]:
    """Problems with the local model files (empty when all are present and intact)."""
    problems = []
    for item in MANIFEST:
        path = root / item.path
        if not path.is_file():
            problems.append(f"{item.path} is missing")
        elif path.stat().st_size != item.size:
            problems.append(f"{item.path} has the wrong size (an interrupted download?)")
        elif sha256_of(path) != item.sha256:
            problems.append(f"{item.path} does not match its SHA-256")
    return problems


class LocalBgeProvider:
    """``BAAI/bge-small-en-v1.5``: CLS pooling, L2-normalised, CPU only."""

    model = MODEL_KEY
    dimensions = DIMENSIONS

    def __init__(self, root: Path, *, threads: int, batch_size: int) -> None:
        problems = check_files(root)
        if problems:
            raise EmbeddingsUnavailableError(
                f"The embedding model is not ready ({'; '.join(problems)}). {DOWNLOAD_HINT}"
            )
        try:
            import numpy  # noqa: F401 - checked here so the message is clear
            import onnxruntime
            from tokenizers import Tokenizer
        except ImportError as exc:  # pragma: no cover - dependencies are pinned
            raise EmbeddingsUnavailableError(
                f"A dependency of the embedding model is missing ({exc.name}). "
                "Install the pinned requirements: pip-sync requirements.txt"
            ) from exc
        self.batch_size = batch_size
        tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
        tokenizer.enable_truncation(max_length=MAX_TOKENS)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")  # noqa: S106 - a token, not a password
        self._tokenizer = tokenizer
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        try:
            self._session = onnxruntime.InferenceSession(
                str(root / "onnx" / "model.onnx"),
                sess_options=options,
                providers=["CPUExecutionProvider"],  # never a remote provider
            )
        except Exception as exc:
            raise EmbeddingsUnavailableError(
                f"The embedding model could not be loaded: {exc}. {DOWNLOAD_HINT}"
            ) from exc
        self._inputs = {i.name for i in self._session.get_inputs()}

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        import numpy as np

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [t if t.strip() else " " for t in texts[start : start + self.batch_size]]
            encodings = self._tokenizer.encode_batch(batch)
            feeds: dict[str, Any] = {
                "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
            }
            outputs = self._session.run(None, {k: v for k, v in feeds.items() if k in self._inputs})
            cls = np.asarray(outputs[0])[:, 0, :]
            if cls.shape != (len(batch), DIMENSIONS) or not np.isfinite(cls).all():
                raise EmbeddingsUnavailableError(
                    f"The embedding model returned an unexpected result (shape {cls.shape})."
                )
            norms = np.linalg.norm(cls, axis=1, keepdims=True)
            vectors.extend((cls / np.maximum(norms, 1e-12)).astype(float).tolist())
        return vectors

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._embed([QUERY_INSTRUCTION + text])[0]


def provider_for(settings: Settings) -> EmbeddingProvider | None:
    """The provider the settings ask for; ``None`` when embeddings are off.

    Raises ``EmbeddingsUnavailableError`` (with what to do) when ``local`` is
    asked for but the model files are missing or damaged, or an unknown model
    is configured, so the worker refuses to start instead of marking chunks
    "pending" that nothing would ever index. Never downloads.
    """
    if settings.embeddings == "disabled":
        return None
    if settings.embedding_model != MODEL_NAME:
        raise EmbeddingsUnavailableError(
            f"Only {MODEL_NAME} is supported (LEXFLOW_EMBEDDING_MODEL is "
            f"{settings.embedding_model!r})."
        )
    return LocalBgeProvider(
        model_path(settings),
        threads=settings.embedding_threads,
        batch_size=settings.embedding_batch_size,
    )


def check_database(session: Session) -> None:
    """Refuse when the database cannot store vectors (migration 0009 not applied)."""
    from sqlalchemy import text

    if session.scalar(text("SELECT to_regclass('document_chunk_embeddings')")) is None:
        raise EmbeddingsUnavailableError(
            "This database cannot store embeddings yet: apply migration 0009 "
            "(alembic upgrade head) on a PostgreSQL server with pgvector."
        )

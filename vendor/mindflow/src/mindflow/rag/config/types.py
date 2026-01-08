"""Type definitions for RAG configuration."""

from typing import TYPE_CHECKING, Annotated, TypeAlias

from pydantic import Field

from mindflow.rag.config.constants import DISCRIMINATOR


# Linter freaks out on conditional imports, assigning in the type checking fixes it
if TYPE_CHECKING:
    from mindflow.rag.chromadb.config import ChromaDBConfig as ChromaDBConfig_

    ChromaDBConfig = ChromaDBConfig_
    from mindflow.rag.qdrant.config import QdrantConfig as QdrantConfig_

    QdrantConfig = QdrantConfig_
else:
    try:
        from mindflow.rag.chromadb.config import ChromaDBConfig
    except ImportError:
        from mindflow.rag.config.optional_imports.providers import (
            MissingChromaDBConfig as ChromaDBConfig,
        )

    try:
        from mindflow.rag.qdrant.config import QdrantConfig
    except ImportError:
        from mindflow.rag.config.optional_imports.providers import (
            MissingQdrantConfig as QdrantConfig,
        )

SupportedProviderConfig: TypeAlias = ChromaDBConfig | QdrantConfig
RagConfigType: TypeAlias = Annotated[
    SupportedProviderConfig, Field(discriminator=DISCRIMINATOR)
]

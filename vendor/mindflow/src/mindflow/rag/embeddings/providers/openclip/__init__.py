"""OpenCLIP embedding providers."""

from mindflow.rag.embeddings.providers.openclip.openclip_provider import (
    OpenCLIPProvider,
)
from mindflow.rag.embeddings.providers.openclip.types import (
    OpenCLIPProviderConfig,
    OpenCLIPProviderSpec,
)


__all__ = [
    "OpenCLIPProvider",
    "OpenCLIPProviderConfig",
    "OpenCLIPProviderSpec",
]

"""Microsoft embedding providers."""

from mindflow.rag.embeddings.providers.microsoft.azure import (
    AzureProvider,
)
from mindflow.rag.embeddings.providers.microsoft.types import (
    AzureProviderConfig,
    AzureProviderSpec,
)


__all__ = [
    "AzureProvider",
    "AzureProviderConfig",
    "AzureProviderSpec",
]

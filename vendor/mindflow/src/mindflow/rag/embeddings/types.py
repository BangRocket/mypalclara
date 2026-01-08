"""Type definitions for the embeddings module."""

from typing import Any, Literal, TypeAlias

from mindflow.rag.core.base_embeddings_provider import BaseEmbeddingsProvider
from mindflow.rag.embeddings.providers.aws.types import BedrockProviderSpec
from mindflow.rag.embeddings.providers.cohere.types import CohereProviderSpec
from mindflow.rag.embeddings.providers.custom.types import CustomProviderSpec
from mindflow.rag.embeddings.providers.google.types import (
    GenerativeAiProviderSpec,
    VertexAIProviderSpec,
)
from mindflow.rag.embeddings.providers.huggingface.types import HuggingFaceProviderSpec
from mindflow.rag.embeddings.providers.ibm.types import (
    WatsonXProviderSpec,
)
from mindflow.rag.embeddings.providers.instructor.types import InstructorProviderSpec
from mindflow.rag.embeddings.providers.jina.types import JinaProviderSpec
from mindflow.rag.embeddings.providers.microsoft.types import AzureProviderSpec
from mindflow.rag.embeddings.providers.ollama.types import OllamaProviderSpec
from mindflow.rag.embeddings.providers.onnx.types import ONNXProviderSpec
from mindflow.rag.embeddings.providers.openai.types import OpenAIProviderSpec
from mindflow.rag.embeddings.providers.openclip.types import OpenCLIPProviderSpec
from mindflow.rag.embeddings.providers.roboflow.types import RoboflowProviderSpec
from mindflow.rag.embeddings.providers.sentence_transformer.types import (
    SentenceTransformerProviderSpec,
)
from mindflow.rag.embeddings.providers.text2vec.types import Text2VecProviderSpec
from mindflow.rag.embeddings.providers.voyageai.types import VoyageAIProviderSpec


ProviderSpec: TypeAlias = (
    AzureProviderSpec
    | BedrockProviderSpec
    | CohereProviderSpec
    | CustomProviderSpec
    | GenerativeAiProviderSpec
    | HuggingFaceProviderSpec
    | InstructorProviderSpec
    | JinaProviderSpec
    | OllamaProviderSpec
    | ONNXProviderSpec
    | OpenAIProviderSpec
    | OpenCLIPProviderSpec
    | RoboflowProviderSpec
    | SentenceTransformerProviderSpec
    | Text2VecProviderSpec
    | VertexAIProviderSpec
    | VoyageAIProviderSpec
    | WatsonXProviderSpec
)

AllowedEmbeddingProviders = Literal[
    "azure",
    "amazon-bedrock",
    "cohere",
    "custom",
    "google-generativeai",
    "google-vertex",
    "huggingface",
    "instructor",
    "jina",
    "ollama",
    "onnx",
    "openai",
    "openclip",
    "roboflow",
    "sentence-transformer",
    "text2vec",
    "voyageai",
    "watsonx",
]

EmbedderConfig: TypeAlias = (
    ProviderSpec | BaseEmbeddingsProvider[Any] | type[BaseEmbeddingsProvider[Any]]
)

"""Memory/Rook configuration models."""

from pydantic import BaseModel, Field


class RookProviderSettings(BaseModel):
    provider: str = "openrouter"
    model: str = "openai/gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""


class VectorStoreSettings(BaseModel):
    database_url: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    collection_name: str = "clara_memories"
    migration_mode: str = "primary_only"


class GraphStoreSettings(BaseModel):
    enabled: bool = False
    provider: str = "falkordb"
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    falkordb_graph_name: str = "clara_memory"


class EmbeddingSettings(BaseModel):
    model: str = "text-embedding-3-small"
    cache_enabled: bool = True


class MemorySettings(BaseModel):
    rook: RookProviderSettings = Field(default_factory=RookProviderSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    graph_store: GraphStoreSettings = Field(default_factory=GraphStoreSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    skip_profile_load: bool = True
    redis_url: str = ""

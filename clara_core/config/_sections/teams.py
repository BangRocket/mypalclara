"""Microsoft Teams configuration models."""

from pydantic import BaseModel


class TeamsSettings(BaseModel):
    app_id: str = ""
    app_password: str = ""
    app_type: str = "MultiTenant"
    app_tenant_id: str = ""
    port: int = 3978

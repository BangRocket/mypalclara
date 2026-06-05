"""Client-side id helpers, vendored from mypalclara.db.models."""

from __future__ import annotations

import uuid


def gen_uuid() -> str:
    return str(uuid.uuid4())

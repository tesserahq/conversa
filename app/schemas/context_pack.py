"""Pydantic schemas for Context Pack API contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class MergeableContextPack(BaseModel):
    """
    Validated pack structure for merge input.
    All packs passed to merge_packs must conform to this schema.
    """

    source_id: str = ""
    schema_version: str = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    facts: dict[str, Any] = Field(default_factory=dict)
    recents: dict[str, Any] = Field(default_factory=dict)
    pointers: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> MergeableContextPack:
        """Parse and validate a raw dict into MergeableContextPack."""
        generated_at = data.get("generated_at")
        if isinstance(generated_at, str):
            generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        elif not isinstance(generated_at, datetime):
            generated_at = datetime.now(timezone.utc)
        return cls(
            source_id=data.get("source_id", ""),
            schema_version=data.get("schema_version", "1.0"),
            generated_at=generated_at,
            facts=data.get("facts") or {},
            recents=data.get("recents") or {},
            pointers=data.get("pointers") or {},
        )


class MergedContextPayload(BaseModel):
    """
    Validated merged payload from merge_packs.
    Stored in context_snapshots.payload (use to_snapshot_dict for JSONB).
    """

    schema_version: str = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    facts: dict[str, Any] = Field(default_factory=dict)
    recents: dict[str, Any] = Field(default_factory=dict)
    pointers: dict[str, list[str]] = Field(default_factory=dict)

    def to_snapshot_dict(self) -> dict[str, Any]:
        """Convert to dict for context_snapshots.payload (JSONB storage)."""
        return self.model_dump(mode="json")


class ContextPackSubject(BaseModel):
    """Subject of the context pack."""

    type: str = "user"
    id: str


class ContextPackSourceInfo(BaseModel):
    """Per-source metadata in the context pack response."""

    source_id: str
    version: Optional[str] = None
    etag: Optional[str] = None


class ContextPackResponse(BaseModel):
    """Context Pack API response schema."""

    schema_version: str
    generated_at: datetime
    audience: str = "conversa"
    subject: Optional[ContextPackSubject] = None
    sources: Optional[dict[str, Any]] = None
    facts: Optional[dict[str, Any]] = None
    recents: Optional[dict[str, Any]] = None
    pointers: Optional[dict[str, list[str]]] = None

    def to_mergeable_pack(self, source_id: str = "") -> MergeableContextPack:
        """Convert to MergeableContextPack for merge."""
        return MergeableContextPack(
            source_id=source_id,
            schema_version=self.schema_version,
            generated_at=self.generated_at,
            facts=self.facts or {},
            recents=self.recents or {},
            pointers=self.pointers or {},
        )


# Validation limits from conversa-context.md
FACTS_MAX_BYTES = 8 * 1024  # 8KB
RECENTS_MAX_COUNT = 50
POINTERS_MAX_PER_CATEGORY = 100

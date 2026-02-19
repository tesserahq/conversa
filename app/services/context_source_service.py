"""Service for context source CRUD."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.models.context_source import ContextSource
from app.schemas.context_source import ContextSourceCreate, ContextSourceUpdate
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters


class ContextSourceService(SoftDeleteService[ContextSource]):
    """Manages context sources for the Source Registry."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ContextSource)

    def get_context_source(self, source_id: UUID) -> Optional[ContextSource]:
        """Fetch a context source by ID."""
        return (
            self.db.query(ContextSource).filter(ContextSource.id == source_id).first()
        )

    def get_context_source_by_source_id(
        self,
        source_id: str,
    ) -> Optional[ContextSource]:
        """Fetch a context source by source_id (e.g. linden-api)."""
        return (
            self.db.query(ContextSource)
            .filter(ContextSource.source_id == source_id)
            .first()
        )

    def get_context_sources(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ContextSource]:
        """List context sources with pagination."""
        return (
            self.db.query(ContextSource)
            .order_by(ContextSource.source_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_context_sources_query(self) -> Query[ContextSource]:
        """Get a query for context sources (for pagination)."""
        return self.db.query(ContextSource).order_by(ContextSource.source_id)

    def create_context_source(
        self,
        data: ContextSourceCreate,
    ) -> ContextSource:
        """Create a context source. Raises ValueError if source_id exists."""
        if self.get_context_source_by_source_id(data.source_id) is not None:
            raise ValueError(
                f"Context source with source_id {data.source_id!r} already exists"
            )

        capabilities = None
        if data.capabilities is not None:
            capabilities = data.capabilities.model_dump()

        source = ContextSource(
            source_id=data.source_id,
            display_name=data.display_name,
            base_url=data.base_url,
            credential_id=data.credential_id,
            capabilities=capabilities,
            poll_interval_seconds=data.poll_interval_seconds,
            enabled=data.enabled,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def update_context_source(
        self,
        source_id: UUID,
        data: ContextSourceUpdate,
    ) -> Optional[ContextSource]:
        """Update a context source. Raises ValueError if new source_id exists."""
        source = self.get_context_source(source_id)
        if not source:
            return None

        if data.source_id is not None and data.source_id != source.source_id:
            if self.get_context_source_by_source_id(data.source_id) is not None:
                raise ValueError(
                    f"Context source with source_id {data.source_id!r} already exists"
                )
            source.source_id = data.source_id

        if data.display_name is not None:
            source.display_name = data.display_name
        if data.base_url is not None:
            source.base_url = data.base_url
        if "credential_id" in data.model_fields_set:
            source.credential_id = data.credential_id
        if data.capabilities is not None:
            source.capabilities = data.capabilities.model_dump()
        if data.poll_interval_seconds is not None:
            source.poll_interval_seconds = data.poll_interval_seconds
        if data.enabled is not None:
            source.enabled = data.enabled

        self.db.commit()
        self.db.refresh(source)
        return source

    def delete_context_source(self, source_id: UUID) -> bool:
        """Soft delete a context source."""
        return self.delete_record(source_id)

    def search(self, filters: Dict[str, Any]) -> List[ContextSource]:
        """Search context sources by filters."""
        query = self.db.query(ContextSource)
        query = apply_filters(query, ContextSource, filters)
        return query.all()

"""Command to sync context packs for a user from all enabled sources."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.adapters.context_pack_fetcher import ContextPackFetcher, FetchResult
from app.models.context_source import ContextSource, ContextSourceState
from app.schemas.context_pack import MergeableContextPack
from app.utils.metrics import CONTEXT_PACK_PAYLOAD_BYTES, CONTEXT_SYNC_TOTAL
from app.services.context_merge_service import ContextMergeService
from app.services.context_snapshot_service import ContextSnapshotService
from app.services.context_source_service import ContextSourceService
from app.services.context_source_state_service import ContextSourceStateService
from app.services.credential_service import CredentialService


class SyncContextForUserCommand:
    """
    Command to sync context packs from all enabled sources for a user,
    merge them, and store the snapshot.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.logger = logging.getLogger(__name__)

    def execute(self, user_id: UUID) -> Optional[UUID]:
        """
        Execute the sync for the given user.

        Args:
            user_id: The user to sync context for

        Returns:
            UUID: The user_id on success
            None: If no enabled sources exist (nothing to sync) or if all
                  sources failed (e.g. HTTP 401)
        """
        source_svc = ContextSourceService(self.db)
        state_svc = ContextSourceStateService(
            self.db, context_source_service=source_svc
        )
        fetcher = ContextPackFetcher(CredentialService(self.db))
        merge_svc = ContextMergeService()
        snapshot_svc = ContextSnapshotService(self.db)

        sources = self._get_enabled_sources(source_svc)
        if not sources:
            self.logger.debug("No enabled context sources for user %s", user_id)
            return user_id

        packs_to_merge, had_fetch_errors = self._fetch_packs_from_sources(
            user_id, sources, state_svc, fetcher
        )
        if not packs_to_merge:
            if had_fetch_errors:
                self.logger.warning(
                    "Context sync failed for user=%s: all sources returned errors",
                    user_id,
                )
                return None
            self.logger.debug("No packs to merge for user %s", user_id)
            return user_id

        self._merge_and_store_snapshot(user_id, packs_to_merge, merge_svc, snapshot_svc)
        self.logger.info("Context snapshot stored for user=%s", user_id)
        return user_id

    def _get_enabled_sources(
        self, source_svc: ContextSourceService
    ) -> List[ContextSource]:
        """Return enabled context sources."""
        return [
            s for s in source_svc.get_context_sources(skip=0, limit=100) if s.enabled
        ]

    def _fetch_packs_from_sources(
        self,
        user_id: UUID,
        sources: List[ContextSource],
        state_svc: ContextSourceStateService,
        fetcher: ContextPackFetcher,
    ) -> tuple[List[MergeableContextPack], bool]:
        """Fetch context packs from all sources and collect successful ones.

        Returns:
            (packs_to_merge, had_fetch_errors) - had_fetch_errors is True if any
            source returned an error (e.g. HTTP 401), used to distinguish
            "all 304" from "all failed" when packs_to_merge is empty.
        """
        packs_to_merge: List[MergeableContextPack] = []
        had_fetch_errors = False
        now = datetime.now(timezone.utc)

        for source in sources:
            state = state_svc.get_or_create_state(UUID(str(source.id)), user_id)
            result = fetcher.fetch(user_id, source, state)
            if result.error:
                had_fetch_errors = True
            pack = self._process_fetch_result(
                user_id, source, state, result, state_svc, now
            )
            if pack is not None:
                packs_to_merge.append(pack)

        return packs_to_merge, had_fetch_errors

    def _process_fetch_result(
        self,
        user_id: UUID,
        source: ContextSource,
        state: ContextSourceState,
        result: FetchResult,
        state_svc: ContextSourceStateService,
        now: datetime,
    ) -> Optional[MergeableContextPack]:
        """Process fetch result, update state, return pack if successful."""
        if result.error:
            self._handle_fetch_error(
                user_id, source, state, result.error, state_svc, now
            )
            return None

        if result.not_modified:
            self._handle_not_modified(source, state, state_svc, now)
            return None

        if result.payload:
            return self._handle_fetch_success(
                user_id, source, state, result, state_svc, now
            )

        return None

    def _handle_fetch_error(
        self,
        user_id: UUID,
        source: ContextSource,
        state: ContextSourceState,
        error: str,
        state_svc: ContextSourceStateService,
        now: datetime,
    ) -> None:
        """Handle fetch error: record metric, update state, log."""
        CONTEXT_SYNC_TOTAL.labels(
            source_id=source.source_id,
            status="failure",
        ).inc()
        state_svc.update_state(
            state,
            last_attempt_at=now,
            last_error=error,
            next_run_at=now + timedelta(minutes=min(60, 2)),
        )
        self.logger.info(
            "Context sync failed for user=%s source=%s: %s",
            user_id,
            source.source_id,
            error[:200],
        )

    def _handle_not_modified(
        self,
        source: ContextSource,
        state: ContextSourceState,
        state_svc: ContextSourceStateService,
        now: datetime,
    ) -> None:
        """Handle 304 Not Modified: update state for next run."""
        poll_interval = int(source.poll_interval_seconds)
        poll_delta = timedelta(seconds=poll_interval)
        state_svc.update_state(
            state,
            last_success_at=now,
            next_run_at=now + poll_delta,
        )

    def _handle_fetch_success(
        self,
        user_id: UUID,
        source: ContextSource,
        state: ContextSourceState,
        result: FetchResult,
        state_svc: ContextSourceStateService,
        now: datetime,
    ) -> MergeableContextPack:
        """Handle successful fetch: record metric, update state, return pack."""
        CONTEXT_SYNC_TOTAL.labels(
            source_id=source.source_id,
            status="success",
        ).inc()
        CONTEXT_PACK_PAYLOAD_BYTES.labels(
            source_id=source.source_id,
        ).observe(len(result.payload.model_dump_json().encode("utf-8")))
        poll_interval = int(source.poll_interval_seconds)
        poll_delta = timedelta(seconds=poll_interval)
        state_svc.update_state(
            state,
            last_success_at=now,
            last_attempt_at=now,
            last_error=None,
            etag=result.etag,
            since_cursor=result.cursor,
            next_run_at=now + poll_delta,
        )
        self.logger.info(
            "Context sync success for user=%s source=%s",
            user_id,
            source.source_id,
        )
        return result.payload

    def _merge_and_store_snapshot(
        self,
        user_id: UUID,
        packs: List[MergeableContextPack],
        merge_svc: ContextMergeService,
        snapshot_svc: ContextSnapshotService,
    ) -> None:
        """Merge packs and store snapshot."""
        merged = merge_svc.merge_packs(packs)
        snapshot_svc.create_snapshot(
            user_id=user_id,
            schema_version=merged.schema_version,
            generated_at=merged.generated_at,
            payload=merged.to_snapshot_dict(),
        )

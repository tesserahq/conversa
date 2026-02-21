"""Fetcher for context packs from registered sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import requests
from pydantic import ValidationError

from app.models.context_source import ContextSource
from app.models.context_source import ContextSourceState
from app.schemas.context_pack import ContextPackResponse, MergeableContextPack
from app.services.credential_service import CredentialService
from app.infra.logging_config import get_logger

logger = get_logger("context_pack_fetcher")

CONTEXT_PACK_PATH = "/context-pack"
AUDIENCE = "conversa"
TIMEOUT_SECONDS = 30


@dataclass
class FetchResult:
    """Result of a context pack fetch."""

    payload: Optional[MergeableContextPack] = None
    etag: Optional[str] = None
    cursor: Optional[str] = None
    not_modified: bool = False
    error: Optional[str] = None


class ContextPackFetcher:
    """Fetches context packs from a registered source."""

    def __init__(self, credential_service: CredentialService) -> None:
        self._credential_service = credential_service

    def fetch(
        self,
        user_id: UUID,
        source: ContextSource,
        state: Optional[ContextSourceState],
    ) -> FetchResult:
        """
        Fetch context pack from source.

        Uses If-None-Match when state has etag. On 304, returns not_modified=True.
        """
        base_url = source.base_url.rstrip("/")
        url = f"{base_url}{CONTEXT_PACK_PATH}"
        params = {"user_id": str(user_id), "audience": AUDIENCE}
        if state and state.since_cursor:
            params["since"] = state.since_cursor

        headers: dict[str, str] = {"Accept": "application/json"}
        try:
            headers = self._credential_service.apply_credentials(
                credential_id=source.credential_id,
                headers=headers,
            )
        except ValueError as e:
            return FetchResult(error=str(e))

        if state and state.etag:
            headers["If-None-Match"] = state.etag
        logger.info("Fetching context pack from %s with headers: %s", url, headers)

        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            return FetchResult(error=str(e))

        if resp.status_code == 304:
            return FetchResult(not_modified=True, etag=state.etag if state else None)

        if resp.status_code != 200:
            return FetchResult(
                error=f"HTTP {resp.status_code}: {resp.text[:500] if resp.text else 'no body'}"
            )

        try:
            data = resp.json()
        except ValueError as e:
            return FetchResult(error=f"Invalid JSON: {e}")

        try:
            pack = ContextPackResponse.model_validate(data)
        except ValidationError as e:
            return FetchResult(error=f"Invalid context pack: {e}")

        etag = None
        if resp.headers.get("ETag"):
            etag = resp.headers.get("ETag", "").strip('"')
        cursor = None
        if pack.sources:
            for src_info in pack.sources.values():
                if isinstance(src_info, dict) and src_info.get("cursor"):
                    cursor = src_info.get("cursor")
                    break

        payload = pack.to_mergeable_pack(source_id=source.source_id)
        return FetchResult(
            payload=payload,
            etag=etag,
            cursor=cursor,
        )

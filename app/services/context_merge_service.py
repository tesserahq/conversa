"""Service for merging context packs from multiple sources."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List

from app.schemas.context_pack import (
    FACTS_MAX_BYTES,
    MergeableContextPack,
    MergedContextPayload,
    POINTERS_MAX_PER_CATEGORY,
    RECENTS_MAX_COUNT,
)


class ContextMergeService:
    """Merges context packs using priority-winner for facts, union for pointers/recents."""

    def merge_packs(self, packs: List[MergeableContextPack]) -> MergedContextPayload:
        """
        Merge multiple source packs into a single payload.

        Uses priority winner for facts (first pack wins per key).
        Uses union for recents and pointers with deduplication.
        Applies size/count caps.
        """
        if not packs:
            return self._empty_payload()

        merged_facts = self._merge_facts(packs)
        merged_recents = self._merge_recents(packs)
        merged_pointers = self._merge_pointers(packs)

        merged_facts = self._apply_facts_cap(merged_facts)
        merged_recents = self._apply_recents_cap(merged_recents)

        return MergedContextPayload(
            schema_version=packs[0].schema_version,
            generated_at=max(pack.generated_at for pack in packs),
            facts=merged_facts,
            recents=merged_recents,
            pointers=merged_pointers,
        )

    def _merge_facts(self, packs: List[MergeableContextPack]) -> dict[str, Any]:
        """Merge facts using priority winner (first pack wins per key)."""
        merged: dict[str, Any] = {}
        for pack in packs:
            for fact_key, fact_value in pack.facts.items():
                if fact_key not in merged:
                    merged[fact_key] = fact_value
        return merged

    def _merge_recents(self, packs: List[MergeableContextPack]) -> dict[str, Any]:
        """Merge recents using union with deduplication by id."""
        merged: dict[str, Any] = {}
        for pack in packs:
            for recent_key, recent_values in pack.recents.items():
                if recent_key not in merged:
                    merged[recent_key] = []
                existing_items = merged[recent_key]
                if isinstance(recent_values, list):
                    for item in recent_values:
                        if isinstance(item, dict) and item.get("id"):
                            if not any(
                                existing_item.get("id") == item["id"]
                                for existing_item in existing_items
                                if isinstance(existing_item, dict)
                            ):
                                existing_items.append(item)
                        elif item not in existing_items:
                            existing_items.append(item)
                elif recent_values not in existing_items:
                    existing_items.append(recent_values)
        return merged

    def _merge_pointers(
        self, packs: List[MergeableContextPack]
    ) -> dict[str, list[str]]:
        """Merge pointers using union per category with deduplication and cap."""
        merged: dict[str, list[str]] = {}
        for pack in packs:
            for category, pointer_ids in pack.pointers.items():
                if category not in merged:
                    merged[category] = []
                seen_ids = set(merged[category])
                for pointer_id in pointer_ids:
                    id_str = str(pointer_id)
                    if (
                        id_str not in seen_ids
                        and len(merged[category]) < POINTERS_MAX_PER_CATEGORY
                    ):
                        merged[category].append(id_str)
                        seen_ids.add(id_str)
        return merged

    def _apply_facts_cap(self, facts: dict[str, Any]) -> dict[str, Any]:
        """Truncate facts if total size exceeds FACTS_MAX_BYTES."""
        facts_bytes = len(json.dumps(facts).encode("utf-8"))
        if facts_bytes > FACTS_MAX_BYTES:
            return self._truncate_facts(facts, FACTS_MAX_BYTES)
        return facts

    def _apply_recents_cap(self, recents: dict[str, Any]) -> dict[str, Any]:
        """Cap each recents list to RECENTS_MAX_COUNT items."""
        result = dict(recents)
        for recent_key in list(result.keys()):
            recent_values = result[recent_key]
            if (
                isinstance(recent_values, list)
                and len(recent_values) > RECENTS_MAX_COUNT
            ):
                result[recent_key] = recent_values[:RECENTS_MAX_COUNT]
        return result

    def _empty_payload(self) -> MergedContextPayload:
        return MergedContextPayload(
            schema_version="1.0",
            generated_at=datetime.now(timezone.utc),
            facts={},
            recents={},
            pointers={},
        )

    def _truncate_facts(self, facts: dict[str, Any], max_bytes: int) -> dict[str, Any]:
        """Truncate facts to fit within max_bytes by dropping keys."""
        result: dict[str, Any] = {}
        for fact_key, fact_value in sorted(facts.items()):
            candidate = {**result, fact_key: fact_value}
            if len(json.dumps(candidate).encode("utf-8")) <= max_bytes:
                result[fact_key] = fact_value
            else:
                break
        return result

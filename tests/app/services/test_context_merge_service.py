"""Tests for ContextMergeService."""

import json
from datetime import datetime, timedelta, timezone

from app.schemas.context_pack import (
    FACTS_MAX_BYTES,
    MergeableContextPack,
    MergedContextPayload,
    RECENTS_MAX_COUNT,
)
from app.services.context_merge_service import ContextMergeService


def _make_pack(
    source_id: str,
    facts: dict | None = None,
    recents: dict | None = None,
    pointers: dict | None = None,
    generated_at: datetime | None = None,
) -> MergeableContextPack:
    """Helper to create a MergeableContextPack with defaults."""
    return MergeableContextPack(
        source_id=source_id,
        schema_version="1.0",
        generated_at=generated_at or datetime.now(timezone.utc),
        facts=facts or {},
        recents=recents or {},
        pointers=pointers or {},
    )


def test_merge_packs_empty_returns_empty_payload():
    """merge_packs with empty list returns empty MergedContextPayload."""
    svc = ContextMergeService()
    result = svc.merge_packs([])
    assert isinstance(result, MergedContextPayload)
    assert result.schema_version == "1.0"
    assert result.facts == {}
    assert result.recents == {}
    assert result.pointers == {}


def test_merge_packs_single_pack():
    """merge_packs with one pack returns its content."""
    pack = _make_pack(
        "linden",
        facts={"display_name": "Emi", "locale": "es-ES"},
        recents={"top_entities": [{"id": "dep_1", "label": "Child"}]},
        pointers={"documents": ["doc_9"]},
    )
    svc = ContextMergeService()
    result = svc.merge_packs([pack])
    assert result.schema_version == "1.0"
    assert result.facts == {"display_name": "Emi", "locale": "es-ES"}
    assert result.recents["top_entities"] == [{"id": "dep_1", "label": "Child"}]
    assert result.pointers == {"documents": ["doc_9"]}


def test_merge_packs_facts_priority_winner():
    """Facts: first pack wins when both have the same key."""
    pack1 = _make_pack("linden", facts={"display_name": "Emi"})
    pack2 = _make_pack("vaulta", facts={"display_name": "Other"})
    svc = ContextMergeService()
    result = svc.merge_packs([pack1, pack2])
    assert result.facts["display_name"] == "Emi"


def test_merge_packs_facts_merged_from_different_keys():
    """Facts: keys from different packs are merged."""
    pack1 = _make_pack("linden", facts={"display_name": "Emi"})
    pack2 = _make_pack("vaulta", facts={"timezone": "Europe/Madrid"})
    svc = ContextMergeService()
    result = svc.merge_packs([pack1, pack2])
    assert result.facts["display_name"] == "Emi"
    assert result.facts["timezone"] == "Europe/Madrid"


def test_merge_packs_recents_union_with_dedup_by_id():
    """Recents: items with same id are deduplicated."""
    pack1 = _make_pack(
        "linden",
        recents={"top_entities": [{"id": "dep_1", "label": "Child"}]},
    )
    pack2 = _make_pack(
        "vaulta",
        recents={"top_entities": [{"id": "dep_1", "label": "Child (dup)"}]},
    )
    svc = ContextMergeService()
    result = svc.merge_packs([pack1, pack2])
    assert len(result.recents["top_entities"]) == 1
    assert result.recents["top_entities"][0]["id"] == "dep_1"


def test_merge_packs_recents_union_distinct_items():
    """Recents: distinct items are unioned."""
    pack1 = _make_pack(
        "linden",
        recents={"top_entities": [{"id": "dep_1", "label": "Child"}]},
    )
    pack2 = _make_pack(
        "vaulta",
        recents={"top_entities": [{"id": "doc_9", "label": "Will"}]},
    )
    svc = ContextMergeService()
    result = svc.merge_packs([pack1, pack2])
    assert len(result.recents["top_entities"]) == 2
    ids = {item["id"] for item in result.recents["top_entities"]}
    assert ids == {"dep_1", "doc_9"}


def test_merge_packs_pointers_union():
    """Pointers: union per category with deduplication."""
    pack1 = _make_pack("linden", pointers={"documents": ["doc_9"]})
    pack2 = _make_pack("vaulta", pointers={"documents": ["doc_10", "doc_9"]})
    svc = ContextMergeService()
    result = svc.merge_packs([pack1, pack2])
    assert result.pointers["documents"] == ["doc_9", "doc_10"]


def test_merge_packs_generated_at_is_max():
    """generated_at is the max of all pack generated_at values."""
    base = datetime.now(timezone.utc)
    pack1 = _make_pack("linden", generated_at=base - timedelta(hours=1))
    pack2 = _make_pack("vaulta", generated_at=base + timedelta(hours=1))
    svc = ContextMergeService()
    result = svc.merge_packs([pack1, pack2])
    assert result.generated_at == pack2.generated_at


def test_merge_packs_recents_cap_applied():
    """Recents lists are capped at RECENTS_MAX_COUNT."""
    pack = _make_pack(
        "linden",
        recents={
            "top_entities": [
                {"id": f"item_{i}", "label": f"Item {i}"}
                for i in range(RECENTS_MAX_COUNT + 10)
            ]
        },
    )
    svc = ContextMergeService()
    result = svc.merge_packs([pack])
    assert len(result.recents["top_entities"]) == RECENTS_MAX_COUNT


def test_merge_packs_to_snapshot_dict_serializable():
    """to_snapshot_dict produces JSON-serializable dict with ISO generated_at."""
    pack = _make_pack("linden", facts={"display_name": "Emi"})
    svc = ContextMergeService()
    result = svc.merge_packs([pack])
    snapshot_dict = result.to_snapshot_dict()
    assert "schema_version" in snapshot_dict
    assert "generated_at" in snapshot_dict
    assert isinstance(snapshot_dict["generated_at"], str)
    assert "facts" in snapshot_dict
    assert snapshot_dict["facts"]["display_name"] == "Emi"
    # Must be JSON-serializable
    json.dumps(snapshot_dict)

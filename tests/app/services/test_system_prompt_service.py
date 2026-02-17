"""Tests for SystemPromptService."""

import pytest

from app.services.system_prompt_service import SystemPromptService


def test_get_system_prompt_by_name_found(db, setup_system_prompt):
    """get_system_prompt_by_name returns the prompt when it exists."""
    prompt = setup_system_prompt
    svc = SystemPromptService(db)
    found = svc.get_system_prompt_by_name(prompt.name)
    assert found is not None
    assert found.id == prompt.id
    assert found.name == prompt.name


def test_get_system_prompt_by_name_not_found(db):
    """get_system_prompt_by_name returns None for unknown name."""
    svc = SystemPromptService(db)
    assert svc.get_system_prompt_by_name("nonexistent") is None


def test_get_current_content_found(db):
    """get_current_content returns the current version content when prompt exists (uses seeded default)."""
    svc = SystemPromptService(db)
    content = svc.get_current_content("default")
    assert content is not None
    assert isinstance(content, str)


def test_get_current_content_not_found(db):
    """get_current_content returns None for unknown name."""
    svc = SystemPromptService(db)
    assert svc.get_current_content("nonexistent") is None


def test_get_versions_empty_for_unknown_name(db):
    """get_versions returns empty list for unknown prompt name."""
    svc = SystemPromptService(db)
    versions = svc.get_versions("nonexistent")
    assert versions == []


def test_get_versions_newest_first(db, setup_system_prompt_with_versions):
    """get_versions returns versions newest first (by version_number desc)."""
    prompt, created_versions = setup_system_prompt_with_versions
    svc = SystemPromptService(db)
    versions = svc.get_versions(prompt.name)
    assert len(versions) == 3
    assert versions[0].version_number == 3
    assert versions[1].version_number == 2
    assert versions[2].version_number == 1


def test_get_versions_pagination(db, setup_system_prompt_with_versions):
    """get_versions respects skip and limit."""
    prompt, _ = setup_system_prompt_with_versions
    svc = SystemPromptService(db)
    page1 = svc.get_versions(prompt.name, skip=0, limit=2)
    assert len(page1) == 2
    assert page1[0].version_number == 3
    assert page1[1].version_number == 2

    page2 = svc.get_versions(prompt.name, skip=2, limit=2)
    assert len(page2) == 1
    assert page2[0].version_number == 1


def test_create_version_first_version(db, faker):
    """create_version adds first version and sets it as current when prompt has no versions."""
    from app.models.system_prompt import SystemPrompt

    name = faker.slug() or "new-prompt"
    prompt = SystemPrompt(name=name)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)

    svc = SystemPromptService(db)
    new_content = "New markdown content"
    version = svc.create_version(name, new_content, note="First")

    assert version is not None
    assert version.content == new_content
    assert version.version_number == 1
    assert version.note == "First"
    assert version.system_prompt_id == prompt.id

    db.refresh(prompt)
    assert prompt.current_version_id == version.id
    assert svc.get_current_content(name) == new_content


def test_create_version_second_version(db, setup_system_prompt):
    """create_version adds new version and updates current."""
    prompt = setup_system_prompt
    svc = SystemPromptService(db)
    new_content = "Updated system prompt"
    version = svc.create_version(prompt.name, new_content, note="Update")

    assert version is not None
    assert version.content == new_content
    assert version.version_number == 2
    assert version.note == "Update"

    assert svc.get_current_content(prompt.name) == new_content
    versions = svc.get_versions(prompt.name)
    assert len(versions) == 2
    assert versions[0].version_number == 2
    assert versions[0].content == new_content


def test_create_version_unknown_name_returns_none(db):
    """create_version returns None when prompt name does not exist."""
    svc = SystemPromptService(db)
    version = svc.create_version("nonexistent", "content", note="x")
    assert version is None

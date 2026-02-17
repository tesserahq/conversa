"""Fixtures for system prompt and version models."""

import pytest

from app.models.system_prompt import SystemPrompt, SystemPromptVersion


@pytest.fixture(scope="function")
def setup_system_prompt(db, faker):
    """
    Create a system prompt with one version and set it as current.
    Returns the SystemPrompt instance (with current_version and versions loaded).
    """
    name = faker.slug() or "default"
    prompt = SystemPrompt(name=name)
    db.add(prompt)
    db.flush()

    version = SystemPromptVersion(
        system_prompt_id=prompt.id,
        content=faker.text(max_nb_chars=200),
        version_number=1,
        note="Initial version",
    )
    db.add(version)
    db.flush()

    prompt.current_version_id = version.id
    db.commit()
    db.refresh(prompt)
    db.refresh(version)
    return prompt


@pytest.fixture(scope="function")
def setup_system_prompt_with_versions(db, faker):
    """
    Create a system prompt with three versions; current is the latest.
    Returns (SystemPrompt, list of SystemPromptVersion in creation order).
    """
    name = faker.slug() or "multi-version"
    prompt = SystemPrompt(name=name)
    db.add(prompt)
    db.flush()

    versions = []
    for i in range(1, 4):
        version = SystemPromptVersion(
            system_prompt_id=prompt.id,
            content=faker.text(max_nb_chars=100),
            version_number=i,
            note=f"Version {i}",
        )
        db.add(version)
        db.flush()
        versions.append(version)

    prompt.current_version_id = versions[-1].id
    db.commit()
    for v in versions:
        db.refresh(v)
    db.refresh(prompt)
    return prompt, versions

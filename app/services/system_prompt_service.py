"""Service for system prompt and version CRUD; get current content, save new version."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session as DBSession

from app.models.system_prompt import SystemPrompt, SystemPromptVersion


class SystemPromptService:
    """Manages system prompts and their version history."""

    def __init__(self, db: DBSession) -> None:
        self.db = db

    def get_system_prompt_by_name(self, name: str) -> Optional[SystemPrompt]:
        """Fetch a system prompt by name."""
        return self.db.query(SystemPrompt).filter(SystemPrompt.name == name).first()

    def get_current_content(self, name: str) -> Optional[str]:
        """
        Return the content of the current version for the given prompt name.
        Returns None if the prompt does not exist or has no current version.
        """
        prompt = self.get_system_prompt_by_name(name)
        if prompt is None or prompt.current_version_id is None:
            return None
        version = (
            self.db.query(SystemPromptVersion)
            .filter(SystemPromptVersion.id == prompt.current_version_id)
            .first()
        )
        if version is None:
            return None
        return str(version.content)

    def get_versions(
        self,
        name: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SystemPromptVersion]:
        """List versions for the given prompt name, newest first."""
        prompt = self.get_system_prompt_by_name(name)
        if prompt is None:
            return []
        return (
            self.db.query(SystemPromptVersion)
            .filter(SystemPromptVersion.system_prompt_id == prompt.id)
            .order_by(SystemPromptVersion.version_number.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_version(
        self,
        name: str,
        content: str,
        note: Optional[str] = None,
    ) -> Optional[SystemPromptVersion]:
        """
        Create a new version for the given prompt and set it as current.
        Returns the new version, or None if the prompt does not exist.
        """
        prompt = self.get_system_prompt_by_name(name)
        if prompt is None:
            return None

        next_version = 1
        latest = (
            self.db.query(SystemPromptVersion)
            .filter(SystemPromptVersion.system_prompt_id == prompt.id)
            .order_by(SystemPromptVersion.version_number.desc())
            .limit(1)
            .first()
        )
        if latest is not None:
            next_version = int(latest.version_number) + 1

        version = SystemPromptVersion(
            system_prompt_id=prompt.id,
            content=content,
            version_number=next_version,
            note=note,
        )
        self.db.add(version)
        self.db.flush()  # get version.id

        prompt.current_version_id = version.id
        self.db.commit()
        self.db.refresh(version)
        return version

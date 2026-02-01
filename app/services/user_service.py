from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOnboard
from app.utils.db.filtering import apply_filters
from app.services.soft_delete_service import SoftDeleteService


class UserService(SoftDeleteService[User]):
    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_user(self, user_id: UUID) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_any_status(self, user_id: UUID) -> Optional[User]:
        """Get a user regardless of deletion status (deleted or not)."""
        return self.get_record_any_status(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_external_id(self, external_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.external_id == external_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).offset(skip).limit(limit).all()

    def create_user(self, user: UserCreate) -> User:
        db_user = User(**user.model_dump())
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def onboard_user(self, user: UserOnboard) -> User:
        db_user = User(**user.model_dump())
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update_user(self, user_id: UUID, user: UserUpdate) -> Optional[User]:
        db_user = self.db.query(User).filter(User.id == user_id).first()
        if db_user:
            update_data = user.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_user, key, value)
            self.db.commit()
            self.db.refresh(db_user)
        return db_user

    def delete_user(self, user_id: UUID) -> bool:
        """Soft delete a user by setting deleted_at timestamp."""
        return self.delete_record(user_id)

    def restore_user(self, user_id: UUID) -> bool:
        """Restore a soft-deleted user by setting deleted_at to None."""
        return self.restore_record(user_id)

    def hard_delete_user(self, user_id: UUID) -> bool:
        """Permanently delete a user from the database."""
        return self.hard_delete_record(user_id)

    def get_deleted_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all soft-deleted users."""
        return self.get_deleted_records(skip, limit)

    def get_deleted_user(self, user_id: UUID) -> Optional[User]:
        """Get a single soft-deleted user by ID."""
        return self.get_deleted_record(user_id)

    def get_users_deleted_after(self, date: datetime) -> List[User]:
        """Get users deleted after a specific date."""
        return self.get_records_deleted_after(date)

    def verify_user(self, user_id: UUID) -> Optional[User]:
        db_user = self.db.query(User).filter(User.id == user_id).first()
        if db_user:
            db_user.verified = True
            db_user.verified_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(db_user)
        return db_user

    def search(self, filters: Dict[str, Any]) -> List[User]:
        """
        Search users based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"email": "test@example.com"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"email": {"operator": "ilike", "value": "%@example.com"}})

        Returns:
            List[User]: Filtered list of users matching the criteria.
        """
        query = self.db.query(User)
        query = apply_filters(query, User, filters)
        return query.all()

"""User feedback entity for learning from user preferences."""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class FeedbackType(str, Enum):
    """Types of feedback a user can give."""

    INTERESTED = "interested"  # User wants to add this community
    NOT_RELEVANT = "not_relevant"  # User marked as not relevant
    ALREADY_MEMBER = "already_member"  # User is already a member


class ContextType(str, Enum):
    """Context where the feedback was given."""

    AUDIENCE = "audience"  # Feedback in audience context
    TEMPLATE = "template"  # Feedback in template context
    SEARCH = "search"  # Feedback in search results
    SIMILAR = "similar"  # Feedback in similar communities suggestions


class UserCommunityFeedback(Base):
    """
    Stores user feedback on community suggestions.
    Used to personalize recommendations and filter unwanted suggestions.
    """

    __tablename__ = "user_community_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=True, index=True)  # Session or user ID
    subreddit_name = Column(String(100), nullable=False, index=True)
    context_type = Column(String(50), nullable=False)  # audience, template, search, similar
    context_id = Column(UUID(as_uuid=True), nullable=True)  # ID of audience/template
    feedback = Column(String(20), nullable=False)  # interested, not_relevant, already_member
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def is_negative(self) -> bool:
        """Check if this is negative feedback (should filter out)."""
        return self.feedback in (FeedbackType.NOT_RELEVANT.value, FeedbackType.ALREADY_MEMBER.value)

    def is_positive(self) -> bool:
        """Check if this is positive feedback (should boost)."""
        return self.feedback == FeedbackType.INTERESTED.value

"""Repository for user community feedback."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.similar_communities.domain.entities.user_feedback import (
    FeedbackType,
    UserCommunityFeedback,
)


class UserFeedbackRepository:
    """Repository for managing user feedback on community suggestions."""

    def __init__(self, db: Session):
        self.db = db

    def save_feedback(
        self,
        user_id: str,
        subreddit_name: str,
        context_type: str,
        feedback: str,
        context_id: UUID | None = None,
    ) -> UserCommunityFeedback:
        """
        Save or update user feedback.

        Uses upsert to handle unique constraint on (user_id, subreddit_name, context_type, context_id).
        """
        existing = (
            self.db.query(UserCommunityFeedback)
            .filter(
                UserCommunityFeedback.user_id == user_id,
                UserCommunityFeedback.subreddit_name == subreddit_name.lower(),
                UserCommunityFeedback.context_type == context_type,
                UserCommunityFeedback.context_id == context_id,
            )
            .first()
        )

        if existing:
            existing.feedback = feedback
            self.db.commit()
            self.db.refresh(existing)
            return existing

        new_feedback = UserCommunityFeedback(
            user_id=user_id,
            subreddit_name=subreddit_name.lower(),
            context_type=context_type,
            context_id=context_id,
            feedback=feedback,
        )
        self.db.add(new_feedback)
        self.db.commit()
        self.db.refresh(new_feedback)
        return new_feedback

    def get_user_feedback(
        self,
        user_id: str,
        subreddit_name: str | None = None,
        context_type: str | None = None,
    ) -> list[UserCommunityFeedback]:
        """Get all feedback for a user, optionally filtered."""
        query = self.db.query(UserCommunityFeedback).filter(
            UserCommunityFeedback.user_id == user_id
        )

        if subreddit_name:
            query = query.filter(
                UserCommunityFeedback.subreddit_name == subreddit_name.lower()
            )

        if context_type:
            query = query.filter(UserCommunityFeedback.context_type == context_type)

        return query.all()

    def get_negative_feedback_names(
        self,
        user_id: str,
        context_type: str | None = None,
    ) -> list[str]:
        """
        Get list of subreddit names the user marked as not relevant.

        Args:
            user_id: The user identifier
            context_type: Optional filter by context type

        Returns:
            List of subreddit names to exclude from suggestions
        """
        query = self.db.query(UserCommunityFeedback.subreddit_name).filter(
            UserCommunityFeedback.user_id == user_id,
            UserCommunityFeedback.feedback.in_([
                FeedbackType.NOT_RELEVANT.value,
                FeedbackType.ALREADY_MEMBER.value,
            ]),
        )

        if context_type:
            query = query.filter(UserCommunityFeedback.context_type == context_type)

        return [row[0] for row in query.distinct().all()]

    def get_positive_feedback_names(
        self,
        user_id: str,
        context_type: str | None = None,
    ) -> list[str]:
        """
        Get list of subreddit names the user showed interest in.

        Args:
            user_id: The user identifier
            context_type: Optional filter by context type

        Returns:
            List of subreddit names to boost in suggestions
        """
        query = self.db.query(UserCommunityFeedback.subreddit_name).filter(
            UserCommunityFeedback.user_id == user_id,
            UserCommunityFeedback.feedback == FeedbackType.INTERESTED.value,
        )

        if context_type:
            query = query.filter(UserCommunityFeedback.context_type == context_type)

        return [row[0] for row in query.distinct().all()]

    def delete_feedback(
        self,
        user_id: str,
        subreddit_name: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
    ) -> bool:
        """Delete user feedback."""
        query = self.db.query(UserCommunityFeedback).filter(
            UserCommunityFeedback.user_id == user_id,
            UserCommunityFeedback.subreddit_name == subreddit_name.lower(),
        )

        if context_type:
            query = query.filter(UserCommunityFeedback.context_type == context_type)

        if context_id:
            query = query.filter(UserCommunityFeedback.context_id == context_id)

        count = query.delete()
        self.db.commit()
        return count > 0

    def count_feedback_by_type(self, user_id: str) -> dict[str, int]:
        """Get count of feedback by type for a user."""
        results = (
            self.db.query(
                UserCommunityFeedback.feedback,
                self.db.func.count(UserCommunityFeedback.id),
            )
            .filter(UserCommunityFeedback.user_id == user_id)
            .group_by(UserCommunityFeedback.feedback)
            .all()
        )
        return {feedback: count for feedback, count in results}

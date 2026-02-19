"""Service for finding similar communities using embeddings."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.similar_communities.application.services.embedding_service import (
    EmbeddingService,
)
from app.modules.similar_communities.domain.entities.user_feedback import (
    ContextType,
    FeedbackType,
)
from app.modules.similar_communities.infra.repositories.community_embedding_repository import (
    CommunityEmbeddingRepository,
)
from app.modules.similar_communities.infra.repositories.user_feedback_repository import (
    UserFeedbackRepository,
)


@dataclass
class SimilarCommunity:
    """A similar community suggestion."""

    name: str
    title: str | None
    description: str | None
    subscribers: int | None
    similarity_score: float
    reason: str | None = None  # Why this community is similar


@dataclass
class SimilarCommunitiesResult:
    """Result of similar communities search."""

    suggestions: list[SimilarCommunity]
    source_communities: list[str]
    total_found: int
    filtered_count: int  # How many were filtered due to user feedback


class SimilarCommunitiesService:
    """
    Service for finding semantically similar communities.

    Uses embedding similarity with user feedback filtering.
    """

    # Boost factor for communities the user has shown interest in similar contexts
    POSITIVE_FEEDBACK_BOOST = 0.1

    def __init__(self, db: Session):
        self.db = db
        self.embedding_repo = CommunityEmbeddingRepository(db)
        self.feedback_repo = UserFeedbackRepository(db)
        self.embedding_service = EmbeddingService(db)

    def find_similar_to_community(
        self,
        subreddit_name: str,
        user_id: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> SimilarCommunitiesResult:
        """
        Find communities similar to a given subreddit.

        Args:
            subreddit_name: The source subreddit
            user_id: Optional user ID for personalization
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)

        Returns:
            SimilarCommunitiesResult with suggestions
        """
        # Get negative feedback to exclude
        exclude_names = [subreddit_name.lower()]
        filtered_count = 0

        if user_id:
            negative_names = self.feedback_repo.get_negative_feedback_names(user_id)
            exclude_names.extend(negative_names)
            filtered_count = len(negative_names)

        # Ensure source community has embedding
        source = self.embedding_repo.find_by_name(subreddit_name)
        if not source or source.embedding is None:
            # Try to create embedding if we have community data
            # This would require fetching from Reddit, so we return empty for now
            return SimilarCommunitiesResult(
                suggestions=[],
                source_communities=[subreddit_name],
                total_found=0,
                filtered_count=filtered_count,
            )

        # Find similar communities
        similar = self.embedding_repo.find_similar(
            embedding=source.embedding,
            limit=limit + filtered_count,  # Request more to account for filtering
            exclude_names=exclude_names,
        )

        # Apply positive feedback boost if user_id provided
        positive_names = set()
        if user_id:
            positive_names = set(self.feedback_repo.get_positive_feedback_names(user_id))

        suggestions = []
        for community, similarity in similar:
            if similarity < min_similarity:
                continue

            # Apply positive boost
            final_score = similarity
            if community.subreddit_name in positive_names:
                final_score = min(1.0, similarity + self.POSITIVE_FEEDBACK_BOOST)

            suggestions.append(
                SimilarCommunity(
                    name=community.subreddit_name,
                    title=community.title,
                    description=community.description,
                    subscribers=community.subscribers,
                    similarity_score=final_score,
                    reason=f"Similar to r/{subreddit_name}",
                )
            )

        # Sort by final score and limit
        suggestions.sort(key=lambda x: x.similarity_score, reverse=True)
        suggestions = suggestions[:limit]

        return SimilarCommunitiesResult(
            suggestions=suggestions,
            source_communities=[subreddit_name],
            total_found=len(suggestions),
            filtered_count=filtered_count,
        )

    def find_similar_to_audience(
        self,
        community_names: list[str],
        user_id: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> SimilarCommunitiesResult:
        """
        Find communities similar to an audience (group of communities).

        Uses average embedding of all source communities.

        Args:
            community_names: List of subreddit names in the audience
            user_id: Optional user ID for personalization
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)

        Returns:
            SimilarCommunitiesResult with suggestions
        """
        if not community_names:
            return SimilarCommunitiesResult(
                suggestions=[],
                source_communities=[],
                total_found=0,
                filtered_count=0,
            )

        # Get negative feedback to exclude
        exclude_names = [n.lower() for n in community_names]
        filtered_count = 0

        if user_id:
            negative_names = self.feedback_repo.get_negative_feedback_names(user_id)
            exclude_names.extend(negative_names)
            filtered_count = len(negative_names)

        # Find similar using aggregate embedding
        similar = self.embedding_repo.find_similar_to_multiple(
            subreddit_names=community_names,
            limit=limit + filtered_count,
            exclude_names=exclude_names,
        )

        # Apply positive feedback boost
        positive_names = set()
        if user_id:
            positive_names = set(self.feedback_repo.get_positive_feedback_names(user_id))

        suggestions = []
        for community, similarity in similar:
            if similarity < min_similarity:
                continue

            final_score = similarity
            if community.subreddit_name in positive_names:
                final_score = min(1.0, similarity + self.POSITIVE_FEEDBACK_BOOST)

            suggestions.append(
                SimilarCommunity(
                    name=community.subreddit_name,
                    title=community.title,
                    description=community.description,
                    subscribers=community.subscribers,
                    similarity_score=final_score,
                    reason=f"Similar to your audience",
                )
            )

        suggestions.sort(key=lambda x: x.similarity_score, reverse=True)
        suggestions = suggestions[:limit]

        return SimilarCommunitiesResult(
            suggestions=suggestions,
            source_communities=community_names,
            total_found=len(suggestions),
            filtered_count=filtered_count,
        )

    def save_feedback(
        self,
        user_id: str,
        subreddit_name: str,
        feedback: str,
        context_type: str,
        context_id: UUID | None = None,
    ) -> dict:
        """
        Save user feedback on a community suggestion.

        Args:
            user_id: User or session identifier
            subreddit_name: The subreddit being rated
            feedback: Type of feedback (interested, not_relevant, already_member)
            context_type: Where the feedback was given (audience, template, search, similar)
            context_id: Optional ID of the context (audience_id, template_id)

        Returns:
            Saved feedback info
        """
        saved = self.feedback_repo.save_feedback(
            user_id=user_id,
            subreddit_name=subreddit_name,
            context_type=context_type,
            feedback=feedback,
            context_id=context_id,
        )

        return {
            "id": str(saved.id),
            "subreddit_name": saved.subreddit_name,
            "feedback": saved.feedback,
            "context_type": saved.context_type,
        }

    def ensure_embeddings_for_communities(
        self,
        communities: list[dict],
    ) -> int:
        """
        Ensure embeddings exist for a list of communities.

        Args:
            communities: List of dicts with name, title, description, subscribers

        Returns:
            Number of embeddings created/updated
        """
        results = self.embedding_service.batch_get_or_create_embeddings(communities)
        return len(results)

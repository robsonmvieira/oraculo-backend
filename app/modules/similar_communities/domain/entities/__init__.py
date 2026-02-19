"""Entity definitions for similar communities."""

from app.modules.similar_communities.domain.entities.community_embedding import (
    CommunityEmbedding,
)
from app.modules.similar_communities.domain.entities.user_feedback import (
    UserCommunityFeedback,
)

__all__ = ["CommunityEmbedding", "UserCommunityFeedback"]

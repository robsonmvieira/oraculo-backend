"""Routes for similar communities and user feedback."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel

from app.modules.audience_templates.infra.repositories.audience_template_repository import (
    AudienceTemplateRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.similar_communities.application.services.similar_communities_service import (
    SimilarCommunitiesService,
)
from app.modules.similar_communities.domain.entities.user_feedback import (
    ContextType,
    FeedbackType,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(tags=["Similar Communities"])


class FeedbackRequest(BaseModel):
    """Request body for saving feedback."""

    subreddit_name: str
    feedback: str  # interested, not_relevant, already_member
    context_type: str  # audience, template, search, similar
    context_id: str | None = None


class FeedbackResponse(BaseModel):
    """Response for feedback operations."""

    id: str
    subreddit_name: str
    feedback: str
    context_type: str


def _get_user_id(x_user_id: str | None = Header(None, alias="X-User-Id")) -> str:
    """Get user ID from header or generate session-based one."""
    return x_user_id or "anonymous"


@router.get("/communities/{community_name}/similar")
def get_similar_communities(
    community_name: str,
    limit: int = Query(default=10, ge=1, le=50),
    min_similarity: float = Query(default=0.5, ge=0.0, le=1.0),
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db),
):
    """
    Find communities similar to a given subreddit.

    Uses semantic embedding similarity to find related communities.
    Results are personalized based on user feedback if X-User-Id header is provided.

    Args:
        community_name: The source subreddit name
        limit: Maximum number of suggestions (1-50)
        min_similarity: Minimum similarity score (0-1)

    Returns:
        List of similar communities with similarity scores
    """
    service = SimilarCommunitiesService(db)
    result = service.find_similar_to_community(
        subreddit_name=community_name,
        user_id=user_id if user_id != "anonymous" else None,
        limit=limit,
        min_similarity=min_similarity,
    )

    return {
        "source": community_name,
        "suggestions": [
            {
                "name": s.name,
                "title": s.title,
                "description": s.description,
                "subscribers": s.subscribers,
                "similarity_score": round(s.similarity_score, 4),
                "reason": s.reason,
            }
            for s in result.suggestions
        ],
        "total_found": result.total_found,
        "filtered_by_feedback": result.filtered_count,
    }


@router.get("/audiences/{audience_id}/suggestions")
def get_audience_suggestions(
    audience_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    min_similarity: float = Query(default=0.5, ge=0.0, le=1.0),
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db),
):
    """
    Get community suggestions for an audience.

    Finds communities similar to the aggregate of all communities in the audience.
    Excludes communities already in the audience and those marked as not relevant.

    Args:
        audience_id: The audience UUID
        limit: Maximum number of suggestions (1-50)
        min_similarity: Minimum similarity score (0-1)

    Returns:
        List of suggested communities with similarity scores
    """
    # Get audience communities
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)

    if not audience:
        raise HTTPException(status_code=404, detail="Audience not found")

    communities = audience_repo.get_communities(audience_id)
    community_names = [c.subreddit_name for c in communities]

    if not community_names:
        return {
            "audience_id": str(audience_id),
            "audience_name": audience.name,
            "suggestions": [],
            "total_found": 0,
            "message": "No communities in audience to find similar",
        }

    service = SimilarCommunitiesService(db)
    result = service.find_similar_to_audience(
        community_names=community_names,
        user_id=user_id if user_id != "anonymous" else None,
        limit=limit,
        min_similarity=min_similarity,
    )

    return {
        "audience_id": str(audience_id),
        "audience_name": audience.name,
        "source_communities": community_names,
        "suggestions": [
            {
                "name": s.name,
                "title": s.title,
                "description": s.description,
                "subscribers": s.subscribers,
                "similarity_score": round(s.similarity_score, 4),
                "reason": s.reason,
            }
            for s in result.suggestions
        ],
        "total_found": result.total_found,
        "filtered_by_feedback": result.filtered_count,
    }


@router.get("/audience-templates/{template_id}/suggestions")
def get_template_suggestions(
    template_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    min_similarity: float = Query(default=0.5, ge=0.0, le=1.0),
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db),
):
    """
    Get community suggestions for an audience template.

    Finds communities similar to the aggregate of all communities in the template.

    Args:
        template_id: The template UUID
        limit: Maximum number of suggestions (1-50)
        min_similarity: Minimum similarity score (0-1)

    Returns:
        List of suggested communities with similarity scores
    """
    template_repo = AudienceTemplateRepository(db)
    template = template_repo.find_by_id(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    communities = template_repo.get_communities(template_id)
    community_names = [c.subreddit_name for c in communities]

    if not community_names:
        return {
            "template_id": str(template_id),
            "template_name": template.name,
            "suggestions": [],
            "total_found": 0,
            "message": "No communities in template to find similar",
        }

    service = SimilarCommunitiesService(db)
    result = service.find_similar_to_audience(
        community_names=community_names,
        user_id=user_id if user_id != "anonymous" else None,
        limit=limit,
        min_similarity=min_similarity,
    )

    return {
        "template_id": str(template_id),
        "template_name": template.name,
        "source_communities": community_names,
        "suggestions": [
            {
                "name": s.name,
                "title": s.title,
                "description": s.description,
                "subscribers": s.subscribers,
                "similarity_score": round(s.similarity_score, 4),
                "reason": s.reason,
            }
            for s in result.suggestions
        ],
        "total_found": result.total_found,
        "filtered_by_feedback": result.filtered_count,
    }


@router.post("/feedback/community", response_model=FeedbackResponse)
def save_community_feedback(
    request: FeedbackRequest,
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db),
):
    """
    Save user feedback on a community suggestion.

    This feedback is used to personalize future suggestions:
    - 'interested': Community will be boosted in future suggestions
    - 'not_relevant': Community will be excluded from future suggestions
    - 'already_member': Community will be excluded from future suggestions

    Args:
        request: Feedback details including subreddit name and feedback type

    Returns:
        Saved feedback confirmation
    """
    # Validate feedback type
    valid_feedbacks = [f.value for f in FeedbackType]
    if request.feedback not in valid_feedbacks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback type. Must be one of: {valid_feedbacks}",
        )

    # Validate context type
    valid_contexts = [c.value for c in ContextType]
    if request.context_type not in valid_contexts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid context type. Must be one of: {valid_contexts}",
        )

    service = SimilarCommunitiesService(db)
    context_uuid = UUID(request.context_id) if request.context_id else None

    result = service.save_feedback(
        user_id=user_id,
        subreddit_name=request.subreddit_name,
        feedback=request.feedback,
        context_type=request.context_type,
        context_id=context_uuid,
    )

    return FeedbackResponse(**result)


@router.delete("/feedback/community/{subreddit_name}")
def delete_community_feedback(
    subreddit_name: str,
    context_type: str | None = Query(default=None),
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db),
):
    """
    Remove user feedback on a community.

    This allows users to "undo" previous feedback decisions.

    Args:
        subreddit_name: The subreddit to remove feedback for
        context_type: Optional filter by context type

    Returns:
        Confirmation of deletion
    """
    from app.modules.similar_communities.infra.repositories.user_feedback_repository import (
        UserFeedbackRepository,
    )

    repo = UserFeedbackRepository(db)
    deleted = repo.delete_feedback(
        user_id=user_id,
        subreddit_name=subreddit_name,
        context_type=context_type,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return {"deleted": True, "subreddit_name": subreddit_name}

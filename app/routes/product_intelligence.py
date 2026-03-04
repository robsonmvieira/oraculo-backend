"""Rotas para Product Intelligence."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.product_intelligence.application.use_cases.trigger_product_intelligence_use_case import (
    TriggerProductIntelligenceUseCase,
)
from app.modules.product_intelligence.infra.repositories.product_intelligence_repository import (
    ProductIntelligenceRepository,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Product Intelligence"])


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _serialize_product_profile(profile, summary: bool = False) -> dict:
    """Serializa um ProductProfile para a resposta da API."""
    data = {
        "id": str(profile.id),
        "product_name": profile.product_name,
        "category": profile.category,
        "total_mentions": profile.total_mentions,
        "sentiment_score": profile.sentiment_score,
        "sentiment_label": profile.sentiment_label,
        "trend_direction": profile.trend_direction,
        "communities": profile.communities or [],
    }
    if not summary:
        data.update(
            {
                "normalized_name": profile.normalized_name,
                "positive_aspects": profile.positive_aspects or [],
                "negative_aspects": profile.negative_aspects or [],
                "gaps": profile.gaps or [],
                "alternatives": profile.alternatives or [],
                "evidence_quotes": profile.evidence_quotes or [],
                "use_cases": profile.use_cases or [],
                "created_at": (
                    profile.created_at.isoformat() if profile.created_at else None
                ),
            }
        )
    return data


def _serialize_opportunity(opp) -> dict:
    """Serializa um ProductOpportunity para a resposta da API."""
    return {
        "id": str(opp.id),
        "opportunity_type": opp.opportunity_type,
        "title": opp.title,
        "description": opp.description,
        "opportunity_score": opp.opportunity_score,
        "demand_signals": opp.demand_signals,
        "existing_solutions_count": opp.existing_solutions_count,
        "evidence": opp.evidence or [],
        "related_products": opp.related_products or [],
        "created_at": (opp.created_at.isoformat() if opp.created_at else None),
    }


@router.get("/{audience_id}/products")
def get_product_intelligence(
    audience_id: UUID,
    sort_by: str = Query(
        "mentions",
        description="Sort products by: mentions, sentiment, name",
    ),
    category: str | None = Query(
        None,
        description="Filter by category: tool, service, brand, platform, saas, physical_product",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Retorna resultado da análise de product intelligence."""
    audience_repo = AudienceRepository(db)
    pi_repo = ProductIntelligenceRepository(db)

    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail="Audience not found")
    _check_ownership(audience, current_user)

    analysis = pi_repo.find_latest_by_audience(audience_id)

    if not analysis:
        return {
            "status": "no_analysis",
            "message": "No product intelligence analysis found. Trigger one using POST /refresh.",
        }

    if analysis.status == "processing":
        return {
            "status": "processing",
            "message": "Product intelligence analysis in progress.",
            "analysis_id": str(analysis.id),
        }

    if analysis.status == "failed":
        return {
            "status": "failed",
            "message": analysis.error_message or "Analysis failed.",
            "analysis_id": str(analysis.id),
        }

    profiles = pi_repo.get_product_profiles(
        analysis.id,
        sort_by=sort_by,
        category=category,
        limit=limit,
        offset=offset,
    )
    opportunities = pi_repo.get_product_opportunities(analysis.id)

    return {
        "status": "ready",
        "analysis_id": str(analysis.id),
        "total_products": analysis.total_products_found,
        "total_mentions": analysis.total_mentions_analyzed,
        "total_opportunities": len(opportunities),
        "created_at": (
            analysis.created_at.isoformat() if analysis.created_at else None
        ),
        "products": [_serialize_product_profile(p, summary=True) for p in profiles],
    }


@router.get("/{audience_id}/products/opportunities")
def get_product_opportunities(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Retorna oportunidades de mercado detectadas."""
    audience_repo = AudienceRepository(db)
    pi_repo = ProductIntelligenceRepository(db)

    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail="Audience not found")
    _check_ownership(audience, current_user)

    analysis = pi_repo.find_latest_by_audience(audience_id)
    if not analysis or analysis.status != "ready":
        return {
            "status": "no_analysis",
            "message": "No ready product intelligence analysis found.",
        }

    opportunities = pi_repo.get_product_opportunities(analysis.id)

    return {
        "status": "ready",
        "analysis_id": str(analysis.id),
        "total_opportunities": len(opportunities),
        "opportunities": [_serialize_opportunity(o) for o in opportunities],
    }


@router.get("/{audience_id}/products/{product_id}")
def get_product_detail(
    audience_id: UUID,
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Retorna detalhe completo de um produto."""
    audience_repo = AudienceRepository(db)
    pi_repo = ProductIntelligenceRepository(db)

    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail="Audience not found")
    _check_ownership(audience, current_user)

    profile = pi_repo.get_product_profile_by_id(product_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "status": "ready",
        "product": _serialize_product_profile(profile, summary=False),
    }


@router.post("/{audience_id}/products/refresh", status_code=202)
def refresh_product_intelligence(
    audience_id: UUID,
    window: str = Query("week", description="Time window: week or month"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Dispara análise de product intelligence em background."""
    audience_repo = AudienceRepository(db)

    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail="Audience not found")
    _check_ownership(audience, current_user)

    use_case = TriggerProductIntelligenceUseCase(db)
    result = use_case.execute(
        audience_id=audience_id,
        window=window,
        language=current_user.preferred_language or "en",
    )

    return result

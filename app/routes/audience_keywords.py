"""Routes for audience keyword analysis."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.audience_keywords.application.use_cases.trigger_keyword_analysis_use_case import (
    TriggerKeywordAnalysisUseCase,
)
from app.modules.audience_keywords.infra.repositories.audience_keyword_repository import (
    AudienceKeywordRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Audience Keywords"])

AUDIENCE_NOT_FOUND = "Audience not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/keywords")
def list_audience_keywords(
    audience_id: UUID,
    sort_by: str = "rank",
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Lista keywords de busca extraídas de uma audiência.

    Retorna a análise mais recente com status 'ready'.
    Se não existe ou está em processamento, retorna status correspondente.

    sort_by: rank (padrão), relevance, keyword, category
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    keyword_repo = AudienceKeywordRepository(db)

    # Buscar análise mais recente (qualquer status)
    latest = keyword_repo.find_latest_by_audience(audience_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma análise de keywords encontrada. Adicione comunidades à audiência.",
            "keywords": [],
            "total_keywords": 0,
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Análise de keywords em andamento. Tente novamente em alguns minutos.",
            "keywords": [],
            "total_keywords": 0,
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Análise falhou: {latest.error_message or 'erro desconhecido'}",
            "keywords": [],
            "total_keywords": 0,
        }

    # Status ready — buscar keywords
    keywords = keyword_repo.get_keywords(
        analysis_id=latest.id,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    return {
        "status": "ready",
        "analysis_id": str(latest.id),
        "total_keywords": latest.total_keywords,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "keywords": [
            {
                "id": str(k.id),
                "keyword": k.keyword,
                "category": k.category,
                "relevance_score": k.relevance_score,
                "rank": k.rank,
            }
            for k in keywords
        ],
    }


@router.post("/{audience_id}/keywords/refresh", status_code=202)
def refresh_audience_keywords(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Força reprocessamento da análise de keywords.
    Útil quando o usuário quer dados atualizados.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    communities = audience_repo.get_communities(audience_id)
    if not communities:
        raise HTTPException(
            status_code=400,
            detail="Audiência não possui comunidades para análise",
        )

    keyword_repo = AudienceKeywordRepository(db)

    # Verificar se já há uma análise em processamento
    latest = keyword_repo.find_latest_by_audience(audience_id)
    if latest and latest.status == "processing":
        return {
            "status": "processing",
            "message": "Já existe uma análise em andamento.",
        }

    # Criar nova análise (ignora fingerprint — força reprocessamento)
    community_names = [c.subreddit_name for c in communities]
    fingerprint = AudienceKeywordRepository.generate_fingerprint(community_names)
    analysis = keyword_repo.create_analysis(audience_id, fingerprint)

    trigger = TriggerKeywordAnalysisUseCase(db)
    trigger._run_in_background(audience_id, analysis.id, language=current_user.preferred_language)

    return {
        "status": "processing",
        "message": "Análise de keywords iniciada. Consulte novamente em alguns minutos.",
        "analysis_id": str(analysis.id),
    }

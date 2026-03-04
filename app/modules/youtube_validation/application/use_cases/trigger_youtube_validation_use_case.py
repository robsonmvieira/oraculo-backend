"""Triggers YouTube cross-platform validation in background when user requests it."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.youtube_validation.infra.repositories.youtube_validation_repository import (
    YouTubeValidationRepository,
)

logger = logging.getLogger(__name__)


class TriggerYouTubeValidationUseCase:
    """
    Verifica se a validação YouTube precisa ser processada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.validation_repo = YouTubeValidationRepository(db)

    def execute(
        self,
        audience_id: UUID,
        user_id: UUID,
        force: bool = False,
        language: str = "en",
    ) -> dict:
        """
        Verifica e dispara validação YouTube se necessário.

        Args:
            audience_id: ID da audiência
            user_id: ID do usuário
            force: Se True, ignora fingerprint e força reprocessamento
            language: Idioma preferido do usuário

        Returns:
            dict com status e informações
        """
        # Verificar se a audiência existe
        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"status": "error", "message": "Audience not found"}

        # Verificar se já há validação em processamento
        latest = self.validation_repo.find_latest_by_audience(audience_id)
        if latest and latest.status == "processing" and not force:
            return {
                "status": "processing",
                "message": "YouTube validation already in progress.",
                "validation_id": str(latest.id),
            }

        # Obter tópicos da audiência para fingerprint
        latest_analysis = self.topic_repo.find_latest_by_audience(audience_id)
        if not latest_analysis or latest_analysis.status != "ready":
            return {
                "status": "error",
                "message": "No topic analysis available. Run topic analysis first.",
            }

        topics = self.topic_repo.get_topics(latest_analysis.id)
        if not topics:
            return {
                "status": "error",
                "message": "No topics found for this audience.",
            }

        # Gerar fingerprint
        topic_names = [t.name for t in topics]
        fingerprint = YouTubeValidationRepository.generate_fingerprint(
            audience_id, topic_names
        )

        # Se não forçar, verificar se já existe validação com mesmo fingerprint
        if not force:
            existing = self.validation_repo.find_by_fingerprint(
                audience_id, fingerprint
            )
            if existing:
                return {
                    "status": existing.status,
                    "message": f"Existing validation (status={existing.status}).",
                    "validation_id": str(existing.id),
                }

        # Criar registro de validação com status "processing"
        validation = self.validation_repo.create_validation(
            audience_id, user_id, fingerprint
        )
        logger.info(
            "Triggering YouTube validation for audience %s (validation %s)",
            audience_id,
            validation.id,
        )

        # Disparar em background
        self._run_in_background(audience_id, validation.id, user_id, language)

        return {
            "status": "processing",
            "message": "YouTube validation started. Check back in a few minutes.",
            "validation_id": str(validation.id),
            "topics_count": len(topics),
        }

    def _run_in_background(
        self,
        audience_id: UUID,
        validation_id: UUID,
        user_id: UUID,
        language: str = "en",
    ) -> None:
        """Dispara validação YouTube em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.youtube_validation.application.use_cases.extract_youtube_validation_use_case.extract_youtube_validation_use_case import (
                    ExtractYouTubeValidationUseCase,
                )

                use_case = ExtractYouTubeValidationUseCase(db)
                use_case.execute(audience_id, validation_id, user_id, language=language)
            except Exception:
                logger.exception(
                    "Background YouTube validation failed for audience %s",
                    audience_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()

"""Use case para disparar geração de sumário narrativo em background."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)

logger = logging.getLogger(__name__)


class TriggerThemeSummaryUseCase:
    """
    Verifica pré-requisitos e dispara geração de sumário narrativo em background.
    Requer que exista uma theme_analysis com status 'ready' e um tema válido.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.summary_repo = ThemeSummaryRepository(db)

    def execute(
        self,
        audience_id: UUID,
        theme_id: UUID,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara geração de sumário narrativo.
        Retorna dict com status e informações.
        """
        # 1. Buscar theme_analysis ready
        theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
            audience_id, window
        )
        if not theme_analysis or theme_analysis.status != "ready":
            return {
                "status": "error",
                "message": "No theme analysis found for this period. Run theme analysis first.",
            }

        # 2. Verificar se o tema existe na análise
        themes = self.theme_repo.get_themes(analysis_id=theme_analysis.id)
        theme = next((t for t in themes if str(t.id) == str(theme_id)), None)
        if not theme:
            return {
                "status": "error",
                "message": "Theme not found in the current analysis.",
            }

        # 3. Gerar fingerprint
        # Buscar intent_analysis_id se disponível
        intent_analysis_id = self._get_intent_analysis_id(audience_id, window)
        fingerprint = ThemeSummaryRepository.generate_fingerprint(
            theme_id, intent_analysis_id
        )

        # 4. Verificar se já existe sumário com mesmo fingerprint
        existing = self.summary_repo.find_by_fingerprint(theme_id, fingerprint)
        if existing:
            return {
                "status": "already_exists",
                "message": "Sumário narrativo já existe para este tema com os dados atuais.",
                "summary_id": str(existing.id),
            }

        logger.info(
            "Triggering theme summary for theme '%s' (audience %s, %s)",
            theme.name,
            audience_id,
            window,
        )

        # 5. Disparar em background
        self._run_in_background(
            audience_id=audience_id,
            theme_id=theme_id,
            analysis_id=theme_analysis.id,
            window=window,
            fingerprint=fingerprint,
            language=language,
        )

        return {
            "status": "processing",
            "message": f"Sumário narrativo para '{theme.name}' sendo gerado. Consulte novamente em alguns minutos.",
            "theme_id": str(theme_id),
        }

    def _get_intent_analysis_id(
        self, audience_id: UUID, window: str
    ) -> UUID | None:
        """Busca ID da classificação de intenção se disponível."""
        try:
            from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
                IntentClassificationRepository,
            )

            intent_repo = IntentClassificationRepository(self.db)
            latest = intent_repo.find_latest_by_audience_and_window(
                audience_id, window
            )
            if latest and latest.status == "ready":
                return latest.id
        except Exception:
            pass
        return None

    def _run_in_background(
        self,
        audience_id: UUID,
        theme_id: UUID,
        analysis_id: UUID,
        window: str,
        fingerprint: str,
        language: str = "en",
    ) -> None:
        """Dispara geração de sumário em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.theme_analysis.application.use_cases.generate_theme_summary_use_case.generate_theme_summary_use_case import (
                    GenerateThemeSummaryUseCase,
                )

                use_case = GenerateThemeSummaryUseCase(db)
                use_case.execute(
                    audience_id,
                    theme_id,
                    analysis_id,
                    window,
                    fingerprint,
                    language=language,
                )
            except Exception:
                logger.exception(
                    "Background theme summary generation failed for theme %s",
                    theme_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()

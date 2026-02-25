"""Trigger para geração de dados estruturados do painel de temas."""

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
from app.modules.theme_analysis.infra.repositories.theme_panel_repository import (
    ThemePanelRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)

logger = logging.getLogger(__name__)


class TriggerThemePanelUseCase:
    """
    Verifica pré-requisitos e dispara geração de dados do painel em background.
    Requer que exista uma theme_analysis com status 'ready' e um tema válido.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.panel_repo = ThemePanelRepository(db)
        self.summary_repo = ThemeSummaryRepository(db)

    def execute(
        self,
        audience_id: UUID,
        theme_id: UUID,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara geração de dados do painel.
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
        # Usar summary_id se existir para invalidar cache quando sumário muda
        summary = self.summary_repo.find_by_theme_id(theme_id)
        summary_id = summary.id if summary else None
        fingerprint = ThemePanelRepository.generate_fingerprint(theme_id, summary_id)

        # 4. Verificar se já existe painel com mesmo fingerprint
        existing = self.panel_repo.find_by_fingerprint(theme_id, fingerprint)
        if existing:
            return {
                "status": "already_exists",
                "message": "Painel de dados já existe para este tema com os dados atuais.",
                "panel_id": str(existing.id),
            }

        logger.info(
            "Triggering theme panel for theme '%s' (audience %s, %s)",
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
            "message": f"Dados do painel para '{theme.name}' sendo gerados. Consulte novamente em alguns minutos.",
            "theme_id": str(theme_id),
        }

    def _run_in_background(
        self,
        audience_id: UUID,
        theme_id: UUID,
        analysis_id: UUID,
        window: str,
        fingerprint: str,
        language: str = "en",
    ) -> None:
        """Dispara geração de painel em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.theme_analysis.application.use_cases.generate_theme_panel_use_case.generate_theme_panel_use_case import (
                    GenerateThemePanelUseCase,
                )

                use_case = GenerateThemePanelUseCase(db)
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
                    "Background theme panel generation failed for theme %s",
                    theme_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()

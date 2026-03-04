"""Use case para producao de conteudo completo + geracao de imagem."""

import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.content_suggestions.application.use_cases.produce_content_use_case.agent.content_production_agent import (
    create_content_production_agent,
)
from app.modules.content_suggestions.infra.repositories.content_draft_repository import (
    ContentDraftRepository,
)
from app.modules.content_suggestions.infra.repositories.content_suggestion_repository import (
    ContentSuggestionRepository,
)

logger = logging.getLogger(__name__)

PLATFORM_ASPECT_RATIOS = {
    "linkedin": "16:9",
    "twitter": "16:9",
    "instagram": "1:1",
    "reddit": "16:9",
}


class ProduceContentUseCase:
    """
    Roda agente de producao de conteudo e gera imagem.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.suggestion_repo = ContentSuggestionRepository(db)
        self.draft_repo = ContentDraftRepository(db)

    def execute(
        self,
        suggestion_id: UUID,
        target_platforms: list[str],
        language: str = "en",
    ) -> bool:
        """
        Produz conteudo completo para as plataformas selecionadas.

        Args:
            suggestion_id: ID da sugestao a produzir
            target_platforms: Plataformas alvo (linkedin, twitter, instagram, reddit)
            language: Idioma preferido

        Returns:
            True se concluiu com sucesso
        """
        try:
            # 1. Buscar sugestao
            suggestion = self.suggestion_repo.get_suggestion_by_id(suggestion_id)
            if not suggestion:
                logger.error("Suggestion %s not found", suggestion_id)
                return False

            # 2. Buscar audiencia e comunidades
            analysis = suggestion.analysis
            audience = self.audience_repo.find_by_id(analysis.audience_id)
            if not audience:
                self.draft_repo.mark_drafts_failed(suggestion_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(analysis.audience_id)
            community_names = [c.subreddit_name for c in communities]

            # 3. Montar dict da sugestao para o agente
            suggestion_dict = {
                "title": suggestion.title,
                "approach": suggestion.approach,
                "why_now": suggestion.why_now,
                "evidence": suggestion.evidence,
                "format": suggestion.format,
                "format_rationale": suggestion.format_rationale,
                "emotional_tone": suggestion.emotional_tone,
                "tone_rationale": suggestion.tone_rationale,
                "outline": suggestion.outline,
                "keywords": suggestion.keywords,
                "research_notes": suggestion.research_notes,
                "image_prompt": suggestion.image_prompt,
                "source_topics": suggestion.source_topics,
            }

            logger.info(
                "Running content production for suggestion '%s' on %d platforms",
                suggestion.title[:50],
                len(target_platforms),
            )

            # 4. Rodar agente LangGraph
            agent = create_content_production_agent()
            model_name = os.getenv(
                "CONTENT_PRODUCTION_MODEL",
                os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
            )

            result = agent.invoke({
                "suggestion": suggestion_dict,
                "target_platforms": target_platforms,
                "audience_name": audience.name,
                "audience_description": audience.description,
                "community_names": community_names,
                "language": language,
                "platform_drafts": [],
                "refined_drafts": [],
            })

            refined = result.get("refined_drafts", [])
            if not refined:
                self.draft_repo.mark_drafts_failed(
                    suggestion_id, "Agent returned no drafts"
                )
                return False

            # 5. Gerar imagem
            image_url = self._generate_and_upload_image(
                image_prompt=suggestion.image_prompt,
                suggestion_id=suggestion_id,
                platforms=target_platforms,
                user_id=audience.user_id,
            )

            # 6. Salvar drafts com model_used
            for draft in refined:
                draft["model_used"] = model_name

            self.draft_repo.save_drafts(
                suggestion_id=suggestion_id,
                drafts=refined,
                image_url=image_url,
            )

            logger.info(
                "Content production complete: %d drafts, image=%s",
                len(refined),
                "yes" if image_url else "no",
            )

            # 7. Notificar usuario
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                platforms_str = ", ".join(target_platforms)
                NotificationEventService(self.db).notify(
                    user_id=audience.user_id,
                    type_="content_production_ready",
                    title="Content Ready",
                    message=f"Content for '{suggestion.title[:80]}' ready on {platforms_str}.",
                    metadata={
                        "audience_id": str(analysis.audience_id),
                        "suggestion_id": str(suggestion_id),
                        "platforms": target_platforms,
                        "draft_count": len(refined),
                        "has_image": bool(image_url),
                    },
                )
            except Exception:
                logger.debug("Failed to send notification for content production")

            return True

        except Exception as e:
            logger.exception(
                "Content production failed for suggestion %s", suggestion_id
            )
            try:
                self.draft_repo.mark_drafts_failed(suggestion_id, str(e))
            except Exception:
                pass
            try:
                suggestion = self.suggestion_repo.get_suggestion_by_id(suggestion_id)
                if suggestion:
                    from app.modules.notifications.application.services.notification_event_service import (
                        NotificationEventService,
                    )

                    NotificationEventService(self.db).notify(
                        user_id=suggestion.analysis.audience.user_id
                        if hasattr(suggestion.analysis, "audience")
                        else None,
                        type_="content_production_failed",
                        title="Content Production Failed",
                        message=f"Failed to produce content: {e}",
                        metadata={
                            "suggestion_id": str(suggestion_id),
                            "error": str(e),
                        },
                    )
            except Exception:
                pass
            return False

    def _generate_and_upload_image(
        self,
        image_prompt: str | None,
        suggestion_id: UUID,
        platforms: list[str],
        user_id: UUID | None = None,
    ) -> str | None:
        """Gera imagem via Imagen e faz upload para S3.

        Returns:
            A S3 key do arquivo enviado (usada para gerar presigned URLs)
            ou None se a geracao falhar.
        """
        if not image_prompt:
            logger.info("No image_prompt, skipping image generation")
            return None

        try:
            from app.modules.shared.application.services.image_generation_service import (
                ImageGenerationService,
            )
            from app.modules.shared.application.services.storage_service import (
                StorageService,
            )
            from app.modules.shared.domain.entities.uploaded_file import UploadedFile
            from app.modules.shared.infra.repositories.uploaded_file_repository import (
                UploadedFileRepository,
            )

            # Determinar aspect ratio (usar o mais versatil)
            has_instagram = "instagram" in platforms
            aspect_ratio = "1:1" if has_instagram and len(platforms) == 1 else "16:9"

            image_service = ImageGenerationService()
            image_bytes = image_service.generate(
                prompt=image_prompt,
                aspect_ratio=aspect_ratio,
            )

            storage = StorageService()
            key = storage.generate_key(
                prefix=f"content-images/{suggestion_id}"
            )
            storage.upload(data=image_bytes, key=key)

            # Registrar arquivo na tabela uploaded_files
            try:
                file_record = UploadedFile(
                    key=key,
                    url=key,
                    content_type="image/png",
                    size_bytes=len(image_bytes),
                    uploaded_by=user_id,
                )
                UploadedFileRepository(self.db).save(file_record)
                logger.info("Image registered in uploaded_files: %s", key)
            except Exception:
                logger.exception("Failed to register image in uploaded_files")

            logger.info("Image uploaded with key: %s", key)
            return key

        except Exception:
            logger.exception("Image generation/upload failed, continuing without image")
            return None

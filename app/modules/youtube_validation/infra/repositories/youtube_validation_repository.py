import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.youtube_validation.domain.entities.youtube_validation import (
    YouTubeCollectedVideo,
    YouTubeValidation,
)


class YouTubeValidationRepository:
    """Repositório para operações com validações YouTube cross-platform."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(audience_id: UUID, topic_names: list[str]) -> str:
        """Gera fingerprint SHA256 da audiência + tópicos."""
        sorted_names = sorted(n.lower() for n in topic_names)
        content = f"{audience_id}:" + ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_by_audience(self, audience_id: UUID) -> YouTubeValidation | None:
        """Busca a validação mais recente (qualquer status) para a audiência."""
        return (
            self.db.query(YouTubeValidation)
            .filter(YouTubeValidation.audience_id == audience_id)
            .order_by(YouTubeValidation.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> YouTubeValidation | None:
        """Busca validação por fingerprint (mesma composição de tópicos)."""
        return (
            self.db.query(YouTubeValidation)
            .filter(
                YouTubeValidation.audience_id == audience_id,
                YouTubeValidation.fingerprint == fingerprint,
                YouTubeValidation.status.in_(["ready", "processing"]),
            )
            .order_by(YouTubeValidation.created_at.desc())
            .first()
        )

    def create_validation(
        self, audience_id: UUID, user_id: UUID, fingerprint: str
    ) -> YouTubeValidation:
        """Cria um novo registro de validação com status 'processing'."""
        validation = YouTubeValidation(
            audience_id=audience_id,
            user_id=user_id,
            fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(validation)
        self.db.commit()
        self.db.refresh(validation)
        return validation

    def mark_ready(
        self,
        validation_id: UUID,
        analysis_data: dict,
        summary: dict,
        total_videos: int,
        total_comments: int,
        model_used: str,
    ) -> YouTubeValidation | None:
        """Marca validação como pronta e salva resultados."""
        validation = (
            self.db.query(YouTubeValidation)
            .filter(YouTubeValidation.id == validation_id)
            .first()
        )
        if not validation:
            return None

        validation.status = "ready"
        validation.analysis_data = analysis_data
        validation.summary = summary
        validation.total_videos = total_videos
        validation.total_comments = total_comments
        validation.model_used = model_used
        validation.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(validation)
        return validation

    def mark_failed(
        self, validation_id: UUID, error_message: str
    ) -> YouTubeValidation | None:
        """Marca validação como falha."""
        validation = (
            self.db.query(YouTubeValidation)
            .filter(YouTubeValidation.id == validation_id)
            .first()
        )
        if not validation:
            return None

        validation.status = "failed"
        validation.error_message = error_message
        validation.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(validation)
        return validation

    def save_collected_videos(self, validation_id: UUID, videos: list[dict]) -> int:
        """Salva vídeos coletados em batch. Retorna quantidade inserida."""
        objects = []
        seen_video_ids: set[str] = set()

        for v in videos:
            vid = v.get("video_id", "")
            if vid in seen_video_ids:
                continue
            seen_video_ids.add(vid)

            published_at = v.get("published_at")
            if isinstance(published_at, str) and published_at:
                try:
                    published_at = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    published_at = None
            elif not isinstance(published_at, datetime):
                published_at = None

            objects.append(
                YouTubeCollectedVideo(
                    validation_id=validation_id,
                    topic_name=v.get("topic_name", ""),
                    video_id=vid,
                    title=v.get("title"),
                    channel_name=v.get("channel_name"),
                    views=v.get("views"),
                    likes=v.get("likes"),
                    duration_seconds=v.get("duration_seconds"),
                    tags=v.get("tags"),
                    description=v.get("description"),
                    comments=v.get("comments"),
                    transcript=v.get("transcript"),
                    transcript_lang=v.get("transcript_lang"),
                    published_at=published_at,
                )
            )

        if objects:
            self.db.add_all(objects)
            self.db.commit()
        return len(objects)

    def get_collected_videos_by_topic(
        self, validation_id: UUID, topic_name: str
    ) -> list[YouTubeCollectedVideo]:
        """Busca vídeos coletados de um tópico específico."""
        return (
            self.db.query(YouTubeCollectedVideo)
            .filter(
                YouTubeCollectedVideo.validation_id == validation_id,
                YouTubeCollectedVideo.topic_name == topic_name,
            )
            .order_by(YouTubeCollectedVideo.views.desc().nullslast())
            .all()
        )

    def delete_old_validations(self, audience_id: UUID, keep_latest: int = 2) -> int:
        """Remove validações antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(YouTubeValidation.id)
            .filter(YouTubeValidation.audience_id == audience_id)
            .order_by(YouTubeValidation.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(YouTubeValidation)
            .filter(
                YouTubeValidation.audience_id == audience_id,
                YouTubeValidation.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted

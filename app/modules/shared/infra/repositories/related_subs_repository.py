from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.related_sub import RelatedSub


class RelatedSubsRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_source(self, source_sub: str) -> list[RelatedSub]:
        """
        Busca comunidades relacionadas por comunidade de origem
        Retorna apenas as que não expiraram
        """
        return (
            self.db.query(RelatedSub)
            .filter(
                RelatedSub.source_sub == source_sub.lower(),
                RelatedSub.expires_at > datetime.now(timezone.utc),
            )
            .all()
        )

    def find_by_source_and_related(
        self, source_sub: str, related_sub: str
    ) -> RelatedSub | None:
        """
        Busca um relacionamento específico
        """
        return (
            self.db.query(RelatedSub)
            .filter(
                RelatedSub.source_sub == source_sub.lower(),
                RelatedSub.related_sub == related_sub.lower(),
            )
            .first()
        )

    def save(self, related_sub: RelatedSub) -> RelatedSub:
        """
        Salva um relacionamento
        """
        self.db.add(related_sub)
        self.db.commit()
        self.db.refresh(related_sub)
        return related_sub

    def save_many(self, related_subs: list[RelatedSub]) -> list[RelatedSub]:
        """
        Salva múltiplos relacionamentos
        """
        self.db.add_all(related_subs)
        self.db.commit()
        return related_subs

    def upsert(self, related_sub: RelatedSub) -> RelatedSub:
        """
        Insere ou atualiza um relacionamento
        """
        existing = self.find_by_source_and_related(
            related_sub.source_sub, related_sub.related_sub
        )
        if existing:
            existing.related_sub_title = related_sub.related_sub_title
            existing.related_sub_description = related_sub.related_sub_description
            existing.related_sub_subscribers = related_sub.related_sub_subscribers
            existing.discovered_via = related_sub.discovered_via
            existing.expires_at = related_sub.expires_at
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.save(related_sub)

    def delete_expired(self) -> int:
        """
        Remove relacionamentos expirados
        """
        deleted = (
            self.db.query(RelatedSub)
            .filter(RelatedSub.expires_at < datetime.now(timezone.utc))
            .delete()
        )
        self.db.commit()
        return deleted

    def get_stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas dos relacionamentos
        """
        total = self.db.query(RelatedSub).count()
        unique_sources = (
            self.db.query(RelatedSub.source_sub).distinct().count()
        )
        return {
            "total_relationships": total,
            "unique_source_communities": unique_sources,
        }

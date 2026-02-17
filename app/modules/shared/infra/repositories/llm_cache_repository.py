from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.llm_cache import LLMCache


class LLMCacheRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_hash_and_type(self, input_hash: str, task_type: str) -> LLMCache | None:
        """
        Busca cache pelo hash do input e tipo de task
        Retorna apenas se ainda não expirou
        """
        return (
            self.db.query(LLMCache)
            .filter(
                LLMCache.input_hash == input_hash,
                LLMCache.task_type == task_type,
                LLMCache.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )

    def save(self, cache_entry: LLMCache) -> LLMCache:
        """
        Salva ou atualiza uma entrada de cache
        """
        self.db.add(cache_entry)
        self.db.commit()
        self.db.refresh(cache_entry)
        return cache_entry

    def delete_expired(self) -> int:
        """
        Remove entradas expiradas
        Retorna quantidade removida
        """
        deleted = (
            self.db.query(LLMCache)
            .filter(LLMCache.expires_at < datetime.now(timezone.utc))
            .delete()
        )
        self.db.commit()
        return deleted

    def get_stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do cache
        """
        total = self.db.query(LLMCache).count()
        by_type = {}
        for task_type in ["related_terms", "pain_analysis", "theme_summary"]:
            count = (
                self.db.query(LLMCache)
                .filter(LLMCache.task_type == task_type)
                .count()
            )
            by_type[task_type] = count

        return {"total": total, "by_type": by_type}

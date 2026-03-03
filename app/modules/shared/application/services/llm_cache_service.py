import hashlib
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.llm_cache import LLMCache
from app.modules.shared.infra.repositories.llm_cache_repository import LLMCacheRepository


class TaskType(str, Enum):
    RELATED_TERMS = "related_terms"
    PAIN_ANALYSIS = "pain_analysis"
    THEME_SUMMARY = "theme_summary"
    COMMUNITY_CATEGORIZATION = "community_categorization"
    AUDIENCE_EXPANSION = "audience_expansion"
    TOPIC_QA = "topic_qa"
    INTENT_QA = "intent_qa"


# TTL em horas para cada tipo de task
TTL_CONFIG = {
    TaskType.RELATED_TERMS: 720,              # 30 dias
    TaskType.PAIN_ANALYSIS: 48,               # 48 horas
    TaskType.THEME_SUMMARY: 24,               # 24 horas
    TaskType.COMMUNITY_CATEGORIZATION: 720,   # 30 dias
    TaskType.AUDIENCE_EXPANSION: 24,          # 24 horas
    TaskType.TOPIC_QA: 48,                    # 48 horas
    TaskType.INTENT_QA: 48,                   # 48 horas
}


class LLMCacheService:
    def __init__(self, db: Session):
        self.repository = LLMCacheRepository(db)

    def _generate_hash(self, input_text: str, task_type: TaskType) -> str:
        """
        Gera SHA256 hash do input + task_type
        """
        content = f"{task_type.value}:{input_text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, input_text: str, task_type: TaskType) -> dict[str, Any] | None:
        """
        Busca resultado no cache
        Retorna None se não existe ou expirou
        """
        input_hash = self._generate_hash(input_text, task_type)
        cache_entry = self.repository.find_by_hash_and_type(input_hash, task_type.value)

        if cache_entry:
            return cache_entry.result_json

        return None

    def set(self, input_text: str, task_type: TaskType, result: dict[str, Any]) -> LLMCache:
        """
        Salva resultado no cache com TTL apropriado
        """
        input_hash = self._generate_hash(input_text, task_type)
        ttl_hours = TTL_CONFIG.get(task_type, 24)

        cache_entry = LLMCache(
            input_hash=input_hash,
            task_type=task_type.value,
            input_text=input_text,
            result_json=result,
            ttl_hours=ttl_hours,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        )

        return self.repository.save(cache_entry)

    def get_or_compute(
        self,
        input_text: str,
        task_type: TaskType,
        compute_fn: callable,
    ) -> dict[str, Any]:
        """
        Busca no cache ou computa usando a função fornecida
        """
        cached = self.get(input_text, task_type)
        if cached:
            return cached

        result = compute_fn()
        self.set(input_text, task_type, result)
        return result

    def cleanup_expired(self) -> int:
        """
        Remove entradas expiradas do cache
        """
        return self.repository.delete_expired()

    def get_stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do cache
        """
        return self.repository.get_stats()

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.intent_ask.domain.entities.intent_ask_log import IntentAskLog


class IntentAskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_log(
        self,
        analysis_id: UUID | None,
        audience_id: UUID,
        user_id: UUID,
        intent_category: str,
        question: str,
        answer: str | None,
        context_quality: str,
        cached: bool = False,
    ) -> IntentAskLog:
        """Persiste uma pergunta/resposta no historico."""
        log = IntentAskLog(
            analysis_id=analysis_id,
            audience_id=audience_id,
            user_id=user_id,
            intent_category=intent_category,
            question=question,
            answer=answer,
            context_quality=context_quality,
            cached=cached,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_recent_by_audience_and_category(
        self, audience_id: UUID, intent_category: str, limit: int = 10
    ) -> list[IntentAskLog]:
        """Busca perguntas recentes de uma audiencia por categoria de intencao."""
        return (
            self.db.query(IntentAskLog)
            .filter(
                IntentAskLog.audience_id == audience_id,
                IntentAskLog.intent_category == intent_category,
            )
            .order_by(IntentAskLog.created_at.desc())
            .limit(limit)
            .all()
        )

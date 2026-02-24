from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_ask.domain.entities.topic_ask_log import TopicAskLog


class TopicAskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_log(
        self,
        topic_id: UUID,
        audience_id: UUID,
        user_id: UUID,
        question: str,
        answer: str | None,
        context_quality: str,
        cached: bool = False,
    ) -> TopicAskLog:
        """Persiste uma pergunta/resposta no histórico."""
        log = TopicAskLog(
            topic_id=topic_id,
            audience_id=audience_id,
            user_id=user_id,
            question=question,
            answer=answer,
            context_quality=context_quality,
            cached=cached,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_recent_by_topic(
        self, topic_id: UUID, limit: int = 10
    ) -> list[TopicAskLog]:
        """Busca perguntas recentes de um tópico."""
        return (
            self.db.query(TopicAskLog)
            .filter(TopicAskLog.topic_id == topic_id)
            .order_by(TopicAskLog.created_at.desc())
            .limit(limit)
            .all()
        )

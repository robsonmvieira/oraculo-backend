"""Use case para avaliar e gerar alertas apos analises de topicos e temas."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_alerts.application.helpers.alert_rules import (
    classify_growth_severity,
    classify_new_theme_severity,
    classify_new_topic_severity,
)
from app.modules.topic_alerts.infra.repositories.topic_alert_repository import (
    TopicAlertRepository,
)

logger = logging.getLogger(__name__)


class EvaluateAlertsUseCase:
    """
    Avalia resultados de analises e gera alertas quando detecta:
    - Topicos novos (ausentes no snapshot anterior)
    - Crescimento explosivo (acima do threshold)
    - Temas semanais/mensais novos
    """

    def __init__(self, db: Session):
        self.db = db
        self.alert_repo = TopicAlertRepository(db)

    def evaluate_topics(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        user_id: UUID,
        audience_name: str,
    ) -> int:
        """
        Avalia topicos recem-extraidos e gera alertas.

        Args:
            audience_id: ID da audiencia
            analysis_id: ID da analise recem-concluida
            user_id: ID do dono da audiencia
            audience_name: Nome da audiencia (para mensagens)

        Returns:
            Numero de alertas gerados
        """
        from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
            AudienceTopicRepository,
        )
        from app.modules.topic_snapshots.infra.repositories.topic_snapshot_repository import (
            TopicSnapshotRepository,
        )

        topic_repo = AudienceTopicRepository(self.db)
        snapshot_repo = TopicSnapshotRepository(self.db)

        # Buscar topicos da analise recem-concluida
        new_topics = topic_repo.get_topics(analysis_id=analysis_id)
        if not new_topics:
            return 0

        # Buscar nomes normalizados do snapshot anterior
        previous_names = self._get_previous_topic_names(
            audience_id, analysis_id, snapshot_repo
        )

        alerts_data: list[dict] = []

        for topic in new_topics:
            name_normalized = topic.name.strip().lower()

            # --- Regra 1: Topico novo ---
            if previous_names is not None and name_normalized not in previous_names:
                community_count = len(topic.communities) if topic.communities else 0
                severity = classify_new_topic_severity(
                    mention_frequency=topic.mention_frequency,
                    community_count=community_count,
                )
                alerts_data.append(
                    {
                        "audience_id": audience_id,
                        "user_id": user_id,
                        "alert_type": "new_topic",
                        "severity": severity,
                        "title": f"New topic: {topic.name}",
                        "message": (
                            f"New topic '{topic.name}' detected in audience "
                            f"'{audience_name}' across {community_count} "
                            f"{'community' if community_count == 1 else 'communities'}."
                        ),
                        "metadata_": {
                            "topic_id": str(topic.id),
                            "topic_name": topic.name,
                            "topic_name_normalized": name_normalized,
                            "audience_id": str(audience_id),
                            "audience_name": audience_name,
                            "analysis_id": str(analysis_id),
                            "mention_frequency": topic.mention_frequency,
                            "community_count": community_count,
                        },
                    }
                )
                continue  # Topico novo nao precisa checar growth

            # --- Regra 2: Crescimento explosivo ---
            growth_data = snapshot_repo.calculate_real_growth(
                audience_id=audience_id,
                topic_name_normalized=name_normalized,
            )
            if growth_data:
                severity = classify_growth_severity(growth_data["growth_percentage"])
                if severity:
                    alerts_data.append(
                        {
                            "audience_id": audience_id,
                            "user_id": user_id,
                            "alert_type": "growth_spike",
                            "severity": severity,
                            "title": f"Growth spike: {topic.name}",
                            "message": (
                                f"Topic '{topic.name}' in audience '{audience_name}' "
                                f"surged {growth_data['growth_percentage']:+.1f}% "
                                f"(trend: {growth_data['trend']})."
                            ),
                            "metadata_": {
                                "topic_id": str(topic.id),
                                "topic_name": topic.name,
                                "topic_name_normalized": name_normalized,
                                "audience_id": str(audience_id),
                                "audience_name": audience_name,
                                "analysis_id": str(analysis_id),
                                "growth_percentage": growth_data["growth_percentage"],
                                "trend": growth_data["trend"],
                            },
                        }
                    )

        if not alerts_data:
            return 0

        count = self.alert_repo.create_batch(alerts_data)
        self._send_notifications(user_id, audience_id, audience_name, alerts_data)

        logger.info(
            "Generated %d topic alerts for audience '%s'",
            count,
            audience_name,
        )
        return count

    def evaluate_themes(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        user_id: UUID,
        audience_name: str,
        time_window: str,
    ) -> int:
        """
        Avalia temas recem-extraidos e gera alertas para temas novos.

        Args:
            audience_id: ID da audiencia
            analysis_id: ID da analise de temas recem-concluida
            user_id: ID do dono da audiencia
            audience_name: Nome da audiencia
            time_window: Janela temporal (week ou month)

        Returns:
            Numero de alertas gerados
        """
        from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
            ThemeAnalysisRepository,
        )

        theme_repo = ThemeAnalysisRepository(self.db)

        # Buscar temas da analise atual
        current_themes = theme_repo.get_themes(analysis_id=analysis_id)
        if not current_themes:
            return 0

        # Buscar nomes dos temas da analise anterior (mesma janela)
        previous_names = self._get_previous_theme_names(
            audience_id, analysis_id, time_window, theme_repo
        )

        alerts_data: list[dict] = []

        for theme in current_themes:
            name_normalized = theme.name.strip().lower()

            if previous_names is not None and name_normalized not in previous_names:
                severity = classify_new_theme_severity(theme.engagement_score)
                alerts_data.append(
                    {
                        "audience_id": audience_id,
                        "user_id": user_id,
                        "alert_type": "new_theme",
                        "severity": severity,
                        "title": f"New theme: {theme.name}",
                        "message": (
                            f"New {time_window}ly theme '{theme.name}' detected in "
                            f"audience '{audience_name}' "
                            f"(engagement: {theme.engagement_score or 0:.1f}/10)."
                        ),
                        "metadata_": {
                            "theme_id": str(theme.id),
                            "theme_name": theme.name,
                            "topic_name_normalized": name_normalized,
                            "audience_id": str(audience_id),
                            "audience_name": audience_name,
                            "analysis_id": str(analysis_id),
                            "time_window": time_window,
                            "engagement_score": theme.engagement_score,
                        },
                    }
                )

        if not alerts_data:
            return 0

        count = self.alert_repo.create_batch(alerts_data)
        self._send_notifications(user_id, audience_id, audience_name, alerts_data)

        logger.info(
            "Generated %d theme alerts for audience '%s' (%s)",
            count,
            audience_name,
            time_window,
        )
        return count

    # --- Metodos auxiliares ---

    def _get_previous_topic_names(
        self,
        audience_id: UUID,
        current_analysis_id: UUID,
        snapshot_repo,
    ) -> set[str] | None:
        """
        Retorna set de nomes normalizados do snapshot mais recente.
        Retorna None se nao houver snapshot (primeira analise).
        """
        from app.modules.topic_snapshots.domain.entities.topic_snapshot import (
            TopicSnapshot,
        )

        snapshots = (
            self.db.query(TopicSnapshot.topic_name_normalized)
            .filter(TopicSnapshot.audience_id == audience_id)
            .distinct()
            .all()
        )

        if not snapshots:
            return None

        return {s.topic_name_normalized for s in snapshots}

    def _get_previous_theme_names(
        self,
        audience_id: UUID,
        current_analysis_id: UUID,
        time_window: str,
        theme_repo,
    ) -> set[str] | None:
        """
        Retorna set de nomes normalizados dos temas da analise anterior
        (mesma janela temporal). Retorna None se nao houver analise anterior.
        """
        from app.modules.theme_analysis.domain.entities.theme import (
            Theme,
            ThemeAnalysis,
        )

        # Buscar as 2 analises mais recentes (ready) da mesma janela
        analyses = (
            self.db.query(ThemeAnalysis)
            .filter(
                ThemeAnalysis.audience_id == audience_id,
                ThemeAnalysis.time_window == time_window,
                ThemeAnalysis.status == "ready",
            )
            .order_by(ThemeAnalysis.created_at.desc())
            .limit(2)
            .all()
        )

        if len(analyses) < 2:
            return None

        # A segunda e a anterior
        previous_analysis = analyses[1]

        themes = (
            self.db.query(Theme.name)
            .filter(Theme.analysis_id == previous_analysis.id)
            .all()
        )

        return {t.name.strip().lower() for t in themes}

    def _send_notifications(
        self,
        user_id: UUID,
        audience_id: UUID,
        audience_name: str,
        alerts_data: list[dict],
    ) -> None:
        """Envia notificacoes SSE para cada alerta gerado."""
        try:
            from app.modules.notifications.application.services.notification_event_service import (
                NotificationEventService,
            )

            notifier = NotificationEventService(self.db)

            for alert in alerts_data:
                notifier.notify(
                    user_id=user_id,
                    type_=f"topic_alert_{alert['alert_type']}",
                    title=alert["title"],
                    message=alert["message"],
                    metadata=alert["metadata_"],
                )
        except Exception:
            logger.debug("Failed to send SSE notifications for alerts")

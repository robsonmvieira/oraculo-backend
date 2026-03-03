from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.domain.entities.audience import Audience, AudienceCommunity


class AudienceRepository:
    """
    Repositório para operações com audiences.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: str | None = None,
        user_id: UUID | None = None,
    ) -> Audience:
        """
        Cria uma nova audiência.
        """
        audience = Audience(
            name=name,
            description=description,
            user_id=user_id,
        )
        self.db.add(audience)
        self.db.commit()
        self.db.refresh(audience)
        return audience

    def find_by_id(self, audience_id: UUID) -> Audience | None:
        """
        Busca audiência por ID.
        """
        return self.db.query(Audience).filter(Audience.id == audience_id).first()

    def find_all(self, user_id: UUID | None = None) -> list[Audience]:
        """
        Lista todas as audiências, opcionalmente filtradas por usuário.
        """
        query = self.db.query(Audience)
        if user_id:
            query = query.filter(Audience.user_id == user_id)
        return query.order_by(Audience.created_at.desc()).all()

    def update(
        self,
        audience_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Audience | None:
        """
        Atualiza uma audiência.
        """
        audience = self.find_by_id(audience_id)
        if not audience:
            return None

        if name is not None:
            audience.name = name
        if description is not None:
            audience.description = description

        self.db.commit()
        self.db.refresh(audience)
        return audience

    def delete(self, audience_id: UUID) -> bool:
        """
        Remove uma audiência.
        """
        audience = self.find_by_id(audience_id)
        if not audience:
            return False

        self.db.delete(audience)
        self.db.commit()
        return True

    def add_community(
        self,
        audience_id: UUID,
        subreddit_name: str,
    ) -> AudienceCommunity | None:
        """
        Adiciona uma comunidade à audiência.
        """
        # Verificar se audiência existe
        audience = self.find_by_id(audience_id)
        if not audience:
            return None

        # Verificar se já existe
        existing = (
            self.db.query(AudienceCommunity)
            .filter(
                AudienceCommunity.audience_id == audience_id,
                AudienceCommunity.subreddit_name == subreddit_name.lower(),
            )
            .first()
        )
        if existing:
            return existing

        community = AudienceCommunity(
            audience_id=audience_id,
            subreddit_name=subreddit_name.lower(),
        )
        self.db.add(community)
        self.db.commit()
        self.db.refresh(community)
        return community

    def remove_community(
        self,
        audience_id: UUID,
        subreddit_name: str,
    ) -> bool:
        """
        Remove uma comunidade da audiência.
        """
        community = (
            self.db.query(AudienceCommunity)
            .filter(
                AudienceCommunity.audience_id == audience_id,
                AudienceCommunity.subreddit_name == subreddit_name.lower(),
            )
            .first()
        )
        if not community:
            return False

        self.db.delete(community)
        self.db.commit()
        return True

    def sync_communities(
        self,
        audience_id: UUID,
        subreddit_names: list[str],
    ) -> tuple[list[AudienceCommunity], set[str], set[str]]:
        """
        Sincroniza comunidades de uma audiência com a lista desejada.
        Remove as que não estão na lista, adiciona as novas.

        Returns:
            (communities, to_add, to_remove)
        """
        current = self.get_communities(audience_id)
        current_names = {c.subreddit_name for c in current}
        desired_names = {name.lower() for name in subreddit_names}

        to_remove = current_names - desired_names
        to_add = desired_names - current_names

        if to_remove:
            self.db.query(AudienceCommunity).filter(
                AudienceCommunity.audience_id == audience_id,
                AudienceCommunity.subreddit_name.in_(to_remove),
            ).delete(synchronize_session="fetch")

        for name in to_add:
            self.db.add(AudienceCommunity(audience_id=audience_id, subreddit_name=name))

        self.db.commit()
        return self.get_communities(audience_id), to_add, to_remove

    def remove_communities_by_names(
        self,
        audience_id: UUID,
        subreddit_names: list[str],
    ) -> None:
        """Remove comunidades específicas de uma audiência."""
        self.db.query(AudienceCommunity).filter(
            AudienceCommunity.audience_id == audience_id,
            AudienceCommunity.subreddit_name.in_([n.lower() for n in subreddit_names]),
        ).delete(synchronize_session="fetch")
        self.db.commit()

    def get_communities(self, audience_id: UUID) -> list[AudienceCommunity]:
        """
        Lista comunidades de uma audiência.
        """
        return (
            self.db.query(AudienceCommunity)
            .filter(AudienceCommunity.audience_id == audience_id)
            .order_by(AudienceCommunity.added_at.desc())
            .all()
        )

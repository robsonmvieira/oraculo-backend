from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_templates.domain.entities.audience_template import (
    AudienceTemplate,
    AudienceTemplateCommunity,
)


class AudienceTemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        slug: str,
        description: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        display_order: int = 0,
    ) -> AudienceTemplate:
        """Cria um novo template de audiência."""
        template = AudienceTemplate(
            name=name,
            slug=slug,
            description=description,
            icon=icon,
            category=category,
            display_order=display_order,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def find_by_id(self, template_id: UUID) -> AudienceTemplate | None:
        """Busca template por ID."""
        return (
            self.db.query(AudienceTemplate)
            .filter(AudienceTemplate.id == template_id)
            .first()
        )

    def find_by_slug(self, slug: str) -> AudienceTemplate | None:
        """Busca template por slug."""
        return (
            self.db.query(AudienceTemplate)
            .filter(AudienceTemplate.slug == slug)
            .first()
        )

    def find_all(
        self, active_only: bool = True, category: str | None = None
    ) -> list[AudienceTemplate]:
        """Lista todos os templates."""
        query = self.db.query(AudienceTemplate)

        if active_only:
            query = query.filter(AudienceTemplate.is_active.is_(True))

        if category:
            query = query.filter(AudienceTemplate.category == category)

        return query.order_by(AudienceTemplate.display_order).all()

    def update(
        self,
        template_id: UUID,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        display_order: int | None = None,
    ) -> AudienceTemplate | None:
        """Atualiza um template."""
        template = self.find_by_id(template_id)
        if not template:
            return None

        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if icon is not None:
            template.icon = icon
        if category is not None:
            template.category = category
        if is_active is not None:
            template.is_active = is_active
        if display_order is not None:
            template.display_order = display_order

        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template_id: UUID) -> bool:
        """Remove um template."""
        template = self.find_by_id(template_id)
        if not template:
            return False

        self.db.delete(template)
        self.db.commit()
        return True

    # ===== Comunidades =====

    def add_community(
        self, template_id: UUID, subreddit_name: str
    ) -> AudienceTemplateCommunity | None:
        """Adiciona uma comunidade ao template."""
        template = self.find_by_id(template_id)
        if not template:
            return None

        # Verificar se já existe
        existing = (
            self.db.query(AudienceTemplateCommunity)
            .filter(
                AudienceTemplateCommunity.template_id == template_id,
                AudienceTemplateCommunity.subreddit_name == subreddit_name.lower(),
            )
            .first()
        )
        if existing:
            return existing

        community = AudienceTemplateCommunity(
            template_id=template_id,
            subreddit_name=subreddit_name.lower(),
        )
        self.db.add(community)
        self.db.commit()
        self.db.refresh(community)
        return community

    def add_communities(
        self, template_id: UUID, subreddit_names: list[str]
    ) -> list[AudienceTemplateCommunity]:
        """Adiciona múltiplas comunidades ao template."""
        communities = []
        for name in subreddit_names:
            community = self.add_community(template_id, name)
            if community:
                communities.append(community)
        return communities

    def remove_community(self, template_id: UUID, subreddit_name: str) -> bool:
        """Remove uma comunidade do template."""
        community = (
            self.db.query(AudienceTemplateCommunity)
            .filter(
                AudienceTemplateCommunity.template_id == template_id,
                AudienceTemplateCommunity.subreddit_name == subreddit_name.lower(),
            )
            .first()
        )
        if not community:
            return False

        self.db.delete(community)
        self.db.commit()
        return True

    def get_communities(self, template_id: UUID) -> list[AudienceTemplateCommunity]:
        """Lista comunidades de um template."""
        return (
            self.db.query(AudienceTemplateCommunity)
            .filter(AudienceTemplateCommunity.template_id == template_id)
            .all()
        )

    def clear_communities(self, template_id: UUID) -> int:
        """Remove todas as comunidades de um template."""
        count = (
            self.db.query(AudienceTemplateCommunity)
            .filter(AudienceTemplateCommunity.template_id == template_id)
            .delete()
        )
        self.db.commit()
        return count

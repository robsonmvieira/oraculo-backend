import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Carregar variáveis de ambiente
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Configurar a URL do banco de dados a partir da variável de ambiente
database_url = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/crmDatabase"
)
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# Importar o Base e todos os models
from app.modules.shared.infra.database.orm.metadata import Base  # noqa: E402
from app.modules.identity.domain.entities import user  # noqa: E402
from app.modules.audiences.domain.entities import audience  # noqa: E402
from app.modules.shared.domain.entities import community_stats  # noqa: E402
from app.modules.shared.domain.entities import llm_cache  # noqa: E402
from app.modules.shared.domain.entities import related_sub  # noqa: E402
from app.modules.similar_communities.domain.entities import community_embedding  # noqa: E402
from app.modules.similar_communities.domain.entities import user_feedback  # noqa: E402
from app.modules.audience_templates.domain.entities import audience_template  # noqa: E402
from app.modules.audience_topics.domain.entities import audience_topic  # noqa: E402
from app.modules.audience_keywords.domain.entities import audience_keyword  # noqa: E402
from app.modules.topic_deep_dive.domain.entities import topic_deep_dive  # noqa: E402
from app.modules.topic_patterns.domain.entities import topic_pattern  # noqa: E402
from app.modules.topic_sentiment.domain.entities import topic_sentiment  # noqa: E402
from app.modules.topic_behavioral_patterns.domain.entities import topic_behavioral_pattern  # noqa: E402
from app.modules.topic_snapshots.domain.entities import topic_snapshot  # noqa: E402
from app.modules.notifications.domain.entities import notification  # noqa: E402
from app.modules.topic_chat.domain.entities import topic_conversation  # noqa: E402
from app.modules.topic_chat.domain.entities import topic_conversation_message  # noqa: E402
from app.modules.theme_analysis.domain.entities import theme  # noqa: E402
from app.modules.intent_classification.domain.entities import intent_classification  # noqa: E402
from app.modules.theme_analysis.domain.entities import theme_summary  # noqa: E402
from app.modules.theme_analysis.domain.entities import theme_panel  # noqa: E402
from app.modules.content_suggestions.domain.entities import content_suggestion  # noqa: E402
from app.modules.content_suggestions.domain.entities import content_draft  # noqa: E402

target_metadata = [Base.metadata]

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

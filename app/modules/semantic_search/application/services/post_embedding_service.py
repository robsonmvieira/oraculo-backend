import hashlib
import logging
import os

from openai import OpenAI
from sqlalchemy.orm import Session

from app.modules.semantic_search.infra.repositories.post_embedding_repository import (
    PostEmbeddingRepository,
)
from app.modules.theme_analysis.domain.entities.theme import ThemePost

logger = logging.getLogger(__name__)


class PostEmbeddingService:
    """
    Service for generating and managing post embeddings.
    Uses OpenAI text-embedding-3-small (1536 dimensions).
    """

    MODEL = "text-embedding-3-small"
    DIMENSIONS = 1536
    BATCH_SIZE = 100

    def __init__(self, db: Session):
        self.db = db
        self.repository = PostEmbeddingRepository(db)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_embedding(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.MODEL,
            input=text,
            dimensions=self.DIMENSIONS,
        )
        return response.data[0].embedding

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.MODEL,
            input=texts,
            dimensions=self.DIMENSIONS,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    def ensure_posts_embedded(self, theme_posts: list[ThemePost]) -> int:
        """
        Ensure all given ThemePosts have embeddings.
        Generates missing embeddings in batches.
        Returns count of newly generated embeddings.
        """
        unique_posts: dict[str, ThemePost] = {}
        for tp in theme_posts:
            if tp.post_reddit_id not in unique_posts:
                unique_posts[tp.post_reddit_id] = tp

        all_ids = list(unique_posts.keys())
        missing_ids = self.repository.find_without_embeddings(all_ids)

        if not missing_ids:
            logger.info("All %d posts already have embeddings", len(all_ids))
            return 0

        logger.info(
            "Generating embeddings for %d/%d posts",
            len(missing_ids),
            len(all_ids),
        )

        generated = 0
        posts_to_embed = [unique_posts[pid] for pid in missing_ids]

        for i in range(0, len(posts_to_embed), self.BATCH_SIZE):
            batch = posts_to_embed[i : i + self.BATCH_SIZE]
            texts = [self._post_to_text(tp) for tp in batch]
            embeddings = self.generate_batch_embeddings(texts)

            for tp, embedding in zip(batch, embeddings):
                selftext_hash = self._compute_hash(tp.selftext)
                self.repository.upsert(
                    post_reddit_id=tp.post_reddit_id,
                    subreddit=tp.subreddit,
                    title=tp.title,
                    selftext_hash=selftext_hash,
                    embedding=embedding,
                )
            generated += len(batch)

        self.db.commit()
        logger.info("Generated %d new post embeddings", generated)
        return generated

    def embed_query(self, query: str) -> list[float]:
        """Embed a user search query."""
        return self.generate_embedding(query)

    @staticmethod
    def _post_to_text(tp: ThemePost) -> str:
        """Build embeddable text from a ThemePost."""
        parts = [tp.title]
        if tp.selftext:
            parts.append(tp.selftext[:500])
        parts.append(f"r/{tp.subreddit}")
        return " ".join(parts)

    @staticmethod
    def _compute_hash(text: str | None) -> str | None:
        if not text:
            return None
        return hashlib.sha256(text.encode()).hexdigest()

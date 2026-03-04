import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.semantic_search.domain.entities.post_embedding import PostEmbedding

logger = logging.getLogger(__name__)


class PostEmbeddingRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_reddit_id(self, post_reddit_id: str) -> PostEmbedding | None:
        return (
            self.db.query(PostEmbedding)
            .filter(PostEmbedding.post_reddit_id == post_reddit_id)
            .first()
        )

    def upsert(
        self,
        post_reddit_id: str,
        subreddit: str,
        title: str,
        selftext_hash: str | None,
        embedding: list[float] | None,
    ) -> PostEmbedding:
        existing = self.find_by_reddit_id(post_reddit_id)
        if existing:
            existing.title = title
            existing.subreddit = subreddit
            existing.selftext_hash = selftext_hash
            if embedding is not None:
                existing.embedding = embedding
            self.db.flush()
            return existing

        new_record = PostEmbedding(
            post_reddit_id=post_reddit_id,
            subreddit=subreddit,
            title=title,
            selftext_hash=selftext_hash,
            embedding=embedding,
        )
        self.db.add(new_record)
        self.db.flush()
        return new_record

    def find_similar_for_audience(
        self,
        query_embedding: list[float],
        post_reddit_ids: list[str],
        limit: int = 50,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        """
        Find posts most similar to the query embedding,
        restricted to a set of post_reddit_ids (audience scope).

        Uses pgvector cosine distance operator (<=>).
        Returns list of dicts with post data + similarity score.
        """
        if not post_reddit_ids:
            return []

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query = text("""
            SELECT
                pe.id,
                pe.post_reddit_id,
                pe.subreddit,
                pe.title,
                1 - (pe.embedding <=> :embedding) as similarity
            FROM post_embeddings pe
            WHERE pe.embedding IS NOT NULL
            AND pe.post_reddit_id = ANY(:reddit_ids)
            AND (1 - (pe.embedding <=> :embedding)) >= :min_similarity
            ORDER BY pe.embedding <=> :embedding
            LIMIT :limit
        """)

        result = self.db.execute(
            query,
            {
                "embedding": embedding_str,
                "reddit_ids": post_reddit_ids,
                "min_similarity": min_similarity,
                "limit": limit,
            },
        )

        posts = []
        for row in result:
            posts.append(
                {
                    "post_reddit_id": row.post_reddit_id,
                    "subreddit": row.subreddit,
                    "title": row.title,
                    "similarity": round(float(row.similarity), 3),
                }
            )

        return posts

    def find_without_embeddings(self, post_reddit_ids: list[str]) -> list[str]:
        """Return reddit_ids from the given set that lack embeddings."""
        if not post_reddit_ids:
            return []

        existing = (
            self.db.query(PostEmbedding.post_reddit_id)
            .filter(
                PostEmbedding.post_reddit_id.in_(post_reddit_ids),
                PostEmbedding.embedding.isnot(None),
            )
            .all()
        )
        existing_ids = {row[0] for row in existing}
        return [pid for pid in post_reddit_ids if pid not in existing_ids]

"""Repository for community embeddings with vector similarity search."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.similar_communities.domain.entities.community_embedding import (
    CommunityEmbedding,
)


class CommunityEmbeddingRepository:
    """Repository for managing community embeddings and similarity search."""

    def __init__(self, db: Session):
        self.db = db

    def find_by_name(self, subreddit_name: str) -> CommunityEmbedding | None:
        """Find embedding by subreddit name."""
        return (
            self.db.query(CommunityEmbedding)
            .filter(CommunityEmbedding.subreddit_name == subreddit_name.lower())
            .first()
        )

    def find_by_id(self, embedding_id: UUID) -> CommunityEmbedding | None:
        """Find embedding by ID."""
        return (
            self.db.query(CommunityEmbedding)
            .filter(CommunityEmbedding.id == embedding_id)
            .first()
        )

    def upsert(
        self,
        subreddit_name: str,
        title: str | None = None,
        description: str | None = None,
        embedding: list[float] | None = None,
        subscribers: int | None = None,
    ) -> CommunityEmbedding:
        """Create or update a community embedding."""
        existing = self.find_by_name(subreddit_name)

        if existing:
            if title is not None:
                existing.title = title
            if description is not None:
                existing.description = description
            if embedding is not None:
                existing.embedding = embedding
            if subscribers is not None:
                existing.subscribers = subscribers
            self.db.commit()
            self.db.refresh(existing)
            return existing

        new_embedding = CommunityEmbedding(
            subreddit_name=subreddit_name.lower(),
            title=title,
            description=description,
            embedding=embedding,
            subscribers=subscribers,
        )
        self.db.add(new_embedding)
        self.db.commit()
        self.db.refresh(new_embedding)
        return new_embedding

    def find_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        exclude_names: list[str] | None = None,
    ) -> list[tuple[CommunityEmbedding, float]]:
        """
        Find similar communities using cosine distance.

        Args:
            embedding: The embedding vector to compare against
            limit: Maximum number of results
            exclude_names: Subreddit names to exclude from results

        Returns:
            List of tuples (CommunityEmbedding, similarity_score)
            Score is 1 - cosine_distance, so higher is more similar
        """
        exclude_names = exclude_names or []
        exclude_names_lower = [n.lower() for n in exclude_names]

        # Use raw SQL for vector similarity search
        # cosine_distance returns 0 for identical, 2 for opposite
        # We convert to similarity: 1 - (distance / 2) gives 1 for identical, 0 for opposite
        query = text("""
            SELECT
                ce.*,
                1 - (ce.embedding <=> :embedding) as similarity
            FROM community_embeddings ce
            WHERE ce.embedding IS NOT NULL
            AND ce.subreddit_name NOT IN :exclude_names
            ORDER BY ce.embedding <=> :embedding
            LIMIT :limit
        """)

        # pgvector expects the embedding as a string representation
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        result = self.db.execute(
            query,
            {
                "embedding": embedding_str,
                "exclude_names": tuple(exclude_names_lower) if exclude_names_lower else ("",),
                "limit": limit,
            },
        )

        communities = []
        for row in result:
            community = CommunityEmbedding(
                id=row.id,
                subreddit_name=row.subreddit_name,
                title=row.title,
                description=row.description,
                embedding=row.embedding,
                subscribers=row.subscribers,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            communities.append((community, row.similarity))

        return communities

    def find_similar_to_community(
        self,
        subreddit_name: str,
        limit: int = 10,
        exclude_names: list[str] | None = None,
    ) -> list[tuple[CommunityEmbedding, float]]:
        """
        Find communities similar to a given subreddit.

        Args:
            subreddit_name: The source subreddit to find similar communities for
            limit: Maximum number of results
            exclude_names: Additional names to exclude

        Returns:
            List of tuples (CommunityEmbedding, similarity_score)
        """
        source = self.find_by_name(subreddit_name)
        if not source or source.embedding is None:
            return []

        exclude = exclude_names or []
        exclude.append(subreddit_name.lower())

        return self.find_similar(
            embedding=source.embedding,
            limit=limit,
            exclude_names=exclude,
        )

    def find_similar_to_multiple(
        self,
        subreddit_names: list[str],
        limit: int = 10,
        exclude_names: list[str] | None = None,
    ) -> list[tuple[CommunityEmbedding, float]]:
        """
        Find communities similar to multiple subreddits (aggregate).

        Computes average embedding of all source communities and finds similar.

        Args:
            subreddit_names: List of source subreddits
            limit: Maximum number of results
            exclude_names: Additional names to exclude

        Returns:
            List of tuples (CommunityEmbedding, similarity_score)
        """
        embeddings = []
        for name in subreddit_names:
            source = self.find_by_name(name)
            if source and source.embedding is not None:
                embeddings.append(source.embedding)

        if not embeddings:
            return []

        # Compute average embedding
        avg_embedding = [
            sum(emb[i] for emb in embeddings) / len(embeddings)
            for i in range(len(embeddings[0]))
        ]

        exclude = exclude_names or []
        exclude.extend([n.lower() for n in subreddit_names])

        return self.find_similar(
            embedding=avg_embedding,
            limit=limit,
            exclude_names=exclude,
        )

    def count_with_embeddings(self) -> int:
        """Count communities that have embeddings."""
        return (
            self.db.query(CommunityEmbedding)
            .filter(CommunityEmbedding.embedding.isnot(None))
            .count()
        )

    def find_without_embeddings(self, limit: int = 100) -> list[CommunityEmbedding]:
        """Find communities that don't have embeddings yet."""
        return (
            self.db.query(CommunityEmbedding)
            .filter(CommunityEmbedding.embedding.is_(None))
            .limit(limit)
            .all()
        )

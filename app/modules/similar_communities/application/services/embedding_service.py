"""Service for generating and managing community embeddings."""

import os
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from app.modules.similar_communities.domain.entities.community_embedding import (
    CommunityEmbedding,
)
from app.modules.similar_communities.infra.repositories.community_embedding_repository import (
    CommunityEmbeddingRepository,
)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    subreddit_name: str
    embedding: list[float]
    text_used: str


class EmbeddingService:
    """
    Service for generating and caching community embeddings.

    Uses OpenAI text-embedding-3-small model (1536 dimensions).
    """

    MODEL = "text-embedding-3-small"
    DIMENSIONS = 1536

    def __init__(self, db: Session):
        self.db = db
        self.repository = CommunityEmbeddingRepository(db)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a text using OpenAI API.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = self.client.embeddings.create(
            model=self.MODEL,
            input=text,
            dimensions=self.DIMENSIONS,
        )
        return response.data[0].embedding

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input)
        """
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.MODEL,
            input=texts,
            dimensions=self.DIMENSIONS,
        )

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    def get_or_create_embedding(
        self,
        subreddit_name: str,
        title: str | None = None,
        description: str | None = None,
        subscribers: int | None = None,
        force_update: bool = False,
    ) -> CommunityEmbedding:
        """
        Get existing embedding or create new one.

        Args:
            subreddit_name: The subreddit name
            title: Subreddit title
            description: Subreddit description
            subscribers: Number of subscribers
            force_update: Force regeneration of embedding

        Returns:
            CommunityEmbedding with embedding vector
        """
        existing = self.repository.find_by_name(subreddit_name)

        # Check if we need to generate/update embedding
        needs_update = (
            force_update
            or existing is None
            or existing.embedding is None
            or existing.needs_embedding_update(title, description)
        )

        if not needs_update and existing:
            return existing

        # Prepare text for embedding
        text_parts = []
        if title:
            text_parts.append(title)
        if description:
            text_parts.append(description)
        if not text_parts:
            text_parts.append(subreddit_name)

        text = " ".join(text_parts)

        # Generate embedding
        embedding = self.generate_embedding(text)

        # Save to database
        return self.repository.upsert(
            subreddit_name=subreddit_name,
            title=title,
            description=description,
            embedding=embedding,
            subscribers=subscribers,
        )

    def batch_get_or_create_embeddings(
        self,
        communities: list[dict],
        force_update: bool = False,
    ) -> list[CommunityEmbedding]:
        """
        Get or create embeddings for multiple communities efficiently.

        Args:
            communities: List of dicts with keys: name, title, description, subscribers
            force_update: Force regeneration of all embeddings

        Returns:
            List of CommunityEmbedding objects
        """
        results = []
        to_generate = []

        # First pass: check which need generation
        for community in communities:
            name = community.get("name", "").lower()
            title = community.get("title")
            description = community.get("description")
            subscribers = community.get("subscribers")

            existing = self.repository.find_by_name(name)

            needs_update = (
                force_update
                or existing is None
                or existing.embedding is None
                or existing.needs_embedding_update(title, description)
            )

            if needs_update:
                to_generate.append({
                    "name": name,
                    "title": title,
                    "description": description,
                    "subscribers": subscribers,
                    "existing": existing,
                })
            elif existing:
                results.append(existing)

        # Batch generate embeddings for those that need it
        if to_generate:
            texts = []
            for item in to_generate:
                parts = []
                if item["title"]:
                    parts.append(item["title"])
                if item["description"]:
                    parts.append(item["description"])
                if not parts:
                    parts.append(item["name"])
                texts.append(" ".join(parts))

            embeddings = self.generate_batch_embeddings(texts)

            # Save all embeddings
            for item, embedding in zip(to_generate, embeddings):
                saved = self.repository.upsert(
                    subreddit_name=item["name"],
                    title=item["title"],
                    description=item["description"],
                    embedding=embedding,
                    subscribers=item["subscribers"],
                )
                results.append(saved)

        return results

    def get_embedding_stats(self) -> dict:
        """Get statistics about embeddings in the database."""
        total = self.repository.count_with_embeddings()
        without = len(self.repository.find_without_embeddings(limit=1000))
        return {
            "total_with_embeddings": total,
            "total_without_embeddings": without,
            "model": self.MODEL,
            "dimensions": self.DIMENSIONS,
        }

import logging
import time
from dataclasses import dataclass, field

import requests

from app.modules.topics.domain.errors.fetch_data_error import FetchDataError

logger = logging.getLogger(__name__)


@dataclass
class RedditPost:
    """Dados de um post do Reddit."""

    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    link_flair_text: str | None = None
    upvote_ratio: float | None = None
    permalink: str | None = None


@dataclass
class RedditComment:
    """Dados de um comentário do Reddit."""

    id: str
    body: str
    score: int
    created_utc: float
    author: str | None = None
    parent_id: str | None = None


@dataclass
class SubredditPostsResult:
    """Resultado da coleta de posts de um subreddit."""

    subreddit: str
    posts: list[RedditPost] = field(default_factory=list)
    sort: str = "hot"


class GenericRedditProvider:
    # reddit.com/subreddits/popular.json → subreddits mais populares
    # reddit.com/subreddits/new.json → subreddits novos
    # reddit.com/r/popular.json → posts mais populares
    """
    Provider para Reddit
    """

    timeout = 10
    headers = {
        "User-Agent": "RedditOracle/1.0 (personal research tool)"
    }
    _rate_limit_delay = 6.0  # ~10 req/min for public API

    def __init__(self):
        """
        Inicializa o provider
        """
        self.timeout = 10
        self._last_request_time = 0.0

    def _respect_rate_limit(self):
        """Aguarda o delay mínimo entre requests para não exceder 10 req/min."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def list_popular_topics(self):
        """
        Lista os tópicos populares
        """
        popular_subreddit_url = "https://www.reddit.com/subreddits/popular.json"
        popular_subreddit_response = requests.get(
            popular_subreddit_url, headers=self.headers, timeout=self.timeout
        )
        if popular_subreddit_response.status_code != 200:
            popular_subreddit_response.raise_for_status()
            raise FetchDataError(
                f"Failed to fetch popular topics: {popular_subreddit_response.status_code}"
            )
        return popular_subreddit_response.json()

    def list_trending_topics(self):
        """
        Lista os tópicos trending
        """
        popular_posts_url = "https://www.reddit.com/r/popular.json"
        popular_posts_response = requests.get(
            popular_posts_url, headers=self.headers, timeout=self.timeout
        )
        if popular_posts_response.status_code != 200:
            popular_posts_response.raise_for_status()
            raise FetchDataError(
                f"Failed to fetch trending topics: {popular_posts_response.status_code}"
            )
        return popular_posts_response.json()

    def list_new_topics(self):
        """
        Lista os tópicos novos
        """
        new_subreddit_url = "https://www.reddit.com/subreddits/new.json"
        new_subreddit_response = requests.get(
            new_subreddit_url, headers=self.headers, timeout=self.timeout
        )
        if new_subreddit_response.status_code != 200:
            new_subreddit_response.raise_for_status()
            raise FetchDataError(
                f"Failed to fetch new topics: {new_subreddit_response.status_code}"
            )
        return new_subreddit_response.json()

    def search_community_by_name(self, community_name: str, limit: int = 30):
        """
        Busca comunidades pelo nome
        """
        search_url = "https://www.reddit.com/subreddits/search.json"
        params = {"q": community_name, "limit": limit}
        community_response = requests.get(
            search_url, params=params, headers=self.headers, timeout=self.timeout
        )
        if community_response.status_code != 200:
            community_response.raise_for_status()
            raise FetchDataError(
                f"Failed to fetch community: {community_response.status_code}"
            )
        return community_response.json()

    def get_community_details(self, community_name: str):
        """
        Obtém os detalhes de uma comunidade

        Args:
            community_name: Nome da comunidade a ser pesquisada

        Returns:
            Dados da comunidade encontrada
        """
        url = f"https://www.reddit.com/r/{community_name}/about.json"
        community_response = requests.get(
            url, headers=self.headers, timeout=self.timeout
        )
        if community_response.status_code != 200:
            community_response.raise_for_status()
            raise FetchDataError(
                f"Failed to fetch community: {community_response.status_code}"
            )
        return community_response.json()

    def get_subreddit_posts(
        self,
        subreddit_name: str,
        sort: str = "hot",
        limit: int = 25,
        time_filter: str = "week",
    ) -> SubredditPostsResult:
        """
        Busca posts de um subreddit.

        Args:
            subreddit_name: Nome do subreddit (sem r/)
            sort: Tipo de ordenação (hot, top, new, rising)
            limit: Número de posts (max 100 por request)
            time_filter: Filtro de tempo para sort=top (hour, day, week, month, year, all)

        Returns:
            SubredditPostsResult com lista de posts
        """
        self._respect_rate_limit()

        url = f"https://www.reddit.com/r/{subreddit_name}/{sort}.json"
        params = {"limit": min(limit, 100)}
        if sort == "top":
            params["t"] = time_filter

        try:
            response = requests.get(
                url, params=params, headers=self.headers, timeout=self.timeout
            )
            if response.status_code != 200:
                logger.warning(
                    "Failed to fetch posts from r/%s: %d",
                    subreddit_name,
                    response.status_code,
                )
                return SubredditPostsResult(subreddit=subreddit_name, sort=sort)

            data = response.json()
            posts = []

            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                posts.append(
                    RedditPost(
                        id=post_data.get("id", ""),
                        subreddit=post_data.get("subreddit", subreddit_name),
                        title=post_data.get("title", ""),
                        selftext=post_data.get("selftext", ""),
                        score=post_data.get("score", 0),
                        num_comments=post_data.get("num_comments", 0),
                        created_utc=post_data.get("created_utc", 0),
                        link_flair_text=post_data.get("link_flair_text"),
                        upvote_ratio=post_data.get("upvote_ratio"),
                        permalink=post_data.get("permalink"),
                    )
                )

            logger.info("Fetched %d posts from r/%s (%s)", len(posts), subreddit_name, sort)
            return SubredditPostsResult(subreddit=subreddit_name, posts=posts, sort=sort)

        except requests.RequestException as e:
            logger.warning("Error fetching posts from r/%s: %s", subreddit_name, e)
            return SubredditPostsResult(subreddit=subreddit_name, sort=sort)

    def get_post_comments(
        self,
        subreddit_name: str,
        post_id: str,
        limit: int = 50,
    ) -> list[RedditComment]:
        """
        Busca comentários de um post.

        Args:
            subreddit_name: Nome do subreddit
            post_id: ID do post
            limit: Número máximo de comentários

        Returns:
            Lista de RedditComment
        """
        self._respect_rate_limit()

        url = f"https://www.reddit.com/r/{subreddit_name}/comments/{post_id}.json"
        params = {"limit": min(limit, 200)}

        try:
            response = requests.get(
                url, params=params, headers=self.headers, timeout=self.timeout
            )
            if response.status_code != 200:
                logger.warning(
                    "Failed to fetch comments for post %s: %d",
                    post_id,
                    response.status_code,
                )
                return []

            data = response.json()
            comments = []

            # Response is an array: [post_listing, comments_listing]
            if len(data) < 2:
                return []

            for child in data[1].get("data", {}).get("children", []):
                comment_data = child.get("data", {})
                if child.get("kind") != "t1":
                    continue
                comments.append(
                    RedditComment(
                        id=comment_data.get("id", ""),
                        body=comment_data.get("body", ""),
                        score=comment_data.get("score", 0),
                        created_utc=comment_data.get("created_utc", 0),
                        author=comment_data.get("author"),
                        parent_id=comment_data.get("parent_id"),
                    )
                )

            logger.info("Fetched %d comments for post %s", len(comments), post_id)
            return comments

        except requests.RequestException as e:
            logger.warning("Error fetching comments for post %s: %s", post_id, e)
            return []

    def collect_posts_for_communities(
        self,
        community_names: list[str],
        posts_per_sort: int = 25,
    ) -> list[SubredditPostsResult]:
        """
        Coleta posts de múltiplas comunidades (hot + top do mês).

        Args:
            community_names: Lista de nomes de subreddits
            posts_per_sort: Número de posts por tipo de sort

        Returns:
            Lista de SubredditPostsResult (2 por comunidade: hot + top)
        """
        results = []
        for name in community_names:
            hot = self.get_subreddit_posts(name, sort="hot", limit=posts_per_sort)
            results.append(hot)

            top = self.get_subreddit_posts(
                name, sort="top", limit=posts_per_sort, time_filter="month"
            )
            results.append(top)

        total_posts = sum(len(r.posts) for r in results)
        logger.info(
            "Collected %d total posts from %d communities",
            total_posts,
            len(community_names),
        )
        return results

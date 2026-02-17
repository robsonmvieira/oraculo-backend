import requests

from app.modules.topics.domain.errors.fetch_data_error import FetchDataError


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

    def __init__(self):
        """
        Inicializa o provider
        """
        self.timeout = 10

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

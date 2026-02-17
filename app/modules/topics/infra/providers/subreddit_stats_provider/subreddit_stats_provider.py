from dataclasses import dataclass

import requests


@dataclass
class SubredditGrowthData:
    """Dados de crescimento de um subreddit."""

    subreddit_name: str
    subscribers: int | None = None
    growth_week: float | None = None  # Percentual: 0.85 = 0.85%
    growth_month: float | None = None
    growth_day: float | None = None


class SubredditStatsProvider:
    """
    Provider para buscar estatísticas de crescimento no SubredditStats.
    https://subredditstats.com/api/subreddit?name={name}
    """

    base_url = "https://subredditstats.com/api"
    timeout = 10
    headers = {"User-Agent": "RedditOracle/1.0 (personal research tool)"}

    def get_growth_data(self, subreddit_name: str) -> SubredditGrowthData | None:
        """
        Busca dados de crescimento de um subreddit.

        Args:
            subreddit_name: Nome do subreddit (sem r/)

        Returns:
            SubredditGrowthData ou None se não encontrado
        """
        try:
            url = f"{self.base_url}/subreddit"
            params = {"name": subreddit_name}

            response = requests.get(
                url, params=params, headers=self.headers, timeout=self.timeout
            )

            if response.status_code != 200:
                return None

            data = response.json()

            # Extrair ratios de crescimento
            # subscriberRatios.week = 1.05 significa +5% na semana
            ratios = data.get("subscriberRatios", {})

            # Converter ratio para percentual
            # ratio 1.05 → (1.05 - 1) * 100 = 5%
            growth_week = None
            growth_month = None
            growth_day = None

            if ratios.get("week") and ratios["week"] != 1:
                growth_week = (ratios["week"] - 1) * 100

            if ratios.get("month") and ratios["month"] != 1:
                growth_month = (ratios["month"] - 1) * 100

            if ratios.get("day") and ratios["day"] != 1:
                growth_day = (ratios["day"] - 1) * 100

            return SubredditGrowthData(
                subreddit_name=data.get("name", subreddit_name),
                subscribers=data.get("subscriberCount"),
                growth_week=growth_week,
                growth_month=growth_month,
                growth_day=growth_day,
            )

        except (requests.RequestException, ValueError, KeyError):
            return None

    def get_growth_data_batch(
        self, subreddit_names: list[str]
    ) -> dict[str, SubredditGrowthData]:
        """
        Busca dados de crescimento para múltiplos subreddits.

        Args:
            subreddit_names: Lista de nomes de subreddits

        Returns:
            Dicionário {nome: SubredditGrowthData}
        """
        results = {}
        for name in subreddit_names:
            data = self.get_growth_data(name)
            if data:
                results[name.lower()] = data
        return results

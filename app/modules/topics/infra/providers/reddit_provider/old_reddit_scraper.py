import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class ScrapedSubreddit:
    """Representa um subreddit extraído do old.reddit.com"""

    name: str
    title: str
    description: str
    subscribers: int | None = None


class OldRedditScraper:
    """
    Scraper para old.reddit.com
    Usado para buscas de volume sem consumir rate limit da API .json
    """

    base_url = "https://old.reddit.com"
    headers = {
        "User-Agent": "RedditOracle/1.0 (personal research tool; by u/IsaacJhonson)"
    }
    delay_seconds = 2.5  # 2-3 segundos entre requests

    def __init__(self):
        self._last_request_time = 0

    def _respect_rate_limit(self):
        """
        Aguarda o delay mínimo entre requests
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_time = time.time()

    def search_subreddits(self, query: str, limit: int = 10) -> list[ScrapedSubreddit]:
        """
        Busca subreddits por termo no old.reddit.com

        Args:
            query: Termo de busca
            limit: Número máximo de resultados

        Returns:
            Lista de subreddits encontrados
        """
        self._respect_rate_limit()

        url = f"{self.base_url}/subreddits/search"
        params = {"q": query}

        response = requests.get(
            url, params=params, headers=self.headers, timeout=10
        )

        if response.status_code != 200:
            return []

        return self._parse_search_results(response.text, limit)

    def _parse_search_results(self, html: str, limit: int) -> list[ScrapedSubreddit]:
        """
        Extrai subreddits do HTML de busca

        Args:
            html: HTML da página de resultados
            limit: Número máximo de resultados

        Returns:
            Lista de ScrapedSubreddit
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Os resultados ficam em divs com class "thing" e data-type="subreddit"
        subreddit_entries = soup.find_all("div", class_="thing")

        count = 0
        for entry in subreddit_entries:
            if count >= limit:
                break
            # Verificar se é um subreddit (data-type="subreddit")
            if entry.get("data-type") != "subreddit":
                continue
            try:
                subreddit = self._parse_subreddit_entry(entry)
                if subreddit:
                    results.append(subreddit)
                    count += 1
            except Exception:
                continue

        return results

    def _parse_subreddit_entry(self, entry) -> ScrapedSubreddit | None:
        """
        Extrai dados de um único resultado de subreddit

        Args:
            entry: Elemento BeautifulSoup do resultado

        Returns:
            ScrapedSubreddit ou None
        """
        # Buscar o link do título que contém o nome do subreddit
        # Formato: "r/SaaS: Software As a Service Companies..."
        title_link = entry.select_one("p.titlerow a.title")
        if not title_link:
            return None

        href = title_link.get("href", "")
        # Extrair nome do href: https://old.reddit.com/r/SaaS/ -> SaaS
        if "/r/" not in href:
            return None

        name = href.split("/r/")[-1].rstrip("/")
        if not name:
            return None

        # O título completo contém "r/Nome: Título"
        full_title = title_link.get_text(strip=True)
        # Remover o prefixo "r/Nome: " se existir
        if ": " in full_title:
            title = full_title.split(": ", 1)[1]
        else:
            title = full_title

        # Buscar descrição no div.md dentro de description
        desc_elem = entry.select_one("div.description div.md p")
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Subscribers não estão diretamente disponíveis na busca
        subscribers = None

        return ScrapedSubreddit(
            name=name,
            title=title,
            description=description,
            subscribers=subscribers,
        )

    def search_multiple_terms(
        self, terms: list[str], limit_per_term: int = 5
    ) -> list[ScrapedSubreddit]:
        """
        Busca subreddits para múltiplos termos

        Args:
            terms: Lista de termos de busca
            limit_per_term: Limite de resultados por termo

        Returns:
            Lista unificada de subreddits (sem duplicatas)
        """
        seen_names = set()
        results = []

        for term in terms:
            subreddits = self.search_subreddits(term, limit=limit_per_term)
            for sub in subreddits:
                if sub.name.lower() not in seen_names:
                    seen_names.add(sub.name.lower())
                    results.append(sub)

        return results

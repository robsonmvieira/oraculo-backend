"""YouTube data collection provider.

Combines three sources:
- YouTube Data API v3: ONLY for search (100 quota units/request)
- yt-dlp: metadata + comments (free, no quota)
- youtube-transcript-api: transcripts (free, no quota)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from app.config import settings

logger = logging.getLogger(__name__)

TRANSCRIPT_LANG_PRIORITY = ["pt-BR", "pt", "en"]
_RATE_LIMIT_DELAY = 1.5  # seconds between yt-dlp requests


class YouTubeProvider:
    """Facade unificada para coleta de dados do YouTube."""

    def __init__(self):
        self._api_key = settings.youtube_api_key
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _respect_rate_limit(self) -> None:
        """Respeita rate limit entre requests yt-dlp (1.5s)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # YouTube Data API v3 (search only — 100 units/request)
    # ------------------------------------------------------------------

    def search_videos(
        self,
        query: str,
        max_results: int = 20,
        published_after_days: int = 30,
        region_code: str = "US",
    ) -> list[dict]:
        """Busca vídeos no YouTube via API v3.

        Retorna lista de {video_id, title, channel_name, published_at}.
        Usa apenas o endpoint search/list (100 units por request).
        """
        if not self._api_key:
            logger.warning("YouTube API key not configured, skipping search")
            return []

        try:
            published_after = (
                datetime.now(timezone.utc) - timedelta(days=published_after_days)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            response = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "relevance",
                    "maxResults": min(max_results, 50),
                    "publishedAfter": published_after,
                    "regionCode": region_code,
                    "key": self._api_key,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                results.append(
                    {
                        "video_id": item["id"]["videoId"],
                        "title": snippet.get("title", ""),
                        "channel_name": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                    }
                )
            return results

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                logger.warning("YouTube API quota exceeded or forbidden: %s", e)
            else:
                logger.error("YouTube API search error: %s", e)
            return []
        except Exception as e:
            logger.error("YouTube API search failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # yt-dlp — metadata (free, no quota)
    # ------------------------------------------------------------------

    def get_video_metadata(self, video_id: str) -> dict | None:
        """Extrai metadados do vídeo via yt-dlp.

        Retorna dict com: video_id, title, channel_name, views, likes,
        duration_seconds, tags, description, published_at.
        """
        try:
            import yt_dlp

            self._respect_rate_limit()

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": False,
            }

            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return None

            published_at = info.get("upload_date")
            if published_at and len(published_at) == 8:
                published_at = (
                    f"{published_at[:4]}-{published_at[4:6]}-{published_at[6:8]}"
                    "T00:00:00Z"
                )

            return {
                "video_id": video_id,
                "title": info.get("title", ""),
                "channel_name": info.get("uploader", "") or info.get("channel", ""),
                "views": info.get("view_count"),
                "likes": info.get("like_count"),
                "duration_seconds": info.get("duration"),
                "tags": info.get("tags") or [],
                "description": info.get("description", ""),
                "published_at": published_at,
            }
        except Exception as e:
            logger.debug("yt-dlp metadata extraction failed for %s: %s", video_id, e)
            return None

    # ------------------------------------------------------------------
    # yt-dlp — comments (free, no quota, with fallbacks)
    # ------------------------------------------------------------------

    def get_video_comments(self, video_id: str, max_comments: int = 100) -> list[dict]:
        """Extrai comentários do vídeo via yt-dlp com fallbacks.

        Strategy 1: yt-dlp com getcomments + extractor_args
        Strategy 2: yt-dlp simplificado (sem extractor_args)

        Retorna lista de {author, text, likes}.
        """
        comments = self._get_comments_strategy_1(video_id, max_comments)
        if comments:
            return comments

        comments = self._get_comments_strategy_2(video_id, max_comments)
        if comments:
            return comments

        logger.debug("All comment strategies failed for %s", video_id)
        return []

    def _get_comments_strategy_1(self, video_id: str, max_comments: int) -> list[dict]:
        """yt-dlp com getcomments e extractor_args."""
        try:
            import yt_dlp

            self._respect_rate_limit()

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "getcomments": True,
                "extractor_args": {"youtube": {"max_comments": [str(max_comments)]}},
            }

            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return []

            return self._parse_yt_dlp_comments(info.get("comments") or [], max_comments)
        except Exception as e:
            logger.debug("Comment strategy 1 failed for %s: %s", video_id, e)
            return []

    def _get_comments_strategy_2(self, video_id: str, max_comments: int) -> list[dict]:
        """yt-dlp simplificado sem extractor_args."""
        try:
            import yt_dlp

            self._respect_rate_limit()

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "getcomments": True,
            }

            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return []

            return self._parse_yt_dlp_comments(info.get("comments") or [], max_comments)
        except Exception as e:
            logger.debug("Comment strategy 2 failed for %s: %s", video_id, e)
            return []

    @staticmethod
    def _parse_yt_dlp_comments(
        raw_comments: list[dict], max_comments: int
    ) -> list[dict]:
        """Normaliza comentários do yt-dlp para formato padrão."""
        parsed = []
        for c in raw_comments[:max_comments]:
            parsed.append(
                {
                    "author": c.get("author", ""),
                    "text": c.get("text", ""),
                    "likes": c.get("like_count", 0) or 0,
                }
            )
        return parsed

    # ------------------------------------------------------------------
    # youtube-transcript-api — transcripts (free, no quota)
    # ------------------------------------------------------------------

    def get_transcript(
        self,
        video_id: str,
        preferred_langs: list[str] | None = None,
    ) -> tuple[str, str] | None:
        """Obtém transcrição do vídeo com fallback de idioma.

        Tenta: pt-BR -> pt -> en -> qualquer disponível.
        Retorna (transcript_text, language_code) ou None.
        """
        langs = preferred_langs or TRANSCRIPT_LANG_PRIORITY

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Tenta idiomas na ordem de prioridade
            for lang in langs:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    segments = transcript.fetch()
                    text = " ".join(s.get("text", "") for s in segments)
                    return (text.strip(), lang)
                except Exception:
                    continue

            # Fallback: qualquer idioma disponível
            try:
                for transcript in transcript_list:
                    segments = transcript.fetch()
                    text = " ".join(s.get("text", "") for s in segments)
                    return (text.strip(), transcript.language_code)
            except Exception:
                pass

            return None

        except Exception as e:
            logger.debug("Transcript extraction failed for %s: %s", video_id, e)
            return None

    # ------------------------------------------------------------------
    # High-level: collect all data for a topic
    # ------------------------------------------------------------------

    def collect_for_topic(
        self,
        topic_name: str,
        max_videos: int = 20,
        max_comments_per_video: int = 100,
        max_videos_with_transcript: int = 10,
        max_transcript_chars: int = 50_000,
    ) -> list[dict]:
        """Pipeline completa de coleta para um tópico.

        1. Busca vídeos via API v3
        2. Para cada vídeo: metadata + comments + transcript
        3. Retorna lista de dicts com dados completos

        Args:
            topic_name: Nome do tópico para buscar no YouTube.
            max_videos: Máximo de vídeos a buscar.
            max_comments_per_video: Máximo de comentários por vídeo.
            max_videos_with_transcript: Quantos vídeos terão transcrição coletada.
            max_transcript_chars: Máximo de caracteres de transcrição por vídeo.

        Returns:
            Lista de dicts com dados completos do vídeo.
        """
        search_results = self.search_videos(topic_name, max_results=max_videos)

        if not search_results:
            logger.info("No YouTube videos found for topic '%s'", topic_name)
            return []

        collected = []
        videos_with_transcript = 0

        for i, search_item in enumerate(search_results):
            video_id = search_item["video_id"]

            # Metadata via yt-dlp (enriches search results)
            metadata = self.get_video_metadata(video_id)
            if metadata:
                video_data = metadata
            else:
                # Fallback: use search snippet data
                video_data = {
                    "video_id": video_id,
                    "title": search_item.get("title", ""),
                    "channel_name": search_item.get("channel_name", ""),
                    "views": None,
                    "likes": None,
                    "duration_seconds": None,
                    "tags": [],
                    "description": "",
                    "published_at": search_item.get("published_at", ""),
                }

            # Comments
            comments = self.get_video_comments(video_id, max_comments_per_video)
            video_data["comments"] = comments

            # Transcript (only for top N videos by position)
            transcript = None
            transcript_lang = None
            if videos_with_transcript < max_videos_with_transcript:
                result = self.get_transcript(video_id)
                if result:
                    transcript, transcript_lang = result
                    if len(transcript) > max_transcript_chars:
                        transcript = transcript[:max_transcript_chars]
                    videos_with_transcript += 1

            video_data["transcript"] = transcript
            video_data["transcript_lang"] = transcript_lang

            collected.append(video_data)

        logger.info(
            "Collected %d videos for topic '%s' (%d with transcripts)",
            len(collected),
            topic_name,
            videos_with_transcript,
        )
        return collected

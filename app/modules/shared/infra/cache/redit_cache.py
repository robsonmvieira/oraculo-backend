import json
import os
from typing import Any

from redis import Redis


class RedisCache:
    """
    Cache para Reddit usando Redis
    """

    def __init__(self):
        """
        Inicializa o cache
        """
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = Redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        """
        Obtém um valor do cache
        """
        value = self.client.get(key)
        if value:
            return json.loads(value)
        return None

    def set(self, key: str, value: Any, ttl: int = 1800) -> None:
        """
        Define um valor no cache

        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de expiração em segundos (padrão: 1 hora)
        """
        self.client.set(key, json.dumps(value), ex=ttl)

    def delete(self, key: str) -> None:
        """
        Remove um valor do cache
        """
        self.client.delete(key)

    def exists(self, key: str) -> bool:
        """
        Verifica se uma chave existe no cache
        """
        return bool(self.client.exists(key))

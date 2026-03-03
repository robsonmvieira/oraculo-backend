"""Servico de CRUD para arquivos em S3-compatible storage."""

import logging
import uuid
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Wrapper para operacoes CRUD de arquivos no S3."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self._bucket = bucket_name or settings.s3_bucket_name
        if not self._bucket:
            raise ValueError("S3 bucket not configured (S3_BUCKET_NAME)")

        self._region = region or settings.aws_region
        self._client = boto3.client(
            "s3",
            region_name=self._region,
            aws_access_key_id=access_key or settings.s3_access_key,
            aws_secret_access_key=secret_key or settings.s3_secret_key,
            config=BotoConfig(signature_version="s3v4"),
        )

    # ------------------------------------------------------------------ #
    # Upload
    # ------------------------------------------------------------------ #

    def upload(
        self,
        data: bytes,
        key: str,
        content_type: str = "image/png",
    ) -> str:
        """
        Upload de bytes para S3.

        Args:
            data: Conteudo do arquivo em bytes.
            key: Caminho/nome do arquivo no bucket (ex: 'images/abc.png').
            content_type: MIME type do arquivo.

        Returns:
            URL publica do arquivo no S3.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        url = f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
        logger.info("Uploaded %d bytes to s3://%s/%s", len(data), self._bucket, key)
        return url

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #

    def delete(self, key: str) -> bool:
        """
        Remove um arquivo do S3.

        Args:
            key: Chave do arquivo no bucket.

        Returns:
            True se a operacao foi executada sem erros.
        """
        self._client.delete_object(Bucket=self._bucket, Key=key)
        logger.info("Deleted s3://%s/%s", self._bucket, key)
        return True

    def delete_many(self, keys: list[str]) -> int:
        """
        Remove multiplos arquivos do S3 em uma unica chamada.

        Args:
            keys: Lista de chaves a serem removidas.

        Returns:
            Quantidade de arquivos efetivamente deletados.
        """
        if not keys:
            return 0

        response = self._client.delete_objects(
            Bucket=self._bucket,
            Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
        )
        deleted_count = len(keys) - len(response.get("Errors", []))
        logger.info(
            "Bulk deleted %d/%d objects from s3://%s",
            deleted_count,
            len(keys),
            self._bucket,
        )
        return deleted_count

    # ------------------------------------------------------------------ #
    # Read / Download
    # ------------------------------------------------------------------ #

    def get_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Gera URL pre-assinada para download temporario.

        Args:
            key: Chave do arquivo no bucket.
            expiration: Tempo de validade em segundos (padrao: 1 hora).

        Returns:
            URL pre-assinada para GET do objeto.
        """
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiration,
        )
        logger.info("Generated presigned URL for s3://%s/%s (expires in %ds)", self._bucket, key, expiration)
        return url

    # ------------------------------------------------------------------ #
    # List
    # ------------------------------------------------------------------ #

    def list_objects(self, prefix: str, max_keys: int = 100) -> list[dict]:
        """
        Lista objetos no bucket filtrados por prefixo.

        Args:
            prefix: Prefixo (pasta) para filtrar (ex: 'content-images/').
            max_keys: Maximo de resultados retornados.

        Returns:
            Lista de dicts com 'key', 'size' e 'last_modified'.
        """
        response = self._client.list_objects_v2(
            Bucket=self._bucket,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        objects = [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
            }
            for obj in response.get("Contents", [])
        ]
        logger.info("Listed %d objects under s3://%s/%s", len(objects), self._bucket, prefix)
        return objects

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def get_file_size(self, key: str) -> int | None:
        """
        Retorna o tamanho em bytes de um arquivo no S3.

        Args:
            key: Chave do arquivo no bucket.

        Returns:
            Tamanho em bytes ou None se o arquivo nao existir.
        """
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
            return response["ContentLength"]
        except ClientError:
            logger.warning("File not found: s3://%s/%s", self._bucket, key)
            return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def generate_key(self, prefix: str = "content-images", extension: str = "png") -> str:
        """Gera chave unica para upload."""
        return f"{prefix}/{uuid.uuid4()}.{extension}"

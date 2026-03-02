"""Servico de upload para S3-compatible storage."""

import logging
import uuid
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Wrapper para upload de arquivos no S3."""

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

    def generate_key(self, prefix: str = "content-images", extension: str = "png") -> str:
        """Gera chave unica para upload."""
        return f"{prefix}/{uuid.uuid4()}.{extension}"

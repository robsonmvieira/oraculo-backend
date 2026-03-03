"""Repositorio para registros de arquivos enviados ao S3."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.uploaded_file import UploadedFile

logger = logging.getLogger(__name__)


class UploadedFileRepository:
    """CRUD para a tabela uploaded_files."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, uploaded_file: UploadedFile) -> UploadedFile:
        """Persiste um novo registro de arquivo."""
        self.db.add(uploaded_file)
        self.db.commit()
        self.db.refresh(uploaded_file)
        return uploaded_file

    def find_by_id(self, file_id: UUID) -> UploadedFile | None:
        """Busca registro por ID."""
        return (
            self.db.query(UploadedFile)
            .filter(UploadedFile.id == file_id)
            .first()
        )

    def find_by_key(self, key: str) -> UploadedFile | None:
        """Busca registro pela chave S3."""
        return (
            self.db.query(UploadedFile)
            .filter(UploadedFile.key == key)
            .first()
        )

    def find_by_uploader(self, user_id: UUID) -> list[UploadedFile]:
        """Lista arquivos enviados por um usuario."""
        return (
            self.db.query(UploadedFile)
            .filter(UploadedFile.uploaded_by == user_id)
            .order_by(UploadedFile.created_at.desc())
            .all()
        )

    def delete(self, file_id: UUID) -> bool:
        """Remove registro por ID."""
        uploaded_file = self.find_by_id(file_id)
        if not uploaded_file:
            return False
        self.db.delete(uploaded_file)
        self.db.commit()
        return True

    def delete_by_key(self, key: str) -> bool:
        """Remove registro pela chave S3."""
        deleted = (
            self.db.query(UploadedFile)
            .filter(UploadedFile.key == key)
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted > 0

"""Servico de geracao de imagens via Google Imagen."""

import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

VALID_ASPECT_RATIOS = ("1:1", "3:4", "4:3", "9:16", "16:9")


class ImageGenerationService:
    """Wrapper para a API Google Imagen via SDK google-genai."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self._model = model or settings.imagen_model
        self._api_key = api_key or settings.imagen_api_key or settings.google_api_key
        if not self._api_key:
            raise ValueError("Imagen API key not configured (IMAGEN_API_KEY or GOOGLE_API_KEY)")
        self._client = genai.Client(api_key=self._api_key)

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        number_of_images: int = 1,
    ) -> bytes:
        """
        Gera imagem a partir de texto.

        Args:
            prompt: Descricao textual da imagem desejada.
            aspect_ratio: Proporcao da imagem (1:1, 3:4, 4:3, 9:16, 16:9).
            number_of_images: Quantidade de imagens (1-4).

        Returns:
            Bytes PNG da primeira imagem gerada.

        Raises:
            ValueError: Se aspect_ratio invalido ou nenhuma imagem retornada.
            Exception: Erros da API Imagen.
        """
        if aspect_ratio not in VALID_ASPECT_RATIOS:
            raise ValueError(f"Invalid aspect_ratio '{aspect_ratio}'. Valid: {VALID_ASPECT_RATIOS}")

        logger.info(
            "Generating image with model=%s, aspect_ratio=%s",
            self._model,
            aspect_ratio,
        )

        response = self._client.models.generate_images(
            model=self._model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=number_of_images,
                aspect_ratio=aspect_ratio,
                output_mime_type="image/png",
            ),
        )

        if not response.generated_images:
            raise ValueError("Imagen API returned no images")

        image_bytes = response.generated_images[0].image.image_bytes
        logger.info("Image generated successfully (%d bytes)", len(image_bytes))
        return image_bytes

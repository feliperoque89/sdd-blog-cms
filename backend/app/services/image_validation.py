"""Detecção do tipo real de uma imagem por assinatura de arquivo (magic bytes).

SPEC-005 / RF02 — evita confiar apenas no `Content-Type` declarado pelo
cliente (forjável) ou na extensão do nome do arquivo enviado; inspeciona os
primeiros bytes do conteúdo real.
"""

from __future__ import annotations

#: Extensão de arquivo por tipo detectado — usada para nomear o objeto no
#: storage (RF04) e como `Content-Type` real gravado no MinIO (nunca o
#: header declarado pelo cliente).
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"


def detect_image_content_type(data: bytes) -> str | None:
    """Retorna o `Content-Type` real de `data` (RF02).

    `None` se `data` não começar com a assinatura de nenhum dos tipos
    permitidos (`ALLOWED_IMAGE_TYPES`).
    """

    if data.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    if data.startswith(_PNG_SIGNATURE):
        return "image/png"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None

"""Testes unitários — `app.services.image_validation` (SPEC-005 / RF02).

Detecção do tipo real de uma imagem pela assinatura de arquivo (magic bytes),
não confiando apenas no `Content-Type` declarado pelo cliente ou na extensão
do nome do arquivo enviado.
"""

from __future__ import annotations

from app.services.image_validation import detect_image_content_type

_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 32
_PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 32


def test_detect_image_content_type_recognizes_jpeg_spec005() -> None:
    assert detect_image_content_type(_JPEG_BYTES) == "image/jpeg"


def test_detect_image_content_type_recognizes_png_spec005() -> None:
    assert detect_image_content_type(_PNG_BYTES) == "image/png"


def test_detect_image_content_type_recognizes_webp_spec005() -> None:
    assert detect_image_content_type(_WEBP_BYTES) == "image/webp"


def test_detect_image_content_type_returns_none_for_disallowed_type_spec005() -> None:
    assert detect_image_content_type(_PDF_BYTES) is None


def test_detect_image_content_type_returns_none_for_empty_bytes_spec005() -> None:
    assert detect_image_content_type(b"") is None


def test_detect_image_content_type_ignores_declared_extension_spec005() -> None:
    # Um PDF "disfarçado" de imagem (nome/Content-Type declarado não
    # importam para esta função — só o conteúdo real é inspecionado).
    disguised = _PDF_BYTES
    assert detect_image_content_type(disguised) is None

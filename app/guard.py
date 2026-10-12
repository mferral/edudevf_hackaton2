"""Capa de seguridad: clasificación con Llama Guard vía Ollama.

Llama Guard devuelve `safe` o `unsafe <categoría>` como primer token
de su respuesta. Esta función envuelve la llamada y devuelve una tupla
`(es_seguro, categoria_o_none)`.
"""
from __future__ import annotations

from typing import Optional, Sequence

import ollama

from app.config import MODELO_GUARD, OLLAMA_HOST


class ErrorLlamaGuard(ValueError):
    """Veredicto de Llama Guard no reconocido."""


def _cliente(host: str = OLLAMA_HOST):
    return ollama.Client(host=host)


def revisar(
    mensajes: Sequence[dict],
    *,
    modelo: str = MODELO_GUARD,
    cliente=None,
) -> tuple[bool, Optional[str]]:
    """Revisa una lista de mensajes y devuelve `(es_seguro, categoria)`.

    `mensajes` es la lista estilo chat: `[{"role": ..., "content": ...}]`.
    Para revisar la salida, el llamador debe incluir el intercambio usuario
    + asistente.
    """
    client = cliente or _cliente()
    respuesta = client.chat(model=modelo, messages=list(mensajes))
    contenido = respuesta["message"]["content"].strip().lower()
    if contenido.startswith("safe"):
        return True, None
    if contenido.startswith("unsafe"):
        partes = contenido.split()
        categoria = partes[1].upper() if len(partes) > 1 else "SIN_CATEGORIA"
        return False, categoria
    raise ErrorLlamaGuard(f"Veredicto inesperado de Llama Guard: {contenido!r}")


# Mensajes fijos (RF4)
MENSAJE_BLOQUEO_ENTRADA = (
    "Lo siento, no puedo ayudarte con ese mensaje. "
    "Si necesitas información del consultorio, escríbeme tu duda."
)
MENSAJE_BLOQUEO_SALIDA = (
    "No puedo compartir esa respuesta. "
    "Un miembro del equipo se pondrá en contacto contigo."
)
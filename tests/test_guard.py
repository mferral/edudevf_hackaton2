"""Pruebas del wrapper de Llama Guard (con cliente Ollama simulado)."""
from __future__ import annotations

from typing import List

import pytest

from app.guard import ErrorLlamaGuard, revisar


class _ClienteOllamaFalso:
    """Devuelve una respuesta configurable para `chat`."""

    def __init__(self, contenido: str) -> None:
        self._contenido = contenido
        self.ultimo_modelo: str | None = None
        self.ultimos_mensajes: List[dict] | None = None

    def chat(self, model: str, messages: List[dict]):
        self.ultimo_modelo = model
        self.ultimos_mensajes = messages
        return {"message": {"content": self._contenido}}


def test_safe_devuelve_true_sin_categoria() -> None:
    cliente = _ClienteOllamaFalso("safe")
    seguro, categoria = revisar([{"role": "user", "content": "hola"}], cliente=cliente)
    assert seguro is True
    assert categoria is None


def test_unsafe_devuelve_false_con_categoria() -> None:
    cliente = _ClienteOllamaFalso("unsafe S1")
    seguro, categoria = revisar(
        [{"role": "user", "content": "malo"}], cliente=cliente
    )
    assert seguro is False
    assert categoria == "S1"


def test_unsafe_sin_categoria_devuelve_sin_categoria() -> None:
    cliente = _ClienteOllamaFalso("unsafe")
    seguro, categoria = revisar([{"role": "user", "content": "malo"}], cliente=cliente)
    assert seguro is False
    assert categoria == "SIN_CATEGORIA"


def test_veredicto_inesperado_lanza_error() -> None:
    cliente = _ClienteOllamaFalso("hola?")
    with pytest.raises(ErrorLlamaGuard):
        revisar([{"role": "user", "content": "x"}], cliente=cliente)


def test_pasa_el_modelo_de_guard_configurado() -> None:
    cliente = _ClienteOllamaFalso("safe")
    revisar([{"role": "user", "content": "hola"}], modelo="llama-guard3", cliente=cliente)
    assert cliente.ultimo_modelo == "llama-guard3"


def test_pasa_los_mensajes_al_cliente() -> None:
    cliente = _ClienteOllamaFalso("safe")
    mensajes = [{"role": "user", "content": "pregunta"}]
    revisar(mensajes, cliente=cliente)
    assert cliente.ultimos_mensajes == mensajes
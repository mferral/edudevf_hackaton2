"""Memoria por número de teléfono (RF3).

  * Historial aislado por paciente (un dict por número).
  * Lock por número para serializar mensajes del mismo usuario.
  * Tamaño máximo del historial para no crecer sin cota.
  * Normalización de números mexicanos `521…` → `52…`.
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.config import HISTORIAL_MAXIMO


def normalizar_numero(numero: str) -> str:
    """WhatsApp MX antepone `1` al código de país: lo quitamos."""
    if numero.startswith("521") and len(numero) == 13:
        return "52" + numero[3:]
    return numero


class MemoriaConversacion:
    def __init__(self, max_mensajes: int = HISTORIAL_MAXIMO) -> None:
        self._lock_global = threading.Lock()
        self._locks_por_numero: Dict[str, threading.Lock] = {}
        self._historiales: Dict[str, List[dict]] = {}
        self.max_mensajes = max_mensajes

    # ------------------------------------------------------------------
    def _lock_de(self, numero: str) -> threading.Lock:
        with self._lock_global:
            lock = self._locks_por_numero.get(numero)
            if lock is None:
                lock = threading.Lock()
                self._locks_por_numero[numero] = lock
            return lock

    def obtener(self, numero: str) -> List[dict]:
        """Devuelve una copia del historial (no mutar el interno)."""
        with self._lock_de(numero):
            return list(self._historiales.get(numero, []))

    def agregar(self, numero: str, rol: str, contenido: str) -> None:
        with self._lock_de(numero):
            historial = self._historiales.setdefault(numero, [])
            historial.append({"role": rol, "content": contenido})
            # Mantener el historial acotado
            if len(historial) > self.max_mensajes:
                historial[:] = historial[-self.max_mensajes :]

    def agregar_tool_call(
        self, numero: str, contenido: str, tool_calls: list, tool_results: list
    ) -> None:
        """Registra el turno intermedio del assistant con tool_calls y los resultados."""
        with self._lock_de(numero):
            historial = self._historiales.setdefault(numero, [])
            historial.append(
                {
                    "role": "assistant",
                    "content": contenido or "",
                    "tool_calls": tool_calls,
                }
            )
            for resultado in tool_results:
                historial.append(
                    {
                        "role": "tool",
                        "content": resultado,
                    }
                )

    def limpiar(self, numero: str) -> None:
        with self._lock_de(numero):
            self._historiales.pop(numero, None)

    # Para serialización de mensajes del mismo usuario --------------------
    def ejecutar_bloqueado(self, numero: str, fn, *args, **kwargs):
        """Ejecuta `fn(*args, **kwargs)` bajo el lock del número."""
        with self._lock_de(numero):
            return fn(*args, **kwargs)
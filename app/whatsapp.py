"""Cliente de WhatsApp Cloud API (Meta) para enviar mensajes."""
from __future__ import annotations

import threading
from typing import Optional

import requests

from app.config import PHONE_ID, WHATSAPP_API_VERSION, WHATSAPP_TOKEN


def enviar_texto(
    numero: str,
    texto: str,
    *,
    phone_id: str = PHONE_ID,
    token: str = WHATSAPP_TOKEN,
    sesion: Optional[requests.Session] = None,
    api_version: str = WHATSAPP_API_VERSION,
) -> requests.Response:
    """Envía un mensaje de texto a `numero` vía la Cloud API.

    Lanza `requests.exceptions.RequestException` si la API responde con
    estado no exitoso.
    """
    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto},
    }
    s = sesion or requests
    return s.post(url, headers=headers, json=payload, timeout=15)


# Singleton de locks por número para serializar envíos (opcional, evita
# condiciones de carrera si dos mensajes del mismo usuario se procesan
# en paralelo).
_locks_por_numero: dict[str, threading.Lock] = {}
_lock_global = threading.Lock()


def lock_de(numero: str) -> threading.Lock:
    with _lock_global:
        lock = _locks_por_numero.get(numero)
        if lock is None:
            lock = threading.Lock()
            _locks_por_numero[numero] = lock
        return lock
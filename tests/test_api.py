"""Pruebas de los endpoints HTTP (webhook y /health)."""
from __future__ import annotations

from typing import List

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.agent import Agente


class _AgenteFalso:
    """Sustituto mínimo de Agente para no tocar Ollama."""

    def __init__(self) -> None:
        self.recibidos: List[tuple[str, str]] = []
        self.respuesta: str = "ok desde el agente falso"
        # `memoria` lo accede el lifespan; no se usa en estos tests.
        self.memoria = None

    def responder(self, numero: str, texto: str) -> str:
        self.recibidos.append((numero, texto))
        return self.respuesta


class _WhatsAppFalso:
    def __init__(self) -> None:
        self.enviados: List[dict] = []

    def __call__(self, numero: str, texto: str, **_kwargs) -> None:
        self.enviados.append({"to": numero, "body": texto})


@pytest.fixture()
def cliente_http(monkeypatch):
    """Crea un TestClient con agente y envío de WhatsApp simulados."""
    agente_falso = _AgenteFalso()
    whatsapp_falso = _WhatsAppFalso()

    # Reemplazamos la fábrica para que el lifespan monte el agente falso
    # y no se intente cargar el modelo de embeddings ni hablar con Ollama.
    monkeypatch.setattr(main, "construir_agente", lambda: agente_falso)
    monkeypatch.setattr(main, "enviar_texto", whatsapp_falso)

    # Limpiar dedupe entre tests
    with main.ids_lock:
        main.ids_procesados.clear()

    with TestClient(main.app) as client:
        yield client, agente_falso, whatsapp_falso


# ----------------------------------------------------------------------
def test_health(cliente_http) -> None:
    client, _, _ = cliente_http
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_webhook_get_token_valido(cliente_http) -> None:
    client, _, _ = cliente_http
    r = client.get(
        "/webhook",
        params={"hub.verify_token": main.VERIFY_TOKEN, "hub.challenge": "abc123"},
    )
    assert r.status_code == 200
    # La respuesta contiene el challenge (puede venir como JSON o texto)
    assert "abc123" in r.text


def test_webhook_get_token_invalido(cliente_http) -> None:
    client, _, _ = cliente_http
    r = client.get(
        "/webhook",
        params={"hub.verify_token": "otro", "hub.challenge": "abc123"},
    )
    assert r.status_code == 200
    assert "error" in r.json()


def test_webhook_post_procesa_mensaje(cliente_http) -> None:
    client, agente_falso, whatsapp_falso = cliente_http
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid-001",
                                    "from": "5215512345678",  # debe normalizarse a 52…
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    r = client.post("/webhook", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # El background task ya corrió dentro de TestClient
    assert ("525512345678", "hola") in agente_falso.recibidos
    assert {"to": "525512345678", "body": "ok desde el agente falso"} in whatsapp_falso.enviados


def test_webhook_post_dedup_por_wamid(cliente_http) -> None:
    client, agente_falso, _ = cliente_http
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid-dup",
                                    "from": "5215512345678",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    client.post("/webhook", json=payload)
    client.post("/webhook", json=payload)
    # Solo una vez llega al agente
    assert agente_falso.recibidos.count(("525512345678", "hola")) == 1


def test_webhook_post_evento_sin_messages(cliente_http) -> None:
    client, _, _ = cliente_http
    payload = {"entry": [{"changes": [{"value": {}}]}]}
    r = client.post("/webhook", json=payload)
    assert r.status_code == 200
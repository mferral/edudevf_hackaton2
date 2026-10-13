"""FastAPI: webhook de WhatsApp, /health y arranque del agente."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Request

from app.agent import Agente
from app.config import VERIFY_TOKEN
from app.guard import MENSAJE_BLOQUEO_ENTRADA, revisar
from app.memory import MemoriaConversacion, normalizar_numero
from app.rag import RAG
from app.tools import Agenda
from app.whatsapp import enviar_texto, lock_de

logger = logging.getLogger("nutribot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ----------------------------------------------------------------------
# Estado del proceso (inicializado en lifespan)
# ----------------------------------------------------------------------
agente: Optional[Agente] = None
memoria: Optional[MemoriaConversacion] = None
ids_procesados: set[str] = set()
ids_lock = threading.Lock()


def construir_agente() -> Agente:
    """Construye el agente con sus dependencias por defecto."""
    rag = RAG()
    agenda = Agenda()
    mem = MemoriaConversacion()
    return Agente(rag=rag, agenda=agenda, memoria=mem)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agente, memoria
    agente = construir_agente()
    memoria = agente.memoria
    logger.info("NutriBot listo.")
    yield
    logger.info("Apagando NutriBot.")


app = FastAPI(
    title="NutriBot",
    version="0.1.0",
    description=(
        "Agente de WhatsApp para consultorio de nutrición: "
        "responde FAQ con RAG y agenda/reagenda citas con function calling."
    ),
    lifespan=lifespan,
)


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@app.get("/health", tags=["meta"], summary="Health check")
async def health() -> dict:
    """Devuelve 200 si el servicio está vivo (Swagger lo documenta)."""
    return {"status": "ok", "servicio": "nutribot"}


@app.get("/webhook", tags=["whatsapp"], summary="Verificación del webhook (Meta)")
async def verificar_webhook(request: Request ):
    """Verifica el `hub.verify_token` enviado por Meta al configurar el webhook."""
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        # Meta espera el challenge como texto plano (int o string)
        return int(params.get("hub.challenge"))
    return {"error": "token inválido"}


@app.post("/webhook", tags=["whatsapp"], summary="Recepción de mensajes de WhatsApp")
async def recibir_mensaje(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Recibe un evento de WhatsApp Cloud API y procesa el mensaje.

    Dedup: si ya vimos el `wamid`, devolvemos 200 sin reprocesar (RF3).
    """
    body = await request.json()
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        mensajes = value.get("messages", [])
        if not mensajes:
            return {"status": "ok"}
        mensaje = mensajes[0]
        wamid = mensaje["id"]
        with ids_lock:
            if wamid in ids_procesados:
                return {"status": "ok"}
            ids_procesados.add(wamid)
        numero = normalizar_numero(mensaje["from"])
        texto = mensaje.get("text", {}).get("body", "")

        background_tasks.add_task(_procesar, numero, texto)
    except (KeyError, IndexError):
        # Estructura inesperada (evento sin mensajes): respondemos 200 igualmente
        pass
    return {"status": "ok"}


def _procesar(numero: str, texto: str) -> None:
    """Procesa un mensaje fuera del ciclo de request."""
    if agente is None:
        logger.error("Agente no inicializado; ignorando mensaje de %s.", numero)
        return

    with lock_de(numero):
        try:
            respuesta = agente.responder(numero, texto)
        except Exception:  # noqa: BLE001
            logger.exception("Fallo al responder a %s", numero)
            respuesta = (
                "Estamos teniendo un problema técnico. "
                "Intenta de nuevo en un momento."
            )

        if respuesta == MENSAJE_BLOQUEO_ENTRADA:
            # Misma respuesta en ambos casos; el mensaje fijo se eligió
            # explícitamente para bloquear contenido inseguro.
            pass

        try:
            enviar_texto(numero, respuesta)
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo enviar la respuesta a %s", numero)
"""Carga de configuración desde variables de entorno (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga .env desde la raíz del proyecto (si existe)
_RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(_RAIZ / ".env")


def _requerido(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            f"Copia .env.example a .env y completa los valores."
        )
    return valor


# --- Credenciales de WhatsApp Cloud API ---
VERIFY_TOKEN: str = os.getenv("VERIFY_TOKEN", "mi_token")
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
PHONE_ID: str = os.getenv("PHONE_ID", "")

# --- Ollama ---
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# --- Modelo y reglas de negocio ---
MODELO_LLM = "llama3.2" #llama3.1:8b
MODELO_GUARD = "llama-guard3:1b" #llama-guard3
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

# Versión de la API de WhatsApp Cloud
WHATSAPP_API_VERSION = "v25.0"

# Umbral de similitud mínima para considerar que el RAG cubre una pregunta
UMBRAL_RAG = 0.30

# Ventana de atención (constitución art. 5)
DIAS_ATENCION = {0, 1, 2, 3}      # lunes (0) a jueves (3)
SABADO = 5                        # sábado
HORARIO_LUNES_JUEVES = (8, 19)   # 8:00 a 19:00
HORARIO_SABADO = (8, 14)         # 8:00 a 14:00

# Anticipación mínima para agendar/reagendar (en horas)
ANTICIPACION_MINIMA_HORAS = 24

# Tamaño máximo del historial por número (en mensajes)
HISTORIAL_MAXIMO = 20

# Rutas de archivos de datos (memoria de citas)
_DATA_DIR = _RAIZ / "data"
DATA_DIR: Path = _DATA_DIR
CITAS_FILE: Path = _DATA_DIR / "citas.json"


def requerir_whatsapp() -> tuple[str, str]:
    """Devuelve (WHATSAPP_TOKEN, PHONE_ID) si están configurados."""
    return _requerido("WHATSAPP_TOKEN"), _requerido("PHONE_ID")
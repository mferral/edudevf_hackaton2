# 001-init: NutriBot (agente de WhatsApp)

## Objetivo
Asistente de consultorio de nutrición por WhatsApp: responde preguntas frecuentes (RAG) y agenda/reagenda citas (function calling), con memoria por sesión y capa de seguridad.

## Alcance
- Webhook WhatsApp Cloud API (`GET/POST /webhook`) y `GET /health`.
- RAG: embeddings `paraphrase-multilingual-MiniLM-L12-v2` sobre `docs/rag.md`.
- Herramientas: `consultar_disponibilidad`, `agendar_cita`, `reagendar_cita` (agenda en memoria/JSON).
- Seguridad: Llama Guard 3 + validación de horario/entrada.
- Fuera de alcance: pagos reales, base de datos externa, despliegue.

## Requisitos
- RF1 Responder FAQ solo con contexto del RAG.
- RF2 Agendar/reagendar respetando horarios y 1 día de anticipación.
- RF3 Memoria por número (normalizar `521...` → `52...`), sin duplicar mensajes (`wamid`).
- RF4 Bloquear mensajes inseguros con respuesta fija.
- RF5 Swagger en `/docs`.

## Estructura
```
app/ main.py  config.py  rag.py  tools.py  guard.py  agent.py  whatsapp.py  memory.py
tests/ test_rag.py  test_tools.py  test_guard.py  test_api.py
requirements.txt  .env.example
```

## requirements.txt
`fastapi`, `uvicorn`, `requests`, `ollama`, `sentence-transformers`, `numpy`, `python-dotenv`, `pytest`, `httpx`

## Prerrequisitos
- Conda y Ollama instalados. Modelos previos: `ollama pull llama3.1:8b` y `ollama pull llama-guard3`.
- `.env`: `VERIFY_TOKEN`, `WHATSAPP_TOKEN`, `PHONE_ID`.

## Ejecución manual
```bash
conda create -n nutribot python=3.11 -y && conda activate nutribot
pip install -r requirements.txt
ollama serve                                   # terminal 1
uvicorn app.main:app --reload --port 8000      # terminal 2 -> http://localhost:8000/docs
pytest -q                                      # pruebas unitarias
```

## Plan
1. Base: estructura, config y `/health`.
2. RAG y herramientas de citas.
3. Guard + agente (Ollama con tools) + memoria.
4. Webhook WhatsApp y Swagger.
5. Pruebas y documentación de ejecución.

## Tareas
- [ ] T1 Crear estructura, `requirements.txt`, `.env.example`
- [ ] T2 `rag.py` + test
- [ ] T3 `tools.py` (reglas de horario/anticipación) + test
- [ ] T4 `guard.py` + test (mock Ollama)
- [ ] T5 `memory.py` y `agent.py` (loop de function calling)
- [ ] T6 `whatsapp.py` y `main.py` (webhook, dedupe) + `test_api.py`
- [ ] T7 Verificar Swagger y actualizar README

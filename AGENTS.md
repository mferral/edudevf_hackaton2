# AGENTS.md

Agente de WhatsApp para consultorio de nutrición (FastAPI + Ollama + RAG + function calling).

## Contexto
- Negocio: `docs/context`. Base de conocimiento RAG: `docs/rag.md`. Referencia técnica: `docs/example_colab`.
- Principios: `specify/memory/constitution.md`. Especificación, plan y tareas: `specs/001-init/spec.md`.

## Reglas
- Código simple en `app/`, pruebas en `tests/`, dependencias en `requirements.txt`.
- Todo se ejecuta manualmente (conda + ollama); sin Docker ni CI.
- Cada endpoint documentado en Swagger (`/docs`) y cada módulo con pruebas unitarias (mocks de Ollama/WhatsApp).
- Antes de cerrar un cambio: `pytest -q` en verde.
- Secretos solo por variables de entorno (`.env`), nunca en el repo.

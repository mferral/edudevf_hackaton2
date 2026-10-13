"""Pruebas del flujo de function calling del agente."""
from __future__ import annotations

from app.agent import Agente
from app.memory import MemoriaConversacion
from app.tools import Agenda


class _RagFalso:
    def __init__(self) -> None:
        self.preguntas: list[str] = []

    def buscar(self, pregunta: str) -> str:
        self.preguntas.append(pregunta)
        return "Fragmentos relevantes: La consulta cuesta $600.00 MXN."


class _ClienteFalso:
    def __init__(self) -> None:
        self.llamadas = [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-rag",
                            "function": {
                                "name": "consultar_reglamento",
                                "arguments": {
                                    "pregunta": "¿Cuánto cuesta la consulta?"
                                },
                            },
                        }
                    ],
                }
            },
            {
                "message": {
                    "content": "La consulta cuesta $600.00 MXN."
                }
            },
        ]
        self.argumentos: list[dict] = []

    def chat(self, **argumentos):
        self.argumentos.append(argumentos)
        return self.llamadas.pop(0)


def test_pregunta_de_precio_consulta_el_rag(tmp_path) -> None:
    rag = _RagFalso()
    cliente = _ClienteFalso()
    agente = Agente(
        rag=rag,
        agenda=Agenda(tmp_path / "citas.json"),
        memoria=MemoriaConversacion(),
    )
    agente._cliente_ollama_con(cliente)

    respuesta = agente.responder("525512345678", "¿Cuánto cuesta la consulta?")

    assert respuesta == "La consulta cuesta $600.00 MXN."
    assert rag.preguntas == ["¿Cuánto cuesta la consulta?"]
    assert "600.00" in cliente.argumentos[1]["messages"][-1]["content"]
    assert any(
        herramienta["function"]["name"] == "consultar_reglamento"
        for herramienta in cliente.argumentos[0]["tools"]
    )

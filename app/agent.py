"""Agente: orquesta RAG + Llama con herramientas + memoria."""
from __future__ import annotations

import json
from typing import Callable, Optional

import ollama

from app.config import MODELO_LLM, OLLAMA_HOST
# from app.guard import MENSAJE_BLOQUEO_ENTRADA, MENSAJE_BLOQUEO_SALIDA, revisar
from app.memory import MemoriaConversacion
from app.rag import RAG
from app.tools import FUNCIONES, HERRAMIENTAS, Agenda


SYSTEM_PROMPT = (
    "Eres el asistente del consultorio de nutrición NutriBot. "
    "Responde de forma breve (2–3 líneas) y amable en español. "
    "Tu única fuente de datos sobre el consultorio es la herramienta de "
    "búsqueda en el reglamento. Úsala siempre que pregunten por precios, "
    "horarios, pagos o políticas. No inventes costos, horarios ni políticas. "
    "Para agendar, reagendar o consultar disponibilidad usa las herramientas "
    "de citas. Si el paciente saluda brevemente, responde el saludo sin "
    "usar herramientas. Si pide hablar con una persona, responde que "
    "alguien del consultorio se pondrá en contacto. "
    "Cuando uses una herramienta y obtengas un resultado, comunícalo "
    "claramente al paciente. Nunca describas tu proceso ni nombres de "
    "funciones, parámetros o claves internas."
)


class Agente:
    """Agente conversacional con RAG, function calling y memoria."""

    def __init__(
        self,
        *,
        rag: RAG,
        agenda: Agenda,
        memoria: Optional[MemoriaConversacion] = None,
        host: str = OLLAMA_HOST,
        modelo: str = MODELO_LLM,
    ) -> None:
        self.rag = rag
        self.agenda = agenda
        self.memoria = memoria or MemoriaConversacion()
        self.host = host
        self.modelo = modelo
        # El cliente Ollama se crea perezosamente
        self._cliente = None

    # ------------------------------------------------------------------
    def _cliente_ollama(self):
        if self._cliente is None:
            self._cliente = ollama.Client(host=self.host)
        return self._cliente

    def _cliente_ollama_con(self, cliente):
        """Inyección para tests."""
        self._cliente = cliente

    # ------------------------------------------------------------------
    @property
    def _herramientas(self) -> list[dict]:
        return HERRAMIENTAS

    # ------------------------------------------------------------------
    def _ejecutar_herramienta(self, nombre: str, argumentos: dict) -> str:
        if nombre == "consultar_reglamento":
            return self._consultar_rag(argumentos.get("pregunta", ""))
        fn = FUNCIONES.get(nombre)
        if fn is None:
            return f"Herramienta desconocida: {nombre}"
        if nombre == "consultar_disponibilidad":
            return fn(argumentos.get("fecha", ""), self.agenda)
        if nombre == "agendar_cita":
            return fn(
                argumentos.get("numero", ""),
                argumentos.get("fecha", ""),
                argumentos.get("hora", ""),
                argumentos.get("modalidad", "presencial"),
                self.agenda,
            )
        if nombre == "reagendar_cita":
            return fn(
                argumentos.get("cita_id", ""),
                argumentos.get("nueva_fecha", ""),
                argumentos.get("nueva_hora", ""),
                self.agenda,
            )
        return f"Herramienta no implementada: {nombre}"

    # ------------------------------------------------------------------
    def _consultar_rag(self, pregunta: str) -> str:
        """Llama al RAG como si fuera una herramienta más."""
        return self.rag.buscar(pregunta)

    # ------------------------------------------------------------------
    def responder(self, numero: str, texto: str) -> str:
        """Genera una respuesta, con memoria y function calling.

        Pasos:
          1. seguridad de entrada (Llama Guard),
          2. agrega el mensaje del usuario al historial,
          3. llama al LLM en bucle hasta respuesta final,
          4. revisa la salida (Llama Guard).
        """
        # 1. Seguridad de entrada
        # seguro, _ = revisar([{"role": "user", "content": texto}])
        # if not seguro:
        #     return MENSAJE_BLOQUEO_ENTRADA

        cliente = self._cliente_ollama()

        # 2. Memoria
        self.memoria.agregar(numero, "user", texto)

        mensajes = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.memoria.obtener(numero),
        ]

        # 3. Loop de function calling
        max_iter = 5
        for _ in range(max_iter):
            resp = cliente.chat(model=self.modelo, messages=mensajes, tools=self._herramientas)
            msg = resp["message"]
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                contenido = msg.get("content") or ""
                self.memoria.agregar(numero, "assistant", contenido)
                # 4. Seguridad de salida
                # seguro_out, _ = revisar(
                #     [
                #         {"role": "user", "content": texto},
                #         {"role": "assistant", "content": contenido},
                #     ]
                # )
                # if not seguro_out:
                #     return MENSAJE_BLOQUEO_SALIDA
                return contenido

            # Ejecutar herramientas y continuar el bucle
            contenido_asistente = msg.get("content") or ""
            resultados = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                nombre = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = {}
                if nombre == "consultar_reglamento":
                    resultado = self._ejecutar_herramienta(nombre, args)
                elif nombre == "consultar_disponibilidad":
                    resultado = self._ejecutar_herramienta(nombre, args)
                else:
                    argumentos = dict(args)
                    if nombre == "agendar_cita":
                        argumentos.setdefault("numero", numero)
                    resultado = self._ejecutar_herramienta(nombre, argumentos)
                resultados.append(resultado)

            self.memoria.agregar_tool_call(
                numero,
                contenido_asistente,
                [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", ""),
                        },
                    }
                    for tc in tool_calls
                ],
                resultados,
            )
            mensajes = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.memoria.obtener(numero),
            ]

        # Si agotamos iteraciones, devolvemos un mensaje neutro
        fallback = (
            "Tuve dificultades para procesar tu mensaje. ¿Podrías reformularlo?"
        )
        self.memoria.agregar(numero, "assistant", fallback)
        return fallback
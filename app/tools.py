"""Herramientas de agenda: consultar disponibilidad, agendar y reagendar citas.

Reglas (constitución art. 5):
  * Solo lunes a jueves 8:00–19:00 y sábados 8:00–14:00.
  * Anticipación mínima de 24 h para agendar y para reagendar.
  * La cita queda registrada en `data/citas.json`.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List, Optional

from app.config import (
    ANTICIPACION_MINIMA_HORAS,
    CITAS_FILE,
    DIAS_ATENCION,
    HORARIO_LUNES_JUEVES,
    HORARIO_SABADO,
    SABADO,
)


# ----------------------------------------------------------------------
# Reglas de horario
# ----------------------------------------------------------------------
def _parsear_fecha(fecha: str) -> date:
    return datetime.strptime(fecha, "%Y-%m-%d").date()


def _parsear_hora(hora: str) -> time:
    return datetime.strptime(hora, "%H:%M").time()


def _rango_horario(dia_semana: int) -> Optional[tuple[int, int]]:
    if dia_semana in DIAS_ATENCION:
        return HORARIO_LUNES_JUEVES
    if dia_semana == SABADO:
        return HORARIO_SABADO
    return None  # viernes o domingo


def validar_fecha_y_hora(fecha: str, hora: str, ahora: Optional[datetime] = None) -> None:
    """Lanza `ValueError` si la combinación fecha+hora no es válida.

    Verifica:
      * fecha y hora con formato correcto,
      * día dentro del horario de atención,
      * hora dentro de la ventana del día,
      * al menos `ANTICIPACION_MINIMA_HORAS` de anticipación respecto a `ahora`.
    """
    f = _parsear_fecha(fecha)
    h = _parsear_hora(hora)

    rango = _rango_horario(f.weekday())
    if rango is None:
        raise ValueError(
            "Solo se atiende de lunes a jueves y los sábados. "
            "No hay consulta los viernes ni domingos."
        )

    inicio, fin = rango
    if not (inicio <= h.hour < fin):
        raise ValueError(
            f"Fuera del horario de atención "
            f"({'lunes a jueves' if f.weekday() in DIAS_ATENCION else 'sábado'} "
            f"{inicio:02d}:00–{fin:02d}:00)."
        )

    ref = ahora or datetime.now()
    cita_dt = datetime.combine(f, h)
    if cita_dt - ref < timedelta(hours=ANTICIPACION_MINIMA_HORAS):
        raise ValueError(
            f"La cita debe agendarse con al menos "
            f"{ANTICIPACION_MINIMA_HORAS} horas de anticipación."
        )


# ----------------------------------------------------------------------
# Modelo y persistencia
# ----------------------------------------------------------------------
@dataclass
class Cita:
    id: str
    numero: str
    fecha: str       # YYYY-MM-DD
    hora: str        # HH:MM
    modalidad: str   # "presencial" | "en_linea"
    creado_en: str   # ISO timestamp

    @staticmethod
    def ahora() -> str:
        return datetime.now().isoformat(timespec="seconds")


class Agenda:
    """Agenda persistente en JSON. Acceso protegido por un lock."""

    def __init__(self, ruta: Path = CITAS_FILE) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._citas: List[dict] = self._cargar()

    # --- Persistencia ----------------------------------------------------
    def _cargar(self) -> List[dict]:
        if not self.ruta.exists():
            return []
        try:
            return json.loads(self.ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _guardar(self) -> None:
        self.ruta.write_text(
            json.dumps(self._citas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- API -------------------------------------------------------------
    def slots_disponibles(self, fecha: str) -> List[str]:
        """Devuelve las horas disponibles (HH:MM) para una fecha válida."""
        f = _parsear_fecha(fecha)
        rango = _rango_horario(f.weekday())
        if rango is None:
            return []
        inicio, fin = rango
        ocupados = {
            c["hora"] for c in self._citas if c["fecha"] == fecha
        }
        return [
            f"{h:02d}:00"
            for h in range(inicio, fin)
            if f"{h:02d}:00" not in ocupados
        ]

    def agendar(
        self,
        numero: str,
        fecha: str,
        hora: str,
        modalidad: str = "presencial",
        ahora: Optional[datetime] = None,
    ) -> Cita:
        """Crea una cita. Valida horario, anticipación y disponibilidad."""
        if modalidad not in ("presencial", "en_linea"):
            raise ValueError("modalidad debe ser 'presencial' o 'en_linea'.")

        validar_fecha_y_hora(fecha, hora, ahora=ahora)

        with self._lock:
            if any(c["fecha"] == fecha and c["hora"] == hora for c in self._citas):
                raise ValueError(f"El horario {fecha} {hora} ya está ocupado.")

            cita = Cita(
                id=uuid.uuid4().hex[:8],
                numero=numero,
                fecha=fecha,
                hora=hora,
                modalidad=modalidad,
                creado_en=Cita.ahora(),
            )
            self._citas.append(asdict(cita))
            self._guardar()
            return cita

    def reagendar(
        self,
        cita_id: str,
        nueva_fecha: str,
        nueva_hora: str,
        ahora: Optional[datetime] = None,
    ) -> Cita:
        validar_fecha_y_hora(nueva_fecha, nueva_hora, ahora=ahora)
        with self._lock:
            cita = next((c for c in self._citas if c["id"] == cita_id), None)
            if not cita:
                raise ValueError(f"No se encontró la cita {cita_id}.")

            if any(
                c["id"] != cita_id
                and c["fecha"] == nueva_fecha
                and c["hora"] == nueva_hora
                for c in self._citas
            ):
                raise ValueError(
                    f"El horario {nueva_fecha} {nueva_hora} ya está ocupado."
                )

            cita["fecha"] = nueva_fecha
            cita["hora"] = nueva_hora
            self._guardar()
            return Cita(**cita)

    def obtener(self, cita_id: str) -> Optional[Cita]:
        for c in self._citas:
            if c["id"] == cita_id:
                return Cita(**c)
        return None

    def listar(self, numero: Optional[str] = None) -> List[Cita]:
        citas = self._citas if numero is None else [
            c for c in self._citas if c["numero"] == numero
        ]
        return [Cita(**c) for c in citas]


# ----------------------------------------------------------------------
# Funciones expuestas al LLM (texto corto y descriptivo)
# ----------------------------------------------------------------------
def fn_consultar_disponibilidad(fecha: str, agenda: Agenda) -> str:
    if not fecha:
        return "¿Para qué fecha quieres consultar disponibilidad? Indícamela (YYYY-MM-DD)."
    try:
        f = _parsear_fecha(fecha)
    except ValueError:
        return "La fecha debe tener el formato YYYY-MM-DD."
    slots = agenda.slots_disponibles(fecha)
    if not slots:
        return f"No hay horarios disponibles el {fecha} (puede ser viernes/domingo o ya están ocupados)."
    return f"Horarios disponibles el {fecha}: {', '.join(slots)}."


def fn_agendar_cita(
    numero: str,
    fecha: str,
    hora: str,
    modalidad: str,
    agenda: Agenda,
    ahora: Optional[datetime] = None,
) -> str:
    if not (fecha and hora):
        return "Necesito fecha (YYYY-MM-DD) y hora (HH:MM) para agendar."
    try:
        cita = agenda.agendar(
            numero, fecha, hora, modalidad or "presencial", ahora=ahora
        )
    except ValueError as e:
        return f"No pude agendar: {e}"
    return (
        f"Cita agendada: {cita.fecha} {cita.hora} "
        f"({cita.modalidad}). Folio: {cita.id}. "
        "Recuerda que el pago se realiza por adelantado para confirmar."
    )


def fn_reagendar_cita(
    cita_id: str,
    nueva_fecha: str,
    nueva_hora: str,
    agenda: Agenda,
    ahora: Optional[datetime] = None,
) -> str:
    if not (cita_id and nueva_fecha and nueva_hora):
        return "Necesito el folio de la cita, la nueva fecha y la nueva hora."
    try:
        cita = agenda.reagendar(cita_id, nueva_fecha, nueva_hora, ahora=ahora)
    except ValueError as e:
        return f"No pude reagendar: {e}"
    return f"Cita reagendada: {cita.fecha} {cita.hora}. Folio: {cita.id}."


# ----------------------------------------------------------------------
# Esquemas de herramientas para Ollama (function calling)
# ----------------------------------------------------------------------
HERRAMIENTAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "consultar_reglamento",
            "description": (
                "Busca en el reglamento del consultorio la respuesta a "
                "preguntas sobre precios, horarios, pagos y políticas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": "Pregunta del paciente sobre el consultorio.",
                    }
                },
                "required": ["pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidad",
            "description": (
                "Consulta los horarios disponibles en una fecha (YYYY-MM-DD) "
                "para consulta nutricional. Devuelve una lista de horas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {
                        "type": "string",
                        "description": "Fecha en formato YYYY-MM-DD.",
                    }
                },
                "required": ["fecha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_cita",
            "description": (
                "Agenda una cita de nutrición para el paciente. "
                "Valida horario de atención y anticipación de 24 h."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "YYYY-MM-DD"},
                    "hora": {"type": "string", "description": "HH:MM (24 h)"},
                    "modalidad": {
                        "type": "string",
                        "enum": ["presencial", "en_linea"],
                        "description": "Modalidad de la consulta.",
                    },
                },
                "required": ["fecha", "hora"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reagendar_cita",
            "description": (
                "Reagenda una cita existente con al menos 24 h de anticipación."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cita_id": {"type": "string", "description": "Folio de la cita."},
                    "nueva_fecha": {"type": "string", "description": "YYYY-MM-DD"},
                    "nueva_hora": {"type": "string", "description": "HH:MM (24 h)"},
                },
                "required": ["cita_id", "nueva_fecha", "nueva_hora"],
            },
        },
    },
]

# Mapa nombre -> función (se inyecta `agenda` en `app.agent`)
FUNCIONES: dict[str, callable] = {
    "consultar_disponibilidad": fn_consultar_disponibilidad,
    "agendar_cita": fn_agendar_cita,
    "reagendar_cita": fn_reagendar_cita,
}
"""Pruebas de las herramientas de agenda."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.tools import (
    Agenda,
    fn_agendar_cita,
    fn_consultar_disponibilidad,
    fn_reagendar_cita,
    validar_fecha_y_hora,
)


# ---------- validar_fecha_y_hora ---------------------------------------
def test_fecha_fuera_de_formato() -> None:
    with pytest.raises(ValueError):
        validar_fecha_y_hora("2025/01/01", "10:00")


def test_viernes_no_se_atiende() -> None:
    # viernes
    viernes = "2026-10-16"  # 2026-10-16 es viernes
    assert datetime.strptime(viernes, "%Y-%m-%d").weekday() == 4
    with pytest.raises(ValueError, match="viernes"):
        validar_fecha_y_hora(viernes, "10:00")


def test_domingo_no_se_atiende() -> None:
    domingo = "2026-10-18"
    assert datetime.strptime(domingo, "%Y-%m-%d").weekday() == 6
    with pytest.raises(ValueError, match="domingos"):
        validar_fecha_y_hora(domingo, "10:00")


def test_hora_fuera_de_ventana_en_sabado() -> None:
    # sábado: ventana 8–14, hora 15 debe fallar
    sabado = "2026-10-17"  # 2026-10-17 es sábado
    assert datetime.strptime(sabado, "%Y-%m-%d").weekday() == 5
    with pytest.raises(ValueError, match="horario"):
        validar_fecha_y_hora(sabado, "15:00")


def test_anticipacion_minima() -> None:
    ahora = datetime(2026, 10, 12, 9, 0)  # lunes
    # misma tarde: solo 1 h de anticipación, falla
    with pytest.raises(ValueError, match="anticipación"):
        validar_fecha_y_hora("2026-10-12", "10:00", ahora=ahora)
    # día siguiente a la misma hora: 24 h, ok
    validar_fecha_y_hora("2026-10-13", "10:00", ahora=ahora)


def test_lunes_en_horario_valido() -> None:
    # lunes 10:00 con 48 h de anticipación
    ahora = datetime(2026, 10, 12, 10, 0)
    validar_fecha_y_hora("2026-10-14", "10:00", ahora=ahora)


# ---------- Agenda ------------------------------------------------------
@pytest.fixture()
def agenda(tmp_path):
    return Agenda(ruta=tmp_path / "citas.json")


def test_agenda_archivo_vacio_al_inicio(agenda: Agenda) -> None:
    assert agenda.listar() == []


def test_slots_sabado_devuelve_ventana_8_a_14(agenda: Agenda) -> None:
    sabado = "2026-10-17"
    slots = agenda.slots_disponibles(sabado)
    assert slots[0] == "08:00"
    assert slots[-1] == "13:00"
    assert len(slots) == 6  # 8,9,10,11,12,13


def test_slots_viernes_devuelve_vacio(agenda: Agenda) -> None:
    assert agenda.slots_disponibles("2026-10-16") == []


def test_agendar_y_listar(agenda: Agenda) -> None:
    cita = agenda.agendar(
        numero="525512345678",
        fecha="2026-10-13",
        hora="10:00",
        modalidad="presencial",
        ahora=datetime(2026, 10, 12, 10, 0),
    )
    assert cita.id
    assert len(agenda.listar(numero="525512345678")) == 1


def test_agendar_horario_duplicado_falla(agenda: Agenda) -> None:
    ahora = datetime(2026, 10, 12, 10, 0)
    agenda.agendar("525511111111", "2026-10-13", "10:00", ahora=ahora)
    with pytest.raises(ValueError, match="ocupado"):
        agenda.agendar("525522222222", "2026-10-13", "10:00", ahora=ahora)


def test_reagendar_cambia_fecha(agenda: Agenda) -> None:
    ahora = datetime(2026, 10, 12, 10, 0)
    cita = agenda.agendar(
        "525511111111", "2026-10-13", "10:00", ahora=ahora
    )
    reagendada = agenda.reagendar(
        cita.id, "2026-10-14", "11:00", ahora=ahora
    )
    assert reagendada.fecha == "2026-10-14"
    assert reagendada.hora == "11:00"


def test_reagendar_sin_anticipacion_falla(agenda: Agenda) -> None:
    ahora = datetime(2026, 10, 12, 10, 0)
    cita = agenda.agendar(
        "525511111111", "2026-10-14", "10:00", ahora=ahora
    )
    # reagendar a mañana mismo (Oct 13 09:00): 23 h < 24 h → falla
    with pytest.raises(ValueError, match="anticipación"):
        agenda.reagendar(cita.id, "2026-10-13", "09:00", ahora=ahora)


# ---------- wrappers de texto ------------------------------------------
def test_fn_consultar_sin_fecha_pide_dato(agenda: Agenda) -> None:
    r = fn_consultar_disponibilidad("", agenda)
    assert "fecha" in r.lower()


def test_fn_consultar_con_fecha_valida_devuelve_slots(agenda: Agenda) -> None:
    r = fn_consultar_disponibilidad("2026-10-17", agenda)
    assert "08:00" in r


def test_fn_agendar_devuelve_folio(agenda: Agenda) -> None:
    r = fn_agendar_cita(
        "525511111111", "2026-10-13", "10:00", "presencial", agenda
    )
    assert "Folio" in r


def test_fn_agendar_sin_datos_pide_completar(agenda: Agenda) -> None:
    r = fn_agendar_cita("525511111111", "", "", "", agenda)
    assert "fecha" in r.lower() or "hora" in r.lower()


def test_fn_reagendar_exitoso(agenda: Agenda) -> None:
    ahora = datetime(2026, 10, 12, 10, 0)
    cita = agenda.agendar(
        "525511111111", "2026-10-13", "10:00", ahora=ahora
    )
    r = fn_reagendar_cita(cita.id, "2026-10-14", "11:00", agenda)
    assert "reagendada" in r.lower()
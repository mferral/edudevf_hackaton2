"""Pruebas del módulo RAG (con codificador simulado)."""
from __future__ import annotations

import hashlib
from typing import List

import numpy as np
import pytest

from app.rag import RAG


class _CodificadorFalso:
    """Codificador determinista estilo bag-of-words con hash.

    - Textos idénticos → vectores idénticos (similitud = 1).
    - Textos sin palabras en común → vectores ortogonales (similitud = 0).
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def encode(self, textos: List[str], normalize_embeddings: bool = True):
        vectores = []
        for texto in textos:
            v = np.zeros(self.dim)
            for palabra in texto.lower().split():
                h = int(hashlib.md5(palabra.encode()).hexdigest(), 16) % self.dim
                v[h] += 1
            if normalize_embeddings:
                norma = np.linalg.norm(v)
                if norma > 0:
                    v = v / norma
            vectores.append(v)
        return np.asarray(vectores)


@pytest.fixture()
def rag(tmp_path) -> RAG:
    """Crea un RAG con un archivo temporal y codificador falso."""
    rag_path = tmp_path / "rag.md"
    # Estructura mínima válida como lista de strings Python
    rag_path.write_text(
        '"El costo de la consulta es 600 pesos y se paga por adelantado.",\n'
        '"El horario de consultas es lunes a jueves de 8 a 19 y sabado de 8 a 14.",\n'
        '"Para reagendar se requiere al menos 1 dia de anticipacion.",\n',
        encoding="utf-8",
    )
    return RAG(
        ruta_archivo=rag_path,
        codificador=_CodificadorFalso(),
        umbral=0.5,
    )


def test_carga_fragmentos(rag: RAG) -> None:
    assert len(rag.fragmentos) == 3


def test_buscar_encuentra_fragmento_relevante(rag: RAG) -> None:
    # La pregunta idéntica a un fragmento debe aparecer en los relevantes
    pregunta = "El costo de la consulta es 600 pesos y se paga por adelantado."
    respuesta = rag.buscar(pregunta)
    assert "600" in respuesta


def test_buscar_indica_no_encontrado(rag: RAG) -> None:
    # El umbral está alto; un texto totalmente nuevo no debería pasar
    respuesta = rag.buscar("xyz123 texto sin sentido conocido")
    assert "No tengo información" in respuesta


def test_mejor_similitud_entre_cero_y_uno(rag: RAG) -> None:
    s = rag.mejor_similitud("El horario de consultas")
    assert 0.0 <= s <= 1.0
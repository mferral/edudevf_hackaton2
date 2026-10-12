"""RAG: base de conocimiento en `docs/rag.md` y búsqueda por similitud."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List

import numpy as np

from app.config import MODELO_EMBEDDINGS, UMBRAL_RAG

# Ruta por defecto al archivo de conocimiento
_RAG_POR_DEFECTO = Path(__file__).resolve().parent.parent / "docs" / "rag.md"


def _cargar_fragmentos(ruta: str | Path) -> List[str]:
    """Lee `docs/rag.md` (que contiene una lista de cadenas Python) y
    devuelve cada fragmento como un solo texto.

    El archivo es Python válido: cada bloque es una concatenación implícita
    de cadenas en una lista. Se envuelve en `[...]` y se evalúa con
    `ast.literal_eval`.
    """
    texto = Path(ruta).read_text(encoding="utf-8")
    return list(ast.literal_eval("[" + texto + "]"))


class RAG:
    """Base de conocimiento RAG con embeddings multilingües."""

    def __init__(
        self,
        ruta_archivo: str | Path = _RAG_POR_DEFECTO,
        modelo_nombre: str = MODELO_EMBEDDINGS,
        umbral: float = UMBRAL_RAG,
        codificador=None,
    ) -> None:
        self.fragmentos: List[str] = _cargar_fragmentos(ruta_archivo)
        self.umbral = umbral
        if codificador is not None:
            # Permite inyectar un codificador mockeado en pruebas
            self._codificador = codificador
        else:
            from sentence_transformers import SentenceTransformer

            self._codificador = SentenceTransformer(modelo_nombre)
        self._embeddings = self._codificar(self.fragmentos)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _codificar(self, textos: List[str]) -> np.ndarray:
        """Calcula embeddings normalizados (coseno == producto punto)."""
        return np.asarray(
            self._codificador.encode(textos, normalize_embeddings=True)
        )

    def _similitudes(self, pregunta: str) -> np.ndarray:
        emb = self._codificar([pregunta])
        # producto punto porque los embeddings están normalizados
        return (self._embeddings @ emb.T).flatten()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def buscar(self, pregunta: str, k: int = 2) -> str:
        """Devuelve los fragmentos relevantes o un mensaje de "no encontrado".

        Si la mejor similitud está por debajo de `umbral`, indica que el
        reglamento no cubre la pregunta (constitución art. 2).
        """
        sims = self._similitudes(pregunta)
        if sims.size == 0 or float(sims.max()) < self.umbral:
            return (
                "No tengo información sobre eso. Te recomiendo contactar "
                "directamente al consultorio para confirmarlo."
            )
        indices = np.argsort(sims)[::-1][:k]
        relevantes = [
            self.fragmentos[int(i)]
            for i in indices
            if float(sims[int(i)]) >= self.umbral
        ]
        return "Fragmentos relevantes: " + " | ".join(relevantes)

    def mejor_similitud(self, pregunta: str) -> float:
        """Útil para depurar el umbral."""
        sims = self._similitudes(pregunta)
        return float(sims.max()) if sims.size else 0.0
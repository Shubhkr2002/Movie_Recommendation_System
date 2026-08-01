"""
Recommendation service.

This module owns the ML side of the API. The algorithm itself -
cosine similarity between rows of a precomputed TF-IDF matrix - is copied
verbatim from the original `main.py`. Nothing about *how* recommendations
are scored or ranked has changed; what changed is *where* it lives:

  * pickles are loaded exactly once, at startup, and cached on the
    instance (never reloaded per-request);
  * the title -> row-index lookup is normalized once into a plain dict;
  * every public method raises the same HTTPException semantics the
    original functions did, so callers/tests don't need to change.
"""

import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _normalize_title(title: str) -> str:
    """Lowercase + strip a title so lookups are case/whitespace insensitive."""
    return str(title).strip().lower()


class RecommendationService:
    """
    Loads the local dataset (df, indices, TF-IDF matrix/vectorizer) once and
    serves content-based recommendations from an in-memory cosine-similarity
    computation against the precomputed TF-IDF matrix.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._data_dir = settings.DATA_DIR

        self.df: Optional[pd.DataFrame] = None
        self.indices_obj: Any = None
        self.tfidf_matrix: Any = None
        self.tfidf_vectorizer: Any = None
        self.title_to_idx: Dict[str, int] = {}

        self._loaded = False

    # ------------------------------------------------------------------
    # Loading (called once, from the app lifespan/startup hook)
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load every pickle from disk exactly once and build the lookup map."""
        if self._loaded:
            logger.debug("RecommendationService.load() called again - skipping reload")
            return

        df_path = os.path.join(self._data_dir, self._settings.DF_FILENAME)
        indices_path = os.path.join(self._data_dir, self._settings.INDICES_FILENAME)
        matrix_path = os.path.join(self._data_dir, self._settings.TFIDF_MATRIX_FILENAME)
        vectorizer_path = os.path.join(
            self._data_dir, self._settings.TFIDF_VECTORIZER_FILENAME
        )

        logger.info("Loading recommendation dataset from '%s'", self._data_dir)

        with open(df_path, "rb") as f:
            self.df = pickle.load(f)

        with open(indices_path, "rb") as f:
            self.indices_obj = pickle.load(f)

        with open(matrix_path, "rb") as f:
            self.tfidf_matrix = pickle.load(f)

        with open(vectorizer_path, "rb") as f:
            self.tfidf_vectorizer = pickle.load(f)

        if self.df is None or "title" not in self.df.columns:
            raise RuntimeError("df.pkl must contain a DataFrame with a 'title' column")

        self.title_to_idx = self._build_title_to_idx_map(self.indices_obj)
        self._loaded = True

        logger.info(
            "Recommendation dataset loaded: %d titles, tfidf matrix shape=%s",
            len(self.title_to_idx),
            getattr(self.tfidf_matrix, "shape", None),
        )

    @staticmethod
    def _build_title_to_idx_map(indices: Any) -> Dict[str, int]:
        """
        indices.pkl can be:
          - dict(title -> index)
          - pandas Series (index=title, value=index)
        Normalize into a plain, lowercase-keyed dict either way.
        """
        title_to_idx: Dict[str, int] = {}

        if isinstance(indices, dict):
            for key, value in indices.items():
                title_to_idx[_normalize_title(key)] = int(value)
            return title_to_idx

        try:
            for key, value in indices.items():
                title_to_idx[_normalize_title(key)] = int(value)
            return title_to_idx
        except Exception as exc:
            raise RuntimeError(
                "indices.pkl must be dict or pandas Series-like (with .items())"
            ) from exc

    # ------------------------------------------------------------------
    # Lookups / recommendations
    # ------------------------------------------------------------------
    def get_local_idx_by_title(self, title: str) -> int:
        """Resolve a title to its row index in the local dataset/TF-IDF matrix."""
        if not self._loaded:
            raise HTTPException(status_code=500, detail="TF-IDF index map not initialized")

        key = _normalize_title(title)
        if key in self.title_to_idx:
            return int(self.title_to_idx[key])

        raise HTTPException(
            status_code=404, detail=f"Title not found in local dataset: '{title}'"
        )

    def recommend_titles(
        self, query_title: str, top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Returns a list of (title, score) using cosine similarity between the
        query row and every other row of the precomputed TF-IDF matrix.
        Safe against missing columns/rows.
        """
        if not self._loaded or self.df is None or self.tfidf_matrix is None:
            raise HTTPException(status_code=500, detail="TF-IDF resources not loaded")

        idx = self.get_local_idx_by_title(query_title)

        query_vector = self.tfidf_matrix[idx]
        scores = (self.tfidf_matrix @ query_vector.T).toarray().ravel()

        order = np.argsort(-scores)

        results: List[Tuple[str, float]] = []
        for i in order:
            if int(i) == int(idx):
                continue
            try:
                title_i = str(self.df.iloc[int(i)]["title"])
            except Exception:
                continue
            results.append((title_i, float(scores[int(i)])))
            if len(results) >= top_n:
                break
        return results

    @property
    def is_ready(self) -> bool:
        """Whether the dataset has finished loading (used by /health)."""
        return self._loaded

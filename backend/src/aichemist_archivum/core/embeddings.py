"""
Embedding utilities for text similarity.

Wraps sentence-transformers for generating text embeddings.
"""

import logging
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class TextEmbeddingModel:
    """
    Wrapper for sentence-transformers embedding model.

    Provides a consistent interface for generating text embeddings
    using pre-trained sentence transformer models.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """
        Initialize the embedding model.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default is "all-MiniLM-L6-v2" which provides a good
                       balance between speed and quality.
        """
        try:
            self.embedding_model = SentenceTransformer(model_name)
            self.model_name = model_name
            logger.info(f"Loaded embedding model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {model_name}: {e}")
            raise

    def encode(self, text: str | list[str], **kwargs: Any) -> Any:
        """
        Encode text into embeddings.

        Args:
            text: Single text string or list of text strings to embed.
            **kwargs: Additional arguments to pass to the model's encode method.

        Returns:
            Numpy array of embeddings. Shape depends on input:
            - Single string: (embedding_dim,)
            - List of strings: (num_strings, embedding_dim)
        """
        return self.embedding_model.encode(text, **kwargs)

    def get_sentence_embedding_dimension(self) -> int:
        """
        Get the dimension of the sentence embeddings.

        Returns:
            Integer dimension of the embedding vectors.
        """
        return self.embedding_model.get_sentence_embedding_dimension()


class VectorIndex:
    """Simple vector index for similarity search."""

    def __init__(self) -> None:
        """Initialize empty vector index."""
        self.vectors: list[np.ndarray] = []
        self.metadata: list[dict] = []

    def add(self, vector: np.ndarray, metadata: dict | None = None) -> None:
        """Add a vector to the index."""
        self.vectors.append(vector)
        self.metadata.append(metadata or {})

    def search(
        self, query_vector: np.ndarray, top_k: int = 10
    ) -> list[tuple[int, float]]:
        """
        Search for similar vectors.

        Args:
            query_vector: Query vector
            top_k: Number of results to return

        Returns:
            List of (index, similarity_score) tuples
        """
        if not self.vectors:
            return []

        vectors_array = np.array(self.vectors)
        similarities = cosine_similarity([query_vector], vectors_array)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [(int(idx), float(similarities[idx])) for idx in top_indices]


def compute_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute pairwise cosine similarity matrix.

    Args:
        embeddings: Array of embeddings

    Returns:
        Similarity matrix
    """
    return cosine_similarity(embeddings)


__all__ = ["TextEmbeddingModel", "VectorIndex", "compute_similarity_matrix"]

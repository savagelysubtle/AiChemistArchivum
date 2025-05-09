"""Text embedding models for The AIchemist Codex.

This module provides classes for creating and managing text embeddings
using various underlying models like SentenceTransformer.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class VectorIndex:
    """Class for storing and searching vector embeddings."""

    def __init__(self, dimension: int = 384):
        """Initialize the vector index.

        Args:
            dimension: Dimension of the vectors
        """
        self.dimension = dimension
        self.vectors = None
        self.path_mapping: list[str] = []

    def add(self, vector: np.ndarray) -> None:
        """Add a vector to the index.

        Args:
            vector: Vector to add
        """
        vector = vector.reshape(1, -1)
        if self.vectors is None:
            self.vectors = vector
        else:
            self.vectors = np.vstack((self.vectors, vector))

    def search(
        self, query_vector: np.ndarray, k: int = 5
    ) -> tuple[np.ndarray, np.ndarray]:
        """Search for similar vectors.

        Args:
            query_vector: Query vector
            k: Number of results to return

        Returns:
            Tuple of (distances, indices)
        """
        if self.vectors is None or len(self.vectors) == 0:
            return np.array([]), np.array([])

        # Calculate cosine similarity
        query_vector = query_vector.reshape(1, -1)
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return np.array([]), np.array([])

        query_normalized = query_vector / query_norm

        # Normalize database vectors
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        valid_indices = norms > 0
        normalized_vectors = np.zeros_like(self.vectors)
        normalized_vectors[valid_indices.flatten()] = (
            self.vectors[valid_indices.flatten()] / norms[valid_indices]
        )

        # Calculate similarities
        similarities = np.dot(normalized_vectors, query_normalized.T).flatten()

        # Get top-k indices
        if k > len(similarities):
            k = len(similarities)

        top_indices = np.argsort(similarities)[-k:][::-1]
        top_similarities = similarities[top_indices]

        return top_similarities, top_indices

    def get_paths(self, indices: np.ndarray) -> list[str]:
        """Get paths corresponding to indices.

        Args:
            indices: Array of indices

        Returns:
            List of paths
        """
        return [
            self.path_mapping[i] for i in indices if 0 <= i < len(self.path_mapping)
        ]


class TextEmbeddingModel:
    """Model for creating text embeddings.

    This class wraps various embedding models (like SentenceTransformer)
    to provide a consistent interface.
    """

    def __init__(self, model=None):
        """Initialize with an optional model instance.

        Args:
            model: Optional embedding model instance
        """
        self.embedding_model = model

    def encode(self, text: str) -> np.ndarray:
        """Encode text into a vector embedding.

        Args:
            text: Text to encode

        Returns:
            Vector embedding
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model not initialized")

        # Handle empty text
        if not text or not text.strip():
            # Return zero vector of appropriate size (384 is common for smaller models)
            return np.zeros(384, dtype=np.float32)

        try:
            return self.embedding_model.encode(text)
        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            # Return zero vector as fallback
            return np.zeros(384, dtype=np.float32)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode multiple texts into vector embeddings.

        Args:
            texts: List of texts to encode

        Returns:
            Array of vector embeddings
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model not initialized")

        if not texts:
            return np.array([])

        try:
            return self.embedding_model.encode(texts)
        except Exception as e:
            logger.error(f"Error batch encoding texts: {e}")
            # Return empty array as fallback
            return np.array([])


def compute_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Compute cosine similarity matrix between embeddings.

    Args:
        embeddings: Array of embeddings

    Returns:
        Similarity matrix
    """
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / norms

    # Compute similarity matrix
    return np.dot(normalized, normalized.T)

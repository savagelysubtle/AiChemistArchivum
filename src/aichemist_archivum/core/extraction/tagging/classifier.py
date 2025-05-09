"""
Tag classification module implementation.
Implements the TagClassifierInterface.
"""

import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.svm import LinearSVC

# Import domain interface
from the_aichemist_codex.domain.services.interfaces.tag_classifier import (
    TagClassifierInterface,
)

# Import infrastructure types/utils
from the_aichemist_codex.infrastructure.fs.file_metadata import FileMetadata

logger = logging.getLogger(__name__)


class TagClassifier(TagClassifierInterface):  # Implement the interface
    """
    Machine learning classifier for automatic file tagging.
    Implements the TagClassifierInterface.
    """

    def __init__(self, model_dir: Path, default_confidence_threshold: float = 0.6):
        """
        Initialize the TagClassifier with a model directory.

        Args:
            model_dir: Directory to store model files
            default_confidence_threshold: Default threshold for classification confidence.
        """
        self.model_dir = model_dir
        self.model_path = self.model_dir / "tag_classifier.pkl"
        self.metadata_path = self.model_dir / "tag_classifier_metadata.json"

        self.pipeline: Pipeline | None = None
        self.mlb: MultiLabelBinarizer | None = None
        self.feature_names: np.ndarray | None = None
        self.tag_names: list[str] = []
        self.training_metadata: dict[str, Any] = {}
        self.default_confidence_threshold = default_confidence_threshold
        self._model_loaded = False  # Track loading status

        # Initialize the default model structure immediately
        self._initialize_default_model()

    def _initialize_default_model(self) -> None:
        """Initialize the default model pipeline."""
        self.pipeline = Pipeline(
            [
                ("vectorizer", TfidfVectorizer(max_features=10000, ngram_range=(1, 2))),
                (
                    "classifier",
                    MultiOutputClassifier(
                        LinearSVC(
                            C=1.0, class_weight="balanced", dual="auto", max_iter=2000
                        )  # Added dual='auto'
                    ),
                ),
            ]
        )
        self.mlb = MultiLabelBinarizer()
        self.tag_names = []
        self.feature_names = None
        self.training_metadata = {}
        self._model_loaded = False  # Reset loaded status

    async def load_model(self) -> bool:
        """Load a trained model from disk."""
        if self._model_loaded:
            return True
        try:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            if not self.model_path.exists():
                logger.info(
                    "No trained model found at %s, using default.", self.model_path
                )
                # Keep the initialized default model
                self._model_loaded = True  # Mark as "loaded" (default is loaded)
                return False  # Indicate that no *trained* model was loaded

            with open(self.model_path, "rb") as f:
                model_data = pickle.load(f)
                self.pipeline = model_data.get("pipeline")
                self.mlb = model_data.get("mlb")
                self.feature_names = model_data.get("feature_names")
                # Ensure tag_names are loaded correctly
                if self.mlb:
                    self.tag_names = list(self.mlb.classes_)
                else:
                    self.tag_names = []  # Fallback

            if self.metadata_path.exists():
                with open(self.metadata_path) as f:
                    self.training_metadata = json.load(f)

            self._model_loaded = True
            logger.info(
                f"Loaded tag classifier model with {len(self.tag_names)} tags from {self.model_path}"
            )
            return True
        except FileNotFoundError as e:
            logger.error(f"Failed to load tag classifier model: file not found - {e}")
            self._initialize_default_model()  # Reset to default on load failure
            self._model_loaded = True  # Default is considered "loaded"
            return False
        except PermissionError as e:
            logger.error(
                f"Failed to load tag classifier model: permission denied - {e}"
            )
            self._initialize_default_model()  # Reset to default on load failure
            self._model_loaded = True  # Default is considered "loaded"
            return False
        except pickle.UnpicklingError as e:
            logger.error(f"Failed to load tag classifier model: unpickling error - {e}")
            self._initialize_default_model()  # Reset to default on load failure
            self._model_loaded = True  # Default is considered "loaded"
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load tag classifier metadata: invalid JSON - {e}")
            # Continue with model but without metadata
            self.training_metadata = {}
            self._model_loaded = True
            return True
        except Exception as e:
            logger.error(
                f"Failed to load tag classifier model: unexpected error - {e}",
                exc_info=True,
            )
            self._initialize_default_model()  # Reset to default on load failure
            self._model_loaded = True  # Default is considered "loaded"
            return False

    async def save_model(self) -> bool:
        """Save the current model to disk."""
        if not self.pipeline or not self.mlb:
            logger.warning("Cannot save model - pipeline or mlb not initialized.")
            return False
        try:
            os.makedirs(self.model_dir, exist_ok=True)
            # Update tag names from MLB before saving
            self.tag_names = list(self.mlb.classes_)
            model_data = {
                "pipeline": self.pipeline,
                "mlb": self.mlb,
                "feature_names": self.feature_names,
                # Explicitly save tag_names derived from mlb
                "tag_names": self.tag_names,
            }
            with open(self.model_path, "wb") as f:
                pickle.dump(model_data, f)

            self.training_metadata.update(
                {
                    "last_updated": datetime.now().isoformat(),
                    "tag_names": self.tag_names,  # Ensure metadata matches mlb
                    "num_tags": len(self.tag_names),
                }
            )
            with open(self.metadata_path, "w") as f:
                json.dump(self.training_metadata, f, indent=2)

            logger.info(
                f"Saved tag classifier model with {len(self.tag_names)} tags to {self.model_path}"
            )
            return True
        except PermissionError as e:
            logger.error(f"Error saving tag classifier model: permission denied - {e}")
            return False
        except OSError as e:
            logger.error(f"Error saving tag classifier model: OS error - {e}")
            return False
        except pickle.PicklingError as e:
            logger.error(f"Error saving tag classifier model: pickling error - {e}")
            return False
        except TypeError as e:
            logger.error(
                f"Error saving tag classifier model: type error (unpicklable object) - {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Error saving tag classifier model: unexpected error - {e}",
                exc_info=True,
            )
            return False

    def _extract_features(self, file_metadata: FileMetadata) -> str:
        """Extract features from file metadata for classification."""
        features = []
        if file_metadata.path:
            path = Path(file_metadata.path)
            features.append(path.name)
            if path.suffix:
                features.append(path.suffix.lstrip("."))
        if file_metadata.mime_type:
            features.append(file_metadata.mime_type)
        if file_metadata.preview:
            features.append(file_metadata.preview[:5000])
        if hasattr(file_metadata, "topics") and file_metadata.topics:
            for topic_dict in file_metadata.topics:
                for topic, score in topic_dict.items():
                    features.append(f"topic:{topic}")
        if hasattr(file_metadata, "keywords") and file_metadata.keywords:
            for keyword in file_metadata.keywords:
                features.append(f"keyword:{keyword}")
        if hasattr(file_metadata, "entities") and file_metadata.entities:
            for entity_type, entities in file_metadata.entities.items():
                for entity in entities:
                    features.append(f"entity:{entity_type}:{entity}")
        if hasattr(file_metadata, "language") and file_metadata.language:
            features.append(f"lang:{file_metadata.language}")
        if hasattr(file_metadata, "content_type") and file_metadata.content_type:
            features.append(f"content_type:{file_metadata.content_type}")
        return " ".join(str(feature) for feature in features if feature)

    async def classify(
        self,
        file_metadata: FileMetadata,
        confidence_threshold: float | None = None,
    ) -> list[tuple[str, float]]:
        """Classify a file and suggest tags with confidence scores."""
        if not self._model_loaded:
            await self.load_model()
        if not self.pipeline or not self.mlb or not self.tag_names:
            logger.warning("Model/tags not available for classification.")
            return []

        # Use instance default threshold if none is provided
        if confidence_threshold is None:
            confidence_threshold = self.default_confidence_threshold

        try:
            features = self._extract_features(file_metadata)
            if not features:
                return []

            X = [features]
            X_tfidf = self.pipeline.named_steps["vectorizer"].transform(X)
            classifier = self.pipeline.named_steps["classifier"]
            tag_scores = []

            # Use decision_function if available (LinearSVC), otherwise predict_proba
            if hasattr(classifier.estimators_[0], "decision_function"):
                decision_scores = classifier.decision_function(X_tfidf)[0]
                for i, score in enumerate(decision_scores):
                    if i < len(self.tag_names):
                        # Sigmoid scaling for confidence
                        confidence = 1 / (1 + np.exp(-score))
                        if confidence >= confidence_threshold:
                            tag_scores.append((self.tag_names[i], float(confidence)))
            elif hasattr(classifier.estimators_[0], "predict_proba"):
                # This path might need adjustment depending on MultiOutputClassifier behavior
                # Assuming predict_proba gives [[prob_class_0, prob_class_1], ...] for each tag
                probabilities = classifier.predict_proba(X_tfidf)  # List of arrays
                for i, prob_array in enumerate(probabilities):
                    if i < len(self.tag_names) and prob_array.shape[1] > 1:
                        confidence = prob_array[0][
                            1
                        ]  # Probability of positive class (tag present)
                        if confidence >= confidence_threshold:
                            tag_scores.append((self.tag_names[i], float(confidence)))
            else:
                logger.warning(
                    "Classifier estimators lack decision_function and predict_proba."
                )
                # Fallback: Use predict if nothing else works (binary output)
                predictions = self.pipeline.predict(X)[0]
                tag_scores = [
                    (self.tag_names[i], 1.0)
                    for i, pred in enumerate(predictions)
                    if pred == 1 and i < len(self.tag_names)
                ]

            tag_scores.sort(key=lambda x: x[1], reverse=True)
            return tag_scores

        except ValueError as e:
            # Catch errors related to data format or incompatible shapes
            logger.error(f"Value error classifying file {file_metadata.path}: {e}")
            return []
        except AttributeError as e:
            # Catch errors related to missing methods or attributes in the model
            logger.error(
                f"Model attribute error classifying file {file_metadata.path}: {e}"
            )
            return []
        except np.linalg.LinAlgError as e:
            # Catch numerical/linear algebra errors in numpy
            logger.error(f"Numerical error classifying file {file_metadata.path}: {e}")
            return []
        except TypeError as e:
            # Catch errors related to type mismatches
            logger.error(f"Type error classifying file {file_metadata.path}: {e}")
            return []
        except Exception as e:
            # Catch all other exceptions as a fallback
            logger.error(
                f"Unexpected error classifying file {file_metadata.path}: {e}",
                exc_info=True,
            )
            return []

    async def train(
        self,
        training_data: list[tuple[FileMetadata, list[str]]],
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> dict[str, Any]:
        """Train the classifier with labeled examples."""
        if not training_data:
            raise ValueError("Training data cannot be empty")
        if not self.pipeline or not self.mlb:
            self._initialize_default_model()
        assert (
            self.pipeline is not None and self.mlb is not None
        ), "Model components not initialized"

        try:
            X = []
            y = []
            for metadata, tags in training_data:
                features = self._extract_features(metadata)
                if features:
                    X.append(features)
                    y.append(tags)
            if not X or not y:
                raise ValueError("No valid features/tags extracted")

            y_bin = self.mlb.fit_transform(y)
            self.tag_names = list(self.mlb.classes_)  # Update tag names from fitted mlb

            X_train, X_test, y_train, y_test = train_test_split(
                X, y_bin, test_size=test_size, random_state=random_state
            )

            self.pipeline.fit(X_train, y_train)
            self.feature_names = self.pipeline.named_steps[
                "vectorizer"
            ].get_feature_names_out()
            accuracy = self.pipeline.score(X_test, y_test)

            self.training_metadata = {
                "num_samples": len(X),
                "num_tags": len(self.tag_names),
                "tag_names": self.tag_names,
                "accuracy": accuracy,
                "training_date": datetime.now().isoformat(),
                "test_size": test_size,
            }
            await self.save_model()
            logger.info(f"Trained tag classifier. Accuracy: {accuracy:.4f}")
            return self.training_metadata
        except ValueError as e:
            logger.error(f"Value error training tag classifier: {e}")
            raise ValueError(f"Error training classifier: {e!s}")
        except TypeError as e:
            logger.error(f"Type error training tag classifier: {e}")
            raise TypeError(f"Incompatible data type: {e!s}")
        except np.linalg.LinAlgError as e:
            logger.error(f"Numerical error training tag classifier: {e}")
            raise ValueError(f"Numerical error during training: {e!s}")
        except MemoryError as e:
            logger.error(f"Memory error training tag classifier: {e}")
            raise MemoryError(f"Insufficient memory for training: {e!s}")
        except Exception as e:
            logger.error(
                f"Unexpected error training tag classifier: {e}", exc_info=True
            )
            raise RuntimeError(f"Training failed: {e!s}") from e

    async def get_model_info(self) -> dict[str, Any]:
        """Get information about the current model."""
        if not self._model_loaded:
            await self.load_model()
        return {
            **self.training_metadata,
            "model_path": str(self.model_path),
            "is_loaded": self._model_loaded
            and self.pipeline is not None
            and self.mlb is not None,
            "num_features": len(self.feature_names)
            if self.feature_names is not None
            else 0,
            "num_tags": len(self.tag_names),
            "tag_names": self.tag_names,
        }

    # Keep get_tag_features and get_similar_tags as they rely on the loaded model state
    # ... (implementation for get_tag_features and get_similar_tags remains similar)
    async def get_tag_features(
        self, tag_name: str, top_n: int = 10
    ) -> list[tuple[str, float]]:
        """Get the most important features for a tag."""
        if not self._model_loaded:
            await self.load_model()
        if (
            not self.pipeline
            or not self.mlb
            or self.feature_names is None
            or not self.tag_names
        ):
            logger.warning("Model/features not available for get_tag_features.")
            return []

        try:
            if tag_name not in self.tag_names:
                return []
            tag_idx = self.tag_names.index(tag_name)
            classifier = self.pipeline.named_steps["classifier"]
            if tag_idx >= len(classifier.estimators_):
                return []

            estimator = classifier.estimators_[tag_idx]
            # Check if estimator has coefficients (like LinearSVC)
            if not hasattr(estimator, "coef_"):
                logger.warning(
                    f"Estimator for tag '{tag_name}' does not have coefficients."
                )
                return []

            coefficients = estimator.coef_[0]
            feature_importance = list(
                zip(self.feature_names, coefficients, strict=False)
            )
            feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)
            return feature_importance[:top_n]
        except ValueError as e:
            logger.error(f"Value error getting features for tag '{tag_name}': {e}")
            return []
        except IndexError as e:
            logger.error(f"Index error getting features for tag '{tag_name}': {e}")
            return []
        except AttributeError as e:
            logger.error(f"Attribute error getting features for tag '{tag_name}': {e}")
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error getting features for tag '{tag_name}': {e}",
                exc_info=True,
            )
            return []

    async def get_similar_tags(
        self, tag_name: str, top_n: int = 5
    ) -> list[tuple[str, float]]:
        """Find tags that are similar based on model coefficients."""
        if not self._model_loaded:
            await self.load_model()
        if not self.pipeline or not self.mlb or not self.tag_names:
            logger.warning("Model/tags not available for get_similar_tags.")
            return []

        try:
            if tag_name not in self.tag_names:
                return []
            tag_idx = self.tag_names.index(tag_name)
            classifier = self.pipeline.named_steps["classifier"]
            if tag_idx >= len(classifier.estimators_) or not hasattr(
                classifier.estimators_[tag_idx], "coef_"
            ):
                return []

            reference_coefficients = classifier.estimators_[tag_idx].coef_[0]
            similarities = []

            for i, estimator in enumerate(classifier.estimators_):
                if (
                    i != tag_idx
                    and i < len(self.tag_names)
                    and hasattr(estimator, "coef_")
                ):
                    coefficients = estimator.coef_[0]
                    dot_product = np.dot(reference_coefficients, coefficients)
                    norm_product = np.linalg.norm(
                        reference_coefficients
                    ) * np.linalg.norm(coefficients)
                    similarity = (
                        dot_product / norm_product if norm_product != 0 else 0.0
                    )
                    similarities.append((self.tag_names[i], float(similarity)))

            # Sort by similarity score and return top N
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_n]
        except ValueError as e:
            logger.error(f"Value error finding similar tags for '{tag_name}': {e}")
            return []
        except IndexError as e:
            logger.error(f"Index error finding similar tags for '{tag_name}': {e}")
            return []
        except AttributeError as e:
            logger.error(f"Attribute error finding similar tags for '{tag_name}': {e}")
            return []
        except np.linalg.LinAlgError as e:
            logger.error(
                f"Linear algebra error finding similar tags for '{tag_name}': {e}"
            )
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error finding similar tags for '{tag_name}': {e}",
                exc_info=True,
            )
            return []

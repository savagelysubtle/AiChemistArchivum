"""Module for registering metadata extractors."""

# Placeholder for EXTRACTOR_REGISTRY
# This should be populated with actual extractor registrations.
# Example: EXTRACTOR_REGISTRY = {'mime/type': [(ExtractorClass, priority, subtype_filter), ...]}
EXTRACTOR_REGISTRY: dict[str, list[tuple[type, float, str | None]]] = {}


def register_extractor(
    mime_type: str,
    extractor_class: type,
    priority: float = 1.0,
    subtype_filter: str | None = None,
) -> None:
    """Registers an extractor for a given MIME type."""
    if mime_type not in EXTRACTOR_REGISTRY:
        EXTRACTOR_REGISTRY[mime_type] = []
    EXTRACTOR_REGISTRY[mime_type].append((extractor_class, priority, subtype_filter))
    # Ensure list is sorted by priority (higher priority first)
    EXTRACTOR_REGISTRY[mime_type].sort(key=lambda x: x[1], reverse=True)


# Example of how extractors might be registered (commented out):
# from .code import CodeExtractor
# from .documents import DocumentExtractor
#
# register_extractor("text/*", CodeExtractor, priority=0.8)
# register_extractor("application/pdf", DocumentExtractor, priority=1.0)

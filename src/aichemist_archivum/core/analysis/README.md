# Infrastructure Analysis Module (`infrastructure/analysis`)

This module contains the infrastructure-level implementations for code and relationship analysis within The AIChemist Codex.

## Core Components

1.  **`technical_analyzer.py`**:
    *   Provides low-level, purely technical functions for code analysis (complexity calculation, structure extraction, comment extraction, similarity comparison, file processing).
    *   Operates on basic types (strings, paths, ASTs) and avoids direct dependencies on `domain` entities.
    *   **Intended Usage**: This module (or a dedicated class within it, e.g., `TechnicalCodeAnalyzer`) is designed to **implement** an interface defined in the `domain` layer.

2.  **`code.py`**:
    *   Provides higher-level functions (`summarize_code`, `summarize_project`) for analyzing entire directories of Python code, leveraging `technical_analyzer.py`.
    *   Generates summaries (e.g., JSON, Markdown).
    *   Useful for batch processing or CLI tools.

3.  **`relationship_graph.py`**:
    *   Implements graph-based analysis of relationships between code artifacts using NetworkX.
    *   Depends on a `RelationshipRepositoryInterface` (defined in `domain`) to fetch relationship data.
    *   Provides methods for finding paths, calculating centrality, and exporting graph data (JSON, GraphViz).

4.  **`code_analysis_service.py` (Moved)**:
    *   This file originally contained a mix of technical analysis and application logic (interacting with domain entities and repositories).
    *   It has been refactored:
        *   Technical functions moved to `technical_analyzer.py`.
        *   Async/sync issues were addressed.
        *   The file is marked (`@ToMove`) and **should be moved** to the `application` layer (e.g., `application/services/code_analysis_service.py`).
    *   Once moved, it needs further refactoring in the application layer to become a true Application Service.

## Integration with Domain/Application Layers (Clean Architecture)

To correctly integrate this infrastructure module according to Clean Architecture principles:

1.  **Define the Interface**: An interface, tentatively named `CodeAnalysisServiceInterface`, **must be defined** in the domain layer, specifically at:
    ```
    src/the_aichemist_codex/domain/services/interfaces/code_analysis_service_interface.py
    ```
    This interface dictates the *contract* for technical code analysis required by higher layers. It should define methods based on the functionalities in `technical_analyzer.py` but use abstract signatures (e.g., `calculate_complexity_from_content(content: str, file_type: str) -> float`).

2.  **Implement the Interface**: The `technical_analyzer.py` module needs a concrete class (e.g., `TechnicalCodeAnalyzer`) that explicitly inherits from and implements the `CodeAnalysisServiceInterface`.
    ```python
    # Example in infrastructure/analysis/technical_analyzer.py
    from the_aichemist_codex.domain.services.interfaces.code_analysis_service_interface import CodeAnalysisServiceInterface
    from . import technical_analyzer # Import the functions if they remain standalone

    class TechnicalCodeAnalyzer(CodeAnalysisServiceInterface):
        async def calculate_complexity_from_content(self, content: str, file_type: str) -> float:
            # Implementation using functions from technical_analyzer
            if file_type == '.py':
                 try:
                     tree = ast.parse(content)
                     return technical_analyzer.calculate_python_complexity(tree)
                 except SyntaxError:
                     return technical_analyzer.calculate_basic_complexity(content)
            else:
                 return technical_analyzer.calculate_basic_complexity(content)
        # ... implement other interface methods
    ```

3.  **Inject the Implementation**: The Application Service (the refactored `code_analysis_service.py` after being moved) should **depend on the `CodeAnalysisServiceInterface` (the abstraction)**, not the concrete `TechnicalCodeAnalyzer` implementation. The concrete implementation should be injected into the Application Service via its constructor (Dependency Injection).

    ```python
    # Example in application/services/code_analysis_service.py (after moving and refactoring)
    from the_aichemist_codex.domain.repositories.code_artifact_repository import CodeArtifactRepository
    from the_aichemist_codex.domain.services.interfaces.code_analysis_service_interface import CodeAnalysisServiceInterface # Depend on interface
    from the_aichemist_codex.domain.entities.code_artifact import CodeArtifact
    from uuid import UUID

    class ApplicationCodeAnalysisService:
        def __init__(self,
                     repository: CodeArtifactRepository,
                     technical_analyzer: CodeAnalysisServiceInterface # Inject interface
                    ):
            self.repository = repository
            self.technical_analyzer = technical_analyzer # Use the injected implementation

        async def analyze_artifact_complexity(self, artifact_id: UUID) -> float:
            artifact = await self.repository.get_by_id(artifact_id)
            if not artifact or not artifact.content:
                return 0.0
            # Use the injected technical analyzer via the interface
            complexity = await self.technical_analyzer.calculate_complexity_from_content(
                artifact.content, artifact.path.suffix
            )
            return complexity
        # ... other application logic using the repository and technical_analyzer interface
    ```

By following these steps, the dependency rule is maintained (Application depends on Domain interfaces, Infrastructure implements Domain interfaces), promoting modularity and testability.

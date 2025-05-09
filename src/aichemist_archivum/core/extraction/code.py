"""Code metadata extractor for extracting information from code files.

This module provides functionality for analyzing code content to extract
language details, complexity metrics, imports, dependencies, and other code-specific metadata.
"""

# mypy: disable-error-code="return-value"

import logging
import re
import time
from pathlib import Path
from typing import TypedDict

from the_aichemist_codex.infrastructure.fs.file_metadata import FileMetadata

from .base_extractor import BaseMetadataExtractor, MetadataExtractorRegistry

logger = logging.getLogger(__name__)


# Define TypedDict for the return type of extract
class CodeComplexityDict(TypedDict):
    line_count: int
    comment_percentage: int
    cyclomatic_complexity: int


class CodeMetadataDict(TypedDict):
    code_language: str
    imports: list[str]
    functions: list[str]
    classes: list[str]
    complexity: CodeComplexityDict
    tags: list[str]
    extraction_complete: bool
    extraction_confidence: float
    extraction_time: float
    error: str | None  # Added error field


@MetadataExtractorRegistry.register
class CodeMetadataExtractor(BaseMetadataExtractor):
    """Metadata extractor for code files.

    Analyzes code content to extract programming language, imports,
    function/class definitions, complexity metrics, and other code-specific metadata.
    """

    def __init__(self):
        """Initialize the code metadata extractor."""
        super().__init__()

        # Language detection patterns
        self.language_patterns = {
            "python": [
                r"^import\s+\w+",
                r"^from\s+[\w.]+\s+import",
                r"def\s+\w+\s*\(",
                r"class\s+\w+[:(]",
            ],
            "javascript": [
                r"const\s+\w+\s*=",
                r"let\s+\w+\s*=",
                r"function\s+\w+\s*\(",
                r"import\s+.*from",
            ],
            "typescript": [
                r"interface\s+\w+",
                r"type\s+\w+\s*=",
                r"class\s+\w+",
                r":\s*\w+(\[\])?",
            ],
            "java": [
                r"public\s+class",
                r"private\s+\w+",
                r"protected\s+\w+",
                r"package\s+[\w.]+;",
            ],
            "c": [
                r"#include",
                r"void\s+\w+\s*\(",
                r"int\s+\w+\s*\(",
                r"struct\s+\w+\s*\{",
            ],
            "cpp": [
                r"#include\s*<\w+>",
                r"namespace",
                r"template",
                r"class\s+\w+\s*\{",
            ],
            "csharp": [
                r"using\s+[\w.]+;",
                r"namespace\s+[\w.]+",
                r"public\s+class",
                r"private\s+\w+",
            ],
            "go": [
                r"package\s+\w+",
                r"func\s+\(",
                r"import\s+\(",
                r"type\s+\w+\s+struct",
            ],
            "ruby": [r"require", r"def\s+\w+", r"class\s+\w+", r"module\s+\w+"],
            "php": [
                r"<\?php",
                r"function\s+\w+\s*\(",
                r"class\s+\w+",
                r"namespace\s+[\w\\]+;",
            ],
            "swift": [
                r"import\s+\w+",
                r"func\s+\w+\s*\(",
                r"class\s+\w+",
                r"var\s+\w+\s*:",
            ],
            "rust": [r"fn\s+\w+", r"struct\s+\w+", r"impl", r"use\s+[\w:]+"],
            "kotlin": [r"fun\s+\w+", r"class\s+\w+", r"val\s+\w+", r"var\s+\w+"],
            "html": [r"<!DOCTYPE", r"<html", r"<head", r"<body"],
            "css": [r"[\.\#][\w-]+\s*\{", r"@media", r"@import", r"@keyframes"],
            "sql": [
                r"SELECT",
                r"INSERT\s+INTO",
                r"CREATE\s+TABLE",
                r"UPDATE\s+\w+\s+SET",
            ],
            "shell": [
                r"#!/bin/(ba)?sh",
                r"if\s+\[\s+",
                r"for\s+\w+\s+in",
                r"while\s+\[\s+",
            ],
        }

        # Extensions to language mapping
        self.extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".rs": "rust",
            ".kt": "kotlin",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".sql": "sql",
            ".sh": "shell",
            ".bash": "shell",
        }

        # Import patterns for different languages
        self.import_patterns = {
            "python": r"^\s*(import|from)\s+([\w.]+)",
            "javascript": r"(import|require)\s*\(?[\'\"]([^\'\"]+)",
            "typescript": r"(import|require)\s*\(?[\'\"]([^\'\"]+)",
            "java": r"import\s+([\w.]+)",
            "go": r"import\s+(?:\(\s*)?([\"\w\./]+)",
            "rust": r"use\s+([\w:]+)",
            "kotlin": r"import\s+([\w.]+)",
        }

        # Function/Class definition patterns
        self.function_patterns = {
            "python": r"def\s+(\w+)",
            "javascript": r"function\s+(\w+)|(\w+)\s*=\s*function|(\w+)\s*:\s*function",
            "typescript": r"function\s+(\w+)|(\w+)\s*=\s*function|(\w+)\s*:\s*function",
            "java": r"(public|private|protected)?\s+(static)?\s+\w+\s+(\w+)\s*\(",
            "go": r"func\s+(\w+)",
            "rust": r"fn\s+(\w+)",
            "kotlin": r"fun\s+(\w+)",
        }

        self.class_patterns = {
            "python": r"class\s+(\w+)",
            "javascript": r"class\s+(\w+)",
            "typescript": r"class\s+(\w+)|interface\s+(\w+)",
            "java": r"class\s+(\w+)",
            "go": r"type\s+(\w+)\s+struct",
            "rust": r"struct\s+(\w+)|impl(?:\s+\w+)?\s+for\s+(\w+)",
            "kotlin": r"class\s+(\w+)",
        }

    @property
    def supported_mime_types(self) -> list[str]:
        """List of MIME types supported by this extractor."""
        return [
            "text/x-python",
            "application/javascript",
            "application/x-javascript",
            "text/javascript",
            "application/typescript",
            "text/x-java",
            "text/x-c",
            "text/x-c++",
            "text/x-csharp",
            "text/x-go",
            "text/x-ruby",
            "application/x-php",
            "text/x-swift",
            "text/x-rust",
            "text/x-kotlin",
            "text/html",
            "text/css",
            "text/x-sql",
            "application/x-sh",
        ]

    async def extract(
        self,
        file_path: str | Path,
        content: str | None = None,
        mime_type: str | None = None,
        metadata: FileMetadata | None = None,
    ) -> CodeMetadataDict:
        """Extract metadata from a code file.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded file content
            mime_type: Optional MIME type of the file
            metadata: Optional existing metadata to enhance

        Returns:
            A CodeMetadataDict containing extracted metadata.
        """
        start_time = time.time()

        # Convert file_path to Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # Get the content if not provided
        if content is None:
            content = await self._get_content(file_path)
            if not content:
                return {
                    "error": "Failed to read file content",
                    "extraction_complete": False,
                    "extraction_confidence": 0.0,
                    "extraction_time": time.time() - start_time,
                    "code_language": "",
                    "imports": [],
                    "functions": [],
                    "classes": [],
                    "complexity": {
                        "line_count": 0,
                        "comment_percentage": 0,
                        "cyclomatic_complexity": 0,
                    },
                    "tags": [],
                }

        # Detect language
        language = self._detect_language(file_path, content)

        # Extract code metadata
        extracted_data: CodeMetadataDict = {
            "code_language": language,
            "imports": [],
            "functions": [],
            "classes": [],
            "complexity": {
                "line_count": 0,
                "comment_percentage": 0,
                "cyclomatic_complexity": 0,
            },
            "tags": [],
            "extraction_complete": False,
            "extraction_confidence": 0.0,
            "extraction_time": 0.0,
            "error": None,
        }

        if language:
            # Extract imports/dependencies
            imports = self._extract_imports(content, language)
            extracted_data["imports"] = imports

            # Extract functions
            functions = self._extract_functions(content, language)
            extracted_data["functions"] = functions

            # Extract classes
            classes = self._extract_classes(content, language)
            extracted_data["classes"] = classes

            # Calculate complexity
            complexity = self._calculate_complexity(content, language)
            extracted_data["complexity"] = complexity

            # Generate tags
            tags = self._generate_tags(
                language, imports, functions, classes, complexity
            )
            extracted_data["tags"] = tags

        # Mark extraction as complete
        extracted_data["extraction_complete"] = True
        extracted_data["extraction_confidence"] = 0.7 if language else 0.3
        extracted_data["extraction_time"] = time.time() - start_time
        extracted_data["error"] = None

        return extracted_data

    def _detect_language(self, file_path: Path, content: str) -> str:
        """Detect the programming language of the file.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            The detected programming language or empty string if unknown
        """
        # First, try to detect by file extension
        extension = file_path.suffix.lower()
        if extension in self.extension_map:
            return self.extension_map[extension]

        # Fallback to content analysis
        language_scores = {}

        # Skip empty content
        if not content.strip():
            return ""

        # Get the first 100 lines of code (or fewer if the file is smaller)
        lines = content.split("\n")[:100]
        code_sample = "\n".join(lines)

        # Check each language's patterns against the code sample
        for language, patterns in self.language_patterns.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, code_sample, re.MULTILINE | re.IGNORECASE)
                score += len(matches)

            if score > 0:
                language_scores[language] = score

        # Return the language with the highest score, or empty string if none match
        if language_scores:
            return max(language_scores.items(), key=lambda x: x[1])[0]

        return ""

    def _extract_imports(self, content: str, language: str) -> list[str]:
        """Extract imports or dependencies from the code.

        Args:
            content: File content
            language: Detected programming language

        Returns:
            A list of imported modules or packages
        """
        imports = []

        if language in self.import_patterns:
            pattern = self.import_patterns[language]
            matches = re.findall(pattern, content, re.MULTILINE)

            # Process matches differently depending on the language
            if language in ["python", "java", "go", "rust", "kotlin"]:
                imports = [
                    match[1] if isinstance(match, tuple) else match for match in matches
                ]
            elif language in ["javascript", "typescript"]:
                imports = [match[1] for match in matches if match[1]]

        # Remove duplicates and return
        return list(set(imports))

    def _extract_functions(self, content: str, language: str) -> list[str]:
        """Extract function definitions from the code.

        Args:
            content: File content
            language: Detected programming language

        Returns:
            A list of function names
        """
        functions = []

        if language in self.function_patterns:
            pattern = self.function_patterns[language]
            matches = re.findall(pattern, content, re.MULTILINE)

            # Process matches differently depending on the language
            if language in ["python", "go", "rust", "kotlin"]:
                functions = [match for match in matches if match]
            elif language in ["javascript", "typescript"]:
                # Extract named functions from multiple capture groups
                for match in matches:
                    if isinstance(match, tuple):
                        for group in match:
                            if group:
                                functions.append(group)
                    elif match:
                        functions.append(match)
            elif language == "java":
                # Extract the last capture group (method name)
                for match in matches:
                    if isinstance(match, tuple) and match[-1]:
                        functions.append(match[-1])

        # Remove duplicates and return
        return list(set(functions))

    def _extract_classes(self, content: str, language: str) -> list[str]:
        """Extract class definitions from the code.

        Args:
            content: File content
            language: Detected programming language

        Returns:
            A list of class names
        """
        classes = []

        if language in self.class_patterns:
            pattern = self.class_patterns[language]
            matches = re.findall(pattern, content, re.MULTILINE)

            # Process matches
            for match in matches:
                if isinstance(match, tuple):
                    for group in match:
                        if group:
                            classes.append(group)
                elif match:
                    classes.append(match)

        # Remove duplicates and return
        return list(set(classes))

    def _calculate_complexity(self, content: str, language: str) -> dict[str, int]:
        """Calculate code complexity metrics.

        This is a simplified implementation that calculates:
        - Line count
        - Comment percentage
        - Cyclomatic complexity estimation

        Args:
            content: File content
            language: Detected programming language

        Returns:
            A dictionary of complexity metrics
        """
        complexity = {
            "line_count": 0,
            "comment_percentage": 0,
            "cyclomatic_complexity": 0,
        }

        # Count lines of code (excluding empty lines)
        lines = content.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]
        complexity["line_count"] = len(non_empty_lines)

        # Count comment lines (language-specific)
        comment_count = 0
        if language in ["python", "ruby", "shell"]:
            comment_count = len(
                [line for line in lines if line.strip().startswith("#")]
            )
        elif language in [
            "javascript",
            "typescript",
            "java",
            "c",
            "cpp",
            "csharp",
            "go",
            "swift",
            "kotlin",
        ]:
            # Single-line comments
            comment_count += len(
                [line for line in lines if line.strip().startswith("//")]
            )

            # Multi-line comments - simplified approach
            comment_blocks = re.findall(r"/\*.*?\*/", content, re.DOTALL)
            for block in comment_blocks:
                comment_count += block.count("\n") + 1

        # Calculate comment percentage
        if complexity["line_count"] > 0:
            complexity["comment_percentage"] = int(
                (comment_count / complexity["line_count"]) * 100
            )

        # Estimate cyclomatic complexity by counting decision points
        decision_points = 0

        # Language-specific patterns for branching structures
        if language in ["python"]:
            decision_points += len(
                re.findall(r"\bif\b|\bfor\b|\bwhile\b|\belif\b|\bexcept\b", content)
            )
        elif language in ["javascript", "typescript", "java", "c", "cpp", "csharp"]:
            decision_points += len(
                re.findall(r"\bif\b|\bfor\b|\bwhile\b|\bcase\b|\bcatch\b|\?", content)
            )
        elif language in ["go"]:
            decision_points += len(
                re.findall(r"\bif\b|\bfor\b|\bswitch\b|\bcase\b|\bselect\b", content)
            )
        elif language in ["ruby"]:
            decision_points += len(
                re.findall(
                    r"\bif\b|\bunless\b|\bwhile\b|\buntil\b|\bcase\b|\brescue\b",
                    content,
                )
            )

        complexity["cyclomatic_complexity"] = max(1, decision_points)

        return complexity

    def _generate_tags(
        self,
        language: str,
        imports: list[str],
        functions: list[str],
        classes: list[str],
        complexity: dict[str, int],
    ) -> list[str]:
        """Generate tags based on code analysis.

        Args:
            language: Detected programming language
            imports: List of imported modules
            functions: List of function names
            classes: List of class names
            complexity: Dictionary of complexity metrics

        Returns:
            A list of tags
        """
        tags = set()

        # Add language tag
        if language:
            tags.add(f"lang:{language}")

        # Add complexity tags
        line_count = complexity.get("line_count", 0)
        if line_count < 50:
            tags.add("size:small")
        elif line_count < 300:
            tags.add("size:medium")
        else:
            tags.add("size:large")

        # Add structural tags
        if classes:
            tags.add("has:classes")

        if len(functions) > 5:
            tags.add("has:many-functions")

        if complexity.get("comment_percentage", 0) > 15:
            tags.add("well-commented")

        if complexity.get("cyclomatic_complexity", 0) > 15:
            tags.add("complex")

        # Add framework/library-specific tags
        if language == "python":
            if any(imp for imp in imports if imp.startswith("django")):
                tags.add("framework:django")
            if any(imp for imp in imports if imp.startswith("flask")):
                tags.add("framework:flask")
            if any(
                imp
                for imp in imports
                if imp in ["numpy", "pandas", "sklearn", "tensorflow", "torch"]
            ):
                tags.add("data-science")

        elif language in ["javascript", "typescript"]:
            if any(imp for imp in imports if "react" in imp.lower()):
                tags.add("framework:react")
            if any(imp for imp in imports if "angular" in imp.lower()):
                tags.add("framework:angular")
            if any(imp for imp in imports if "vue" in imp.lower()):
                tags.add("framework:vue")

        return list(tags)

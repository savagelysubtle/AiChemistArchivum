"""
Relationship graph functionality using NetworkX.

Moved from domain/relations/graph.py as graph analysis is often considered
an application or infrastructure concern.
"""

import datetime
import logging
import time
from pathlib import Path

import networkx as nx

# Import domain interfaces and models
from the_aichemist_codex.domain.relationships.relationship_type import RelationshipType
from the_aichemist_codex.domain.repositories.interfaces.relationship_repository import (
    RelationshipRepositoryInterface,
)

logger = logging.getLogger(__name__)


class RelationshipGraph:
    """
    Represents file relationships as a graph structure using NetworkX.

    Provides graph-based operations using data fetched via a RelationshipRepository.
    """

    def __init__(
        self,
        repository: RelationshipRepositoryInterface,
        default_export_dir: Path | None = None,
        default_max_nodes: int | None = 100,
    ) -> None:
        """
        Initialize the relationship graph.

        Args:
            repository: An implementation of RelationshipRepositoryInterface.
            default_export_dir: Optional default directory for exporting graphs.
            default_max_nodes: Optional default maximum nodes for exports.
        """
        self.repository = repository
        self._graph: nx.DiGraph | None = None
        self._last_update: float | None = None
        self.default_export_dir = default_export_dir
        self.default_max_nodes = default_max_nodes

    async def build_graph(
        self,
        rel_types: list[RelationshipType] | None = None,
        min_strength: float = 0.0,
    ) -> nx.DiGraph:
        """
        Build a directed graph from the relationships in the repository.

        Args:
            rel_types: Optional filter for relationship types.
            min_strength: Minimum relationship strength (0.0 to 1.0).

        Returns:
            NetworkX directed graph.
        """
        graph = nx.DiGraph()
        relationships = await self.repository.get_all()

        # Filter relationships
        filtered_relationships = relationships
        if rel_types:
            filtered_relationships = [
                r for r in filtered_relationships if r.type in rel_types
            ]
        if min_strength > 0:
            filtered_relationships = [
                r for r in filtered_relationships if r.strength >= min_strength
            ]

        # Add nodes and edges
        for rel in filtered_relationships:
            source_str = str(rel.source_path)
            target_str = str(rel.target_path)

            if not graph.has_node(source_str):
                graph.add_node(source_str, path=rel.source_path)
            if not graph.has_node(target_str):
                graph.add_node(target_str, path=rel.target_path)

            graph.add_edge(
                source_str,
                target_str,
                id=str(rel.id),
                type=rel.type,
                strength=rel.strength,
                metadata=rel.metadata,
                bidirectional=rel.bidirectional,
            )
            # If bidirectional, add the reverse edge for easier graph traversal?
            # Or rely on graph algorithms that handle undirected nature if needed.
            # For now, keeping it directed based on the Relationship object.

        self._graph = graph
        self._last_update = time.time()  # Optional: for caching
        return graph

    async def get_graph(
        self,
        rel_types: list[RelationshipType] | None = None,
        min_strength: float = 0.0,
        force_rebuild: bool = False,
    ) -> nx.DiGraph:
        """
        Get the relationship graph, building it if necessary or forced.

        Args:
            rel_types: Optional filter for relationship types.
            min_strength: Minimum relationship strength.
            force_rebuild: Whether to force rebuilding the graph.

        Returns:
            NetworkX directed graph.
        """
        # Add cache check logic if self._last_update is used
        if self._graph is None or force_rebuild:
            await self.build_graph(rel_types, min_strength)

        if self._graph is None:  # Ensure graph is not None after build attempt
            raise RuntimeError("Failed to build relationship graph.")

        return self._graph

    async def find_paths(
        self,
        source_path: Path,
        target_path: Path,
        max_length: int = 5,
        rel_types: list[RelationshipType] | None = None,
        min_strength: float = 0.0,
    ) -> list[list[tuple[Path, RelationshipType]]]:
        """Find all paths between two files up to a maximum length."""
        graph = await self.get_graph(rel_types, min_strength)
        source_str = str(source_path)
        target_str = str(target_path)

        if not graph.has_node(source_str) or not graph.has_node(target_str):
            return []

        try:
            paths_nodes = list(
                nx.all_simple_paths(graph, source_str, target_str, cutoff=max_length)
            )
        except nx.NetworkXNoPath:
            return []

        result_paths = []
        for node_path in paths_nodes:
            path_with_types = []
            for i in range(len(node_path) - 1):
                u, v = node_path[i], node_path[i + 1]
                edge_data = graph.get_edge_data(u, v)
                if edge_data:
                    path_with_types.append((Path(v), edge_data["type"]))
            result_paths.append(path_with_types)

        return result_paths

    async def calculate_centrality(
        self,
        rel_types: list[RelationshipType] | None = None,
        min_strength: float = 0.0,
        top_n: int = 10,
    ) -> list[tuple[Path, float]]:
        """Calculate centrality metrics."""
        graph = await self.get_graph(rel_types, min_strength)
        if not graph:
            return []

        try:
            # Use degree centrality as an example, PageRank might be better
            centrality = nx.degree_centrality(graph)
        except Exception as e:
            logger.error(f"Error calculating centrality: {e}")
            return []

        result = [(Path(node), score) for node, score in centrality.items()]
        result.sort(key=lambda x: x[1], reverse=True)
        return result[:top_n]

    async def export_graphviz(
        self,
        output_path: Path | None = None,
        rel_types: list[RelationshipType] | None = None,
        min_strength: float = 0.0,
        max_nodes: int | None = None,
    ) -> None:
        """Export the relationship graph to a GraphViz DOT file.

        Args:
            output_path: Path to save the DOT file. If None, uses default dir or current dir.
            rel_types: Optional filter for relationship types.
            min_strength: Minimum relationship strength.
            max_nodes: Maximum nodes to include. If None, uses instance default or 100.
        """
        graph = await self.get_graph(rel_types, min_strength)

        # Determine effective max_nodes
        effective_max_nodes = (
            max_nodes if max_nodes is not None else self.default_max_nodes
        )
        if effective_max_nodes is None:  # Fallback if instance default is also None
            effective_max_nodes = 100

        # Determine effective output path
        effective_output_path = output_path
        if effective_output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"relationship_graph_{timestamp}.dot"
            if self.default_export_dir:
                # Ensure the default export directory exists
                self.default_export_dir.mkdir(parents=True, exist_ok=True)
                effective_output_path = self.default_export_dir / filename
            else:
                effective_output_path = Path.cwd() / filename

        logger.info(
            f"Exporting graph (max_nodes={effective_max_nodes}) to {effective_output_path}"
        )

        if len(graph.nodes) > effective_max_nodes:
            # Limit nodes based on centrality or other metric if needed
            centrality = nx.degree_centrality(graph)  # Example
            important_nodes = sorted(centrality, key=centrality.get, reverse=True)[
                :effective_max_nodes
            ]
            graph = graph.subgraph(important_nodes)

        # Ensure pydot is installed or handle the ImportError
        try:
            import pydot

            nx.drawing.nx_pydot.write_dot(graph, str(effective_output_path))
            logger.info(f"Exported relationship graph to {effective_output_path}")
        except ImportError:
            logger.error("pydot library is required to export to GraphViz DOT format.")
        except Exception as e:
            logger.error(f"Error exporting graph to {effective_output_path}: {e!s}")
            raise

    async def export_json(
        self,
        output_path: Path | None = None,
        rel_types: list[RelationshipType] | None = None,
        min_strength: float = 0.0,
        max_nodes: int | None = None,
    ) -> None:
        """Export the relationship graph to a JSON file for visualization.

        Args:
            output_path: Path to save the JSON file. If None, uses default dir or current dir.
            rel_types: Optional filter for relationship types.
            min_strength: Minimum relationship strength.
            max_nodes: Maximum nodes to include. If None, uses instance default or 100.
        """
        from the_aichemist_codex.infrastructure.utils.io.async_io import (
            AsyncFileIO,
        )  # Use existing utility

        graph = await self.get_graph(rel_types, min_strength)

        # Determine effective max_nodes
        effective_max_nodes = (
            max_nodes if max_nodes is not None else self.default_max_nodes
        )
        if effective_max_nodes is None:  # Fallback if instance default is also None
            effective_max_nodes = 100

        # Determine effective output path
        effective_output_path = output_path
        if effective_output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"relationship_graph_{timestamp}.json"
            if self.default_export_dir:
                # Ensure the default export directory exists
                self.default_export_dir.mkdir(parents=True, exist_ok=True)
                effective_output_path = self.default_export_dir / filename
            else:
                effective_output_path = Path.cwd() / filename

        logger.info(
            f"Exporting graph (max_nodes={effective_max_nodes}) to {effective_output_path}"
        )

        if len(graph.nodes) > effective_max_nodes:
            centrality = nx.degree_centrality(graph)
            important_nodes = sorted(centrality, key=centrality.get, reverse=True)[
                :effective_max_nodes
            ]
            graph = graph.subgraph(important_nodes)

        nodes = [
            {"id": node, "label": Path(node).name, "path": node}
            for node in graph.nodes()
        ]
        edges = [
            {
                "source": u,
                "target": v,
                "id": data.get("id"),
                "type": data.get(
                    "type", RelationshipType.CUSTOM
                ).name,  # Use name for JSON
                "strength": data.get("strength", 1.0),
                "bidirectional": data.get("bidirectional", False),
            }
            for u, v, data in graph.edges(data=True)
        ]

        result = {"nodes": nodes, "edges": edges}

        try:
            await AsyncFileIO.write_json(effective_output_path, result)
            logger.info(f"Exported relationship graph to {effective_output_path}")
        except Exception as e:
            logger.error(f"Error exporting graph to {effective_output_path}: {e!s}")
            raise

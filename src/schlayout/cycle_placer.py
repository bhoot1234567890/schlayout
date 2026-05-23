"""Cycle-aware schematic placement using Weighted Feedback Arc Set.

Detects cycles in the netlist graph, breaks them by removing low-weight
edges (power returns, GND) to convert to a tree, then places+routes cleanly.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import math

GRID = 2.54


def snap(v: float) -> float:
    return round(v / GRID) * GRID


@dataclass
class NetEdge:
    """Edge in the component-net graph: a net connecting two components."""
    net_name: str
    comp_a: str
    pin_a: str
    comp_b: str
    pin_b: str
    # Weight for cycle breaking: high = important, don't break
    weight: float = 1.0
    is_power: bool = False
    is_ground: bool = False
    is_return: bool = False  # return path (BAT- to GND, etc.)


class CycleBreaker:
    """Detect cycles and break them by removing low-weight edges."""

    # Net name patterns that indicate power/ground/return
    POWER_PATTERNS = ["VCC", "VDD", "VIN", "V+", "+5", "+3", "+12", "PWR"]
    GROUND_PATTERNS = ["GND", "VSS", "VEE", "DGND", "AGND"]
    RETURN_PATTERNS = ["RTN", "RETURN"]

    def __init__(self):
        pass

    @classmethod
    def classify_edge(cls, net_name: str) -> Tuple[float, bool, bool, bool]:
        """Classify a net edge and assign weight.
        
        Returns: (weight, is_power, is_ground, is_return)
        """
        upper = net_name.upper()
        for p in cls.POWER_PATTERNS:
            if p in upper:
                return (0.5, True, False, False)
        for g in cls.GROUND_PATTERNS:
            if g in upper:
                return (0.1, False, True, False)
        for r in cls.RETURN_PATTERNS:
            if r in upper:
                return (0.2, False, False, True)
        return (1.0, False, False, False)

    def analyze(
        self, components: List[str], nets: List[Tuple[str, List[Tuple[str, str]]]]
    ) -> Tuple[Dict[str, Set[str]], List[NetEdge], List[NetEdge]]:
        """Analyze netlist: return (adjacency, all_edges, broken_edges).
        
        Args:
            components: list of component refs
            nets: list of (net_name, [(comp_ref, pin_num), ...])
        
        Returns:
            adj: component adjacency {comp_ref: {connected_comp_refs}}
            edges: all net edges
            broken: edges that should be removed to break cycles
        """
        # Build edge list
        edges: List[NetEdge] = []
        for net_name, conns in nets:
            weight, is_pwr, is_gnd, is_ret = self.classify_edge(net_name)
            for i in range(len(conns)):
                for j in range(i + 1, len(conns)):
                    edges.append(NetEdge(
                        net_name=net_name,
                        comp_a=conns[i][0], pin_a=conns[i][1],
                        comp_b=conns[j][0], pin_b=conns[j][1],
                        weight=weight, is_power=is_pwr,
                        is_ground=is_gnd, is_return=is_ret,
                    ))

        # Build adjacency
        adj: Dict[str, Set[str]] = defaultdict(set)
        for e in edges:
            adj[e.comp_a].add(e.comp_b)
            adj[e.comp_b].add(e.comp_a)

        # Find cycle-breaking edges (lowest weight edge in each cycle)
        broken = self._find_cycle_edges(components, adj, edges)

        return adj, edges, broken

    def _find_cycle_edges(
        self,
        components: List[str],
        adj: Dict[str, Set[str]],
        edges: List[NetEdge],
    ) -> List[NetEdge]:
        """Find edges to remove to break all cycles.
        
        Strategy: DFS to find cycles, remove the lowest-weight edge in each.
        Power/ground nets are preferred targets for removal.
        """
        # Build edge lookup: (comp_a, comp_b) → NetEdge
        edge_lookup: Dict[Tuple[str, str], NetEdge] = {}
        for e in edges:
            key = tuple(sorted([e.comp_a, e.comp_b]))
            if key not in edge_lookup or e.weight < edge_lookup[key].weight:
                edge_lookup[key] = e

        broken: List[NetEdge] = []
        remaining_edges = set(edge_lookup.keys())

        # Find cycles using DFS
        def find_cycle(start: str) -> Optional[List[Tuple[str, str]]]:
            """Find one cycle in the graph. Returns list of (comp_a, comp_b) edges."""
            path: List[str] = []
            visited: Set[str] = set()
            parent: Dict[str, str] = {}

            def dfs(node: str, prev: str | None) -> bool:
                visited.add(node)
                path.append(node)
                for neighbor in adj.get(node, set()):
                    if neighbor == prev:
                        continue
                    key = tuple(sorted([node, neighbor]))
                    if key not in remaining_edges:
                        continue
                    if neighbor in visited:
                        # Found cycle! Trace back
                        cycle = [(node, neighbor)]
                        curr = node
                        while curr != neighbor:
                            for p in adj.get(curr, set()):
                                k2 = tuple(sorted([curr, p]))
                                if k2 in remaining_edges and p in visited:
                                    cycle.append((curr, p))
                                    curr = p
                                    break
                            else:
                                break
                        return True
                    parent[neighbor] = node
                    if dfs(neighbor, node):
                        return True
                path.pop()
                return False

            for comp in components:
                if comp not in adj:
                    continue
                visited.clear()
                path.clear()
                parent.clear()
                if dfs(comp, None):
                    return None  # cycle found via return
            return None

        # Repeatedly find and break cycles
        max_iterations = 20
        for _ in range(max_iterations):
            # Find any cycle
            cycle_edges = None
            # Simple: find first back-edge in DFS
            visited_all = set()
            parent = {}
            stack = []

            def dfs_cycle(node):
                visited_all.add(node)
                stack.append(node)
                for nb in adj.get(node, set()):
                    key = tuple(sorted([node, nb]))
                    if key not in remaining_edges:
                        continue
                    if nb in stack and nb != parent.get(node):
                        # Found cycle
                        # Collect edges from nb to node along the stack
                        cycle = []
                        idx = stack.index(nb)
                        cycle_nodes = stack[idx:] + [nb]
                        for k in range(len(cycle_nodes) - 1):
                            cycle.append(tuple(sorted([cycle_nodes[k], cycle_nodes[k+1]])))
                        return cycle
                    if nb not in visited_all:
                        parent[nb] = node
                        result = dfs_cycle(nb)
                        if result:
                            return result
                stack.pop()
                return None

            cycle = None
            for comp in components:
                if comp not in visited_all and comp in adj:
                    visited_all.clear()
                    stack.clear()
                    parent.clear()
                    cycle = dfs_cycle(comp)
                    if cycle:
                        break

            if cycle is None:
                break  # no more cycles

            # Find lowest-weight edge in this cycle
            best_edge = None
            best_weight = float('inf')
            for key in cycle:
                if key in edge_lookup:
                    e = edge_lookup[key]
                    if e.weight < best_weight:
                        best_weight = e.weight
                        best_edge = key

            if best_edge and best_edge in remaining_edges:
                remaining_edges.remove(best_edge)
                broken.append(edge_lookup[best_edge])

        return broken


class TreePlacer:
    """Place components using the tree resulting from cycle breaking."""

    def __init__(self, adj: Dict[str, Set[str]], broken: List[NetEdge]):
        self.adj = adj
        self.broken = broken
        self.broken_set = {tuple(sorted([e.comp_a, e.comp_b])) for e in broken}

    def place(
        self,
        positions: Dict[str, Tuple[float, float, int]],  # ref -> (x, y, rotation)
        component_sizes: Dict[str, Tuple[float, float]],  # ref -> (width, height)
        page_width: float = 297.0,
        page_height: float = 210.0,
    ) -> Dict[str, Tuple[float, float, int]]:
        """Place components using tree-based layout.
        
        Simple approach: pick a root, do BFS, place children to the right.
        """
        if not self.adj:
            return positions

        # Find root: component with most connections
        root = max(self.adj, key=lambda r: len(self.adj.get(r, set())))
        cx, cy = page_width / 2, page_height / 2

        # BFS from root, place children in layers
        placed = {}
        queue = [(root, None)]
        layer = 0
        while queue:
            next_queue = []
            layer_x = cx - 50 + layer * 30
            col_y = cy
            for comp, parent in queue:
                if comp in placed:
                    continue
                w, h = component_sizes.get(comp, (10, 10))
                placed[comp] = (snap(layer_x), snap(col_y), 0)
                col_y -= h + 10

                for nb in self.adj.get(comp, set()):
                    key = tuple(sorted([comp, nb]))
                    if key not in self.broken_set and nb not in placed:
                        next_queue.append((nb, comp))
            queue = next_queue
            layer += 1

        return placed

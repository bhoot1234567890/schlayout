"""Check loop circuits for tangling and wire length optimality."""

from __future__ import annotations
from typing import List, Tuple
import math

def wire_length(wires: List[Tuple[float,float,float,float]]) -> float:
    """Total Euclidean length of all wire segments."""
    total = 0.0
    for x1, y1, x2, y2 in wires:
        total += math.sqrt((x2-x1)**2 + (y2-y1)**2)
    return total

def hpwl(points: List[Tuple[float,float]]) -> float:
    """Half-perimeter wire length of a point set."""
    if not points:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))

def segments_intersect(
    a: Tuple[float,float], b: Tuple[float,float],
    c: Tuple[float,float], d: Tuple[float,float],
    tolerance: float = 0.1,
) -> bool:
    """Check if line segments AB and CD intersect.
    
    Returns True if they cross (excluding shared endpoints).
    """
    # Check if they share an endpoint — that's a junction, not an intersection
    if (abs(a[0]-c[0]) < tolerance and abs(a[1]-c[1]) < tolerance): return False
    if (abs(a[0]-d[0]) < tolerance and abs(a[1]-d[1]) < tolerance): return False
    if (abs(b[0]-c[0]) < tolerance and abs(b[1]-c[1]) < tolerance): return False
    if (abs(b[0]-d[0]) < tolerance and abs(b[1]-d[1]) < tolerance): return False
    
    # Cross product orientation test
    def orient(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    
    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    
    # General case: segments straddle each other
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    
    # Collinear cases: check if they overlap
    if abs(o1) < 1e-9 and _on_segment(a, b, c): return True
    if abs(o2) < 1e-9 and _on_segment(a, b, d): return True
    if abs(o3) < 1e-9 and _on_segment(c, d, a): return True
    if abs(o4) < 1e-9 and _on_segment(c, d, b): return True
    
    return False

def _on_segment(p, q, r):
    """Check if point r lies on segment pq."""
    return (min(p[0], q[0]) - 0.1 <= r[0] <= max(p[0], q[0]) + 0.1 and
            min(p[1], q[1]) - 0.1 <= r[1] <= max(p[1], q[1]) + 0.1)

def wire_passes_through_component(
    wire: Tuple[float,float,float,float],
    comp_bbox: Tuple[float,float,float,float],  # (cx, cy, w, h)
) -> bool:
    """Check if a wire segment passes through a component's bounding box."""
    cx, cy, w, h = comp_bbox
    left, right = cx - w/2, cx + w/2
    bottom, top = cy - h/2, cy + h/2
    
    x1, y1, x2, y2 = wire
    
    # Check if either endpoint is inside the bbox
    if left <= x1 <= right and bottom <= y1 <= top: return True
    if left <= x2 <= right and bottom <= y2 <= top: return True
    
    # Check line-segment vs rectangle intersection
    # Ray casting: check all four edges
    edges = [
        (left, bottom, right, bottom),   # bottom
        (right, bottom, right, top),     # right
        (right, top, left, top),         # top
        (left, top, left, bottom),       # left
    ]
    for ex1, ey1, ex2, ey2 in edges:
        if segments_intersect((x1,y1), (x2,y2), (ex1,ey1), (ex2,ey2)):
            return True
    
    return False

def check_loop(
    wires: List[Tuple[float,float,float,float]],
    component_bboxes: List[Tuple[float,float,float,float]],
    pin_positions: List[List[Tuple[float,float]]],
) -> dict:
    """Check a loop circuit for tangling and overlaps.
    
    Returns dict with:
      - total_length: total wire length
      - crossings: list of wire pairs that cross
      - component_crossings: list of (wire_idx, comp_idx) where wire passes through comp
      - is_clean: True if no crossings and no component penetrations
    """
    result = {
        'total_length': wire_length(wires),
        'crossings': [],
        'component_crossings': [],
        'is_clean': True,
    }
    
    # Check wire-wire crossings (between different nets)
    for i in range(len(wires)):
        for j in range(i+1, len(wires)):
            w1 = wires[i]
            w2 = wires[j]
            if segments_intersect(
                (w1[0],w1[1]), (w1[2],w1[3]),
                (w2[0],w2[1]), (w2[2],w2[3])
            ):
                result['crossings'].append((i, j))
                result['is_clean'] = False
    
    # Check wires passing through components
    for i, wire in enumerate(wires):
        for j, bbox in enumerate(component_bboxes):
            if wire_passes_through_component(wire, bbox):
                result['component_crossings'].append((i, j))
                result['is_clean'] = False
    
    return result

def minimal_wire_length_possible(
    pin_positions: List[List[Tuple[float,float]]],
    nets: List[List[int]],  # list of pin indices per net
) -> float:
    """Compute the minimum possible wire length for a given placement.
    
    For each net, computes the HPWL (half-perimeter wire length)
    which is the theoretical minimum for orthogonal routing.
    """
    total = 0.0
    for net_pin_indices in nets:
        pts = []
        for comp_idx, pin_idx in net_pin_indices:
            if comp_idx < len(pin_positions) and pin_idx < len(pin_positions[comp_idx]):
                pts.append(pin_positions[comp_idx][pin_idx])
        if pts:
            total += hpwl(pts)
    return total

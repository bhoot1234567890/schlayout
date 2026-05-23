"""Force-directed schematic placement with SA acceptance and multi-start.

Production-ready placer for 2-200 components. Combines force-directed
attraction/repulsion with simulated annealing temperature schedule
and multi-start rotation optimization.
"""

from __future__ import annotations
import math, random, time, itertools
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from .symbols import SymbolData

GRID = 2.54


def snap(v: float) -> float:
    return round(v / GRID) * GRID


@dataclass
class PlacedComponent:
    ref: str
    symbol: SymbolData
    cx: float
    cy: float
    rotation: int

    @property
    def w(self) -> float:
        return self.symbol.rotated_size(self.rotation)[0]

    @property
    def h(self) -> float:
        return self.symbol.rotated_size(self.rotation)[1]

    def pin_world(self, pin_index: int) -> Tuple[float, float]:
        offsets = self.symbol.rotated_offsets(self.rotation)
        ox, oy = offsets[pin_index]
        return (self.cx + ox, self.cy - oy)

    def pin_by_number(self, number: str) -> Tuple[float, float]:
        for i, p in enumerate(self.symbol.pins):
            if p.number == number:
                return self.pin_world(i)
        return (self.cx, self.cy)


@dataclass
class NetDef:
    name: str
    connections: List[Tuple[str, str]]
    weight: float = 1.0


class ForceDirectedPlacer:
    """Force-directed placement with SA acceptance and rotation optimization.

    Uses multi-start: tries multiple rotation combos, runs force-directed
    for each, picks the best overall.

    Cost = HPWL + overlap_penalty + net_collision_penalty
    """

    def __init__(
        self,
        components: List[Tuple[str, SymbolData]],
        nets: List[NetDef],
        random_seed: int | None = 42,
        # Annealing
        T_initial: float = 200.0,
        T_min: float = 0.05,
        alpha: float = 0.93,
        moves_per_temp: int = 40,
        max_steps: int = 150,
        # Forces
        attraction: float = 1.0,
        repulsion: float = 80.0,
        centering: float = 0.02,  # weak pull toward page center
        damping: float = 0.4,
        margin: float = 3.0,
        # Multi-start
        rotation_restarts: bool = True,
        position_restarts: int = 3,
        allowed_rotations: List[int] | None = None,
        # Page
        page_width: float = 297.0,
        page_height: float = 210.0,
    ):
        self.comp_defs = components
        self.nets = nets
        self.T_initial = T_initial
        self.T_min = T_min
        self.alpha = alpha
        self.moves_per_temp = moves_per_temp
        self.max_steps = max_steps
        self.attraction = attraction
        self.repulsion = repulsion
        self.centering = centering
        self.damping = damping
        self.margin = margin
        self.rotation_restarts = rotation_restarts
        self.position_restarts = position_restarts
        self.allowed_rotations = allowed_rotations or [0, 90, 180, 270]
        self.pw = page_width
        self.ph = page_height
        self.rng = random.Random(random_seed)

        # Index nets for fast lookup
        self.comp_index = {ref: i for i, (ref, _) in enumerate(components)}
        self.net_index = []
        for net in nets:
            self.net_index.append([
                (self.comp_index[ref], pn) for ref, pn in net.connections
            ])

    def search(self) -> Tuple[List[PlacedComponent], float]:
        """Run the full multi-start placement pipeline."""
        n = len(self.comp_defs)
        center_x, center_y = self.pw / 2, self.ph / 2

        # Try all rotation combos (or just default if rotation_restarts=False)
        if self.rotation_restarts and n <= 4:
            rot_combos = list(itertools.product(self.allowed_rotations, repeat=n))
        else:
            rot_combos = [(0,) * n]

        best_result = None
        best_score = float('inf')

        for rotations in rot_combos:
            # Precompute rotated data
            comp_data = []
            for i, ((ref, sym), rot) in enumerate(zip(self.comp_defs, rotations)):
                w, h = sym.rotated_size(rot)
                offs = sym.rotated_offsets(rot)
                pinfo = [(p.number, ox, oy) for p, (ox, oy) in zip(sym.pins, offs)]
                comp_data.append({
                    'ref': ref, 'sym': sym, 'rot': rot,
                    'w': w, 'h': h, 'pinfo': pinfo,
                })

            # Multiple position restarts
            for restart in range(self.position_restarts):
                xs, ys = self._init_positions(comp_data, center_x, center_y, restart)
                best_xs, best_ys = list(xs), list(ys)
                local_best_cost = float('inf')

                cost, xs, ys = self._anneal(xs, ys, comp_data)
                if cost < local_best_cost:
                    local_best_cost = cost
                    best_xs, best_ys = list(xs), list(ys)

                if local_best_cost < best_score:
                    best_score = local_best_cost
                    best_result = (best_xs, best_ys, comp_data)

        if best_result is None:
            raise RuntimeError("No valid placement found")

        xs, ys, comp_data = best_result
        result = []
        for i, cd in enumerate(comp_data):
            result.append(PlacedComponent(
                ref=cd['ref'], symbol=cd['sym'],
                cx=snap(xs[i]), cy=snap(ys[i]),
                rotation=cd['rot'],
            ))
        return result, best_score

    def _init_positions(self, comp_data, cx, cy, restart):
        """Initialize positions: first restart near center, others random."""
        n = len(comp_data)
        if restart == 0:
            # Place in a rough grid near center
            cols = math.ceil(math.sqrt(n))
            xs = []; ys = []
            spacing = 15.0
            for i, cd in enumerate(comp_data):
                row = i // cols; col = i % cols
                xs.append(cx + (col - cols/2 + 0.5) * spacing)
                ys.append(cy + (row - (n/cols)/2 + 0.5) * spacing)
            return xs, ys
        else:
            # Random within central 60% of page
            xs = [self.rng.uniform(self.pw*0.2, self.pw*0.8) for _ in range(n)]
            ys = [self.rng.uniform(self.ph*0.2, self.ph*0.8) for _ in range(n)]
            return xs, ys

    def _anneal(self, xs, ys, comp_data):
        """Run the SA + force-directed loop."""
        n = len(comp_data)
        center_x, center_y = self.pw / 2, self.ph / 2
        velocities = [(0.0, 0.0)] * n
        T = self.T_initial
        best_cost = self._total_cost(xs, ys, comp_data)
        best_xs, best_ys = list(xs), list(ys)

        for step in range(self.max_steps):
            if T < self.T_min:
                break

            for _ in range(self.moves_per_temp):
                forces = [(0.0, 0.0)] * n

                # 1. Attractive forces along nets
                for net_conns in self.net_index:
                    pts = []
                    for ci, pn in net_conns:
                        cd = comp_data[ci]
                        for pn2, ox, oy in cd['pinfo']:
                            if pn2 == pn:
                                pts.append((xs[ci] + ox, ys[ci] - oy))
                                break
                    if len(pts) < 2:
                        continue
                    # Center of mass
                    cmx = sum(p[0] for p in pts) / len(pts)
                    cmy = sum(p[1] for p in pts) / len(pts)
                    for k, (ci, pn) in enumerate(net_conns):
                        px, py = pts[k]
                        fx = (cmx - px) * self.attraction
                        fy = (cmy - py) * self.attraction
                        f0 = forces[ci]
                        forces[ci] = (f0[0] + fx, f0[1] + fy)

                # 2. Repulsive forces between overlapping components
                for i in range(n):
                    wi, hi = comp_data[i]['w'], comp_data[i]['h']
                    for j in range(i + 1, n):
                        wj, hj = comp_data[j]['w'], comp_data[j]['h']
                        dx = xs[j] - xs[i]
                        dy = ys[j] - ys[i]
                        dist = math.sqrt(dx*dx + dy*dy) + 0.001
                        min_dist = (wi + wj)/2 + self.margin

                        if dist < min_dist + 15.0:  # repulsion range
                            overlap = max(0, min_dist - dist)
                            force_mag = self.repulsion * (overlap + 1.0) / max(dist, 0.1)
                            if dist > 0.001:
                                fx = force_mag * dx / dist
                                fy = force_mag * dy / dist
                            else:
                                fx = 10.0 * (self.rng.random() - 0.5)
                                fy = 10.0 * (self.rng.random() - 0.5)
                            fi = forces[i]; fj = forces[j]
                            forces[i] = (fi[0] - fx, fi[1] - fy)
                            forces[j] = (fj[0] + fx, fj[1] + fy)

                # 3. Weak centering force
                for i in range(n):
                    dx = center_x - xs[i]
                    dy = center_y - ys[i]
                    f0 = forces[i]
                    forces[i] = (f0[0] + dx * self.centering, f0[1] + dy * self.centering)

                # 4. Apply forces with damping
                for i in range(n):
                    fx, fy = forces[i]
                    vx, vy = velocities[i]
                    vx = self.damping * vx + fx
                    vy = self.damping * vy + fy
                    velocities[i] = (vx, vy)

                    old_x, old_y = xs[i], ys[i]
                    new_x = old_x + vx
                    new_y = old_y + vy

                    # Clamp to page bounds
                    w, h = comp_data[i]['w'], comp_data[i]['h']
                    new_x = max(self.margin + w/2, min(self.pw - self.margin - w/2, new_x))
                    new_y = max(self.margin + h/2, min(self.ph - self.margin - h/2, new_y))

                    # Compute cost change for this component
                    old_cost = self._local_cost(i, xs, ys, comp_data)
                    xs[i], ys[i] = new_x, new_y
                    new_cost = self._local_cost(i, xs, ys, comp_data)
                    delta = new_cost - old_cost

                    # SA acceptance
                    if delta <= 0 or self.rng.random() < math.exp(-delta / max(T, 0.001)):
                        pass  # keep
                    else:
                        xs[i], ys[i] = old_x, old_y
                        velocities[i] = (0.0, 0.0)

            # End of temperature step
            T *= self.alpha
            cost = self._total_cost(xs, ys, comp_data)
            if cost < best_cost:
                best_cost = cost
                best_xs, best_ys = list(xs), list(ys)

        return best_cost, best_xs, best_ys

    def _local_cost(self, idx, xs, ys, comp_data):
        """Cost contributed by one component (nets + overlaps)."""
        cost = 0.0
        n = len(xs)
        wi, hi = comp_data[idx]['w'], comp_data[idx]['h']

        # Wire length for nets touching this component
        for net_conns in self.net_index:
            if any(ci == idx for ci, _ in net_conns):
                pts = []
                for ci, pn in net_conns:
                    cd = comp_data[ci]
                    for pn2, ox, oy in cd['pinfo']:
                        if pn2 == pn:
                            pts.append((xs[ci] + ox, ys[ci] - oy))
                            break
                if pts:
                    cost += (max(p[0] for p in pts) - min(p[0] for p in pts))
                    cost += (max(p[1] for p in pts) - min(p[1] for p in pts))

        # Overlap penalty
        for j in range(n):
            if j == idx: continue
            wj, hj = comp_data[j]['w'], comp_data[j]['h']
            dx = abs(xs[idx] - xs[j])
            dy = abs(ys[idx] - ys[j])
            if dx < (wi + wj)/2 + self.margin and dy < (hi + hj)/2 + self.margin:
                cost += 50.0

        # Net collision: different nets shouldn't have pins at same Y
        net_ys = []
        for net_conns in self.net_index:
            if any(ci == idx for ci, _ in net_conns):
                for ci, pn in net_conns:
                    cd = comp_data[ci]
                    for pn2, ox, oy in cd['pinfo']:
                        if pn2 == pn:
                            net_ys.append(round(ys[ci] - oy, 1))
        if len(set(net_ys)) < len(net_ys):  # collision
            cost += 30.0

        return cost

    def _total_cost(self, xs, ys, comp_data):
        """Full placement cost."""
        cost = 0.0
        n = len(xs)

        for net_conns in self.net_index:
            pts = []
            for ci, pn in net_conns:
                cd = comp_data[ci]
                for pn2, ox, oy in cd['pinfo']:
                    if pn2 == pn:
                        pts.append((xs[ci] + ox, ys[ci] - oy))
                        break
            if pts:
                cost += (max(p[0] for p in pts) - min(p[0] for p in pts))
                cost += (max(p[1] for p in pts) - min(p[1] for p in pts))

        for i in range(n):
            wi, hi = comp_data[i]['w'], comp_data[i]['h']
            for j in range(i+1, n):
                wj, hj = comp_data[j]['w'], comp_data[j]['h']
                dx = abs(xs[i] - xs[j])
                dy = abs(ys[i] - ys[j])
                if dx < (wi + wj)/2 + self.margin and dy < (hi + hj)/2 + self.margin:
                    cost += 50.0

        return cost

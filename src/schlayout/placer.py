"""Brute-force optimal placement engine for schematic components.

Searches over rotations × grid positions to minimize total Manhattan
wire length plus bend penalties. Uses tuple-based inner loops for speed.
"""

from __future__ import annotations
import itertools, math
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

    def bbox(self) -> Tuple[float, float, float, float]:
        hw, hh = self.w / 2, self.h / 2
        return (self.cx - hw, self.cx + hw, self.cy - hh, self.cy + hh)


@dataclass
class NetDef:
    name: str
    connections: List[Tuple[str, str]]


def boxes_overlap(
    ax: float, ay: float, aw: float, ah: float,
    bx: float, by: float, bw: float, bh: float,
) -> bool:
    """True if two axis-aligned rectangles overlap."""
    if ax + aw/2 + 2.54 <= bx - bw/2: return False  # a right of b (2.54mm margin)
    if bx + bw/2 + 2.54 <= ax - aw/2: return False  # b right of a (2.54mm margin)
    if ay + ah/2 + 2.54 <= by - bh/2: return False  # a above b (2.54mm margin)
    if by + bh/2 + 2.54 <= ay - ah/2: return False  # b above a (2.54mm margin)
    return True


class BruteForcePlacer:
    """Search rotations × positions to minimize wire cost."""

    def __init__(
        self,
        components: List[Tuple[str, SymbolData]],
        nets: List[NetDef],
        x_range: List[float] | None = None,
        y_range: List[float] | None = None,
        rotations: List[int] | None = None,
        bend_penalty: float = 10.0,
        page_margin: float = 5.0,
        page_width: float = 297.0,
        page_height: float = 210.0,
    ):
        self.comp_defs = components
        self.nets = nets
        self.xs = x_range or [snap(x) for x in _arange(page_margin, page_width - page_margin, GRID)]
        self.ys = y_range or [snap(y) for y in _arange(page_margin, page_height - page_margin, GRID)]
        self.rots = rotations or [0, 90, 180, 270]
        self.bend = bend_penalty
        self.pm = page_margin
        self.pw = page_width
        self.ph = page_height

    def search(self) -> Tuple[List[PlacedComponent], float]:
        n = len(self.comp_defs)
        best_score = float('inf')
        best_spec = None

        # Precompute: for each component, for each rotation:
        #   (ref, rot, w, h, [(pin_num, ox, oy), ...])
        variants = []
        for ref, sym in self.comp_defs:
            var = []
            for rot in self.rots:
                w, h = sym.rotated_size(rot)
                offs = sym.rotated_offsets(rot)
                pinfo = [(p.number, ox, oy) for p, (ox, oy) in zip(sym.pins, offs)]
                var.append((ref, rot, w, h, pinfo))
            variants.append(var)

        # Index net connections into (comp_idx, pin_num) pairs
        comp_idx = {ref: i for i, (ref, _) in enumerate(self.comp_defs)}
        net_index = []
        for net in self.nets:
            indexed = []
            for ref, pn in net.connections:
                indexed.append((comp_idx[ref], pn))
            net_index.append(indexed)

        for rot_indices in itertools.product(range(len(self.rots)), repeat=n):
            vdata = [variants[i][r] for i, r in enumerate(rot_indices)]

            for xs in itertools.product(self.xs, repeat=n):
                # Quick X-only overlap check
                ok = True
                for i in range(n):
                    xi, wi = xs[i], vdata[i][2]
                    for j in range(i+1, n):
                        xj, wj = xs[j], vdata[j][2]
                        if abs(xi - xj) < (wi + wj) / 2:
                            ok = False; break
                    if not ok: break
                if not ok: continue

                for ys in itertools.product(self.ys, repeat=n):
                    # Full 2D overlap check
                    ok = True
                    for i in range(n):
                        xi, yi, wi, hi = xs[i], ys[i], vdata[i][2], vdata[i][3]
                        for j in range(i+1, n):
                            if boxes_overlap(xi, yi, wi, hi, xs[j], ys[j], vdata[j][2], vdata[j][3]):
                                ok = False; break
                        if not ok: break
                    if not ok: continue

                    # Compute pin world positions
                    pin_world = []
                    for i in range(n):
                        ref, rot, w, h, pinfo = vdata[i]
                        pw = {}
                        for pn, ox, oy in pinfo:
                            pw[pn] = (xs[i] + ox, ys[i] - oy)
                        pin_world.append(pw)

                    # Score
                    score = 0.0
                    # Track pin Y-values per net to detect net collisions
                    net_ys = []
                    for net_conns in net_index:
                        ys_in_net = set()
                        for k in range(len(net_conns) - 1):
                            ci, pn_a = net_conns[k]
                            cj, pn_b = net_conns[k + 1]
                            ax, ay = pin_world[ci][pn_a]
                            bx, by = pin_world[cj][pn_b]
                            ys_in_net.add(round(ay, 1))
                            ys_in_net.add(round(by, 1))
                            score += abs(ax - bx) + abs(ay - by)
                            if abs(ax - bx) > 0.01 and abs(ay - by) > 0.01:
                                score += self.bend
                        net_ys.append(ys_in_net)
                    # Penalize if different nets share Y values (likely collision)
                    for a in range(len(net_ys)):
                        for b in range(a + 1, len(net_ys)):
                            if net_ys[a] & net_ys[b]:  # overlap in Y
                                score += 30.0

                    if score < best_score:
                        best_score = score
                        best_spec = (vdata, xs, ys)

        if best_spec is None:
            raise RuntimeError("No valid placement in search space")

        vdata, xs, ys = best_spec
        result = []
        for i in range(n):
            ref, rot, w, h, pinfo = vdata[i]
            result.append(PlacedComponent(
                ref=ref, symbol=self.comp_defs[i][1],
                cx=xs[i], cy=ys[i], rotation=rot,
            ))
        return result, best_score


def _arange(start: float, stop: float, step: float) -> List[float]:
    result = []
    v = start
    while v <= stop:
        result.append(v)
        v += step
    return result

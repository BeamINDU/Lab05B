from __future__ import annotations

from dataclasses import dataclass
from math import inf
from itertools import permutations
from collections import deque
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import numba

from .entities import (
    EPS,
    Item,
    Container,
    OrientationCache,
    Placement,
    getRotDim,
    sku_signature,
)
from .geometry import (
    generate_and_filter_positions_numba,
    check_collision_numba,
    check_priority_adjacency_numba,
    check_support_and_stacking_numba,
)


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float
    rotated: bool = False
    region: Optional[str] = None


class MaxRects2D:
    """Simple MaxRects implementation for the floor layer."""

    def __init__(self, length: float, width: float) -> None:
        self.free_rects: List[Rect] = [Rect(0.0, 0.0, width, length)]
        self.used_rects: List[Rect] = []

    def insert(self, width: float, height: float, allow_rotation: bool = True) -> Optional[Rect]:
        best_rect = self.find_position(width, height, allow_rotation=allow_rotation)
        if best_rect:
            self.commit(best_rect)
        return best_rect

    def insert_fixed(self, width: float, height: float) -> Optional[Rect]:
        return self.insert(width, height, allow_rotation=False)

    def find_position(self, width: float, height: float, allow_rotation: bool = True) -> Optional[Rect]:
        best_rect: Optional[Rect] = None
        best_score = (inf, inf, inf)

        for free in self.free_rects:
            # Try normal orientation
            if width <= free.width + EPS and height <= free.height + EPS:
                leftover_horiz = abs(free.width - width)
                leftover_vert = abs(free.height - height)
                # Score: (1) minimize wasted area, (2) minimize short side leftover, (3) minimize free rect area
                wasted_area = leftover_horiz * height + leftover_vert * width - leftover_horiz * leftover_vert
                short_side = min(leftover_horiz, leftover_vert)
                free_area = free.width * free.height
                score = (wasted_area, short_side, free_area)

                if score < best_score:
                    best_score = score
                    best_rect = Rect(free.x, free.y, width, height, rotated=False)

            # Try rotated orientation
            if allow_rotation and height <= free.width + EPS and width <= free.height + EPS:
                leftover_horiz = abs(free.width - height)
                leftover_vert = abs(free.height - width)
                wasted_area = leftover_horiz * width + leftover_vert * height - leftover_horiz * leftover_vert
                short_side = min(leftover_horiz, leftover_vert)
                free_area = free.width * free.height
                # Add small penalty for rotation to prefer non-rotated when equal
                score = (wasted_area, short_side, free_area + 0.01)

                if score < best_score:
                    best_score = score
                    best_rect = Rect(free.x, free.y, height, width, rotated=True)

        return best_rect

    def commit(self, rect: Rect) -> None:
        self._place(rect)

    def _place(self, rect: Rect) -> None:
        i = 0
        while i < len(self.free_rects):
            if self._split_free_rect(self.free_rects[i], rect):
                self.free_rects.pop(i)
                i -= 1
            i += 1
        self._prune_free_list()
        self.used_rects.append(rect)

    def _split_free_rect(self, free: Rect, used: Rect) -> bool:
        if not self._rects_overlap(free, used):
            return False
        if used.x > free.x:
            width = used.x - free.x
            if width > EPS:
                self.free_rects.append(Rect(free.x, free.y, width, free.height))
        if used.x + used.width < free.x + free.width:
            w = (free.x + free.width) - (used.x + used.width)
            if w > EPS:
                self.free_rects.append(Rect(used.x + used.width, free.y, w, free.height))
        if used.y > free.y:
            width = min(free.x + free.width, used.x + used.width) - max(free.x, used.x)
            height = used.y - free.y
            if width > EPS and height > EPS:
                self.free_rects.append(Rect(max(free.x, used.x), free.y, width, height))
        if used.y + used.height < free.y + free.height:
            h = (free.y + free.height) - (used.y + used.height)
            width = min(free.x + free.width, used.x + used.width) - max(free.x, used.x)
            if width > EPS and h > EPS:
                self.free_rects.append(Rect(max(free.x, used.x), used.y + used.height, width, h))
        return True

    def _prune_free_list(self) -> None:
        pruned: List[Rect] = []
        for i, rect in enumerate(self.free_rects):
            dominated = False
            for j, other in enumerate(self.free_rects):
                if i == j:
                    continue
                if (
                    rect.x >= other.x - EPS
                    and rect.y >= other.y - EPS
                    and rect.x + rect.width <= other.x + other.width + EPS
                    and rect.y + rect.height <= other.y + other.height + EPS
                ):
                    dominated = True
                    break
            if not dominated:
                pruned.append(rect)
        self.free_rects = pruned

    @staticmethod
    def _rects_overlap(a: Rect, b: Rect) -> bool:
        return not (
            a.x + a.width <= b.x + EPS
            or b.x + b.width <= a.x + EPS
            or a.y + a.height <= b.y + EPS
            or b.y + b.height <= a.y + EPS
        )


class FirstLayerPlanner:
    """Builds a dense floor layer using MaxRects with uniform and mixed orientation attempts."""

    def __init__(
        self,
        container: Container,
        orientation_cache: Dict[int, OrientationCache],
        item_to_group: Dict[int, str],
        group_registry: Dict[str, Set[int]],
    ) -> None:
        self.container = container
        self.orientation_cache = orientation_cache
        self.item_to_group = item_to_group
        self.group_sizes = {}
        for gid, members in group_registry.items():
            for item_id in members:
                self.group_sizes[item_id] = len(members)
        self.area = container.length * container.width
        if container.door_type_int == 1:
            self.door_axis = "width"
            self.max_depth = container.width
        elif container.door_type_int == 0:
            self.door_axis = "length"
            self.max_depth = container.length
        else:
            self.door_axis = None
            self.max_depth = 1.0

    def plan(self, items: List[Item]) -> Tuple[List[Placement], Set[int]]:
        candidates = self._select_candidates(items)
        if not candidates:
            return [], set()
        attempts = [
            ("uniform", self._attempt_uniform(candidates)),
            ("mixed", self._attempt_mixed(candidates)),
        ]
        best_layout: List[Placement] = []
        best_metric = (-float("inf"), float("inf"))
        best_ids: Set[int] = set()
        for label, result in attempts:
            placements, utilization, door_metric = result
            if not placements:
                continue
            metric = (utilization, -door_metric)
            if metric > best_metric:
                best_metric = metric
                best_layout = placements
                best_ids = {p.item.id for p in placements}
        return best_layout, best_ids

    def _select_candidates(self, items: List[Item]) -> List[Item]:
        grounded = [it for it in items if it.grounded]
        non_grounded = [it for it in items if not it.grounded]

        def sort_key(item: Item) -> Tuple[int, float, float, float, int]:
            return (-item.senddate_ts, -item.pickup_priority, -item.weight, -item.volume, item.id)

        non_grounded.sort(key=sort_key)
        ordered: List[Item] = grounded + non_grounded
        if non_grounded and self.container.door_type_int in (0, 1):
            unique_priorities = len(set(it.pickup_priority for it in non_grounded))
            if unique_priorities == 1:
                max_w = max(it.weight for it in non_grounded)
                non_grounded = [it for it in non_grounded if it.weight >= max_w - 1e-6]

        selected: List[Item] = []
        area_sum = 0.0

        for item in grounded:
            cache = self.orientation_cache[item.id]
            base_rot = cache.rotations[0]
            dims = cache.dimensions[base_rot]
            footprint = dims[0] * dims[1]
            if area_sum + footprint > self.area * 1.25:
                continue
            selected.append(item)
            area_sum += footprint

        sku_queues: Dict[Tuple, deque[Item]] = {}
        sku_footprint: Dict[Tuple, float] = {}
        is_pallet = (self.container.door_type_int == -1)
        for item in non_grounded:
            group_id = self.item_to_group.get(item.id)
            if group_id and self.group_sizes.get(item.id, 1) > 1:
                continue
            if is_pallet:
                key = ("id", item.id)
            else:
                key = (self.orientation_cache[item.id].rotations[0], sku_signature(item))
            sku_queues.setdefault(key, deque()).append(item)
            if key not in sku_footprint:
                cache = self.orientation_cache[item.id]
                dims = cache.dimensions[cache.rotations[0]]
                sku_footprint[key] = dims[0] * dims[1]

        limit_area = self.area * 1.25
        ordered_skus = sorted(sku_queues.keys(), key=lambda k: -sku_footprint[k])
        max_candidates = 5000 if is_pallet else 1000

        added = True
        while added and len(selected) < max_candidates:
            added = False
            for key in ordered_skus:
                queue = sku_queues[key]
                while queue:
                    item = queue[0]
                    cache = self.orientation_cache[item.id]
                    base_rot = cache.rotations[0]
                    dims = cache.dimensions[base_rot]
                    footprint = dims[0] * dims[1]
                    if area_sum + footprint > limit_area:
                        queue.popleft()
                        continue
                    selected.append(item)
                    area_sum += footprint
                    queue.popleft()
                    added = True
                    break
                if len(selected) >= max_candidates:
                    break

        if len(selected) < max_candidates:
            leftovers: List[Item] = []
            for key in sorted(sku_queues.keys()):
                leftovers.extend(sku_queues[key])

            def footprint(it: Item) -> float:
                cache = self.orientation_cache[it.id]
                dims = cache.dimensions[cache.rotations[0]]
                return dims[0] * dims[1]

            leftovers.sort(key=footprint)
            for item in leftovers:
                cache = self.orientation_cache[item.id]
                dims = cache.dimensions[cache.rotations[0]]
                fp = dims[0] * dims[1]
                if area_sum + fp > limit_area:
                    continue
                selected.append(item)
                area_sum += fp
                if len(selected) >= max_candidates:
                    break
        return selected

    def _attempt_uniform(self, items: List[Item]) -> Tuple[List[Placement], float, float]:
        packer = MaxRects2D(self.container.length, self.container.width)
        placements: List[Placement] = []
        area_used = 0.0
        door_metric = 0.0
        for item in items:
            cache = self.orientation_cache[item.id]
            preferred = self._preferred_rotations(cache)

            # Try ALL rotations (not just preferred) to maximize utilization
            all_rotations = preferred + [r for r in cache.rotations if r not in preferred]
            best_choice: Optional[Tuple[Rect, int, Tuple[float, float, float]]] = None
            best_score = (inf, inf, inf)

            for rot in all_rotations:
                dims = cache.dimensions[rot]
                rect = packer.find_position(dims[0], dims[1], allow_rotation=False)
                if rect is None:
                    continue

                # Enhanced scoring for maximum utilization:
                # 1. Minimize wasted area (primary)
                # 2. Minimize short side leftover (secondary)
                # 3. Minimize long side leftover (tertiary)
                leftover_horiz = abs(rect.width - dims[0])
                leftover_vert = abs(rect.height - dims[1])
                wasted_area = leftover_horiz * dims[1] + leftover_vert * dims[0] - leftover_horiz * leftover_vert
                short_side_leftover = min(leftover_horiz, leftover_vert)
                long_side_leftover = max(leftover_horiz, leftover_vert)
                score = (wasted_area, short_side_leftover, long_side_leftover)

                if score < best_score:
                    best_score = score
                    best_choice = (rect, rot, dims)

            if best_choice is None:
                continue

            rect, rot, dims = best_choice
            packer.commit(rect)
            placement = Placement(
                item=item,
                x=rect.x,
                y=rect.y,
                z=0.0,
                rotation=rot,
                dims=(dims[0], dims[1], dims[2]),
                supporters=[],
            )
            placements.append(placement)
            area_used += dims[0] * dims[1]
            door_metric += self._door_metric(placement)
        utilization = area_used / self.area if self.area > EPS else 0.0
        return placements, utilization, door_metric

    def _preferred_rotations(self, cache: OrientationCache) -> List[int]:
        rotations = self._ordered_rotations(cache)
        if self.container.door_type_int == 0:
            primary = [r for r in rotations if cache.dimensions[r][0] >= cache.dimensions[r][1] - EPS]
        elif self.container.door_type_int == 1:
            primary = [r for r in rotations if cache.dimensions[r][1] >= cache.dimensions[r][0] - EPS]
        else:
            primary = rotations
        tail = [r for r in rotations if r not in primary]
        return primary + tail

    def _attempt_mixed(self, items: List[Item]) -> Tuple[List[Placement], float, float]:
        if items:
            f = items[0]
            uniform = all(
                abs(it.length - f.length) <= EPS
                and abs(it.width - f.width) <= EPS
                and abs(it.height - f.height) <= EPS
                and it.isSideUp == f.isSideUp
                for it in items
            )
            if uniform:
                layout = self._mixed_row_layout(items)
                if layout:
                    return layout

        packer = MaxRects2D(self.container.length, self.container.width)
        placements: List[Placement] = []
        area_used = 0.0
        door_metric = 0.0
        for item in items:
            cache = self.orientation_cache[item.id]
            ordered = self._preferred_rotations(cache)

            # Try ALL available rotations for maximum utilization
            # For mixed mode, we try all rotations including those not in (0, 1)
            rotations = ordered

            best_choice: Optional[Tuple[Rect, int, Tuple[float, float, float]]] = None
            best_score = (inf, inf, inf)

            for rot in rotations:
                dims = cache.dimensions[rot]
                rect = packer.find_position(dims[0], dims[1], allow_rotation=False)
                if rect is None:
                    continue
                actual_dims = dims
                actual_rot = rot
                if rect.rotated:
                    swapped = (dims[1], dims[0], dims[2])
                    actual_rot = self._match_rotation(cache, swapped)
                    actual_dims = swapped

                # Check door type constraints - be more lenient to improve utilization
                if self.container.door_type_int == 0 and actual_dims[0] + EPS < actual_dims[1]:
                    # Allow some flexibility if it significantly improves fit
                    leftover = abs(rect.width - actual_dims[0]) + abs(rect.height - actual_dims[1])
                    if leftover > min(actual_dims[0], actual_dims[1]) * 0.3:
                        continue
                if self.container.door_type_int == 1 and actual_dims[1] + EPS < actual_dims[0]:
                    # Allow some flexibility if it significantly improves fit
                    leftover = abs(rect.width - actual_dims[0]) + abs(rect.height - actual_dims[1])
                    if leftover > min(actual_dims[0], actual_dims[1]) * 0.3:
                        continue

                # Enhanced scoring for maximum utilization
                leftover_horiz = abs(rect.width - actual_dims[0])
                leftover_vert = abs(rect.height - actual_dims[1])
                wasted_area = leftover_horiz * actual_dims[1] + leftover_vert * actual_dims[0] - leftover_horiz * leftover_vert
                short_side_leftover = min(leftover_horiz, leftover_vert)
                long_side_leftover = max(leftover_horiz, leftover_vert)
                score = (wasted_area, short_side_leftover, long_side_leftover)

                if score < best_score:
                    best_choice = (rect, actual_rot, actual_dims)
                    best_score = score

            if not best_choice:
                continue

            rect, rot, dims = best_choice
            packer.commit(rect)
            placement = Placement(
                item=item,
                x=rect.x,
                y=rect.y,
                z=0.0,
                rotation=rot,
                dims=dims,
                supporters=[],
            )
            placements.append(placement)
            area_used += dims[0] * dims[1]
            door_metric += self._door_metric(placement)
        utilization = area_used / self.area if self.area > EPS else 0.0
        return placements, utilization, door_metric

    def _door_metric(self, placement: Placement) -> float:
        if not self.door_axis:
            return 0.0
        if self.door_axis == "width":
            depth_center = placement.y + placement.dims[1] / 2
            return depth_center * placement.dims[0] * placement.dims[1]
        else:
            depth_center = placement.x + placement.dims[0] / 2
            return max(self.max_depth - depth_center, 0.0) * placement.dims[0] * placement.dims[1]

    @staticmethod
    def _match_rotation(cache: OrientationCache, dims: Tuple[float, float, float]) -> int:
        for rot, rdims in cache.dimensions.items():
            if (
                abs(rdims[0] - dims[0]) <= EPS
                and abs(rdims[1] - dims[1]) <= EPS
                and abs(rdims[2] - dims[2]) <= EPS
            ):
                return rot
        return cache.rotations[0]

    def _mixed_row_layout(self, items: List[Item]) -> Optional[Tuple[List[Placement], float, float]]:
        if not items:
            return None
        cache = self.orientation_cache[items[0].id]
        footprints: Dict[Tuple[float, float], Tuple[int, Tuple[float, float, float]]] = {}
        for rot in self._preferred_rotations(cache):
            dims = cache.dimensions[rot]
            key = (round(dims[0], 4), round(dims[1], 4))
            if key not in footprints:
                footprints[key] = (rot, dims)
            if len(footprints) >= 2:
                break
        if len(footprints) < 2:
            return None
        options = list(footprints.values())[:2]
        row_layout = self._enumerate_rows(options, self.container.length, self.container.width)
        column_layout = self._enumerate_columns(options, self.container.length, self.container.width)
        best_layout = None
        if row_layout:
            best_layout = ("row", row_layout)
        if column_layout:
            if not best_layout or column_layout[0] > best_layout[1][0] or (
                column_layout[0] == best_layout[1][0] and column_layout[1] < best_layout[1][1]
            ):
                best_layout = ("column", column_layout)
        if not best_layout:
            return None
        mode, (total_items, slack, configs) = best_layout
        items_iter = iter(items)
        placements: List[Placement] = []
        area_used = 0.0
        door_metric = 0.0
        if mode == "row":
            current_x = 0.0
            for rot, dims, cols in configs:
                for c in range(cols):
                    try:
                        item = next(items_iter)
                    except StopIteration:
                        break
                    y = c * dims[1]
                    if y + dims[1] > self.container.length + EPS:
                        continue
                    placement = Placement(
                        item=item,
                        x=current_x,
                        y=y,
                        z=0.0,
                        rotation=rot,
                        dims=dims,
                        supporters=[],
                    )
                    placements.append(placement)
                    area_used += dims[0] * dims[1]
                    door_metric += self._door_metric(placement)
                current_x += dims[0]
        else:
            current_y = 0.0
            for rot, dims, rows in configs:
                for r in range(rows):
                    try:
                        item = next(items_iter)
                    except StopIteration:
                        break
                    x = r * dims[0]
                    if x + dims[0] > self.container.width + EPS:
                        continue
                    placement = Placement(
                        item=item,
                        x=x,
                        y=current_y,
                        z=0.0,
                        rotation=rot,
                        dims=dims,
                        supporters=[],
                    )
                    placements.append(placement)
                    area_used += dims[0] * dims[1]
                    door_metric += self._door_metric(placement)
                current_y += dims[1]
        utilization = area_used / self.area if self.area > EPS else 0.0
        return placements, utilization, door_metric

    def _ordered_rotations(self, cache: OrientationCache) -> List[int]:
        rotations = list(cache.rotations)
        if self.container.door_type_int == 0:
            rotations.sort(
                key=lambda r: (
                    cache.dimensions[r][0] < cache.dimensions[r][1],
                    cache.dimensions[r][1],
                    cache.dimensions[r][0],
                )
            )
        elif self.container.door_type_int == 1:
            rotations.sort(
                key=lambda r: (
                    cache.dimensions[r][1] < cache.dimensions[r][0],
                    cache.dimensions[r][0],
                    cache.dimensions[r][1],
                )
            )
        else:
            rotations.sort(
                key=lambda r: (
                    -cache.dimensions[r][0] * cache.dimensions[r][1],
                    cache.dimensions[r][2],
                    cache.dimensions[r][0],
                    cache.dimensions[r][1],
                )
            )
        return rotations

    def _enumerate_rows(
        self,
        options: List[Tuple[int, Tuple[float, float, float]]],
        container_length: float,
        container_width: float,
    ) -> Optional[Tuple[int, float, List[Tuple[int, Tuple[float, float, float], int]]]]:
        best: Optional[Tuple[int, float, List[Tuple[int, Tuple[float, float, float], int]]]] = None
        for order in permutations(range(len(options))):
            counts: List[Tuple[int, Tuple[float, float, float]]] = [options[idx] for idx in order]
            bounds = [int(container_width // dims[0]) for (_, dims) in counts]
            for rows_a in range(bounds[0] + 1):
                for rows_b in range(bounds[1] + 1):
                    if rows_a == 0 and rows_b == 0:
                        continue
                    width_used = rows_a * counts[0][1][0] + rows_b * counts[1][1][0]
                    if width_used > container_width + EPS:
                        continue
                    cols_a = int(container_length // counts[0][1][1]) if rows_a > 0 else 0
                    cols_b = int(container_length // counts[1][1][1]) if rows_b > 0 else 0
                    total_items = rows_a * cols_a + rows_b * cols_b
                    if total_items == 0:
                        continue
                    slack = (container_width - width_used) * container_length
                    slack += rows_a * (container_length - cols_a * counts[0][1][1]) * counts[0][1][0]
                    slack += rows_b * (container_length - cols_b * counts[1][1][1]) * counts[1][1][0]
                    layout: List[Tuple[int, Tuple[float, float, float], int]] = []
                    layout.extend([(*counts[0], cols_a)] * rows_a)
                    layout.extend([(*counts[1], cols_b)] * rows_b)
                    score = (total_items, -slack)
                    if not best or score > (best[0], -best[1]):
                        best = (total_items, slack, layout)
        return best

    def _enumerate_columns(
        self,
        options: List[Tuple[int, Tuple[float, float, float]]],
        container_length: float,
        container_width: float,
    ) -> Optional[Tuple[int, float, List[Tuple[int, Tuple[float, float, float], int]]]]:
        best: Optional[Tuple[int, float, List[Tuple[int, Tuple[float, float, float], int]]]] = None
        for order in permutations(range(len(options))):
            counts: List[Tuple[int, Tuple[float, float, float]]] = [options[idx] for idx in order]
            bounds = [int(container_length // dims[1]) for (_, dims) in counts]
            for cols_a in range(bounds[0] + 1):
                for cols_b in range(bounds[1] + 1):
                    if cols_a == 0 and cols_b == 0:
                        continue
                    length_used = cols_a * counts[0][1][1] + cols_b * counts[1][1][1]
                    if length_used > container_length + EPS:
                        continue
                    rows_a = int(container_width // counts[0][1][0]) if cols_a > 0 else 0
                    rows_b = int(container_width // counts[1][1][0]) if cols_b > 0 else 0
                    total_items = cols_a * rows_a + cols_b * rows_b
                    if total_items == 0:
                        continue
                    slack = (container_length - length_used) * container_width
                    slack += cols_a * (container_width - rows_a * counts[0][1][0]) * counts[0][1][1]
                    slack += cols_b * (container_width - rows_b * counts[1][1][0]) * counts[1][1][0]
                    layout: List[Tuple[int, Tuple[float, float, float], int]] = []
                    layout.extend([(*counts[0], rows_a)] * cols_a)
                    layout.extend([(*counts[1], rows_b)] * cols_b)
                    score = (total_items, -slack)
                    if not best or score > (best[0], -best[1]):
                        best = (total_items, slack, layout)
        return best


def get_supporters(
    container: Container,
    x: float,
    y: float,
    z: float,
    dims: Tuple[float, float, float],
    eps: float = 1e-5,
) -> List[Item]:
    """Get list of items directly supporting this placement."""
    supporters = []
    if z < eps:
        return supporters

    dx, dy = dims[0], dims[1]
    item_x1, item_y1 = x, y
    item_x2, item_y2 = x + dx, y + dy

    for placed in container.items:
        if placed.position is None:
            continue

        px, py, pz = placed.position
        pdims = placed.get_rotated_dimensions()
        placed_top_z = pz + pdims[2]

        if abs(placed_top_z - z) > eps:
            continue

        if (item_x1 < px + pdims[0] + eps and item_x2 > px - eps and
            item_y1 < py + pdims[1] + eps and item_y2 > py - eps):
            supporters.append(placed)

    return supporters


def clone_container(container: Container) -> Container:
    return Container(
        id=container.id,
        type_id=container.type_id,
        length=container.length,
        width=container.width,
        height=container.height,
        max_weight=container.max_weight,
        exlength=container.exlength,
        exwidth=container.exwidth,
        exheight=container.exheight,
        exweight=container.exweight,
        pickup_priority=container.pickup_priority,
        door_position=container.door_position,
        origin=container.origin,
    )

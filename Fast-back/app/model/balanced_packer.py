"""
Balanced 3D Bin Packing Implementation for Mixed-SKU Pallet Placement.

This module implements a balanced weight distribution system using:
- Quadrant-based balance tracking
- Grid-based weight distribution
- Extreme point management with TOP surface support
- Comprehensive scoring system

Based on the implementation plan in pallet_mixed_item_placement_info_improved.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from .entities import (
    EPS,
    Item,
    Container,
    OrientationCache,
    Placement,
    clone_container,
    clone_item,
)
from .geometry import (
    check_bounds_within_container,
    check_collision_numba,
    check_support_and_stacking_numba,
)
from .common_packers import get_supporters


class QuadrantBalancer:
    """
    Tracks and enforces balanced distribution across pallet floor quadrants.
    Prevents L-shaped clustering and ensures even weight distribution.
    """

    def __init__(self, container_width: float, container_length: float):
        self.width = container_width
        self.length = container_length
        self.mid_x = container_width / 2
        self.mid_y = container_length / 2

        # Track floor coverage per quadrant (%)
        self.quadrant_coverage: Dict[str, float] = {
            'Q1': 0.0,  # x >= mid_x, y >= mid_y (back-right)
            'Q2': 0.0,  # x < mid_x,  y >= mid_y (back-left)
            'Q3': 0.0,  # x < mid_x,  y < mid_y  (front-left)
            'Q4': 0.0,  # x >= mid_x, y < mid_y  (front-right)
        }

        # Track weight per quadrant
        self.quadrant_weight: Dict[str, float] = {
            'Q1': 0.0, 'Q2': 0.0, 'Q3': 0.0, 'Q4': 0.0
        }

        # Track item placements per quadrant
        self.quadrant_items: Dict[str, List[Placement]] = {
            'Q1': [], 'Q2': [], 'Q3': [], 'Q4': []
        }

        # Floor area per quadrant
        self.quadrant_area = (container_width / 2) * (container_length / 2)

    def get_quadrant(self, x: float, y: float, w: float, l: float) -> str:
        """
        Determine primary quadrant for item placement.
        Returns quadrant where item's CENTER resides.
        """
        center_x = x + w / 2
        center_y = y + l / 2

        if center_x >= self.mid_x and center_y >= self.mid_y:
            return 'Q1'
        elif center_x < self.mid_x and center_y >= self.mid_y:
            return 'Q2'
        elif center_x < self.mid_x and center_y < self.mid_y:
            return 'Q3'
        else:
            return 'Q4'

    def add_floor_item(self, placement: Placement, item: Item) -> None:
        """Register a floor-level item placement."""
        if placement.z > 0.01:
            return

        x, y = placement.x, placement.y
        w, l = placement.dims[0], placement.dims[1]

        quad = self.get_quadrant(x, y, w, l)

        # Update coverage
        footprint_area = w * l
        coverage_increase = (footprint_area / self.quadrant_area) * 100 if self.quadrant_area > 0 else 0
        self.quadrant_coverage[quad] += coverage_increase

        # Update weight
        self.quadrant_weight[quad] += item.weight

        # Track placement
        self.quadrant_items[quad].append(placement)

    def add_stacked_item(self, placement: Placement, item: Item) -> None:
        """Register a stacked item (z > 0)."""
        if placement.z <= 0.01:
            return

        x, y = placement.x, placement.y
        w, l = placement.dims[0], placement.dims[1]
        quad = self.get_quadrant(x, y, w, l)

        self.quadrant_weight[quad] += item.weight

    def get_least_utilized_quadrants(self, n: int = 2) -> List[str]:
        """Return n quadrants with lowest floor coverage."""
        sorted_quads = sorted(
            self.quadrant_coverage.items(),
            key=lambda x: x[1]
        )
        return [q[0] for q in sorted_quads[:n]]

    def get_imbalance_penalty(self) -> float:
        """
        Calculate quadrant imbalance penalty.
        Returns 0 for perfect balance, higher for worse imbalance.
        """
        weights = list(self.quadrant_weight.values())
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        avg_weight = total_weight / 4
        variance = sum((w - avg_weight) ** 2 for w in weights) / 4

        # Also penalize coverage imbalance
        coverages = list(self.quadrant_coverage.values())
        avg_coverage = sum(coverages) / 4 if coverages else 0
        coverage_variance = sum((c - avg_coverage) ** 2 for c in coverages) / 4 if coverages else 0

        # Normalized combined score
        weight_imbalance = variance / (avg_weight ** 2 + 0.01)
        coverage_imbalance = coverage_variance / 100

        return weight_imbalance + coverage_imbalance

    def should_prefer_quadrant(
        self,
        quad: str,
        item: Item,
        total_items: int,
        placed_count: int
    ) -> bool:
        """
        Strategic decision: should we prefer this quadrant for this item?

        Strategy:
        - Early phase (0–30%): distribute heavy items across all quadrants
        - Middle phase (30–70%): balance coverage
        - Late phase (70–100%): fill remaining space anywhere
        """
        progress = placed_count / total_items if total_items > 0 else 0

        # Early phase: distribute heavy items across underused quadrants
        if progress < 0.3:
            if item.weight > 0:
                least_used = self.get_least_utilized_quadrants(2)
                return quad in least_used

        # Middle phase: balance coverage
        elif progress < 0.7:
            return self.quadrant_coverage[quad] < 60

        # Late phase: fill remaining space anywhere
        return True

    def get_quadrant_preference_score(
        self,
        x: float,
        y: float,
        w: float,
        l: float,
        item: Item,
        total_items: int,
        placed_count: int
    ) -> float:
        """
        Score based on quadrant balance strategy.
        Lower = better placement for maintaining balance.
        """
        quad = self.get_quadrant(x, y, w, l)

        # Penalize overused quadrants (coverage)
        coverage_penalty = self.quadrant_coverage[quad] * 10

        # Penalize weight-heavy quadrants for heavy items
        total_weight = sum(self.quadrant_weight.values())
        if total_weight > 0 and item.weight > 0:
            weight_ratio = self.quadrant_weight[quad] / total_weight
            weight_penalty = weight_ratio * 100 * item.weight
        else:
            weight_penalty = 0.0

        # Strategic preference bonus/penalty
        if self.should_prefer_quadrant(quad, item, total_items, placed_count):
            strategic_bonus = -50  # negative = good
        else:
            strategic_bonus = 100  # positive = avoid

        return coverage_penalty + weight_penalty + strategic_bonus


class WeightDistributionTracker:
    """
    Tracks weight distribution across pallet floor using a grid system.
    Finer granularity than quadrants for detailed balance analysis.
    """

    def __init__(self, container_width: float, container_length: float, grid_size: int = 4):
        self.grid_size = grid_size
        self.width = container_width
        self.length = container_length
        self.cell_width = container_width / grid_size if grid_size > 0 else container_width
        self.cell_length = container_length / grid_size if grid_size > 0 else container_length

        # Track cumulative weight per floor cell [row][col]
        self.weight_grid: List[List[float]] = [[0.0] * grid_size for _ in range(grid_size)]

    def add_item_weight(self, placement: Placement, item: Item) -> None:
        """Distribute item weight across floor cells it occupies."""
        x, y = placement.x, placement.y
        w, l = placement.dims[0], placement.dims[1]

        # Find grid cells this item overlaps
        cells = self._get_overlapping_cells(x, y, w, l)

        # Distribute weight proportionally by overlapping area
        total_overlap = sum(overlap for _, _, overlap in cells)
        if total_overlap > 0:
            for cell_x, cell_y, overlap_area in cells:
                weight_fraction = overlap_area / total_overlap
                if 0 <= cell_y < self.grid_size and 0 <= cell_x < self.grid_size:
                    self.weight_grid[cell_y][cell_x] += item.weight * weight_fraction

    def get_weight_balance_penalty(self) -> float:
        """
        Calculate weight imbalance penalty.
        Returns 0 for perfect balance, higher for imbalance.
        """
        total_weight = sum(sum(row) for row in self.weight_grid)
        if total_weight == 0:
            return 0.0

        num_cells = self.grid_size ** 2
        avg_weight = total_weight / num_cells
        variance = sum(
            (cell - avg_weight) ** 2
            for row in self.weight_grid
            for cell in row
        )

        # Normalized variance
        return variance / (avg_weight ** 2 + 0.01)

    def get_center_bias_score(
        self,
        x: float,
        y: float,
        w: float,
        l: float
    ) -> float:
        """
        Score favoring center placement.
        Lower = better for heavy items (closer to center).
        """
        item_center_x = x + w / 2
        item_center_y = y + l / 2
        container_center_x = self.width / 2
        container_center_y = self.length / 2

        distance_from_center = (
            (item_center_x - container_center_x) ** 2 +
            (item_center_y - container_center_y) ** 2
        ) ** 0.5

        return distance_from_center

    def _get_overlapping_cells(
        self,
        x: float,
        y: float,
        w: float,
        l: float
    ) -> List[Tuple[int, int, float]]:
        """
        Find grid cells overlapped by item.
        Returns list of (cell_x, cell_y, overlap_area).
        """
        cells: List[Tuple[int, int, float]] = []
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                cell_x = j * self.cell_width
                cell_y = i * self.cell_length

                overlap = self._calculate_overlap_area(
                    (x, y, w, l),
                    (cell_x, cell_y, self.cell_width, self.cell_length)
                )
                if overlap > 0:
                    cells.append((j, i, overlap))
        return cells

    @staticmethod
    def _calculate_overlap_area(
        rect1: Tuple[float, float, float, float],
        rect2: Tuple[float, float, float, float]
    ) -> float:
        """Calculate overlapping area between two rectangles."""
        x1, y1, w1, l1 = rect1
        x2, y2, w2, l2 = rect2

        x_overlap = max(0.0, min(x1 + w1, x2 + w2) - max(x1, x2))
        y_overlap = max(0.0, min(y1 + l1, y2 + l2) - max(y1, y2))

        return x_overlap * y_overlap


class ExtremePointManager:
    """
    Manages extreme points for corner/empty-space placement heuristic.
    CRITICAL: Generates points on TOP surfaces for vertical stacking.
    """

    def __init__(self, container: Container, seed_all_corners: bool = True):
        self.container = container
        ox, oy, oz = container.origin
        
        if seed_all_corners:
            # Seed with all four floor corners to encourage quadrant distribution
            self.extreme_points: List[Tuple[float, float, float]] = [
                (ox, oy, oz),                                    # front-left (Q3)
                (ox + container.width / 2, oy, oz),              # front-center
                (ox, oy + container.length / 2, oz),             # left-center
                (ox + container.width / 2, oy + container.length / 2, oz),  # center
            ]
        else:
            self.extreme_points: List[Tuple[float, float, float]] = [(ox, oy, oz)]

    def update_extreme_points(self, placement: Placement) -> None:
        """
        Generate new extreme points from placed item.
        CRITICAL: Include TOP surface corners for stacking.
        """
        x, y, z = placement.x, placement.y, placement.z
        w, l, h = placement.dims

        # Generate 7 potential new extreme points
        new_eps = [
            # BOTTOM LAYER (same z-level)
            (x + w, y, z),          # right-front corner
            (x, y + l, z),          # left-back corner
            (x + w, y + l, z),      # right-back corner

            # TOP LAYER (z + height) — CRITICAL FOR STACKING
            (x, y, z + h),          # top - left-front
            (x + w, y, z + h),      # top - right-front
            (x, y + l, z + h),      # top - left-back
            (x + w, y + l, z + h),  # top - right-back
        ]

        # Remove the EP that was used for this placement
        placement_ep = (x, y, z)
        self.extreme_points = [
            ep for ep in self.extreme_points 
            if not (abs(ep[0] - x) < EPS and abs(ep[1] - y) < EPS and abs(ep[2] - z) < EPS)
        ]

        # Filter out invalid points and add new ones
        for new_ep in new_eps:
            if self._is_valid_ep(new_ep, placement):
                self.extreme_points.append(new_ep)

        # Remove duplicate points
        self.extreme_points = self._remove_dominated_points(self.extreme_points)

        # Sort by z → x → y to fill lower layers first
        self.extreme_points.sort(key=lambda ep: (ep[2], ep[0], ep[1]))

    def _is_valid_ep(
        self,
        ep: Tuple[float, float, float],
        placement: Placement
    ) -> bool:
        """Check if EP is valid (within container bounds, not strictly inside the placed box)."""
        x, y, z = ep
        px, py, pz = placement.x, placement.y, placement.z
        w, l, h = placement.dims

        ox, oy, oz = self.container.origin

        # EP must be within container bounds (with small tolerance)
        if x < ox - EPS or x > ox + self.container.width + EPS:
            return False
        if y < oy - EPS or y > oy + self.container.length + EPS:
            return False
        if z < oz - EPS or z > oz + self.container.height + EPS:
            return False

        # EP cannot be strictly inside the box (boundary is OK)
        if (px + EPS < x < px + w - EPS and
            py + EPS < y < py + l - EPS and
            pz + EPS < z < pz + h - EPS):
            return False

        return True

    def _remove_dominated_points(
        self,
        eps: List[Tuple[float, float, float]]
    ) -> List[Tuple[float, float, float]]:
        """
        Remove duplicate EPs and those that are too close together.
        Note: We keep all valid EPs to maximize placement options.
        """
        if not eps:
            return []
        
        # Remove exact duplicates using a set with rounded values
        seen: Set[Tuple[float, float, float]] = set()
        unique_eps: List[Tuple[float, float, float]] = []
        
        for ep in eps:
            # Round to avoid floating point issues
            rounded = (round(ep[0], 2), round(ep[1], 2), round(ep[2], 2))
            if rounded not in seen:
                seen.add(rounded)
                unique_eps.append(ep)
        
        return unique_eps
    
    def _remove_dominated_points_strict(
        self,
        eps: List[Tuple[float, float, float]]
    ) -> List[Tuple[float, float, float]]:
        """
        Remove dominated EPs (Pareto optimization) - stricter version.
        An EP is dominated if another EP is <= in all dimensions and < in at least one.
        """
        non_dominated: List[Tuple[float, float, float]] = []
        for ep1 in eps:
            dominated = False
            for ep2 in eps:
                if ep1 == ep2:
                    continue
                if (ep2[0] <= ep1[0] + EPS and
                    ep2[1] <= ep1[1] + EPS and
                    ep2[2] <= ep1[2] + EPS and
                    (ep2[0] < ep1[0] - EPS or ep2[1] < ep1[1] - EPS or ep2[2] < ep1[2] - EPS)):
                    dominated = True
                    break
            if not dominated:
                non_dominated.append(ep1)
        return non_dominated

    def select_best_extreme_points(
        self,
        quadrant_balancer: QuadrantBalancer,
        max_candidates: int = 15
    ) -> List[Tuple[float, float, float]]:
        """
        Select diverse set of EPs covering all quadrants.
        Prevents L-shaped clustering by ensuring all floor regions are considered.
        """
        if len(self.extreme_points) <= max_candidates:
            return self.extreme_points.copy()

        # Separate floor-level and stacking points
        floor_eps = [ep for ep in self.extreme_points if ep[2] <= 0.01]
        stacking_eps = [ep for ep in self.extreme_points if ep[2] > 0.01]

        # Categorize floor EPs by quadrant
        ep_by_quad: Dict[str, List[Tuple[float, float, float]]] = {
            'Q1': [], 'Q2': [], 'Q3': [], 'Q4': []
        }

        mid_x = self.container.width / 2
        mid_y = self.container.length / 2

        for ep in floor_eps:
            x, y, _ = ep
            if x >= mid_x and y >= mid_y:
                ep_by_quad['Q1'].append(ep)
            elif x < mid_x and y >= mid_y:
                ep_by_quad['Q2'].append(ep)
            elif x < mid_x and y < mid_y:
                ep_by_quad['Q3'].append(ep)
            else:
                ep_by_quad['Q4'].append(ep)

        # Select EPs from each quadrant proportionally
        selected: List[Tuple[float, float, float]] = []
        least_used = quadrant_balancer.get_least_utilized_quadrants(4)

        quota_per_quad = max(2, max_candidates // 6)
        for quad in least_used:
            selected.extend(ep_by_quad[quad][:quota_per_quad])

        # Add stacking points (z > 0)
        stacking_quota = max_candidates - len(selected)
        selected.extend(stacking_eps[:stacking_quota])

        return selected[:max_candidates]

    def get_extreme_points(self) -> List[Tuple[float, float, float]]:
        """Get current list of extreme points."""
        return self.extreme_points.copy()


class PlacementScorer:
    """
    Scores candidate placements to find optimal position.
    Lower score = better placement.
    """

    @staticmethod
    def score_candidate(
        container: Container,
        position: Tuple[float, float, float],
        dims: Tuple[float, float, float],
        item: Item,
        weight_tracker: WeightDistributionTracker,
        quadrant_balancer: QuadrantBalancer,
        placed: List[Placement],
        total_items: int,
        placed_count: int
    ) -> float:
        """
        Complete scoring with stacking pickup_priority + weight distribution.

        Components:
        1. Height pickup_priority
        2. Quadrant balance
        3. Heavy item clustering penalty
        4. Space utilization (waste below/around)
        5. Corner preference (soft)
        """
        x, y, z = position
        w, l, h = dims

        score = 0.0

        # 1. HEIGHT PRIORITY
        if z <= 0.01:
            height_score = 0.0  # floor is ideal
            quadrant_score = quadrant_balancer.get_quadrant_preference_score(
                x, y, w, l, item, total_items, placed_count
            )
            quadrant_weight = 500  # heavy weight on quadrant balance
        else:
            height_score = z * 100.0  # prefer lower stacks
            quadrant_score = 0.0
            quadrant_weight = 0.0

        score += height_score
        score += quadrant_score * (quadrant_weight / 500)  # Normalize

        # 2. SPREAD HEAVY ITEMS
        median_weight = PlacementScorer._get_median_weight(placed)
        if item.weight > median_weight:
            if z <= 0.01:
                clustering_penalty = PlacementScorer._calculate_heavy_item_clustering(
                    placed, x, y, w, l, item.weight, median_weight
                )
                score += clustering_penalty * 200.0

        # 3. SPACE UTILIZATION
        waste_below = PlacementScorer._calculate_waste_below(
            placed, x, y, z, w, l
        )
        waste_around = PlacementScorer._calculate_waste_around(
            placed, position, dims, container
        )
        utilization_score = waste_below * 5.0 + waste_around * 2.0
        score += utilization_score

        # 4. CORNER PREFERENCE (very weak)
        corner_score = (x + y) * 0.01
        score += corner_score

        return score

    @staticmethod
    def _get_median_weight(placed: List[Placement]) -> float:
        """Calculate median weight of placed items."""
        if not placed:
            return 0.0
        weights = sorted(p.item.weight for p in placed)
        n = len(weights)
        if n % 2 == 0:
            return (weights[n // 2 - 1] + weights[n // 2]) / 2
        return weights[n // 2]

    @staticmethod
    def _calculate_heavy_item_clustering(
        placed: List[Placement],
        x: float,
        y: float,
        w: float,
        l: float,
        item_weight: float,
        median_weight: float
    ) -> float:
        """
        Penalize placing heavy items near other heavy items on the floor.
        Encourages spreading heavy items across the pallet.
        """
        center_x = x + w / 2
        center_y = y + l / 2

        penalty = 0.0

        for p in placed:
            if p.z > 0.01:
                continue
            if p.item.weight > median_weight:
                p_center_x = p.x + p.dims[0] / 2
                p_center_y = p.y + p.dims[1] / 2

                distance = ((center_x - p_center_x) ** 2 +
                            (center_y - p_center_y) ** 2) ** 0.5

                if distance < 500.0:  # within 500 mm
                    penalty += (500.0 - distance) * item_weight * 0.1

        return penalty

    @staticmethod
    def _calculate_waste_below(
        placed: List[Placement],
        x: float,
        y: float,
        z: float,
        w: float,
        l: float
    ) -> float:
        """
        Approximate empty space below this position.
        Penalizes floating placements.
        """
        if z <= 0.01:
            return 0.0

        # Simplified: vertical gap volume
        waste_volume = z * w * l * 0.1
        return waste_volume

    @staticmethod
    def _calculate_waste_around(
        placed: List[Placement],
        position: Tuple[float, float, float],
        dims: Tuple[float, float, float],
        container: Container
    ) -> float:
        """
        Calculate wasted space around the placement.
        Prefers tight fits against container walls.
        """
        x, y, z = position
        w, l, h = dims

        waste = 0.0

        # Distances to container walls
        ox, oy, oz = container.origin
        waste += x - ox                              # left wall
        waste += y - oy                              # front wall
        waste += (ox + container.width - (x + w))   # right wall
        waste += (oy + container.length - (y + l))  # back wall

        return waste * 0.1


class PackingStrategySelector:
    """
    Selects the appropriate packing algorithm based on item characteristics.
    Uses percentage-based thresholds for size and weight variation.
    """

    SIZE_THRESHOLD = 10.0   # 10% size variation
    WEIGHT_THRESHOLD = 10.0  # 10% weight variation
    HEIGHT_THRESHOLD = 10.0  # 10% height variation

    @staticmethod
    def percent_size_difference(items: List[Item]) -> float:
        """Calculate percentage difference in item dimensions."""
        if not items:
            return 0.0

        all_dims: List[float] = []
        for item in items:
            all_dims.extend([item.width, item.length, item.height])

        max_dim = max(all_dims)
        min_dim = min(all_dims)
        if max_dim == 0:
            return 0.0

        return 100.0 * (max_dim - min_dim) / max_dim

    @staticmethod
    def percent_weight_difference(items: List[Item]) -> float:
        """Calculate percentage difference in item weights."""
        if not items:
            return 0.0

        weights = [item.weight for item in items]
        max_weight = max(weights)
        min_weight = min(weights)
        if max_weight == 0:
            return 0.0

        return 100.0 * (max_weight - min_weight) / max_weight

    @staticmethod
    def percent_height_difference(items: List[Item]) -> float:
        """Calculate percentage difference in item heights."""
        if not items:
            return 0.0

        heights = [item.height for item in items]
        max_height = max(heights)
        min_height = min(heights)
        if max_height == 0:
            return 0.0

        return 100.0 * (max_height - min_height) / max_height

    @staticmethod
    def select_algorithm(items: List[Item]) -> str:
        """
        Select packing algorithm based on item characteristics.

        Returns:
            "balanced_ep" - Extreme Point with quadrant balancing (default)
            "layer_based" - Layer/shelf packing (similar heights)
            "guillotine"  - Guillotine cuts (mixed sizes, no rotation)
            "hybrid"      - Complex cases (highly mixed)
        """
        size_diff = PackingStrategySelector.percent_size_difference(items)
        weight_diff = PackingStrategySelector.percent_weight_difference(items)
        height_diff = PackingStrategySelector.percent_height_difference(items)

        # CASE 1: Similar-size items
        if size_diff <= PackingStrategySelector.SIZE_THRESHOLD:
            # A) Similar-size + similar-height
            if height_diff <= PackingStrategySelector.HEIGHT_THRESHOLD:
                return "layer_based"
            else:
                return "balanced_ep"

        # CASE 2: Mixed-size items - always use balanced EP
        return "balanced_ep"


class BalancedBinPacker:
    """
    Main 3D bin packing algorithm with balanced weight distribution.
    Uses extreme point heuristic with quadrant balancing.
    """

    def __init__(
        self,
        container: Container,
        orientation_cache: Dict[int, OrientationCache],
        must_be_on_top: Optional[Dict[int, bool]] = None,
    ):
        self.container = container
        self.orientation_cache = orientation_cache
        self.must_be_on_top = must_be_on_top or {}
        self.EPS = 1e-5

        self.ep_manager = ExtremePointManager(container)
        self.weight_tracker = WeightDistributionTracker(
            container.width, container.length
        )
        self.quadrant_balancer = QuadrantBalancer(
            container.width, container.length
        )
        self.placed: List[Placement] = []

    def pack(self, items: List[Item]) -> List[Item]:
        """
        Pack items into container with balanced distribution.
        Returns list of items that could not be placed.
        """
        if not items:
            return []

        # Strategic ordering — distribute weight classes
        ordered_items = self._strategic_item_ordering(items)
        total_items = len(ordered_items)

        remaining: List[Item] = []

        for idx, item in enumerate(ordered_items):
            success = self._place_item(item, total_items, idx)
            if not success:
                remaining.append(item)

        return remaining

    def _place_item(
        self,
        item: Item,
        total_items: int,
        placed_count: int
    ) -> bool:
        """Find and commit the best position for a single item."""
        best_position: Optional[Tuple[
            Tuple[float, float, float],  # position
            int,                          # rotation
            Tuple[float, float, float],   # dims
            List[Item],                   # supporters
            int                           # layer
        ]] = None
        best_score = float('inf')

        # Get orientation cache for this item
        cache = self.orientation_cache.get(item.id)
        if not cache:
            cache = OrientationCache.build(item)

        # Select diverse EPs covering all quadrants
        candidate_eps = self.ep_manager.select_best_extreme_points(
            self.quadrant_balancer,
            max_candidates=15
        )

        for ep in candidate_eps:
            for rot in cache.rotations:
                dims = cache.dimensions[rot]

                # Bounds check
                if not self._fits_in_container(ep, dims):
                    continue

                # Collision check
                if self._collides(ep, dims):
                    continue

                # Support check
                supporters = self._find_supporters(ep, dims)
                is_valid, new_layer = self._has_valid_support(
                    item, ep, dims, supporters
                )
                if not is_valid:
                    continue

                # Weight constraint check
                if self.container.total_weight + item.weight > self.container.max_weight + self.EPS:
                    continue

                # Score the candidate
                score = PlacementScorer.score_candidate(
                    self.container, ep, dims, item,
                    self.weight_tracker, self.quadrant_balancer,
                    self.placed, total_items, placed_count
                )

                if score < best_score:
                    best_score = score
                    best_position = (ep, rot, dims, supporters, new_layer)

        if best_position is None:
            return False

        # Commit placement
        pos, rot, dims, supporters, layer = best_position
        placement = Placement(
            item=item,
            x=pos[0],
            y=pos[1],
            z=pos[2],
            rotation=rot,
            dims=dims,
            supporters=supporters,
            layer_level=layer,
        )

        # Update item state
        item.position = (pos[0], pos[1], pos[2])
        item.rotation = rot
        item.layer = layer

        # Update container
        self.container.items.append(item)
        self.container.total_weight += item.weight

        # Track placement
        self.placed.append(placement)

        # Update trackers
        self.weight_tracker.add_item_weight(placement, item)
        if placement.z <= 0.01:
            self.quadrant_balancer.add_floor_item(placement, item)
        else:
            self.quadrant_balancer.add_stacked_item(placement, item)

        # Update extreme points
        self.ep_manager.update_extreme_points(placement)

        return True

    def _fits_in_container(
        self,
        position: Tuple[float, float, float],
        dims: Tuple[float, float, float]
    ) -> bool:
        """Check if item fits within container bounds."""
        x, y, z = position
        dx, dy, dz = dims
        ox, oy, oz = self.container.origin

        return check_bounds_within_container(
            x, y, z, dx, dy, dz,
            ox, oy, oz,
            ox + self.container.width,
            oy + self.container.length,
            oz + self.container.height
        )

    def _collides(
        self,
        position: Tuple[float, float, float],
        dims: Tuple[float, float, float]
    ) -> bool:
        """Check for collision with placed items."""
        if not self.container.items:
            return False

        # Build placed items data for numba function
        placed_geom = np.zeros((len(self.container.items), 6), dtype=np.float64)
        for i, p_item in enumerate(self.container.items):
            if p_item.position is None:
                continue
            p_dims = p_item.get_rotated_dimensions()
            px, py, pz = p_item.position
            placed_geom[i, 0:3] = (px, py, pz)
            placed_geom[i, 3:6] = p_dims

        item_pos = np.array(position, dtype=np.float64)
        item_dims = np.array(dims, dtype=np.float64)

        return check_collision_numba(item_pos, item_dims, placed_geom, self.EPS)

    def _find_supporters(
        self,
        position: Tuple[float, float, float],
        dims: Tuple[float, float, float]
    ) -> List[Item]:
        """Find items supporting this position."""
        x, y, z = position
        return get_supporters(self.container, x, y, z, dims, self.EPS)

    def _has_valid_support(
        self,
        item: Item,
        position: Tuple[float, float, float],
        dims: Tuple[float, float, float],
        supporters: List[Item]
    ) -> Tuple[bool, int]:
        """Check if placement has valid support and stacking constraints."""
        x, y, z = position

        # Floor level - always supported
        if z < self.EPS:
            return True, 1

        # Build placed items data for numba function
        type_map: Dict[str, int] = {}
        next_tid = 1

        def get_type_int(type_id: str) -> int:
            nonlocal next_tid
            if type_id not in type_map:
                type_map[type_id] = next_tid
                next_tid += 1
            return type_map[type_id]

        placed_items_data = np.zeros((len(self.container.items), 15), dtype=np.float64)
        for i, p_item in enumerate(self.container.items):
            if p_item.position is None:
                continue
            p_dims = p_item.get_rotated_dimensions()
            px, py, pz = p_item.position
            placed_items_data[i, 0:3] = (px, py, pz)
            placed_items_data[i, 3:6] = p_dims
            placed_items_data[i, 6] = float(get_type_int(p_item.itemType_id))
            placed_items_data[i, 7] = float(getattr(p_item, "layer", 1))
            placed_items_data[i, 8] = float(p_item.maxStack)
            placed_items_data[i, 9] = float(p_item.maxStackWeight if p_item.maxStackWeight else 1e9)
            placed_items_data[i, 10] = 1.0 if self.must_be_on_top.get(
                p_item.id, getattr(p_item, "must_be_on_top", False)
            ) else 0.0
            placed_items_data[i, 11] = float(p_item.weight)
            placed_items_data[i, 12] = float(getattr(p_item, "pickup_priority", 1))
            placed_items_data[i, 13] = float(hash(getattr(p_item, "order_id", "")) % (2**31))
            placed_items_data[i, 14] = float(getattr(p_item, "senddate_ts", 0))

        item_pos = np.array(position, dtype=np.float64)
        item_dims = np.array(dims, dtype=np.float64)

        is_valid, new_layer = check_support_and_stacking_numba(
            item_pos=item_pos,
            item_dims=item_dims,
            item_type_id=int(get_type_int(item.itemType_id)),
            item_weight=float(item.weight),
            max_stack=int(item.maxStack),
            item_order_id_hash=float(hash(item.order_id) % (2**31)),
            item_senddate_ts=float(getattr(item, "senddate_ts", 0)),
            placed_items_data=placed_items_data,
            enforce_order_stacking=False,  # Pallet mode
            epsilon=self.EPS,
        )

        return is_valid, int(new_layer)

    def _strategic_item_ordering(
        self,
        items: List[Item]
    ) -> List[Item]:
        """
        Order items to encourage balanced floor distribution.
        Interleaves weight groups instead of strict heavy→light ordering.
        """
        if not items:
            return []

        sorted_by_weight = sorted(
            items,
            key=lambda i: i.weight,
            reverse=True
        )
        n = len(items)

        # Group into ~quartiles by weight
        groups: List[List[Item]] = []
        group_size = max(1, n // 4)

        for i in range(0, n, group_size):
            groups.append(sorted_by_weight[i:i + group_size])

        # Round-robin through groups
        ordered: List[Item] = []
        max_len = max(len(g) for g in groups) if groups else 0

        for i in range(max_len):
            for group in groups:
                if i < len(group):
                    ordered.append(group[i])

        return ordered

    def get_balance_score(self) -> float:
        """Get current balance score (lower is better)."""
        return self.quadrant_balancer.get_imbalance_penalty()

    def get_quadrant_stats(self) -> Dict[str, Dict[str, float]]:
        """Get quadrant statistics for debugging."""
        return {
            'coverage': dict(self.quadrant_balancer.quadrant_coverage),
            'weight': dict(self.quadrant_balancer.quadrant_weight),
        }


class MixedSkuPalletPacker:
    """
    Specialized packer for mixed-SKU pallets using balanced weight distribution.
    Integrates with existing pallet packing infrastructure.
    """

    def __init__(
        self,
        container: Container,
        orientation_cache: Dict[int, OrientationCache],
        must_be_on_top: Optional[Dict[int, bool]] = None,
        co_loc_groups: Optional[Dict[str, Set[int]]] = None,
    ):
        self.container = container
        self.orientation_cache = orientation_cache
        self.must_be_on_top = must_be_on_top or {}
        self.co_loc_groups = co_loc_groups or {}
        self.EPS = 1e-5

        # Initialize placements list (required by solver for layout caching)
        self.placements: List[Placement] = []

        # Initialize balance trackers
        self.quadrant_balancer = QuadrantBalancer(
            container.width, container.length
        )
        self.weight_tracker = WeightDistributionTracker(
            container.width, container.length
        )

    def pack(self, items: List[Item]) -> List[Item]:
        """
        Pack mixed-SKU items with balanced weight distribution.
        Returns list of items that could not be placed.
        """
        if not items:
            return []

        # Analyze items to select strategy
        algorithm = PackingStrategySelector.select_algorithm(items)

        if algorithm == "layer_based":
            return self._pack_layer_based(items)
        else:
            return self._pack_balanced_ep(items)

    def _pack_balanced_ep(self, items: List[Item]) -> List[Item]:
        """Pack using balanced extreme point algorithm."""
        packer = BalancedBinPacker(
            self.container,
            self.orientation_cache,
            self.must_be_on_top,
        )
        remaining = packer.pack(items)
        
        # Copy trackers and placements back for metrics reporting and layout caching
        self.quadrant_balancer = packer.quadrant_balancer
        self.weight_tracker = packer.weight_tracker
        self.placements = packer.placed  # Copy placements for layout caching
        
        return remaining

    def _pack_layer_based(self, items: List[Item]) -> List[Item]:
        """
        Pack similar-height items in layers.
        Falls back to balanced EP if layer packing fails.
        """
        if not items:
            return []

        # Group items by similar height
        height_groups = self._group_by_height(items)

        remaining: List[Item] = []
        current_z = 0.0

        for height, group_items in sorted(height_groups.items()):
            # Try to pack this layer
            layer_remaining = self._pack_single_layer(
                group_items, current_z, height
            )
            remaining.extend(layer_remaining)

            # Update z for next layer
            if len(layer_remaining) < len(group_items):
                current_z += height

        # Try balanced EP for remaining items
        if remaining:
            packer = BalancedBinPacker(
                self.container,
                self.orientation_cache,
                self.must_be_on_top,
            )
            remaining = packer.pack(remaining)
            
            # Copy placements from fallback packer
            self.placements.extend(packer.placed)

        return remaining

    def _group_by_height(
        self,
        items: List[Item],
        tolerance: float = 10.0
    ) -> Dict[float, List[Item]]:
        """Group items by similar height within tolerance."""
        groups: Dict[float, List[Item]] = {}

        for item in items:
            # Find existing group within tolerance
            matched_height = None
            for h in groups.keys():
                if abs(item.height - h) <= tolerance:
                    matched_height = h
                    break

            if matched_height is not None:
                groups[matched_height].append(item)
            else:
                groups[item.height] = [item]

        return groups

    def _pack_single_layer(
        self,
        items: List[Item],
        z_level: float,
        layer_height: float
    ) -> List[Item]:
        """Pack items in a single layer at given z-level."""
        from .common_packers import MaxRects2D

        # Check if layer fits in container
        if z_level + layer_height > self.container.height + self.EPS:
            return items

        packer_2d = MaxRects2D(self.container.length, self.container.width)
        remaining: List[Item] = []

        # Sort by footprint (largest first) then weight
        sorted_items = sorted(
            items,
            key=lambda it: (-(it.width * it.length), -it.weight, it.id)
        )

        for item in sorted_items:
            # Check weight constraint
            if self.container.total_weight + item.weight > self.container.max_weight + self.EPS:
                remaining.append(item)
                continue

            cache = self.orientation_cache.get(item.id)
            if not cache:
                cache = OrientationCache.build(item)

            placed = False
            for rot in cache.rotations:
                dims = cache.dimensions[rot]

                # Try to find position using quadrant preference
                rect = self._find_balanced_position(
                    packer_2d, dims[0], dims[1], item
                )

                if rect is None:
                    continue

                x, y = rect.x, rect.y

                # Validate placement
                if not self._validate_layer_placement(
                    item, x, y, z_level, dims
                ):
                    continue

                # Commit placement
                packer_2d.commit(rect)
                self._commit_placement(item, x, y, z_level, rot, dims)
                placed = True
                break

            if not placed:
                remaining.append(item)

        return remaining

    def _find_balanced_position(
        self,
        packer: "MaxRects2D",
        width: float,
        height: float,
        item: Item
    ) -> Optional["Rect"]:
        """Find position that maintains quadrant balance."""
        from .common_packers import Rect

        # Get least utilized quadrants
        least_used = self.quadrant_balancer.get_least_utilized_quadrants(2)

        best_rect: Optional[Rect] = None
        best_score = float('inf')

        for free in packer.free_rects:
            # Try normal orientation
            if width <= free.width + EPS and height <= free.height + EPS:
                rect = Rect(free.x, free.y, width, height, rotated=False)
                score = self._score_rect_position(rect, item, least_used)
                if score < best_score:
                    best_score = score
                    best_rect = rect

            # Try rotated orientation
            if height <= free.width + EPS and width <= free.height + EPS:
                rect = Rect(free.x, free.y, height, width, rotated=True)
                score = self._score_rect_position(rect, item, least_used)
                if score < best_score:
                    best_score = score
                    best_rect = rect

        return best_rect

    def _score_rect_position(
        self,
        rect: "Rect",
        item: Item,
        preferred_quads: List[str]
    ) -> float:
        """Score a rectangle position for balance."""
        quad = self.quadrant_balancer.get_quadrant(
            rect.x, rect.y, rect.width, rect.height
        )

        score = 0.0

        # Prefer least utilized quadrants
        if quad in preferred_quads:
            score -= 100.0

        # Penalize overused quadrants
        score += self.quadrant_balancer.quadrant_coverage[quad] * 10

        # For heavy items, prefer center
        if item.weight > 0:
            center_dist = self.weight_tracker.get_center_bias_score(
                rect.x, rect.y, rect.width, rect.height
            )
            score += center_dist * (item.weight / 100)

        return score

    def _validate_layer_placement(
        self,
        item: Item,
        x: float,
        y: float,
        z: float,
        dims: Tuple[float, float, float]
    ) -> bool:
        """Validate placement for layer-based packing."""
        ox, oy, oz = self.container.origin

        # Bounds check
        if not check_bounds_within_container(
            x, y, z, dims[0], dims[1], dims[2],
            ox, oy, oz,
            ox + self.container.width,
            oy + self.container.length,
            oz + self.container.height
        ):
            return False

        # Collision check
        if self.container.items:
            placed_geom = np.zeros((len(self.container.items), 6), dtype=np.float64)
            for i, p_item in enumerate(self.container.items):
                if p_item.position is None:
                    continue
                p_dims = p_item.get_rotated_dimensions()
                px, py, pz = p_item.position
                placed_geom[i, 0:3] = (px, py, pz)
                placed_geom[i, 3:6] = p_dims

            item_pos = np.array([x, y, z], dtype=np.float64)
            item_dims = np.array(dims, dtype=np.float64)

            if check_collision_numba(item_pos, item_dims, placed_geom, self.EPS):
                return False

        # Grounded constraint
        if item.grounded and z > self.EPS:
            return False

        return True

    def _commit_placement(
        self,
        item: Item,
        x: float,
        y: float,
        z: float,
        rotation: int,
        dims: Tuple[float, float, float]
    ) -> None:
        """Commit item placement and update trackers."""
        item.position = (x, y, z)
        item.rotation = rotation
        item.layer = self._compute_layer_number(z)

        self.container.items.append(item)
        self.container.total_weight += item.weight

        # Create placement for tracking
        placement = Placement(
            item=item,
            x=x,
            y=y,
            z=z,
            rotation=rotation,
            dims=dims,
            supporters=[],
            layer_level=item.layer,
        )

        # Add to placements list for layout caching
        self.placements.append(placement)

        # Update balance trackers
        self.weight_tracker.add_item_weight(placement, item)
        if z <= 0.01:
            self.quadrant_balancer.add_floor_item(placement, item)
        else:
            self.quadrant_balancer.add_stacked_item(placement, item)

    def _compute_layer_number(self, z: float) -> int:
        """Compute layer number based on z position."""
        if z < self.EPS:
            return 1

        z_levels = set()
        for item in self.container.items:
            if item.position:
                z_levels.add(round(item.position[2], 3))

        z_levels.add(round(z, 3))
        sorted_levels = sorted(z_levels)

        for i, level in enumerate(sorted_levels):
            if abs(level - z) < self.EPS:
                return i + 1

        return len(sorted_levels) + 1

    def get_balance_metrics(self) -> Dict[str, any]:
        """Get balance metrics for analysis."""
        return {
            'imbalance_score': self.quadrant_balancer.get_imbalance_penalty(),
            'weight_balance_penalty': self.weight_tracker.get_weight_balance_penalty(),
            'quadrant_coverage': dict(self.quadrant_balancer.quadrant_coverage),
            'quadrant_weight': dict(self.quadrant_balancer.quadrant_weight),
        }


# Export all classes
__all__ = [
    'QuadrantBalancer',
    'WeightDistributionTracker',
    'ExtremePointManager',
    'PlacementScorer',
    'PackingStrategySelector',
    'BalancedBinPacker',
    'MixedSkuPalletPacker',
]

from __future__ import annotations

import copy
import time
import traceback
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict
from itertools import permutations, combinations

from .entities import *
from .geometry import *
from .packers import *

from .. import schemas
from app.logger import logger


def _grid_fallback_generic(container: Container, items: List[Item]) -> Optional[Set[int]]:
    """
    Grid-based fallback packing optimization for uniform or near-uniform item sets.
    
    This function attempts to tile items perfectly in a single container by:
    1. Grouping items by their dimensions (SKU signature)
    2. Finding optimal rotation for each item type
    3. Computing how many items fit per layer and how many layers fit
    4. Placing items in a regular grid pattern
    
    Works best when items are uniform (same dimensions) or have compatible dimensions.
    
    Args:
        container: The container to pack items into
        items: List of items to pack
        
    Returns:
        Set of placed item IDs if all items were successfully placed, None otherwise
    """
    if not items:
        return set()
    
    # Group items by their geometric signature (dimensions + constraints)
    def geo_key(item: Item) -> Tuple:
        return (
            round(item.length, 4),
            round(item.width, 4),
            round(item.height, 4),
            item.isSideUp,
            item.maxStack,
            item.grounded,
        )
    
    groups: Dict[Tuple, List[Item]] = {}
    for item in items:
        key = geo_key(item)
        groups.setdefault(key, []).append(item)
    
    # For simplicity, this optimization works best with uniform items (single group)
    # or a small number of compatible groups
    if len(groups) > 3:
        return None  # Too many different item types, fall back to standard packing
    
    # Check total weight constraint
    total_weight = sum(item.weight for item in items)
    if total_weight > container.max_weight + EPS:
        return None
    
    # Check total volume constraint (quick feasibility check)
    total_volume = sum(item.volume for item in items)
    if total_volume > container.volume + EPS:
        return None
    
    placed_ids: Set[int] = set()
    current_z = 0.0
    remaining_items = list(items)
    
    # Sort items: grounded items first, then by weight descending for stability
    remaining_items.sort(key=lambda it: (not it.grounded, -it.weight, -it.volume, it.id))
    
    # Process items layer by layer
    while remaining_items and current_z < container.height - EPS:
        # Find items that can be placed at this z level
        layer_candidates = []
        for item in remaining_items:
            # Grounded items can only go on floor
            if item.grounded and current_z > EPS:
                continue
            layer_candidates.append(item)
        
        if not layer_candidates:
            break
        
        # Try to fill this layer using grid placement
        layer_placed, layer_height = _fill_layer_grid(
            container, layer_candidates, current_z, placed_ids
        )
        
        if not layer_placed:
            break
        
        # Update state
        for item in layer_placed:
            placed_ids.add(item.id)
            remaining_items.remove(item)
        
        current_z += layer_height
    
    # Only return success if ALL items were placed
    if len(placed_ids) == len(items):
        return placed_ids
    else:
        # Rollback: clear positions for items that were placed
        for item in items:
            if item.id in placed_ids:
                item.position = None
                item.rotation = 0
                if item in container.items:
                    container.items.remove(item)
        container.total_weight = 0.0
        return None


def _fill_layer_grid(
    container: Container,
    candidates: List[Item],
    z: float,
    already_placed: Set[int],
) -> Tuple[List[Item], float]:
    """
    Fill a single layer at height z using grid-based placement.
    
    Args:
        container: The container to place items in
        candidates: Items available for this layer
        z: Z coordinate for this layer
        already_placed: Set of item IDs already placed (to avoid duplicates)
        
    Returns:
        Tuple of (list of items placed in this layer, layer height)
    """
    if not candidates:
        return [], 0.0
    
    # Group candidates by dimensions to find the best tiling
    dim_groups: Dict[Tuple[float, float, float], List[Tuple[Item, int]]] = {}
    
    for item in candidates:
        if item.id in already_placed:
            continue
        
        # Try all allowed rotations
        rotations = [0, 1] if item.isSideUp else [0, 1, 2, 3, 4, 5]
        
        for rot in rotations:
            dims = item.get_rotated_dimensions(rot)
            # Check if item fits in container at this rotation
            if (dims[0] <= container.width + EPS and 
                dims[1] <= container.length + EPS and
                z + dims[2] <= container.height + EPS):
                # Round dimensions for grouping
                key = (round(dims[0], 4), round(dims[1], 4), round(dims[2], 4))
                dim_groups.setdefault(key, []).append((item, rot))
                break  # Use first valid rotation
    
    if not dim_groups:
        return [], 0.0
    
    # Find the dimension group that can place the most items
    best_placement: List[Tuple[Item, int, float, float]] = []  # (item, rotation, x, y)
    best_height = 0.0
    
    for (dx, dy, dz), item_rot_list in dim_groups.items():
        # Calculate grid dimensions
        cols = int((container.width + EPS) / dx) if dx > EPS else 0
        rows = int((container.length + EPS) / dy) if dy > EPS else 0
        
        if cols <= 0 or rows <= 0:
            continue
        
        max_per_layer = cols * rows
        items_to_place = item_rot_list[:max_per_layer]
        
        if not items_to_place:
            continue
        
        # Check stacking constraints
        valid_items: List[Tuple[Item, int, float, float]] = []
        for idx, (item, rot) in enumerate(items_to_place):
            col = idx % cols
            row = idx // cols
            x = col * dx
            y = row * dy
            
            # Check maxStack constraint (layer count)
            if item.maxStack > 0:
                # Calculate which layer this would be
                layer_num = int(z / dz) + 1 if dz > EPS else 1
                if layer_num > item.maxStack:
                    continue
            
            valid_items.append((item, rot, x, y))
        
        if len(valid_items) > len(best_placement):
            best_placement = valid_items
            best_height = dz
    
    if not best_placement:
        return [], 0.0
    
    # Calculate the bounding box of all placements to center them
    if best_placement:
        # Get dimensions from first item (all items in best_placement have same dims)
        first_item, first_rot, _, _ = best_placement[0]
        item_dims = first_item.get_rotated_dimensions(first_rot)
        dx, dy = item_dims[0], item_dims[1]
        
        # Find the extent of the placement grid
        max_x = max(x + dx for _, _, x, _ in best_placement)
        max_y = max(y + dy for _, _, _, y in best_placement)
        
        # Calculate offset to center the group on the pallet
        offset_x = (container.width - max_x) / 2.0
        offset_y = (container.length - max_y) / 2.0
        
        # Ensure non-negative offsets
        offset_x = max(0.0, offset_x)
        offset_y = max(0.0, offset_y)
    else:
        offset_x = 0.0
        offset_y = 0.0
    
    # Place the items with centering offset
    placed_items: List[Item] = []
    for item, rot, x, y in best_placement:
        centered_x = x + offset_x
        centered_y = y + offset_y
        item.position = (centered_x, centered_y, z)
        item.rotation = rot
        item.layer = int(z / best_height) + 1 if best_height > EPS else 1
        container.items.append(item)
        container.total_weight += item.weight
        placed_items.append(item)
    
    return placed_items, best_height


class PackingSolver:
    """Top-level solver coordinating container selection and packing."""

    def __init__(
        self,
        containers: List[Container],
        items: List[Item],
        co_loc_groups: Optional[Dict[str, Set[int]]] = None,
        origin: Tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        self.containers = containers
        self.items = items
        self.must_be_on_top = {item.id: True for item in items if getattr(item, "must_be_on_top", False)}
        self.co_loc_groups = co_loc_groups or {}
        self.layout_cache: Dict[Tuple[str, int], List[PlacementTemplate]] = {}
        # Lightweight monitor instance used only in tests like test_support_calc
        # that call PackingSolver.support_monitor.support_ratio() directly.
        self.origin = origin
        # Apply origin to all containers
        for container in self.containers:
            container.origin = origin


    def solve(self) -> Dict[str, Any]:
        if not self.containers:
            return {"containers": [], "unused": self.items}

        trimmed_containers = self._cap_container_pool(self.containers, self.items)
        pool_trimmed = len(trimmed_containers) < len(self.containers)
        # Generic discrete-grid fallback: if there's a single container, try to
        # tile it perfectly by discovering unit sizes from the item dimensions.
        # try:
        #     if len(trimmed_containers) == 1:
        #         fallback_container = clone_container(trimmed_containers[0])
        #         fallback_items = [clone_item(it) for it in self.items]
        #         # Normalize priorities before packing
        #         self._normalize_priorities(fallback_items)
        #         placed_ids = _grid_fallback_generic(fallback_container, fallback_items)
        #         if placed_ids is not None and len(placed_ids) == len(fallback_items):
        #             self._sort_container_items_by_door(fallback_container)
        #             return {"containers": [fallback_container], "unused": []}
        # except Exception:
        #     pass

        containers = [clone_container(container) for container in trimmed_containers]
        items_copy = [clone_item(item) for item in self.items]
        # Compute final ranks FIRST before priorities are normalized
        self._compute_final_ranks(items_copy)
        # Then normalize priorities for packing constraints
        self._normalize_priorities(items_copy)
        orientation_cache = {item.id: OrientationCache.build(item) for item in items_copy}
        full_pool_cache: Dict[str, Any] = {}

        def maybe_use_full_pool(result: Dict[str, Any]) -> Dict[str, Any]:
            """
            When the container pool was trimmed and items remain unused, retry with
            the full pool of containers to avoid leaving items stranded simply
            because the cap was too aggressive.
            """
            if not pool_trimmed:
                return result
            if not result or not result.get("unused"):
                return result
            try:
                base_placed = len(self.items) - len(result["unused"])
                if "full_result" not in full_pool_cache:
                    full_items = [clone_item(item) for item in self.items]
                    self._compute_final_ranks(full_items)
                    self._normalize_priorities(full_items)
                    full_orientation_cache = {
                        item.id: OrientationCache.build(item) for item in full_items
                    }
                    full_containers = [clone_container(c) for c in self.containers]
                    full_pool_cache["full_result"] = self._pack_containers(
                        full_containers, full_items, full_orientation_cache
                    )
                full_result = full_pool_cache["full_result"]
                full_placed = len(self.items) - len(full_result["unused"])
                if full_placed > base_placed:
                    return full_result
            except Exception:
                pass
            return result

        # If every container shares the exact same template (single pallet/container
        # size offered in multiple copies), skip the combination selector and just
        # pack them sequentially so we can consume as many as needed.
        if self._is_single_template(containers) and len(containers) > 1:
            return maybe_use_full_pool(self._pack_containers(containers, items_copy, orientation_cache))


        combo_order = self._enumerate_container_combinations(containers, items_copy)
        if not combo_order:
            return self._pack_containers(containers, items_copy, orientation_cache)

        # Performance optimization for large instances: only evaluate top few combos
        LARGE_ITEM_THRESHOLD = 500
        MAX_COMBOS_TO_EVAL = 10

        if len(items_copy) >= LARGE_ITEM_THRESHOLD:
            # Large instance path: try only top N combos by analytical cost
            best_result: Optional[Dict[str, Any]] = None
            best_placed = -1
            best_combo_size = 0

            for combo in combo_order[:MAX_COMBOS_TO_EVAL]:
                working_containers = [clone_container(c) for c in combo]
                working_items = [clone_item(item) for item in items_copy]
                result = self._pack_containers(working_containers, working_items, orientation_cache)
                placed = len(items_copy) - len(result["unused"])

                if placed > best_placed:
                    best_result = result
                    best_placed = placed
                    best_combo_size = len(combo)

                # Early exit if perfect
                if not result["unused"]:
                    return result

            # Safety net: compare with "use everything" plan
            full_result = self._pack_containers(containers, [clone_item(item) for item in items_copy], orientation_cache)
            full_placed = len(items_copy) - len(full_result["unused"])
            if full_placed > best_placed:
                return maybe_use_full_pool(full_result)

            return maybe_use_full_pool(best_result if best_result else full_result)

        # Small instance path: keep original exhaustive loop for test compatibility
        best_result: Optional[Dict[str, Any]] = None
        best_placed = -1
        best_combo_size = 0
        for combo in combo_order:
            working_containers = [clone_container(c) for c in combo]
            working_items = [clone_item(item) for item in items_copy]
            result = self._pack_containers(working_containers, working_items, orientation_cache)
            placed = len(working_items) - len(result["unused"])
            if placed > best_placed:
                best_result = result
                best_placed = placed
                best_combo_size = len(combo)
            if not result["unused"]:
                return maybe_use_full_pool(result)
        if best_result:
            # If combo search left items unused while more containers exist,
            # fall back to packing all containers sequentially to allow
            # consuming extra pallets instead of sticking to a lean subset.
            if best_result["unused"] and len(containers) > best_combo_size:
                full_result = self._pack_containers(containers, items_copy, orientation_cache)
                full_placed = len(items_copy) - len(full_result["unused"])
                if full_placed > best_placed:
                    return maybe_use_full_pool(full_result)
            return maybe_use_full_pool(best_result)
        return maybe_use_full_pool(self._pack_containers(containers, items_copy, orientation_cache))

    def _group_items_by_sku(self, items: List[Item]) -> Dict[Tuple, List[Item]]:
        buckets: Dict[Tuple, List[Item]] = {}
        for item in items:
            key = sku_signature(item)
            buckets.setdefault(key, []).append(item)
        return buckets

    def _group_items_preserving_rank(self, items: List[Item]) -> Dict[Tuple, List[Item]]:
        """Group items by order_id, senddate_ts, pickup_priority, weight, volume, and itemType_id.
        
        Within each group, items are sorted by final_rank descending to preserve
        the global ordering as much as possible.
        
        Args:
            items: List of items to group
            
        Returns:
            Dictionary mapping group keys to sorted lists of items
        """
        buckets: Dict[Tuple, List[Item]] = {}
        for item in items:
            # Create grouping key from the specified attributes
            key = (
                item.order_id,
                item.senddate_ts,
                item.pickup_priority,
                round(item.weight, 3),  # Round to avoid floating point issues
                round(item.volume, 1),   # Round to avoid floating point issues
                item.itemType_id
            )
            buckets.setdefault(key, []).append(item)
        
        # Sort items within each group by final_rank descending
        for key in buckets:
            buckets[key].sort(key=lambda x: -x.final_rank)
        
        return buckets

    @staticmethod
    def _normalize_priorities(items: List[Item]) -> None:
        """
        Normalize priorities based on whether they are positive or negative.

        Rules:
        - If all priorities are positive: use as-is (lower value = more important)
        - If all priorities are negative: convert to positive ranking where
          least negative becomes most important (rank 1)

        After normalization: lower values = more important (1 is most important)
        """
        if not items:
            return

        priorities = [item.pickup_priority for item in items]
        all_positive = all(p > 0 for p in priorities)
        all_negative = all(p < 0 for p in priorities)

        # print('all unique pickup_priority', set(priorities))
        # print(all_positive, all_negative)

        if all_positive:
            # Already positive, use as-is (lower value = more important)
            pass
        elif all_negative:
            # Convert negative to positive ranking
            # Most negative (e.g., -3) gets rank 1 (most important)
            # Least negative (e.g., -1) gets highest rank (least important)
            # Example: -1 -> 3, -2 -> 2, -3 -> 1
            sorted_priorities = sorted(set(priorities))  # [-3, -2, -1]
            priority_to_rank = {p: idx + 1 for idx, p in enumerate(sorted_priorities)}
            for item in items:
                item.pickup_priority = priority_to_rank[item.pickup_priority]
        else:
            # Mixed positive and negative - convert all to absolute values
            for item in items:
                item.pickup_priority = abs(item.pickup_priority)


    @staticmethod
    def _compute_final_ranks(items: List[Item]) -> None:
        """
        Compute final_rank for each item based on lexicographic sort order.
        
        Items in the same group (same order_id, senddate_ts, pickup_priority, weight, 
        volume, itemType_id) receive the same rank.
        
        Sort order (ASCENDING - lower values get lower ranks):
        1. order_id (asc) - lower order_id get lower rank (rank 1, 2, 3...)
        2. senddate_ts (asc) - earlier dates get lower rank
        3. pickup_priority (asc) - lower pickup_priority values get lower rank
        4. weight (asc) - lighter items get lower rank
        5. volume (asc) - smaller items get lower rank
        6. itemType_id (asc) - for stable tie-breaking

        The rank is the 1-based index of the group in the sorted list.
        Higher ranks (6, 5, 4...) should be packed FIRST (using -final_rank sorting).
        """
        # Group items by the specified attributes
        from collections import OrderedDict
        groups = OrderedDict()

        # Sort items first to determine group order (ASCENDING)
        sorted_items = sorted(
            items,
            key=lambda it: (
                it.senddate_ts,     # ASC
                it.order_id,        # ASC
                it.pickup_priority,        # ASC
                it.weight,          # ASC
                it.volume,          # ASC
                it.itemType_id      # ASC
            ),
        )
        
        # Group items while preserving order
        for item in sorted_items:
            group_key = (
                item.senddate_ts,
                item.order_id,
                item.pickup_priority,
                round(item.weight, 3),    # Round for grouping
                round(item.volume, 1),     # Round for grouping
                item.itemType_id
            )
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(item)
        
        # Assign the same rank to all items in each group
        rank = 1
        for group_items in groups.values():
            for item in group_items:
                item.final_rank = rank
            rank += 1

    @staticmethod
    def _sort_items(items: List[Item]) -> List[Item]:
        # Sort items for container assignment - use consistent descending pickup_priority
        return sorted(
            items,
            key=lambda it: (
                -it.final_rank,                    # Sort by final_rank (desc) - PRIMARY
                # -it.senddate_ts,                   # Sort by plan_send_date (desc)
                # -it.pickup_priority,                      # Sort by pickup_priority (DESC)
                # -it.weight,                        # Sort by weight (desc)
                # -it.volume,                        # Sort by volume (desc)
                # it.id,                             # Sort by id (asc) - stable tiebreaker
            ),
        )

    def _cap_container_pool(
        self, containers: List[Container], items: List[Item], hard_limit: int = 500
    ) -> List[Container]:
        """
        Limit massive container pools (high qty) to the amount we could realistically use.
        Keeps enough per template to cover total item volume/weight plus slack, which
        trims runtime without reducing feasibility.
        """
        if len(containers) <= hard_limit:
            return containers[:]

        total_vol = sum(it.volume for it in items)
        total_wt = sum(it.weight for it in items)

        def key_fn(c: Container) -> Tuple:
            return (
                c.type_id,
                round(c.length, 4),
                round(c.width, 4),
                round(c.height, 4),
                round(c.max_weight, 4),
                c.door_type_int,
            )

        grouped: Dict[Tuple, Dict[str, Any]] = {}
        for c in containers:
            k = key_fn(c)
            if k not in grouped:
                grouped[k] = {"container": c, "count": 0}
            grouped[k]["count"] += 1

        keep_counts: Dict[Tuple, int] = {}
        for k, info in grouped.items():
            tmpl = info["container"]
            available = info["count"]
            if available <= 0:
                continue
            if tmpl.volume <= EPS or tmpl.max_weight <= EPS:
                target = min(available, 10)
            else:
                need_by_vol = ceil((total_vol + EPS) / tmpl.volume) if total_vol > EPS else 1
                need_by_wt = ceil((total_wt + EPS) / tmpl.max_weight) if total_wt > EPS else 1
                base_need = max(need_by_vol, need_by_wt)
                # Inflate need to assume only ~70% utilization of this container size,
                # which prevents trimming the pool too aggressively for large boxes.
                target_util = 0.70
                effective_need = ceil((total_vol + EPS) / max(tmpl.volume * target_util, EPS)) if total_vol > EPS else 1
                base_need = max(base_need, effective_need)
                slack = max(3, int(base_need * 0.15) + 1)
                target = min(available, base_need + slack)
            keep_counts[k] = max(1, target)

        trimmed: List[Container] = []
        for c in containers:
            k = key_fn(c)
            quota = keep_counts.get(k, 0)
            if quota <= 0:
                continue
            trimmed.append(c)
            keep_counts[k] = quota - 1

        return trimmed

    @staticmethod
    def _is_single_template(containers: List[Container]) -> bool:
        templates = {
            (
                c.type_id,
                round(c.length, 6),
                round(c.width, 6),
                round(c.height, 6),
                round(c.max_weight, 6),
                round(c.exlength, 6),
                round(c.exwidth, 6),
                round(c.exheight, 6),
                round(c.exweight, 6),
                c.door_type_int,
            )
            for c in containers
        }
        return len(templates) == 1

    def _combo_worst_bin_utilization(
        self, total_items_volume: float, combo: List[Container]
    ) -> float:
        """Estimate the lowest per-bin utilization using descending volume order.
        
        Simulates filling containers from largest to smallest and returns
        the minimum utilization across all containers.
        """
        if total_items_volume <= EPS:
            return 1.0
        
        if len(combo) == 0:
            return 1.0
        
        # Sort containers by descending volume
        sorted_volumes = sorted([c.volume for c in combo], reverse=True)
        
        remaining = total_items_volume
        worst_util = 1.0
        
        for volume in sorted_volumes:
            if volume <= EPS:
                continue
            filled = min(remaining, volume)
            util = filled / volume
            worst_util = min(worst_util, util)
            remaining = max(remaining - filled, 0.0)
        
        return worst_util

    def _combo_rank_key(self, combo: List[Container], total_items_volume: float) -> Tuple:
        """
        Compute the cost tuple for a container combination.
        
        Returns (K1, K2, K3, max_volume, avg_volume) where:
        - K1 = number of containers (minimize)
        - K2 = slack ratio (minimize)
        - K3 = 1 - worst_bin_utilization (minimize, i.e., maximize worst utilization)
        - max_volume = largest container volume (minimize, prefer smaller containers)
        - avg_volume = average container volume (minimize)
        
        Combinations are compared lexicographically: lower cost tuples are better.
        """
        # Avoid division by zero
        epsilon = 1e-9
        V_items = max(total_items_volume, epsilon)
        
        # K1: Number of containers
        K1 = len(combo)
        
        # K2: Slack ratio
        total_volume = sum(c.volume for c in combo)
        slack = max(total_volume - V_items, 0.0)
        K2 = slack / V_items
        
        # K3: 1 - worst_bin_utilization
        worst_util = self._combo_worst_bin_utilization(V_items, combo)
        K3 = 1.0 - worst_util
        
        # K4: Smallness penalty (max_volume, avg_volume)
        if len(combo) == 0:
            max_volume = 0.0
            avg_volume = 0.0
        else:
            volumes = [c.volume for c in combo]
            max_volume = max(volumes)
            avg_volume = total_volume / len(combo)
        
        return (K1, K2, K3, max_volume, avg_volume)

    def _enumerate_container_combinations(
        self, containers: List[Container], items: List[Item]
    ) -> List[List[Container]]:
        """Enumerate and rank compact container selections covering the item volume/weight.

        When a small number of containers is provided, enumerate exact subsets.
        When many containers are available (e.g., dozens of identical types),
        fall back to a grouped count-based enumeration that only considers the
        minimum number of containers needed per type.
        """
        COMBO_LIMIT = 50  # hard cap to keep solve fast
        total_items_volume = sum(item.volume for item in items)
        total_items_weight = sum(item.weight for item in items)

        max_enum = 15
        if len(containers) <= max_enum:
            combos: List[Tuple[Tuple, List[Container]]] = []
            idxs = list(range(len(containers)))
            for r in range(1, len(containers) + 1):
                for combo_idx in combinations(idxs, r):
                    combo = [containers[i] for i in combo_idx]
                    total_volume = sum(c.volume for c in combo)
                    if total_volume + EPS < total_items_volume:
                        continue
                    total_weight_cap = sum(c.max_weight for c in combo)
                    if total_items_weight - EPS > total_weight_cap:
                        continue
                    combos.append((self._combo_rank_key(combo, total_items_volume), combo))
            # Always include the full set as a fallback candidate so we don't
            # drop a feasible "use everything" choice when we cap the list.
            full_combo = tuple(range(len(containers)))
            if full_combo not in combos:
                combos.append(
                    (
                        self._combo_rank_key(containers, total_items_volume),
                        containers,
                    )
                )
            combos.sort(key=lambda entry: entry[0])
            trimmed = [combo for _, combo in combos[:COMBO_LIMIT]]
            # Ensure the full set survives trimming
            if containers not in trimmed:
                trimmed[-1] = containers
            return trimmed

        # Large pool: group identical container types and enumerate counts.
        grouped: Dict[Tuple, Dict[str, Any]] = {}
        for c in containers:
            key = (c.type_id, round(c.volume, 4), round(c.max_weight, 4), c.door_type_int)
            if key not in grouped:
                grouped[key] = {"container": c, "count": 0}
            grouped[key]["count"] += 1

        group_entries: List[Tuple[Container, int]] = []
        for info in grouped.values():
            template: Container = info["container"]
            available = info["count"]
            vol = template.volume
            weight_cap = template.max_weight
            if vol <= EPS or weight_cap <= EPS or available <= 0:
                continue
            target_util = 0.70
            need_vol = ceil((total_items_volume + EPS) / vol)
            effective_vol_need = ceil((total_items_volume + EPS) / max(vol * target_util, EPS))
            need_vol = max(need_vol, effective_vol_need)
            need_weight = ceil((total_items_weight + EPS) / weight_cap)
            target = max(need_vol, need_weight)
            # Allow substantial slack so awkward geometry can still fit.
            slack_bound = max(target + 8, ceil(target * 1.5))
            max_use = max(1, min(available, slack_bound))
            group_entries.append((template, max_use))

        combos: List[Tuple[Tuple, List[Container]]] = []

        def backtrack(idx: int, chosen: List[Container], combo_volume: float, combo_weight: float) -> None:
            # Do not accumulate more than COMBO_LIMIT candidates
            if len(combos) >= COMBO_LIMIT * 2:
                return
            if idx == len(group_entries):
                if combo_volume + EPS >= total_items_volume and combo_weight + EPS >= total_items_weight:
                    combos.append((self._combo_rank_key(chosen, total_items_volume), list(chosen)))
                return

            template, max_use = group_entries[idx]
            for count in range(0, max_use + 1):
                next_volume = combo_volume + count * template.volume
                next_weight = combo_weight + count * template.max_weight
                # Quick check: if no containers chosen, skip zero at final return
                if idx == len(group_entries) - 1 and len(chosen) + count == 0:
                    continue
                # Clone templates so each pallet/container instance is independent
                clones = [clone_container(template) for _ in range(count)]
                chosen.extend(clones)
                backtrack(idx + 1, chosen, next_volume, next_weight)
                # pop back
                for _ in range(count):
                    chosen.pop()

        backtrack(0, [], 0.0, 0.0)
        combos.sort(key=lambda entry: entry[0])
        trimmed = [combo for _, combo in combos[:COMBO_LIMIT]]
        # Ensure the "all available" option is retained as a last resort.
        all_combo = [clone_container(info["container"]) for info in grouped.values() for _ in range(info["count"])]
        if all_combo and all_combo not in trimmed:
            trimmed[-1:] = [all_combo]
        return trimmed

    def _template_fits(self, template: List[PlacementTemplate], sku_map: Dict[Tuple, List[Item]]) -> bool:
        requirements: Dict[Tuple, int] = {}
        for entry in template:
            requirements[entry.sku_key] = requirements.get(entry.sku_key, 0) + 1
        for key, needed in requirements.items():
            if len(sku_map.get(key, [])) < needed:
                return False
        return True

    def _apply_template(
        self,
        container: Container,
        template: List[PlacementTemplate],
        sku_map: Dict[Tuple, List[Item]],
    ) -> List[Item]:
        used_items: List[Item] = []
        for entry in template:
            pool = sku_map.get(entry.sku_key)
            if not pool:
                raise RuntimeError("Template application missing SKU items")
            item = pool.pop()
            if not pool:
                sku_map.pop(entry.sku_key, None)
            item.position = entry.position
            item.rotation = entry.rotation
            used_items.append(item)
        container.items.extend(used_items)
        container.total_weight += sum(item.weight for item in used_items)
        return used_items

    def _flatten_sku_map(self, sku_map: Dict[Tuple, List[Item]]) -> List[Item]:
        items: List[Item] = []
        # Sort keys for deterministic iteration
        for key in sorted(sku_map.keys()):
            items.extend(sku_map[key])
        return self._sort_items(items)

    def _sort_container_items_by_door(self, container: Container) -> None:
        if not container.items:
            return
        if container.door_type_int not in (0, 1):
            return
        def depth_key(item: Item) -> Tuple[float, float, float]:
            dims = item.get_rotated_dimensions()
            x, y, z = item.position or (0.0, 0.0, 0.0)
            center_x = x + dims[0] / 2
            center_y = y + dims[1] / 2
            center_z = z + dims[2] / 2
            if container.door_type_int == 1:  # front door → depth along width (y)
                return (center_y, center_z, center_x)
            else:  # side door → depth along length (x)
                return (center_x, center_z, center_y)
        container.items.sort(key=depth_key)

    def _pack_containers(
            self,
            containers: List[Container],
            items: List[Item],
            orientation_cache: Dict[int, OrientationCache],
        ) -> Dict[str, Any]:

        containers.sort(
            key=lambda c: (
                priority_sort_key(c.pickup_priority),
                -c.volume,
            )
        )

        remaining_items = self._sort_items(items)
        sku_map = self._group_items_preserving_rank(remaining_items)

        # print('total containers:', len(containers), flush=True)

        for idx, container in enumerate(containers):

            # If all remaining items would fit into a smaller container still unused,
            # pick that smaller one instead of the current large box to avoid ending
            # with a half-empty large container.
            rem_total_vol = sum(it.volume for it in remaining_items)
            rem_total_wt = sum(it.weight for it in remaining_items)
            best_fit_idx = None
            best_fit_vol = float("inf")
            for j in range(idx, len(containers)):
                c = containers[j]
                if c.volume + EPS >= rem_total_vol and c.max_weight + EPS >= rem_total_wt:
                    if c.volume < best_fit_vol - EPS:
                        best_fit_idx = j
                        best_fit_vol = c.volume
            if best_fit_idx is not None and best_fit_idx != idx:
                containers[idx], containers[best_fit_idx] = containers[best_fit_idx], containers[idx]
                container = containers[idx]

            # print('begin packing container')
            layout_key = (container.type_id, container.door_type_int)
            template = self.layout_cache.get(layout_key)
            # Use any cached layout only if it matches this container's door type.
            if template and container.door_type_int != -1 and self._template_fits(template, sku_map):

                # print('checking items')
                used_items = self._apply_template(container, template, sku_map)
                if self._has_overlaps(container.items):
                    for item in used_items:
                        container.items.remove(item)
                        container.total_weight -= item.weight
                        item.position = None
                        sku_map.setdefault(sku_signature(item), []).append(item)
                    remaining_items = self._flatten_sku_map(sku_map)
                else:
                    remaining_items = self._flatten_sku_map(sku_map)
                    if not remaining_items:
                        break
                    continue

            packer = create_packer(container, orientation_cache, self.must_be_on_top, self.co_loc_groups)


            # Iteratively attempt to pack items in this container, preferring
            # to fully utilize its space (including stacking) before moving on.
            progress = True
            while progress and remaining_items:
                progress = False
                base_items = [it for it in remaining_items if not self.must_be_on_top.get(it.id, False)]
                top_items = [it for it in remaining_items if self.must_be_on_top.get(it.id, False)]
                leftover = packer.pack(base_items)
                if len(leftover) < len(base_items):
                    progress = True
                if top_items:
                    leftover_top = packer.pack(top_items, skip_floor_prefill=True)
                    if len(leftover_top) < len(top_items):
                        progress = True
                    leftover.extend(leftover_top)
                remaining_items = leftover
            sku_map = self._group_items_by_sku(remaining_items)
            if layout_key not in self.layout_cache and packer.placements:
                self.layout_cache[layout_key] = [
                    PlacementTemplate(
                        position=(pl.x, pl.y, pl.z),
                        dims=pl.dims,
                        rotation=pl.rotation,
                        layer_level=pl.layer_level,
                        sku_key=sku_signature(pl.item),
                    )
                    for pl in packer.placements
                ]
            if not remaining_items:
                # print('end packing container')
                break

            # print('end packing container')

        # Consolidation pass for pallets: try to merge the last used pallet
        # into earlier ones by repacking their combined items. This reduces the
        # total pallet count without changing item assignments in aggregate.
        def consolidate_pallets() -> bool:
            used_idxs = [i for i, c in enumerate(containers) if c.items]
            if len(used_idxs) <= 1:
                return False
            last_idx = used_idxs[-1]
            src = containers[last_idx]
            if not src.items:
                return False
            # Try earlier pallets from most filled to least filled first
            target_order = sorted(used_idxs[:-1], key=lambda i: -containers[i].total_weight)
            for ti in target_order:
                tgt = containers[ti]
                if tgt.door_type_int != -1 or src.door_type_int != -1:
                    continue  # only for pallets
                combined = [clone_item(it) for it in (tgt.items + src.items)]
                new_container = clone_container(tgt)
                packer = create_packer(new_container, orientation_cache, self.must_be_on_top, self.co_loc_groups)

                # Run a local packing loop to try to place all combined items
                remaining = sorted(
                    combined,
                    key=lambda it: (-it.final_rank)
                )
                progress = True
                while progress and remaining:
                    progress = False
                    before = len(remaining)
                    remaining = packer.pack(remaining)
                    if len(remaining) < before:
                        progress = True
                if remaining:
                    continue
                # Success: replace target with new_container, clear src
                containers[ti] = new_container
                src.items.clear()
                src.total_weight = 0.0
                return True
            return False

        # Attempt consolidation repeatedly until no more merges are possible
        merged = True
        while merged:
            merged = consolidate_pallets()

        for container in containers:
            self._sort_container_items_by_door(container)

            total_volume = 0

            for item in container.items:
                total_volume = total_volume + item.volume
            
            container.total_volume = total_volume

        containers = [c for c in containers if len(c.items) > 0]

        ## just to check total volume in container
        # print(containers[0].__dict__)


        return {"containers": containers, "unused": remaining_items}

    @staticmethod
    def _has_overlaps(items: List[Item]) -> bool:
        for i in range(len(items)):
            a = items[i]
            ax, ay, az = a.position or (0.0, 0.0, 0.0)
            ad = a.get_rotated_dimensions()
            a_bounds = (ax, ay, az, ax + ad[0], ay + ad[1], az + ad[2])
            for j in range(i + 1, len(items)):
                b = items[j]
                bx, by, bz = b.position or (0.0, 0.0, 0.0)
                bd = b.get_rotated_dimensions()
                b_bounds = (bx, by, bz, bx + bd[0], by + bd[1], bz + bd[2])
                if not (
                    a_bounds[3] <= b_bounds[0] + EPS
                    or b_bounds[3] <= a_bounds[0] + EPS
                    or a_bounds[4] <= b_bounds[1] + EPS
                    or b_bounds[4] <= a_bounds[1] + EPS
                    or a_bounds[5] <= b_bounds[2] + EPS
                    or b_bounds[5] <= a_bounds[2] + EPS
                ):
                    return True
        return False

    def _solve_multi_pallet_min_pallets(
        self,
        containers: List[Container],
        items: List[Item],
        orientation_cache: Dict[int, OrientationCache],
    ) -> Dict[str, Any]:
        """
        Multi-pallet packing strategy that minimizes the number of pallets used.
        
        For each iteration:
        1. Try packing remaining items on each available pallet type
        2. Choose the pallet type that packs the most items
        3. Use that pallet and repeat with remaining items
        
        This ensures we select the most efficient pallet for each batch of items.
        """
        remaining_items = items[:]
        used_pallets: List[Container] = []
        unused_pallets = containers[:]
        
        while remaining_items and unused_pallets:

            # If a smaller unused pallet can hold ALL remaining items (by volume/weight
            # and per-item fit), pick the smallest-volume such pallet directly to avoid
            # finishing with a half-empty larger pallet.
            rem_total_vol = sum(it.volume for it in remaining_items)
            rem_total_wt = sum(it.weight for it in remaining_items)
            best_fit_idx = None
            best_fit_vol = float("inf")
            for i, p in enumerate(unused_pallets):
                if p.volume + EPS < rem_total_vol or p.max_weight + EPS < rem_total_wt:
                    continue
                # Ensure every item can geometrically fit this pallet
                if any(not self._item_can_fit(it, p, orientation_cache) for it in remaining_items):
                    continue
                if p.volume < best_fit_vol - EPS:
                    best_fit_vol = p.volume
                    best_fit_idx = i
            if best_fit_idx is not None:
                best_pallet = clone_container(unused_pallets.pop(best_fit_idx))
                best_pallet.items = []
                best_pallet.total_weight = 0.0
                packer = create_packer(best_pallet, orientation_cache, self.must_be_on_top, self.co_loc_groups)
                progress = True
                work_items = [clone_item(it) for it in remaining_items]
                while progress and work_items:
                    progress = False
                    before = len(work_items)
                    work_items = packer.pack(work_items)
                    if len(work_items) < before:
                        progress = True
                packed_ids = {it.id for it in best_pallet.items}
                remaining_items = [it for it in remaining_items if it.id not in packed_ids]
                used_pallets.append(best_pallet)
                continue

            # Choose the best pallet for the current remaining items
            best_pallet, best_packed_items = self._choose_best_pallet(
                unused_pallets, remaining_items, orientation_cache
            )
            
            if not best_pallet or not best_packed_items:
                # No pallet can pack any more items
                break
            
            # Remove the used pallet from the pool
            # Find and remove one instance of this pallet type
            for i, p in enumerate(unused_pallets):
                if (p.type_id == best_pallet.type_id and
                    abs(p.volume - best_pallet.volume) < EPS and
                    abs(p.max_weight - best_pallet.max_weight) < EPS):
                    unused_pallets.pop(i)
                    break
            
            # Add the packed pallet to results
            used_pallets.append(best_pallet)
            
            # Remove packed items from remaining
            packed_ids = {it.id for it in best_packed_items}
            remaining_items = [it for it in remaining_items if it.id not in packed_ids]
        
        return {"containers": used_pallets, "unused": remaining_items}

    def _item_can_fit(
        self,
        item: Item,
        container: Container,
        orientation_cache: Dict[int, OrientationCache],
    ) -> bool:
        """
        Quick feasibility check: does the item fit in the container in any rotation?
        """
        if item.volume > container.volume + EPS:
            return False
        if item.weight > container.max_weight + EPS:
            return False
        
        cache = orientation_cache.get(item.id)
        if not cache:
            cache = OrientationCache.build(item)
            
        for rot in cache.rotations:
            d = cache.dimensions[rot]
            if (
                d[0] <= container.width + EPS
                and d[1] <= container.length + EPS
                and d[2] <= container.height + EPS
            ):
                return True
        return False

    def _consolidate_pallets(
        self,
        pallets: List[Container],
        orientation_cache: Dict[int, OrientationCache],
    ) -> List[Container]:
        """
        Try to empty sparsely loaded pallets by redistributing their items to other pallets.
        """
        improved = True
        while improved:
            improved = False
            # Sort by item count ascending (try to empty the smallest pallets first)
            # or by volume utilization? Item count is usually a good proxy for "effort to move".
            pallets.sort(key=lambda p: len(p.items))
            
            for i, victim in enumerate(pallets):
                if not victim.items:
                    continue
                    
                victim_items = [clone_item(it) for it in victim.items]
                
                # Try to repack these items into OTHER pallets
                # We need to simulate adding these items to other pallets.
                # This is tricky because "other pallets" are already packed.
                # We can try to repack other pallets from scratch with their items + victim items.
                
                # Candidates for receiving items: all other pallets
                # Sort them by free space? Or just try all?
                others_indices = [j for j in range(len(pallets)) if j != i]
                
                # We can try to distribute victim items one by one, or all together.
                # The pseudocode says "TRY_REPACK_ITEMS_ON_OTHERS".
                # A simple approach: Try to move ALL victim items to ONE other pallet?
                # Or distribute them across multiple?
                # Distributing across multiple is better but harder to backtrack.
                
                # Let's try a greedy distribution:
                # For each item in victim, try to place it in any other pallet.
                # If all items placed, we can remove victim.
                # If any item fails, we revert everything (transactional).
                
                # To do this transactionally without messing up state, we can work on clones first.
                
                # Optimization: Check if total volume of victim items fits in total free volume of others.
                victim_vol = sum(it.volume for it in victim_items)
                free_vol = sum(p.volume - sum(it.volume for it in p.items) for j, p in enumerate(pallets) if j != i)
                
                if victim_vol > free_vol:
                    continue # No chance
                
                # Attempt to move items
                # We will try to pack victim items into other pallets one by one.
                # For each victim item, find a pallet that accepts it.
                # If we modify a pallet, we need to persist that change ONLY if we succeed with ALL victim items.
                
                # We'll use a temporary copy of others to simulate.
                temp_others = {j: clone_container(pallets[j]) for j in others_indices}
                
                success = True
                for item in victim_items:
                    placed = False
                    # Try to fit item in any of temp_others
                    # Sort others by most filled? or least filled?
                    # Most filled first -> Fill up pallets to max.
                    sorted_temp_indices = sorted(temp_others.keys(), key=lambda k: -sum(it.volume for it in temp_others[k].items))
                    
                    for idx in sorted_temp_indices:
                        target = temp_others[idx]
                        # Check simple constraints first
                        if target.total_weight + item.weight > target.max_weight + EPS:
                            continue
                            
                        # Try to pack using PalletPacker (incremental pack)
                        # We need to be careful: PalletPacker.pack usually packs a list.
                        # We can try to pack just this one item.
                        # But PalletPacker needs to be initialized with current state of target.
                        
                        # Re-initializing Packer for every item is expensive.
                        # But we have no choice if we want to use the logic.
                        # Optimization: Reuse packer if possible? Packer keeps state.
                        
                        packer = create_packer(target, orientation_cache, self.must_be_on_top, self.co_loc_groups)
                        leftovers = packer.pack([item])
                        
                        if not leftovers:
                            placed = True
                            break
                            
                    if not placed:
                        success = False
                        break
                
                if success:
                    # All victim items moved!
                    # Update real pallets with temp_others
                    for idx, new_c in temp_others.items():
                        pallets[idx] = new_c
                    
                    # Remove victim
                    pallets.pop(i)
                    improved = True
                    break # Restart outer loop
                    
        return pallets

    def _choose_best_pallet(
        self,
        unused_pallets: List[Container],
        remaining_items: List[Item],
        orientation_cache: Dict[int, OrientationCache],
    ) -> Tuple[Optional[Container], List[Item]]:
        """
        Simulate packing on all unique available pallet types and return the best result.
        Scoring prioritizes:
        1. Number of items packed (primary)
        2. Volume utilization (secondary)
        """
        # Identify unique pallet templates to avoid redundant simulations
        unique_templates: Dict[Tuple, Container] = {}
        for p in unused_pallets:
            # Key by type and dimensions
            key = (p.type_id, round(p.length, 4), round(p.width, 4), round(p.height, 4))
            if key not in unique_templates:
                unique_templates[key] = p

        best_score = -1.0
        best_pallet: Optional[Container] = None
        best_packed_items: List[Item] = []

        for template in unique_templates.values():
            # Fast pre-filter: only consider items that geometrically fit
            candidates = [it for it in remaining_items if self._item_can_fit(it, template, orientation_cache)]
            if not candidates:
                continue

            packed_pallet, packed_items = self._simulate_pack(template, candidates, orientation_cache)

            if not packed_items:
                continue

            # Calculate score
            count_score = len(packed_items)
            
            packed_vol = sum(it.volume for it in packed_items)
            vol_score = packed_vol / (template.volume + EPS)

            # Heuristic: heavily weight item count, then volume
            score = count_score * 10.0 + vol_score

            if score > best_score:
                best_score = score
                best_pallet = packed_pallet
                best_packed_items = packed_items

        return best_pallet, best_packed_items

    def _simulate_pack(
        self,
        template: Container,
        candidates: List[Item],
        orientation_cache: Dict[int, OrientationCache],
    ) -> Tuple[Container, List[Item]]:
        """
        Simulate packing candidate items on a pallet template.
        
        Args:
            template: The pallet template to pack on
            candidates: List of items to attempt packing
            orientation_cache: Orientation cache for items
            
        Returns:
            Tuple of (packed_pallet, list_of_successfully_packed_items)
        """
        # Clone the template and items for simulation
        sim_pallet = clone_container(template)
        sim_pallet.items = []
        sim_pallet.total_weight = 0.0
        sim_items = [clone_item(it) for it in candidates]
        
        # Create packer and attempt to pack
        packer = create_packer(sim_pallet, orientation_cache, self.must_be_on_top, self.co_loc_groups)
        
        # Try to pack items iteratively
        progress = True
        while progress and sim_items:
            progress = False
            before_count = len(sim_items)
            sim_items = packer.pack(sim_items)
            if len(sim_items) < before_count:
                progress = True
        
        # Identify which items were packed (items in sim_pallet.items)
        # Map back to original items by ID
        packed_ids = {it.id for it in sim_pallet.items}
        packed_items = [it for it in candidates if it.id in packed_ids]
        
        return sim_pallet, packed_items



def print_solution_summary(solution):
    total_itmes = 0
    total_pallets = 0

    total_weight = 0

    total_unused_items = len(solution["unused"])

    for i in range(0, len(solution["containers"])):
        item_count = len(solution["containers"][i].items)

        # if item_count > 0:
        total_itmes = total_itmes + item_count
        total_pallets += 1

        container_weight = solution["containers"][i].total_weight
        container_max_weight = solution["containers"][i].max_weight

        total_weight = total_weight + container_weight

        print(
            f"container #{i+1} -> {item_count},  {container_weight}/{container_max_weight}"
        )

    print(f"total unused items: {total_unused_items}")
    print(f"total packed pallets: {total_pallets}")
    print(f"total packed items: {total_itmes}")
    print(f"total weight: {total_weight}")


def prepare_products(products: List[schemas.ModelProduct]) -> List[Item]:
    ind_items = [item for item in products for _ in range(item.qty)]

    model_items = [
        Item(
            id=id,
            itemType_id=item.product_id,
            itemType="product",
            length=item.product_length,
            width=item.product_width,
            height=item.product_height,
            weight=item.product_weight,
            isSideUp=item.is_side_up,
            maxStack=(
                item.max_stack
                if not (item.is_stack or item.is_fragile or item.is_on_top)
                else 1
            ),
            maxStackWeight=item.stack_weight,
            order_id=item.orders_id,
            pickup_priority=item.pickup_priority,
            plan_send_date=item.plan_send_date,
        )
        for id, item in enumerate(ind_items)
    ]
    return model_items


def prepare_pallets(pallets: List[schemas.ModelPallet]) -> List[Container]:
    ind_pallets = [pallet for pallet in pallets for _ in range(pallet.qty)]
    model_containers = [
        Container(
            id=id,
            type_id=pallet.palletid,
            length=pallet.load_length,
            width=pallet.load_width,
            height=pallet.load_height,
            exlength=pallet.palletlength,
            exwidth=pallet.palletwidth,
            exheight=pallet.palletheight,
            exweight=pallet.palletweight,
            max_weight=pallet.load_weight,
            pickup_priority=pallet.pickup_priority,
        )
        for id, pallet in enumerate(ind_pallets)
    ]
    return model_containers


def prepare_containers(containers: List[schemas.ModelContainer]) -> List[Container]:
    ind_containers = [
        container for container in containers for _ in range(container.qty)
    ]
    model_containers: List[Container] = []
    for id, container in enumerate(ind_containers):
        containerRot = (
            1
            if container.door_position == "side"
            or container.door_position == "left"
            or container.door_position == "right"
            else 0
        )
        w, l, h = getRotDim(
            container.load_width,
            container.load_length,
            container.load_height,
            containerRot,
        )
        exw, exl, exh = getRotDim(
            container.package_width,
            container.package_length,
            container.package_height,
            containerRot,
        )

        model_containers.append(
            Container(
                id=id,
                type_id=container.package_id,
                length=l,
                width=w,
                height=h,
                exlength=exl,
                exwidth=exw,
                exheight=exh,
                exweight=container.package_weight,
                max_weight=container.load_weight,
                pickup_priority=container.pickup_priority,
                door_position=container.door_position,
            )
        )

    return model_containers


def prepare_palletitems(pallets: List[Container]) -> List[Item]:
    # Filter pallets with items first to maintain consistent indexing
    non_empty_pallets = [pallet for pallet in pallets if len(pallet.items) > 0]
    
    model_items = [
        Item(
            id=idx,  # Use enumerate index for unique IDs
            itemType_id=pallet.type_id,
            itemType="sim_batch",
            length=pallet.exlength,
            width=pallet.exwidth,
            height=pallet.exheight + pallet.height,
            weight=pallet.exweight + pallet.total_weight,
            isSideUp=True,
            maxStack=1,
            maxStackWeight=-1,
            grounded=True,
            order_id="",
            pickup_priority=sum(list(set([item.pickup_priority for item in pallet.items]))),
            pallet_id=idx,  # Use enumerate index to match batch IDs
        )
        for idx, pallet in enumerate(non_empty_pallets)
    ]
    return model_items


class simulation_result(TypedDict):
    containers: list[Container]
    unused: list[Item]


def simulate(
    model_items: List[Item], model_containers: List[Container], centered=True
) -> simulation_result:
    
    item_ids = [item.id for item in model_items]
    container_ids = [c.id for c in model_containers]
    inputuniqueitemNum = len(set(item_ids))
    inputuniquecontNum = len(set(container_ids))
    if inputuniqueitemNum != len(item_ids) or inputuniquecontNum != len(container_ids):
        logger.error(f"""duplicate input ids 
                     item: {len(item_ids)-inputuniqueitemNum} 
                     container: {len(container_ids)-inputuniquecontNum}
                     """)
    
    total_weight = 0

    for i in model_items:
        total_weight += i.weight

    print("input", len(model_items))
    print("total weights:", total_weight)

    solver = PackingSolver(model_containers, model_items, co_loc_groups={})

    # print('item info')
    # print(model_items[0].__dict__)

    # optimizer = MultiContainerLoadingBLF(
    #     model_containers, model_items, centered=centered
    # )

    try:
        # solution = optimizer.run()
        solution = solver.solve()

        print_solution_summary(solution)

        # Reassign unique IDs to containers to prevent duplicates
        for idx, container in enumerate(solution["containers"]):
            container.id = idx

        total_weight = 0

        for c in solution["containers"]:
            for i in c.items:
                total_weight += i.weight

        item_ids = [item.id for c in solution["containers"] for item in c.items]
        container_ids = [c.id for c in solution["containers"]]
        inputuniqueitemNum = len(set(item_ids))
        inputuniquecontNum = len(set(container_ids))
        if inputuniqueitemNum != len(item_ids) or inputuniquecontNum != len(container_ids):
            logger.error(f"""duplicate output ids
                            item: {len(item_ids)-inputuniqueitemNum}
                            container: {len(container_ids)-inputuniquecontNum}
                            """)
        print(
            "output", sum(len(container.items) for container in solution["containers"])
        )
        print("total items weight:", total_weight)

        return solution

    except Exception as e:
        # print(e.__traceback__)
        print(e)
        traceback.print_exc()
        return None

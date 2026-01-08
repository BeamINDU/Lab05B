from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from app.logger import logger

from .entities import (
    EPS,
    Item,
    Container,
    OrientationCache,
    Placement,
)
from .geometry import (
    check_bounds_within_container,
    check_collision_numba,
    check_support_and_stacking_numba,
)
from .common_packers import (
    Rect,
    MaxRects2D,
    FirstLayerPlanner,
    get_supporters,
)
from .blf_packer import BottomLeftFill


class PalletPacker:
    """Hybrid EP/EMS packer for pallets (door_type_int == -1)."""

    def __init__(
        self,
        container: Container,
        orientation_cache: Dict[int, OrientationCache],
        must_be_on_top: Optional[Dict[int, bool]] = None,
        co_loc_groups: Optional[Dict[str, Set[int]]] = None,
    ) -> None:
        self.container = container
        self.co_loc_groups = co_loc_groups or {}
        self.item_to_group = self._map_item_groups()
        self.placements: List[Placement] = []
        self.first_layer = FirstLayerPlanner(
            container, orientation_cache, self.item_to_group, self.co_loc_groups
        )
        self.container.door_type_int = -1
        self.EPS = 1e-5
        self.remaining_types: Set[str] = set()
        self.must_be_on_top = must_be_on_top or {}
        self.orientation_cache = orientation_cache
        self.priority_set: Set[int] = {self._priority_of(it) for it in container.items}
        self.stack_counts: Dict[Tuple[float, float], int] = {}
        self.weight_above: Dict[Tuple[float, float], float] = {}
        self.top_reserved_positions: Set[Tuple[float, float]] = set()

    def _priority_of(self, obj: Item) -> int:
        try:
            return int(getattr(obj, "pickup_priority", 1))
        except (TypeError, ValueError):
            return 1

    def _priority_allowed_on_pallet(self, item_priority: int) -> bool:
        if not self.priority_set:
            return True
        allowed = {item_priority, item_priority + 1}
        return self.priority_set.issubset(allowed)

    def _check_priority_rules(
        self,
        item: Item,
        x: float,
        y: float,
        z: float,
        dims: Tuple[float, float, float],
    ) -> bool:
        pickup_priority = self._priority_of(item)
        allowed = {pickup_priority, pickup_priority + 1}

        if self.priority_set and not self.priority_set.issubset(allowed):
            return False

        if z > self.EPS:
            supporters = get_supporters(self.container, x, y, z, dims, self.EPS)
            for supporter in supporters:
                if self._priority_of(supporter) not in allowed:
                    return False

        return True

    def _build_numba_views(self) -> Tuple[np.ndarray, np.ndarray, callable]:
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

        placed_geom = placed_items_data[:, :6]
        return placed_items_data, placed_geom, get_type_int

    def _validate_placement(
        self,
        item: Item,
        x: float,
        y: float,
        z: float,
        dims: Tuple[float, float, float],
    ) -> bool:
        placed_items_data, placed_geom, get_type_int = self._build_numba_views()

        ox, oy, oz = self.container.origin
        if not check_bounds_within_container(
            x, y, z, dims[0], dims[1], dims[2],
            ox, oy, oz,
            ox + self.container.width,
            oy + self.container.length,
            oz + self.container.height,
        ):
            return False

        item_pos = np.array([x, y, z], dtype=np.float64)
        item_dims = np.array(dims, dtype=np.float64)

        if check_collision_numba(item_pos, item_dims, placed_geom, self.EPS):
            return False

        if item.grounded and z > self.EPS:
            return False

        is_valid, _ = check_support_and_stacking_numba(
            item_pos=item_pos,
            item_dims=item_dims,
            item_type_id=int(get_type_int(item.itemType_id)),
            item_weight=float(item.weight),
            max_stack=int(item.maxStack),
            item_order_id_hash=float(hash(item.order_id) % (2**31)),
            item_senddate_ts=float(getattr(item, "senddate_ts", 0)),
            placed_items_data=placed_items_data,
            enforce_order_stacking=False,
            epsilon=self.EPS,
        )
        if not is_valid:
            return False

        if self.container.total_weight + item.weight > self.container.max_weight + self.EPS:
            return False

        return self._check_priority_rules(item, x, y, z, dims)

    def _commit_placement(
        self,
        item: Item,
        x: float,
        y: float,
        z: float,
        rotation: int,
        layer: int,
    ) -> None:
        item.position = (x, y, z)
        item.rotation = rotation
        item.layer = layer

        self.container.items.append(item)
        self.container.total_weight += item.weight
        self.priority_set.add(self._priority_of(item))

        if self.must_be_on_top.get(item.id, False):
            self.top_reserved_positions.add((round(x, 2), round(y, 2)))

    def pack(self, items: List[Item]) -> List[Item]:
        if not items:
            return []

        sorted_items = sorted(
            items,
            key=lambda x: (-x.senddate_ts, -x.pickup_priority, -x.weight, -x.volume, str(x.id))
        )

        unique_types = {it.itemType_id for it in sorted_items}

        if len(unique_types) == 1:
            logger.info("Single SKU packing detected.")
            return self._pack_single_sku(sorted_items)
        else:
            logger.info(f"Mixed SKU packing detected with {len(unique_types)} unique SKUs.")
            return self._pack_mixed_sku(sorted_items)

    def _pack_single_sku(self, items: List[Item]) -> List[Item]:
        if not items:
            return []

        box = items[0]

        if not self._priority_allowed_on_pallet(self._priority_of(box)):
            return items

        remaining_items = items[:]
        orientation_cache = {item.id: OrientationCache.build(item) for item in items}

        # SPECIAL CASE: If total items is small, use direct centered placement
        # This handles cases where FirstLayerPlanner might fail or return suboptimal results
        if len(items) <= 1:
            return self._pack_items_centered_direct(remaining_items, orientation_cache)

        first_layer_planner = FirstLayerPlanner(
            self.container,
            orientation_cache,
            self.item_to_group,
            self.co_loc_groups,
        )

        floor_placements, placed_ids = first_layer_planner.plan(remaining_items)

        if not floor_placements:
            # Fallback to direct centered placement instead of BLF
            logger.info("FirstLayerPlanner returned no placements, falling back to direct centered placement.")
            return self._pack_items_centered_direct(remaining_items, orientation_cache)

        boxes_per_layer = len(floor_placements)
        if boxes_per_layer == 0:
            logger.info("FirstLayerPlanner returned 0 boxes per layer, falling back to BLF.")
            return self._pack_blf_fallback(remaining_items)

        layer_height = floor_placements[0].dims[2]
        layer_dims = floor_placements[0].dims

        # Calculate max layers based on constraints
        max_layers_by_stack = box.maxStack if box.maxStack > 0 else 10000
        max_layers_by_height = int(self.container.height / layer_height) if layer_height > 0 else 1

        single_layer_weight = boxes_per_layer * box.weight
        if self.container.max_weight and single_layer_weight > 0:
            max_layers_by_weight = int(self.container.max_weight / single_layer_weight)
        else:
            max_layers_by_weight = 10000

        if box.maxStackWeight and box.maxStackWeight > 0:
            max_layers_by_item_weight = int(box.maxStackWeight / box.weight) + 1
        else:
            max_layers_by_item_weight = 10000

        if box.grounded:
            max_layers_by_flags = 1
        else:
            max_layers_by_flags = 10000

        max_layers = min(
            max_layers_by_stack,
            max_layers_by_height,
            max_layers_by_weight,
            max_layers_by_item_weight,
            max_layers_by_flags,
        )

        # Calculate total floor area coverage
        floor_area = self.container.width * self.container.length
        placement_area = sum(p.dims[0] * p.dims[1] for p in floor_placements)
        floor_coverage_ratio = placement_area / floor_area if floor_area > 0 else 0

        # Determine placement strategy based on item count and floor coverage
        # Case 1: Only 1 item per layer - center it
        # Case 2: Multiple items but don't fill floor (< 75% coverage) - center the group
        # Case 3: Items fill the floor well (>= 75% coverage) - use FirstLayerPlanner positions
        use_centered_placement = False
        
        if boxes_per_layer == 1:
            # Single item per layer - always center
            use_centered_placement = True
            logger.info("Single item per layer, using centered placement.")
        elif floor_coverage_ratio < 0.75:
            # Multiple items but don't fill floor well - center the group
            use_centered_placement = True
            logger.info(f"Floor coverage is {floor_coverage_ratio:.2f} (< 0.75), using centered placement.")

        if use_centered_placement:
            return self._pack_single_sku_centered(
                remaining_items, floor_placements, layer_height, max_layers, orientation_cache
            )
        else:
            # Use standard FirstLayerPlanner-based placement
            logger.info(f"Floor coverage is {floor_coverage_ratio:.2f} (>= 0.75), using standard placement.")
            return self._pack_single_sku_standard(
                remaining_items, floor_placements, layer_height, max_layers
            )

    def _pack_single_sku_centered(
        self,
        items: List[Item],
        floor_placements: List[Placement],
        layer_height: float,
        max_layers: int,
        orientation_cache: Dict[int, OrientationCache],
    ) -> List[Item]:
        """Pack single-SKU items with centered placement.
        
        Centers items (or group of items) on the pallet for better stability
        when items don't fill the entire floor.
        """
        logger.info("Executing single SKU centered packing.")
        if not items or not floor_placements:
            return items

        remaining_items = items[:]
        placed_ids: Set[int] = set()
        boxes_per_layer = len(floor_placements)

        # Calculate the bounding box of the floor placements
        min_x = min(p.x for p in floor_placements)
        max_x = max(p.x + p.dims[0] for p in floor_placements)
        min_y = min(p.y for p in floor_placements)
        max_y = max(p.y + p.dims[1] for p in floor_placements)

        group_width = max_x - min_x
        group_length = max_y - min_y

        # Calculate offset to center the group on the pallet
        pallet_center_x = self.container.width / 2.0
        pallet_center_y = self.container.length / 2.0
        group_center_x = (min_x + max_x) / 2.0
        group_center_y = (min_y + max_y) / 2.0

        # Offset to move group center to pallet center
        offset_x = pallet_center_x - group_center_x
        offset_y = pallet_center_y - group_center_y

        # Ensure the centered group stays within container bounds
        new_min_x = min_x + offset_x
        new_max_x = max_x + offset_x
        new_min_y = min_y + offset_y
        new_max_y = max_y + offset_y

        # Clamp to container bounds
        if new_min_x < 0:
            offset_x -= new_min_x
        elif new_max_x > self.container.width:
            offset_x -= (new_max_x - self.container.width)

        if new_min_y < 0:
            offset_y -= new_min_y
        elif new_max_y > self.container.length:
            offset_y -= (new_max_y - self.container.length)

        # Create centered placements
        centered_placements = []
        for p in floor_placements:
            centered_x = p.x + offset_x
            centered_y = p.y + offset_y
            centered_placements.append(Placement(
                item=p.item,
                x=centered_x,
                y=centered_y,
                z=0.0,
                rotation=p.rotation,
                dims=p.dims,
                supporters=p.supporters,
                layer_level=1,
            ))

        # Place items layer by layer using centered positions
        item_index = 0
        current_z = 0.0

        for layer_index in range(max_layers):
            if item_index >= len(remaining_items):
                break

            if current_z + layer_height > self.container.height + self.EPS:
                break

            layer_placed = 0
            for placement in centered_placements:
                if item_index >= len(remaining_items):
                    break

                item = remaining_items[item_index]
                dims = placement.dims

                if not self._validate_placement(item, placement.x, placement.y, current_z, dims):
                    item_index += 1
                    continue

                self._commit_placement(
                    item,
                    placement.x,
                    placement.y,
                    current_z,
                    placement.rotation,
                    layer_index + 1,
                )
                placed_ids.add(item.id)
                item_index += 1
                layer_placed += 1

            if layer_placed == 0:
                break

            current_z += layer_height

        return [it for it in remaining_items if it.id not in placed_ids]

    def _pack_single_sku_standard(
        self,
        items: List[Item],
        floor_placements: List[Placement],
        layer_height: float,
        max_layers: int,
    ) -> List[Item]:
        """Pack single-SKU items using standard FirstLayerPlanner positions.
        
        Used when items fill the floor well (>= 80% coverage).
        """
        logger.info("Executing single SKU standard packing.")
        if not items or not floor_placements:
            return items

        remaining_items = items[:]
        placed_ids: Set[int] = set()

        item_index = 0
        current_z = 0.0

        for layer_index in range(max_layers):
            if item_index >= len(remaining_items):
                break

            if current_z + layer_height > self.container.height + self.EPS:
                break

            layer_placed = 0
            for placement in floor_placements:
                if item_index >= len(remaining_items):
                    break

                item = remaining_items[item_index]
                dims = placement.dims

                if not self._validate_placement(item, placement.x, placement.y, current_z, dims):
                    item_index += 1
                    continue

                self._commit_placement(
                    item,
                    placement.x,
                    placement.y,
                    current_z,
                    placement.rotation,
                    layer_index + 1,
                )
                placed_ids.add(item.id)
                item_index += 1
                layer_placed += 1

            if layer_placed == 0:
                break

            current_z += layer_height

        return [it for it in remaining_items if it.id not in placed_ids]

    def _pack_items_centered_direct(
        self,
        items: List[Item],
        orientation_cache: Dict[int, OrientationCache],
    ) -> List[Item]:
        """Pack items directly with centered placement.
        
        This method handles small item counts by:
        1. Finding the best rotation for items
        2. Calculating centered positions
        3. Stacking items vertically at the center
        
        Used when FirstLayerPlanner fails or for small item counts.
        """
        logger.info("Executing direct centered packing for small item counts.")
        if not items:
            return []

        remaining_items = list(items)
        placed_ids: Set[int] = set()
        box = items[0]

        # Find the best rotation (prefer the one with largest footprint that fits)
        cache = orientation_cache.get(box.id)
        if not cache:
            cache = OrientationCache.build(box)

        best_rot = None
        best_dims = None
        best_footprint = 0.0

        for rot in cache.rotations:
            dims = cache.dimensions[rot]
            # Check if item fits in container
            if (dims[0] <= self.container.width + self.EPS and
                dims[1] <= self.container.length + self.EPS and
                dims[2] <= self.container.height + self.EPS):
                footprint = dims[0] * dims[1]
                if footprint > best_footprint:
                    best_footprint = footprint
                    best_rot = rot
                    best_dims = dims

        if best_rot is None or best_dims is None:
            # Item doesn't fit in any rotation
            return items

        item_width, item_length, item_height = best_dims

        # Calculate centered position
        center_x = (self.container.width - item_width) / 2.0
        center_y = (self.container.length - item_length) / 2.0

        # Ensure non-negative positions
        center_x = max(0.0, center_x)
        center_y = max(0.0, center_y)

        # Calculate max layers
        max_layers_by_stack = box.maxStack if box.maxStack > 0 else 10000
        max_layers_by_height = int(self.container.height / item_height) if item_height > 0 else 1

        if box.maxStackWeight and box.maxStackWeight > 0:
            max_layers_by_item_weight = int(box.maxStackWeight / box.weight) + 1
        else:
            max_layers_by_item_weight = 10000

        if box.grounded:
            max_layers_by_flags = 1
        else:
            max_layers_by_flags = 10000

        # Weight constraint for single column
        if self.container.max_weight and box.weight > 0:
            max_layers_by_weight = int(self.container.max_weight / box.weight)
        else:
            max_layers_by_weight = 10000

        max_layers = min(
            max_layers_by_stack,
            max_layers_by_height,
            max_layers_by_weight,
            max_layers_by_item_weight,
            max_layers_by_flags,
            len(remaining_items),  # Don't try more layers than items
        )

        # Place items in a single centered column
        current_z = 0.0
        item_idx = 0
        
        for layer_index in range(max_layers):
            if item_idx >= len(remaining_items):
                break

            if current_z + item_height > self.container.height + self.EPS:
                break

            # Check weight constraint
            if self.container.total_weight + box.weight > self.container.max_weight + self.EPS:
                break

            item = remaining_items[item_idx]
            
            # For floor placement (z=0), skip complex validation - just do basic checks
            # This ensures the item gets placed at center
            can_place = True
            if current_z > self.EPS:
                # For upper layers, use full validation
                can_place = self._validate_placement(item, center_x, center_y, current_z, best_dims)
            else:
                # For floor, just check bounds
                ox, oy, oz = self.container.origin
                can_place = check_bounds_within_container(
                    center_x, center_y, current_z,
                    item_width, item_length, item_height,
                    ox, oy, oz,
                    ox + self.container.width,
                    oy + self.container.length,
                    oz + self.container.height,
                )
            
            if not can_place:
                item_idx += 1
                continue

            # Commit placement
            self._commit_placement(
                item,
                center_x,
                center_y,
                current_z,
                best_rot,
                layer_index + 1,
            )
            placed_ids.add(item.id)
            remaining_items = [it for it in remaining_items if it.id != item.id]
            current_z += item_height

        return [it for it in items if it.id not in placed_ids]

    def _pack_mixed_sku(self, items: List[Item]) -> List[Item]:
        if not items:
            return []
        logger.info("Using BottomLeftFill for mixed SKUs on pallet.")
        unused: List[Item] = []
        self.placements = []
        removed_ids: Set[int] = set()

        # Avoid re-placing items that are already in the container
        placed_ids: Set[int] = {item.id for item in self.container.items}

        # Higher-ranked, heavier, higher-pickup_priority items go first for stability
        sorted_items = sorted(
            items,
            key=lambda it: (
                -getattr(it, "final_rank", 0),
                # -getattr(it, "pickup_priority", 1),
                # -it.weight,
                # -it.volume,
                # str(it.id),
            ),
        )

        for item in sorted_items:
            if item.id in placed_ids:
                continue

            if not self._priority_allowed_on_pallet(self._priority_of(item)):
                unused.append(item)
                continue

            if self.container.total_weight + item.weight > self.container.max_weight + self.EPS:
                unused.append(item)
                continue

            blf = BottomLeftFill(self.container, must_be_on_top=self.must_be_on_top)
            best = blf.find_best_position_for_item(item)

            if best is None:
                unused.append(item)
                continue

            x, y, z, rot, new_layer = best
            dims = item.get_rotated_dimensions(rot)

            if not self._validate_placement(item, x, y, z, dims):
                unused.append(item)
                continue

            self._commit_placement(item, x, y, z, rot, new_layer)
            supporters = get_supporters(self.container, x, y, z, dims, self.EPS)
            self.placements.append(
                Placement(
                    item=item,
                    x=x,
                    y=y,
                    z=z,
                    rotation=rot,
                    dims=dims,
                    supporters=supporters,
                    layer_level=new_layer,
                )
            )
            placed_ids.add(item.id)

        removed_ids = self._cleanup_overlaps_and_duplicates()
        if removed_ids:
            self.placements = [pl for pl in self.placements if pl.item.id not in removed_ids]
            unused.extend([it for it in items if it.id in removed_ids and it.id not in {u.id for u in unused}])

        return unused

    def _cleanup_overlaps_and_duplicates(self) -> Set[int]:
        """
        Remove any duplicate IDs or overlapping items in the container.

        Returns:
            Set of removed item IDs.
        """
        cleaned: List[Item] = []
        seen_ids: Set[int] = set()
        removed_ids: Set[int] = set()

        def overlaps(a: Item, b: Item) -> bool:
            ax, ay, az = a.position or (0.0, 0.0, 0.0)
            adx, ady, adz = a.get_rotated_dimensions()
            bx, by, bz = b.position or (0.0, 0.0, 0.0)
            bdx, bdy, bdz = b.get_rotated_dimensions()
            return not (
                ax + adx <= bx + self.EPS
                or bx + bdx <= ax + self.EPS
                or ay + ady <= by + self.EPS
                or by + bdy <= ay + self.EPS
                or az + adz <= bz + self.EPS
                or bz + bdz <= az + self.EPS
            )

        for item in self.container.items:
            if item.id in seen_ids:
                self.container.total_weight -= item.weight
                removed_ids.add(item.id)
                continue

            has_overlap = any(overlaps(item, placed) for placed in cleaned)
            if has_overlap:
                self.container.total_weight -= item.weight
                removed_ids.add(item.id)
                continue

            cleaned.append(item)
            seen_ids.add(item.id)

        if removed_ids:
            self.container.items = cleaned
        return removed_ids

    def _compute_center_distance(
        self, x: float, y: float, dims: Tuple[float, float, float]
    ) -> float:
        pallet_center_x = self.container.width / 2.0
        pallet_center_y = self.container.length / 2.0
        item_center_x = x + dims[0] / 2.0
        item_center_y = y + dims[1] / 2.0
        return ((item_center_x - pallet_center_x) ** 2 + (item_center_y - pallet_center_y) ** 2) ** 0.5

    def _score_position_for_plateau(
        self,
        x: float,
        y: float,
        z: float,
        dims: Tuple[float, float, float],
        item_weight: float,
        max_weight_in_batch: float,
    ) -> Tuple[float, float, float, float]:
        center_dist = self._compute_center_distance(x, y, dims)
        weight_ratio = item_weight / max(max_weight_in_batch, self.EPS)
        center_penalty = center_dist * (1.0 - weight_ratio * 0.8)
        return (z, center_penalty, x, y)

    def _pack_plateau_first(self, items: List[Item]) -> List[Item]:
        if not items:
            return []

        unique_skus = set(item.itemType_id for item in items)

        if len(unique_skus) > 1:
            sorted_items = sorted(
                items,
                key=lambda it: (-(it.width * it.length), -it.weight, -it.volume, -it.final_rank, str(it.id))
            )
        else:
            sorted_items = sorted(
                items,
                key=lambda it: (-it.weight, -it.volume, -it.final_rank, str(it.id))
            )

        max_weight = max(it.weight for it in sorted_items) if sorted_items else 1.0

        remaining_items = sorted_items[:]
        placed_ids: Set[int] = set()

        grounded = [it for it in remaining_items if it.grounded]
        non_grounded = [it for it in remaining_items if not it.grounded]
        floor_candidates = grounded + non_grounded

        if floor_candidates:
            logger.info("Building floor layer for mixed SKU.")
            best_placements: Tuple[List[Placement], Set[int]] = ([], set())
            best_coverage = -1.0

            logger.info("Trying initial sorting for dense layer.")
            floor_placements_1, floor_placed_ids_1 = self._build_dense_layer(
                floor_candidates, 0.0, max_weight
            )
            coverage_1 = sum(p.dims[0] * p.dims[1] for p in floor_placements_1)
            best_coverage = coverage_1
            best_placements = (floor_placements_1, floor_placed_ids_1)

            if len(unique_skus) > 1:
                logger.info("Trying alternative sorting strategies for denser floor layer.")
                alt_candidates_2 = sorted(
                    floor_candidates,
                    key=lambda it: (-(it.width * it.length), -it.final_rank, str(it.id))
                )
                logger.info("Trying 2nd sorting for dense layer.")
                floor_placements_2, floor_placed_ids_2 = self._build_dense_layer(
                    alt_candidates_2, 0.0, max_weight
                )
                coverage_2 = sum(p.dims[0] * p.dims[1] for p in floor_placements_2)
                if coverage_2 > best_coverage:
                    for placement in best_placements[0]:
                        if placement.item in self.container.items:
                            self.container.items.remove(placement.item)
                            self.container.total_weight -= placement.item.weight
                    best_coverage = coverage_2
                    best_placements = (floor_placements_2, floor_placed_ids_2)
                else:
                    # Revert strategy 2 if not better
                    for placement in floor_placements_2:
                        if placement.item in self.container.items:
                            self.container.items.remove(placement.item)
                            self.container.total_weight -= placement.item.weight

                alt_candidates_3 = sorted(
                    floor_candidates,
                    key=lambda it: ((it.width * it.length), -it.final_rank, str(it.id))
                )
                logger.info("Trying 3rd sorting for dense layer.")
                floor_placements_3, floor_placed_ids_3 = self._build_dense_layer(
                    alt_candidates_3, 0.0, max_weight
                )
                coverage_3 = sum(p.dims[0] * p.dims[1] for p in floor_placements_3)
                if coverage_3 > best_coverage:
                    for placement in best_placements[0]:
                        if placement.item in self.container.items:
                            self.container.items.remove(placement.item)
                            self.container.total_weight -= placement.item.weight
                    best_coverage = coverage_3
                    best_placements = (floor_placements_3, floor_placed_ids_3)

            floor_placements, floor_placed_ids = best_placements
            for placement in floor_placements:
                placed_ids.add(placement.item.id)
            remaining_items = [it for it in remaining_items if it.id not in placed_ids]

        max_passes = 5
        for pass_num in range(max_passes):
            logger.info(f"Building upper layer, pass {pass_num + 1}/{max_passes}.")
            upper_candidates = [
                it for it in remaining_items if not it.grounded and it.id not in placed_ids
            ]

            if not upper_candidates:
                break

            layer_placements, layer_placed_ids = self._build_dense_layer(
                upper_candidates, 1.0, max_weight
            )

            if not layer_placements:
                break

            for placement in layer_placements:
                placed_ids.add(placement.item.id)

            remaining_items = [it for it in remaining_items if it.id not in placed_ids]

        return remaining_items

    def _build_dense_layer(
        self,
        candidates: List[Item],
        layer_z: float,
        max_weight: float,
    ) -> Tuple[List[Placement], Set[int]]:
        placements: List[Placement] = []
        placed_ids: Set[int] = set()
        logger.info(f"Building a dense layer at z={layer_z}.")

        is_floor_layer = layer_z < self.EPS
        unique_skus = set(item.itemType_id for item in candidates)

        if len(unique_skus) > 1 and candidates:
            weights = sorted([it.weight for it in candidates], reverse=True)
            weight_threshold = weights[min(len(weights) - 1, int(len(weights) * 0.3))]
        else:
            weight_threshold = 0.0

        packer_2d = MaxRects2D(self.container.length, self.container.width) if is_floor_layer else None
        if is_floor_layer:
            logger.info("Using MaxRects2D for floor layer.")

        for item in candidates:
            if item.id in placed_ids:
                continue

            if self.container.total_weight + item.weight > self.container.max_weight + self.EPS:
                continue

            if not self._priority_allowed_on_pallet(self._priority_of(item)):
                continue

            cache = self.orientation_cache.get(item.id)
            if not cache:
                cache = OrientationCache.build(item)

            best_placement: Optional[Tuple[float, float, float, int, Tuple[float, float, float]]] = None
            best_score: Optional[Tuple[float, float, float, float]] = None

            if is_floor_layer:
                for rot in cache.rotations:
                    dims = cache.dimensions[rot]

                    if dims[2] > self.container.height + self.EPS:
                        continue

                    rect = None
                    if len(unique_skus) > 1 and item.weight >= weight_threshold:
                        rect = self._find_center_position(packer_2d, dims[0], dims[1])
                        if rect is None:
                            rect = packer_2d.find_position(dims[0], dims[1], allow_rotation=False)
                    else:
                        rect = packer_2d.find_position(dims[0], dims[1], allow_rotation=False)

                    if rect is None:
                        continue

                    x, y = rect.x, rect.y
                    z = 0.0
                    actual_dims = (dims[0], dims[1], dims[2])

                    if not self._validate_placement(item, x, y, z, actual_dims):
                        continue

                    if len(unique_skus) > 1 and item.weight >= weight_threshold:
                        center_dist = self._compute_center_distance(x, y, actual_dims)
                        score = (z, center_dist, y, x)
                    else:
                        score = (z, y, x, 0.0)

                    if best_score is None or score < best_score:
                        best_score = score
                        best_placement = (x, y, z, rot, actual_dims)
            else:
                # logger.info("Using BottomLeftFill for upper layers.")
                blf = BottomLeftFill(self.container, must_be_on_top=self.must_be_on_top)
                result = blf.find_best_position_for_item(item)

                if result is not None:
                    x, y, z, rot, new_layer = result
                    dims = item.get_rotated_dimensions(rot)

                    if not self._validate_placement(item, x, y, z, dims):
                        continue

                    if len(unique_skus) > 1 and item.weight >= weight_threshold:
                        center_dist = self._compute_center_distance(x, y, dims)
                        score = (z, center_dist, y, x)
                    else:
                        score = (z, y, x, 0.0)

                    best_score = score
                    best_placement = (x, y, z, rot, dims)

            if best_placement:
                x, y, z, rot, dims = best_placement

                if is_floor_layer and packer_2d:
                    commit_rect = Rect(x, y, dims[0], dims[1])
                    packer_2d.commit(commit_rect)

                layer_num = self._compute_layer_number(z)
                self._commit_placement(item, x, y, z, rot, layer_num)
                placed_ids.add(item.id)

                placements.append(Placement(
                    item=item,
                    x=x,
                    y=y,
                    z=z,
                    rotation=rot,
                    dims=dims,
                    layer_level=layer_num,
                ))

        return placements, placed_ids

    def _find_center_position(
        self,
        packer: MaxRects2D,
        width: float,
        height: float,
    ) -> Optional[Rect]:
        pallet_center_x = self.container.width / 2.0
        pallet_center_y = self.container.length / 2.0

        best_rect: Optional[Rect] = None
        best_center_dist = float('inf')

        for free in packer.free_rects:
            if width <= free.width + EPS and height <= free.height + EPS:
                ideal_x = pallet_center_x - width / 2.0
                ideal_y = pallet_center_y - height / 2.0

                x = max(free.x, min(ideal_x, free.x + free.width - width))
                y = max(free.y, min(ideal_y, free.y + free.height - height))

                item_center_x = x + width / 2.0
                item_center_y = y + height / 2.0
                center_dist = ((item_center_x - pallet_center_x) ** 2 +
                              (item_center_y - pallet_center_y) ** 2) ** 0.5

                if center_dist < best_center_dist:
                    best_center_dist = center_dist
                    best_rect = Rect(x, y, width, height, rotated=False)

            if height <= free.width + EPS and width <= free.height + EPS:
                ideal_x = pallet_center_x - height / 2.0
                ideal_y = pallet_center_y - width / 2.0

                x = max(free.x, min(ideal_x, free.x + free.width - height))
                y = max(free.y, min(ideal_y, free.y + free.height - width))

                item_center_x = x + height / 2.0
                item_center_y = y + width / 2.0
                center_dist = ((item_center_x - pallet_center_x) ** 2 +
                              (item_center_y - pallet_center_y) ** 2) ** 0.5

                center_dist += 0.01

                if center_dist < best_center_dist:
                    best_center_dist = center_dist
                    best_rect = Rect(x, y, height, width, rotated=True)

        return best_rect

    def _compute_layer_number(self, z: float) -> int:
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

    def _pack_blf_fallback(self, items: List[Item]) -> List[Item]:
        logger.info("Executing BLF fallback packing.")
        remaining = items[:]
        placed_ids: Set[int] = set()

        for item in items:
            if item.id in placed_ids:
                continue

            if not self._priority_allowed_on_pallet(self._priority_of(item)):
                continue

            blf = BottomLeftFill(self.container, must_be_on_top=self.must_be_on_top)
            result = blf.find_best_position_for_item(item)

            if result is None:
                continue

            x, y, z, rot, new_layer = result
            dims = item.get_rotated_dimensions(rot)

            if not self._validate_placement(item, x, y, z, dims):
                continue

            self._commit_placement(item, x, y, z, rot, new_layer)
            placed_ids.add(item.id)

        return [it for it in remaining if it.id not in placed_ids]

    def _map_item_groups(self) -> Dict[int, str]:
        mapping: Dict[int, str] = {}
        for gid, members in self.co_loc_groups.items():
            for item_id in members:
                mapping[item_id] = gid
        return mapping

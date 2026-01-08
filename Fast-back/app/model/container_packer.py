from __future__ import annotations
 
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .entities import (
    Item,
    Container,
    OrientationCache,
    Placement,
    getRotDim,
    door_type_map,
)
from .blf_packer import BottomLeftFill
from .common_packers import FirstLayerPlanner

logger = logging.getLogger(__name__)


class DoorContainerPacker:
    """Hybrid EP/EMS packer for containers with doors (door_type_int in [0,1]) using front-door logic for all door types."""

    def __init__(
        self,
        container: Container,
        orientation_cache: Dict[int, OrientationCache],
        must_be_on_top: Optional[Dict[int, bool]] = None,
        co_loc_groups: Optional[Dict[str, Set[int]]] = None,
    ) -> None:
        self.container = container
        self.orientation_cache = orientation_cache
        self.must_be_on_top = must_be_on_top or {}
        self.co_loc_groups = co_loc_groups or {}
        self.item_to_group = self._map_item_groups()
        self.placements: List[Placement] = []

        dp_raw = getattr(self.container, "door_position", None)
        if isinstance(dp_raw, str):
            dp = dp_raw.strip().lower()
            if dp:
                effective_door_type = 1  # any declared door → front-door logic
            else:
                effective_door_type = getattr(self.container, "door_type_int", -1)
        else:
            effective_door_type = getattr(self.container, "door_type_int", -1)

        # Normalize legacy side-door flag (0) to front-door behaviour as well.
        if effective_door_type in (0, 1):
            effective_door_type = 1
        else:
            effective_door_type = -1

        self.container.door_type_int = effective_door_type
        if effective_door_type == 1:
            self.door_axis = ("y", container.length)
        else:
            self.door_axis = (None, 1.0)
        self.EPS = 1e-5

        self.container.is_side_door = False
        self.container.is_front_door = (self.container.door_type_int == 1)

    def _sort_items(self, items: List[Item]) -> List[Item]:
        def key_fn(x: Item) -> Tuple:
            sid = str(getattr(x, "id", ""))
            return (-x.final_rank, -x.pickup_priority, -getattr(x, "weight", 0.0), -x.volume, sid)
        return sorted(items, key=key_fn)

    def _create_priority_mapping(self, items: List[Item]) -> Dict[int, int]:
        """Create a mapping from original priorities to contiguous ranks."""
        unique_priorities = sorted(set(item.pickup_priority for item in items))
        priority_map = {orig: rank + 1 for rank, orig in enumerate(unique_priorities)}
        return priority_map

    def _apply_priority_mapping(
        self, items: List[Item], priority_map: Dict[int, int]
    ) -> Dict[int, int]:
        """Apply pickup_priority mapping to items and return a restore map."""
        original_priorities = {}
        for item in items:
            original_priorities[item.id] = item.pickup_priority
            item.pickup_priority = priority_map.get(item.pickup_priority, item.pickup_priority)
        return original_priorities

    def _restore_priorities(
        self, items: List[Item], original_priorities: Dict[int, int]
    ) -> None:
        """Restore original priorities to items."""
        for item in items:
            if item.id in original_priorities:
                item.pickup_priority = original_priorities[item.id]


    def _are_items_identical(self, items: List[Item]) -> bool:
        """Check if all items have identical dimensions and weight."""
        if not items:
            return True
        
        first = items[0]
        EPS = 1e-4
        
        for item in items[1:]:
            if (abs(item.length - first.length) > EPS or
                abs(item.width - first.width) > EPS or
                abs(item.height - first.height) > EPS or
                abs(item.weight - first.weight) > EPS):
                return False
        
        return True
    
    def _compute_grid_capacity(
        self,
        item: Item,
        rotation: int,
    ) -> Tuple[int, float, Tuple[float, float, float]]:
        """
        Compute theoretical grid capacity for a rotation.
        
        Args:
            item: The item to pack
            rotation: Rotation to test (0-5)
            
        Returns:
            (total_capacity, utilization_ratio, rotated_dims)
        """
        # Get rotated dimensions
        dims = item.get_rotated_dimensions(rotation)
        item_width, item_length, item_height = dims
        
        # Check if item fits in container at all
        if (item_width > self.container.width + self.EPS or
            item_length > self.container.length + self.EPS or
            item_height > self.container.height + self.EPS):
            return 0, 0.0, dims
        
        # Calculate how many items fit in each dimension
        items_x = int(self.container.width / item_width) if item_width > self.EPS else 0
        items_y = int(self.container.length / item_length) if item_length > self.EPS else 0
        items_z = int(self.container.height / item_height) if item_height > self.EPS else 0
        
        # Apply maxStack constraint (items_z is number of layers)
        if item.maxStack > 0:
            items_z = min(items_z, item.maxStack)
        
        # Calculate total capacity
        items_per_layer = items_x * items_y
        total_capacity = items_per_layer * items_z
        
        # Apply weight constraint
        if self.container.max_weight > self.EPS and item.weight > self.EPS:
            max_items_by_weight = int(self.container.max_weight / item.weight)
            total_capacity = min(total_capacity, max_items_by_weight)
        
        # Calculate volume utilization
        if total_capacity > 0 and self.container.volume > self.EPS:
            utilization = (total_capacity * item.volume) / self.container.volume
        else:
            utilization = 0.0
        
        return total_capacity, utilization, dims
    
    def _find_optimal_rotation_grid(
        self,
        item: Item,
    ) -> Optional[Tuple[int, Tuple[float, float, float], int]]:
        """
        Find rotation with maximum grid capacity for identical items.
        
        Args:
            item: Sample item to analyze
            
        Returns:
            (best_rotation, best_dims, capacity) or None if no valid rotation
        """
        # Get allowed rotations
        allowed_rotations = [0, 1] if item.isSideUp else [0, 1, 2, 3, 4, 5]
        
        best_rotation = None
        best_dims = None
        best_capacity = 0
        best_utilization = 0.0
        
        for rotation in allowed_rotations:
            capacity, utilization, dims = self._compute_grid_capacity(item, rotation)

            logger.info(f"Rotation {rotation}: Capacity {capacity}, Utilization {utilization}")
            
            # Select rotation with highest capacity (tie-break with utilization)
            if (capacity > best_capacity or 
                (capacity == best_capacity and utilization > best_utilization)):
                best_capacity = capacity
                best_utilization = utilization
                best_rotation = rotation
                best_dims = dims
        
        if best_rotation is not None:
            return best_rotation, best_dims, best_capacity
        
        return None

    def pack(self, items: List[Item], skip_floor_prefill: bool = False) -> List[Item]:
        """Pack items into the single container using Bottom-Left Fill algorithm.

        Items are placed ONE-BY-ONE in strict final_rank order (descending).
        For sim_batch items (pallets), use FirstLayerPlanner to maximize floor utilization.
        For single-SKU items, use optimal rotation from grid analysis.
        """
        unused: List[Item] = []

        logger.info(f"Packing {len(items)} items into container with dimensions {self.container.width} x {self.container.length} x {self.container.height}")

        # Check if all items are identical (single-SKU)
        if items and self._are_items_identical(items) and len(self.container.items) == 0:
            logger.info("All items are identical, using grid-based rotation selection")

            # Find optimal rotation for this single SKU
            optimal_rotation_result = self._find_optimal_rotation_grid(items[0])
            if optimal_rotation_result is not None:
                rotation, dims, capacity = optimal_rotation_result
                logger.info(f"Optimal rotation {rotation} with capacity {capacity}, dims {dims}")
                # Use BottomLeftFill with the optimal rotation
                return self._pack_blf_fallback(items, forced_rotation=rotation)
            else:
                logger.info("No optimal rotation found, falling back to standard BLF")

        else:
            logger.info("Not all items are identical, using standard BLF")

        all_items = items + list(self.container.items)
        priority_map = self._create_priority_mapping(all_items)

        original_priorities_items = self._apply_priority_mapping(items, priority_map)
        original_priorities_container = self._apply_priority_mapping(
            list(self.container.items), priority_map
        )

        # Separate sim_batch items (pallets) from regular items
        sim_batch_items = [item for item in items if getattr(item, "itemType", None) == "sim_batch"]
        regular_items = [item for item in items if getattr(item, "itemType", None) != "sim_batch"]

        print(
            {
                "event": "door_container_packer_strategy",
                "container_id": getattr(self.container, "id", None),
                "door_type_int": getattr(self.container, "door_type_int", None),
                "algorithm": "BottomLeftFill",
                "has_sim_batch_items": bool(sim_batch_items),
            },
            flush=True,
        )

        # If we have sim_batch items and the container is empty, use FirstLayerPlanner
        if sim_batch_items and len(self.container.items) == 0 and not skip_floor_prefill:
            floor_placements, placed_ids = self._pack_sim_batch_floor(sim_batch_items)

            # Apply the floor placements
            for placement in floor_placements:
                item = placement.item
                item.position = (placement.x, placement.y, placement.z)
                item.rotation = placement.rotation
                item.layer = 1
                item.stackLimit = 1
                self.container.items.append(item)
                self.container.total_weight += item.weight

            # Remove placed items from sim_batch_items
            sim_batch_items = [item for item in sim_batch_items if item.id not in placed_ids]

        # Combine remaining sim_batch items with regular items
        remaining_items = sim_batch_items + regular_items

        # Pack remaining items using standard BLF approach
        # Track IDs of items already placed to prevent duplicates
        already_placed_ids = {item.id for item in self.container.items}

        rank_groups = defaultdict(list)
        for item in remaining_items:
            rank_groups[item.final_rank].append(item)

        for rank in sorted(rank_groups.keys(), reverse=True):
            group_items = rank_groups[rank]

            for item in group_items:
                # Skip if item was already placed (duplicate prevention)
                if item.id in already_placed_ids:
                    continue

                if (
                    self.container.total_weight + item.weight
                    > self.container.max_weight + self.EPS
                ):
                    unused.append(item)
                    continue

                blf = BottomLeftFill(self.container, must_be_on_top=self.must_be_on_top)
                best = blf.find_best_position_for_item(item)
                if best is None:
                    unused.append(item)
                    continue

                x, y, z, rot, new_layer = best
                item.position = (x, y, z)
                item.rotation = rot
                item.layer = new_layer
                item.stackLimit = new_layer
                self.container.items.append(item)
                self.container.total_weight += item.weight
                already_placed_ids.add(item.id)  # Track this placement

        self._restore_priorities(items, original_priorities_items)
        self._restore_priorities(list(self.container.items), original_priorities_container)

        # Final safety check: remove any duplicate items in container
        seen_ids = set()
        unique_items = []
        for item in self.container.items:
            if item.id not in seen_ids:
                unique_items.append(item)
                seen_ids.add(item.id)
            else:
                # Duplicate detected - subtract its weight
                self.container.total_weight -= item.weight
                logger.warning(f"Duplicate item {item.id} removed from container {self.container.id}")

        if len(unique_items) != len(self.container.items):
            logger.warning(f"Container {self.container.id}: Removed {len(self.container.items) - len(unique_items)} duplicate items")
            self.container.items = unique_items

        return unused

    def _pack_blf_fallback(self, items: List[Item], forced_rotation: Optional[int] = None) -> List[Item]:
        """
        Pack items using BottomLeftFill algorithm with optional forced rotation.

        When forced_rotation is provided, items are packed using only that rotation orientation.
        This is useful for single-SKU optimization where we've determined the optimal rotation.

        Args:
            items: Items to pack
            forced_rotation: If provided, use only this rotation (0-5) for all items

        Returns:
            List of items that could not be placed
        """
        unused: List[Item] = []
        placed_ids: Set[int] = set()

        # Sort items by final_rank (descending)
        sorted_items = sorted(items, key=lambda x: -x.final_rank)

        if forced_rotation is not None:
            logger.info(f"Packing {len(sorted_items)} items with forced rotation {forced_rotation}")

        for item in sorted_items:
            if item.id in placed_ids:
                continue

            # Check weight constraint
            if self.container.total_weight + item.weight > self.container.max_weight + self.EPS:
                unused.append(item)
                continue

            # Create BLF instance
            blf = BottomLeftFill(self.container, must_be_on_top=self.must_be_on_top)
            result = blf.find_best_position_for_item(item, forced_rotation=forced_rotation)

            if result is None:
                unused.append(item)
                continue

            x, y, z, rot, new_layer = result
            item.position = (x, y, z)
            # If we forced a rotation, store that; otherwise use the rotation returned by BLF
            item.rotation = forced_rotation if forced_rotation is not None else rot
            item.layer = new_layer
            item.stackLimit = new_layer
            self.container.items.append(item)
            self.container.total_weight += item.weight
            placed_ids.add(item.id)

        logger.info(f"BLF packing complete: {len(placed_ids)} placed, {len(unused)} unused")
        return unused

    def _pack_sim_batch_floor(self, items: List[Item]) -> Tuple[List[Placement], Set[int]]:
        """Use FirstLayerPlanner to optimize floor placement of sim_batch items (pallets)."""
        # Build group registry for FirstLayerPlanner
        group_registry: Dict[str, Set[int]] = {}
        for gid, members in self.co_loc_groups.items():
            group_registry[gid] = members

        # Create FirstLayerPlanner
        planner = FirstLayerPlanner(
            container=self.container,
            orientation_cache=self.orientation_cache,
            item_to_group=self.item_to_group,
            group_registry=group_registry,
        )

        # Plan the floor layout
        placements, placed_ids = planner.plan(items)

        return placements, placed_ids

    def _create_bundles(
        self, items: List[Item]
    ) -> Tuple[List[List[Item]], List[Item]]:
        """Group items into bundles based on co-location groups and order_id."""
        bundle_map: Dict[Tuple[str, str], List[Item]] = {}
        individual_items: List[Item] = []

        for item in items:
            group_id = self.item_to_group.get(item.id)
            if group_id:
                key = (group_id, item.order_id)
                if key not in bundle_map:
                    bundle_map[key] = []
                bundle_map[key].append(item)
            else:
                individual_items.append(item)

        bundles: List[List[Item]] = []
        for key, group_items in bundle_map.items():
            if len(group_items) >= 2:
                group_items.sort(key=lambda x: -x.final_rank)
                bundles.append(group_items)
            else:
                individual_items.extend(group_items)

        bundles.sort(key=lambda b: -max(it.final_rank for it in b))
        individual_items.sort(key=lambda x: -x.final_rank)

        return bundles, individual_items

    def _place_bundle(self, bundle: List[Item]) -> bool:
        """Place a bundle of co-located items as a 2D micro-layout."""
        if not bundle:
            return True

        bundle_weight = sum(item.weight for item in bundle)
        if self.container.total_weight + bundle_weight > self.container.max_weight + self.EPS:
            return False

        layout = self._create_bundle_layout(bundle)
        if not layout:
            return False

        blf = BottomLeftFill(self.container, must_be_on_top=self.must_be_on_top)
        bundle_pos = blf.find_best_position_for_bundle(layout)
        if bundle_pos is None:
            return False

        base_x, base_y, base_z = bundle_pos

        for item, (offset_x, offset_y, offset_z, rot) in layout:
            item.position = (base_x + offset_x, base_y + offset_y, base_z + offset_z)
            item.rotation = rot
            item.stackLimit = item.maxStack
            self.container.items.append(item)
            self.container.total_weight += item.weight

        return True

    def _create_bundle_layout(
        self, bundle: List[Item]
    ) -> Optional[List[Tuple[Item, Tuple[float, float, float, int]]]]:
        """Create a 2D micro-layout for a bundle of items."""
        if not bundle:
            return None

        layout: List[Tuple[Item, Tuple[float, float, float, int]]] = []
        current_x = 0.0

        for item in bundle:
            dims = getRotDim(item.width, item.length, item.height, 0)
            dx, dy, dz = dims
            layout.append((item, (current_x, 0.0, 0.0, 0)))
            current_x += dx

        return layout

    def _map_item_groups(self) -> Dict[int, str]:
        """Map item IDs to their co-location group IDs."""
        mapping: Dict[int, str] = {}
        for gid, members in self.co_loc_groups.items():
            for item_id in members:
                mapping[item_id] = gid
        return mapping

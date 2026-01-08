from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import numba

from .entities import (
    EPS,
    Item,
    Container,
    getRotDim,
)
from .geometry import (
    generate_and_filter_positions_numba,
    check_collision_numba,
    check_priority_adjacency_numba,
    check_support_and_stacking_numba,
)


@numba.jit(nopython=True)
def _generate_positions_numba(
    placed_items_data: np.ndarray,
    item_dims: np.ndarray,
    container_bounds: np.ndarray,
    epsilon: float,
) -> np.ndarray:
    """Generate and filter candidate positions using Numba (fast)."""
    max_positions = 1 + placed_items_data.shape[0] * 6
    positions = np.empty((max_positions, 3), dtype=np.float64)
    count = 0

    xmin, ymin, zmin, xmax, ymax, zmax = container_bounds

    positions[count, 0] = xmin
    positions[count, 1] = ymin
    positions[count, 2] = zmin
    count += 1

    dx, dy, dz = item_dims

    for i in range(placed_items_data.shape[0]):
        px, py, pz, pdx, pdy, pdz = placed_items_data[i, :6]

        x, y, z = px + pdx, py, pz
        if (x >= xmin - epsilon and y >= ymin - epsilon and z >= zmin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

        x, y, z = px, py + pdy, pz
        if (x >= xmin - epsilon and y >= ymin - epsilon and z >= zmin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

        x, y, z = px, py, pz + pdz
        if (x >= xmin - epsilon and y >= ymin - epsilon and z >= zmin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

        if pz > zmin + epsilon:
            x, y, z = px + pdx, py, zmin
            if (x >= xmin - epsilon and y >= ymin - epsilon and
                x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
                positions[count, 0] = x
                positions[count, 1] = y
                positions[count, 2] = z
                count += 1

        if pz > zmin + epsilon:
            x, y, z = px, py + pdy, zmin
            if (x >= xmin - epsilon and y >= ymin - epsilon and
                x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
                positions[count, 0] = x
                positions[count, 1] = y
                positions[count, 2] = z
                count += 1

        x, y, z = px + pdx, py + pdy, zmin
        if (x >= xmin - epsilon and y >= ymin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

    return positions[:count]


class BottomLeftFill:
    """Bottom-Left Fill algorithm for 3D bin packing."""

    def __init__(
        self,
        container: Container,
        must_be_on_top: Optional[Dict[int, bool]] = None,
    ):
        self.container = container
        self.epsilon = 1e-5
        self.must_be_on_top = must_be_on_top or {}

    def find_best_position_for_item(
        self,
        item_to_place: Item,
        forced_rotation: Optional[int] = None,
    ) -> Optional[Tuple[float, float, float, int, int]]:
        """
        Tries all valid rotations to find the best placement.

        Returns:
            (x, y, z, rot, new_layer) or None if no valid position found
        """
        original_rotation = item_to_place.rotation
        if forced_rotation is not None:
            rotations_to_try = [forced_rotation]
        else:
            rotations_to_try = [0, 1] if item_to_place.isSideUp else [0, 1, 2, 3, 4, 5]
        door_type = getattr(self.container, 'door_type_int', -1)
        enforce_order_stacking = door_type != -1
        door_axis_idx = 1 if door_type == 1 else (0 if door_type == 0 else None)

        current_frontier = 0.0
        if door_axis_idx is not None and self.container.items:
            current_frontier = max(
                (
                    (p_item.position[door_axis_idx] + p_item.get_rotated_dimensions()[door_axis_idx])
                    for p_item in self.container.items
                    if p_item.position is not None
                ),
                default=0.0,
            )

        def score_position(pos: np.ndarray, dims: np.ndarray) -> Tuple:
            if door_axis_idx is not None:
                frontier_after = max(current_frontier, pos[door_axis_idx] + dims[door_axis_idx])
            else:
                frontier_after = pos[2]

            if door_type == 1:
                tie = (pos[1], pos[2], pos[0])
            elif door_type == 0:
                tie = (pos[0], pos[2], pos[1])
            else:
                tie = (pos[2], pos[1], pos[0])
            return (round(frontier_after, 5),) + tuple(tie)

        type_id_map = {}
        next_tid = 1

        def get_type_int(t: str) -> int:
            nonlocal next_tid
            if t not in type_id_map:
                type_id_map[t] = next_tid
                next_tid += 1
            return type_id_map[t]

        candidate_type_int = get_type_int(item_to_place.itemType_id)

        num_placed = len(self.container.items)
        placed_items_data = np.zeros((num_placed, 15), dtype=np.float64)
        for i, p_item in enumerate(self.container.items):
            p_dims = p_item.get_rotated_dimensions()
            px, py, pz = p_item.position
            placed_items_data[i, 0:3] = (px, py, pz)
            placed_items_data[i, 3:6] = p_dims
            placed_items_data[i, 6] = float(get_type_int(p_item.itemType_id))
            placed_items_data[i, 7] = float(getattr(p_item, "layer", 1))
            placed_items_data[i, 8] = float(p_item.maxStack)
            placed_items_data[i, 9] = float(p_item.maxStackWeight if p_item.maxStackWeight else 1e9)
            placed_items_data[i, 10] = 1.0 if getattr(p_item, "must_be_on_top", False) else 0.0
            placed_items_data[i, 11] = float(p_item.weight)
            placed_items_data[i, 12] = float(getattr(p_item, "pickup_priority", 1))
            placed_items_data[i, 13] = float(hash(getattr(p_item, "order_id", "")) % (2**31))
            placed_items_data[i, 14] = float(getattr(p_item, "senddate_ts", 0))

        placed_geom = placed_items_data[:, :6]
        ox, oy, oz = self.container.origin
        container_bounds = np.array(
            [ox, oy, oz,
             ox + self.container.width,
             oy + self.container.length,
             oz + self.container.height],
            dtype=np.float64,
        )

        def cross_floor_positions(item_dims: np.ndarray) -> np.ndarray:
            if placed_geom.shape[0] == 0:
                return np.empty((0, 3), dtype=np.float64)

            xs = {ox}
            ys = {oy}
            for row in placed_geom:
                px, py, _, pdx, pdy, _ = row
                xs.add(px + pdx)
                ys.add(py + pdy)

            dx, dy, dz = item_dims
            results: List[Tuple[float, float, float]] = []
            for x in xs:
                if x + dx > container_bounds[3] + self.epsilon:
                    continue
                for y in ys:
                    if y + dy > container_bounds[4] + self.epsilon:
                        continue
                    if dz > container_bounds[5] + self.epsilon:
                        continue
                    results.append((x, y, oz))

            if not results:
                return np.empty((0, 3), dtype=np.float64)
            grid_size = max(self.epsilon * 10, 0.1)
            arr = np.array(results, dtype=np.float64)
            rounded = np.round(arr / grid_size).astype(np.int64)
            _, uniq_idx = np.unique(
                rounded.view(dtype=[('x', np.int64), ('y', np.int64), ('z', np.int64)]),
                return_index=True,
            )
            return arr[uniq_idx]

        best_candidate: Optional[Tuple[float, float, float, int, int]] = None
        best_score: Optional[Tuple] = None

        for rot in rotations_to_try:
            item_dims_tuple = getRotDim(
                item_to_place.width, item_to_place.length, item_to_place.height, rot
            )
            item_dims = np.array(item_dims_tuple, dtype=np.float64)

            possible_positions = generate_and_filter_positions_numba(
                placed_geom, item_dims, container_bounds, self.epsilon, door_type
            )
            extra_floor = cross_floor_positions(item_dims)
            if extra_floor.size:
                possible_positions = np.vstack([possible_positions, extra_floor])

            for i in range(possible_positions.shape[0]):
                item_pos = possible_positions[i]

                if item_to_place.grounded and item_pos[2] > self.epsilon:
                    continue

                if check_collision_numba(
                    item_pos, item_dims, placed_geom, self.epsilon
                ):
                    continue

                if not check_priority_adjacency_numba(
                    item_pos=item_pos,
                    item_dims=item_dims,
                    item_priority=int(item_to_place.pickup_priority),
                    item_order_id_hash=float(hash(item_to_place.order_id) % (2**31)),
                    item_senddate_ts=float(item_to_place.senddate_ts),
                    placed_items_data=placed_items_data,
                    epsilon=self.epsilon,
                    door_type=door_type,
                ):
                    continue

                is_valid, new_layer = check_support_and_stacking_numba(
                    item_pos=item_pos,
                    item_dims=item_dims,
                    item_type_id=int(candidate_type_int),
                    item_weight=float(item_to_place.weight),
                    max_stack=int(item_to_place.maxStack),
                    item_order_id_hash=float(hash(item_to_place.order_id) % (2**31)),
                    item_senddate_ts=float(item_to_place.senddate_ts),
                    placed_items_data=placed_items_data,
                    enforce_order_stacking=enforce_order_stacking,
                    epsilon=self.epsilon,
                )

                if not is_valid:
                    continue

                x, y, z = float(item_pos[0]), float(item_pos[1]), float(item_pos[2])
                dims = (float(item_dims[0]), float(item_dims[1]), float(item_dims[2]))

                candidate_score = score_position(item_pos, item_dims)
                if best_score is None or candidate_score < best_score:
                    best_score = candidate_score
                    best_candidate = (
                        x,
                        y,
                        z,
                        int(rot),
                        int(new_layer),
                    )

        item_to_place.rotation = original_rotation
        if best_candidate is None:
            item_to_place.position = None
        return best_candidate

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
import numba

from .entities import EPS, Item, getRotDim

if TYPE_CHECKING:
    from .entities import Container


@numba.njit(cache=True)
def check_bounds_within_container(x: float, y: float, z: float,
                                   dx: float, dy: float, dz: float,
                                   xmin: float, ymin: float, zmin: float,
                                   xmax: float, ymax: float, zmax: float) -> bool:
    """Check if a box at (x,y,z) with dimensions (dx,dy,dz) fits within container bounds."""
    EPS_LOCAL = 1e-6
    if x < xmin - EPS_LOCAL or y < ymin - EPS_LOCAL or z < zmin - EPS_LOCAL:
        return False
    if x + dx > xmax + EPS_LOCAL:
        return False
    if y + dy > ymax + EPS_LOCAL:
        return False
    if z + dz > zmax + EPS_LOCAL:
        return False
    return True


def _generate_positions_numba(
    placed_items_data: np.ndarray,
    item_dims: np.ndarray,
    container_bounds: np.ndarray,
    epsilon: float,
) -> np.ndarray:
    """Generate and filter candidate positions using Numba (fast)."""
    # Estimate max positions: origin + 6 per item (3 extreme + 3 floor projections)
    max_positions = 1 + placed_items_data.shape[0] * 6
    positions = np.empty((max_positions, 3), dtype=np.float64)
    count = 0

    # Extract bounds
    xmin, ymin, zmin, xmax, ymax, zmax = container_bounds
    
    # Add origin as first candidate
    positions[count, 0] = xmin
    positions[count, 1] = ymin
    positions[count, 2] = zmin
    count += 1

    dx, dy, dz = item_dims

    for i in range(placed_items_data.shape[0]):
        px, py, pz, pdx, pdy, pdz = placed_items_data[i, :6]

        # Extreme point: right of item
        x, y, z = px + pdx, py, pz
        if (x >= xmin - epsilon and y >= ymin - epsilon and z >= zmin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

        # Extreme point: behind item
        x, y, z = px, py + pdy, pz
        if (x >= xmin - epsilon and y >= ymin - epsilon and z >= zmin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

        # Extreme point: on top of item
        x, y, z = px, py, pz + pdz
        if (x >= xmin - epsilon and y >= ymin - epsilon and z >= zmin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

        # Floor projection: right of item projected to floor
        if pz > zmin + epsilon:
            x, y, z = px + pdx, py, zmin
            if (x >= xmin - epsilon and y >= ymin - epsilon and
                x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
                positions[count, 0] = x
                positions[count, 1] = y
                positions[count, 2] = z
                count += 1

        # Floor projection: behind item projected to floor
        if pz > zmin + epsilon:
            x, y, z = px, py + pdy, zmin
            if (x >= xmin - epsilon and y >= ymin - epsilon and
                x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
                positions[count, 0] = x
                positions[count, 1] = y
                positions[count, 2] = z
                count += 1

        # Floor projection: corner projected to floor
        x, y, z = px + pdx, py + pdy, zmin
        if (x >= xmin - epsilon and y >= ymin - epsilon and
            x + dx <= xmax + epsilon and y + dy <= ymax + epsilon and z + dz <= zmax + epsilon):
            positions[count, 0] = x
            positions[count, 1] = y
            positions[count, 2] = z
            count += 1

    return positions[:count]


def generate_and_filter_positions_numba(
    placed_items_data: np.ndarray,
    item_dims: np.ndarray,
    container_bounds: np.ndarray,
    epsilon: float,
    door_type: int = -1,
) -> np.ndarray:
    """
    Generates, filters, sorts, and de-duplicates possible placement positions.
    Uses Numba for generation and NumPy lexsort for O(n log n) sorting.

    Coordinate system: x=width, y=length, z=height
    - door_type: -1=pallet, 0=side door, 1=front door
    - container_bounds: [xmin, ymin, zmin, xmax, ymax, zmax]

    Filling order based on door_type:
    - Front door (1): y ASC, z ASC, x ASC
    - Side door (0): x ASC, z ASC, y ASC
    - Pallet (-1): z ASC, y ASC, x ASC
    """
    # Generate positions using fast Numba function
    positions = _generate_positions_numba(placed_items_data, item_dims, container_bounds, epsilon)

    if positions.shape[0] == 0:
        return np.empty((0, 3), dtype=np.float64)

    # Round to epsilon grid for deduplication (much faster than comparing floats)
    grid_size = max(epsilon * 10, 0.1)  # Use larger grid for faster dedup
    rounded = np.round(positions / grid_size).astype(np.int64)

    # Fast unique using structured array view
    rounded_view = rounded.view(dtype=[('x', np.int64), ('y', np.int64), ('z', np.int64)])
    _, unique_indices = np.unique(rounded_view, return_index=True)
    unique_positions = positions[unique_indices]

    if unique_positions.shape[0] == 0:
        return np.empty((0, 3), dtype=np.float64)

    # Sort using numpy lexsort (O(n log n)) based on door_type
    # lexsort sorts by last key first, so reverse the order
    if door_type == 1:
        # Front door: y ASC, z ASC, x ASC -> lexsort keys: (x, z, y)
        sort_idx = np.lexsort((unique_positions[:, 0], unique_positions[:, 2], unique_positions[:, 1]))
    elif door_type == 0:
        # Side door: x ASC, z ASC, y ASC -> lexsort keys: (y, z, x)
        sort_idx = np.lexsort((unique_positions[:, 1], unique_positions[:, 2], unique_positions[:, 0]))
    else:
        # Pallet: z ASC, y ASC, x ASC -> lexsort keys: (x, y, z)
        sort_idx = np.lexsort((unique_positions[:, 0], unique_positions[:, 1], unique_positions[:, 2]))

    return unique_positions[sort_idx]


@numba.jit(nopython=True)
def check_collision_numba(
    item_pos: np.ndarray,
    item_dims: np.ndarray,
    placed_items_data: np.ndarray,
    epsilon: float,
) -> bool:
    """Checks for collisions between a new item and already placed items using NumPy arrays."""
    x1, y1, z1 = item_pos
    l1, w1, h1 = item_dims

    for i in range(placed_items_data.shape[0]):
        x2, y2, z2, l2, w2, h2 = placed_items_data[i, :6]
        if (
            x1 < x2 + l2 - epsilon
            and x1 + l1 > x2 + epsilon
            and y1 < y2 + w2 - epsilon
            and y1 + w1 > y2 + epsilon
            and z1 < z2 + h2 - epsilon
            and z1 + h1 > z2 + epsilon
        ):
            return True
    return False


@numba.jit(nopython=True)
def check_priority_adjacency_numba(
    item_pos: np.ndarray,  # [x, y, z]
    item_dims: np.ndarray,  # [dx, dy, dz]
    item_priority: int,  # candidate's pickup_priority
    item_order_id_hash: float,  # candidate's order_id hash
    item_senddate_ts: float,  # candidate's senddate_ts
    placed_items_data: np.ndarray,  # rows: [..., pickup_priority at index 12, order_id_hash at 13, senddate_ts at 14]
    epsilon: float,
    door_type: int = -1,  # -1=pallet, 0=side door, 1=front door
) -> bool:
    """
    Check if the new item's pickup_priority is compatible with placement constraints.

    Priority constraints only apply to items with the SAME order_id AND senddate_ts.
    Items from different orders are kept in door-axis slices (front/back). They can
    touch at the slice boundary only if the more urgent load (earlier plan_send_date,
    then lower pickup_priority) is closer to the door.

    Rules (applied only within same order_id and senddate_ts):
    1. GLOBAL POSITION: Item with pickup_priority P must be positioned toward the door
       relative to items with lower pickup_priority (higher P values). This ensures
       higher pickup_priority items are always in front of lower pickup_priority items.
       - Side door (0): item.x must be >= x of items with pickup_priority > P
       - Front door (1): item.y must be >= y of items with pickup_priority > P

    2. ADJACENCY: An item with pickup_priority P can only be adjacent to items with pickup_priority P or P+1.

    3. DIRECTION: When adjacent to item with pickup_priority P+1, the new item (P) must be:
       - In front of the P+1 item (toward door), OR
       - Above the P+1 item

    Returns True if placement is valid.
    """
    x, y, z = item_pos
    dx, dy, dz = item_dims
    door_axis = 1 if door_type == 1 else (0 if door_type == 0 else -1)
    c_axis_start = y if door_axis == 1 else (x if door_axis == 0 else 0.0)
    c_axis_end = (y + dy) if door_axis == 1 else ((x + dx) if door_axis == 0 else 0.0)

    n = placed_items_data.shape[0]

    # ------------------------------------------------------------------
    # Cross-order grouping rule (door containers only):
    #   Keep different orders in non-overlapping slices along the door
    #   axis (y for front door, x for side door). Only allow touching
    #   at the boundary if the more urgent load (earlier plan_send_date, then
    #   lower pickup_priority) is on the door side of the less urgent load.
    # ------------------------------------------------------------------
    if door_axis != -1:
        for i in range(n):
            p_order_id_hash = placed_items_data[i, 13]
            p_senddate_ts = placed_items_data[i, 14]
            # Skip if same order; handled below
            if abs(p_order_id_hash - item_order_id_hash) <= epsilon:
                continue

            px, py, pz = placed_items_data[i, 0:3]
            pdx, pdy, pdz = placed_items_data[i, 3:6]
            p_priority = int(placed_items_data[i, 12])

            p_axis_start = py if door_axis == 1 else px
            p_axis_end = (py + pdy) if door_axis == 1 else (px + pdx)

            # Prevent overlapping ranges along the door axis (keeps orders grouped)
            if c_axis_start < p_axis_end - epsilon and c_axis_end > p_axis_start + epsilon:
                return False

            candidate_in_front = c_axis_start >= p_axis_end - epsilon
            candidate_behind = c_axis_end <= p_axis_start + epsilon

            # If they just touch, enforce ordering by (plan_send_date, pickup_priority)
            if candidate_in_front or candidate_behind:
                # More urgent = earlier plan_send_date, then lower pickup_priority value
                more_urgent = False
                less_urgent = False
                if item_senddate_ts < p_senddate_ts - epsilon:
                    more_urgent = True
                elif item_senddate_ts > p_senddate_ts + epsilon:
                    less_urgent = True
                else:
                    if item_priority < p_priority:
                        more_urgent = True
                    elif item_priority > p_priority:
                        less_urgent = True

                if more_urgent and candidate_behind:
                    return False  # more urgent load placed behind a less urgent order
                if less_urgent and candidate_in_front:
                    return False  # less urgent load placed in front of a more urgent order

    # GLOBAL POSITION CHECK: Ensure item is not behind lower pickup_priority items
    # Items with higher pickup_priority (lower P) must be toward the door
    # ONLY CHECK WITHIN SAME ORDER_ID AND SENDDATE_TS
    for i in range(n):
        p_order_id_hash = placed_items_data[i, 13]
        p_senddate_ts = placed_items_data[i, 14]
        
        # Skip if different order_id or senddate_ts - pickup_priority constraints don't apply
        if abs(p_order_id_hash - item_order_id_hash) > epsilon or abs(p_senddate_ts - item_senddate_ts) > epsilon:
            continue
            
        px, py, pz = placed_items_data[i, 0:3]
        pdx, pdy, pdz = placed_items_data[i, 3:6]
        p_priority = int(placed_items_data[i, 12])

        # Only check against items with LOWER pickup_priority (higher P value)
        if p_priority > item_priority:
            if door_type == 0:  # Side door: higher pickup_priority must have higher x
                # New item's back edge (x) must be >= existing item's back edge (px)
                # Allow some tolerance for items at same level
                if x < px - epsilon:
                    return False  # New item is behind a lower pickup_priority item
            elif door_type == 1:  # Front door: higher pickup_priority must have higher y
                # New item's back edge (y) must be >= existing item's back edge (py)
                if y < py - epsilon:
                    return False  # New item is behind a lower pickup_priority item

    # ADJACENCY AND DIRECTION CHECKS
    # ONLY CHECK WITHIN SAME ORDER_ID AND SENDDATE_TS
    for i in range(n):
        p_order_id_hash = placed_items_data[i, 13]
        p_senddate_ts = placed_items_data[i, 14]
        
        # Skip if different order_id or senddate_ts - pickup_priority constraints don't apply
        if abs(p_order_id_hash - item_order_id_hash) > epsilon or abs(p_senddate_ts - item_senddate_ts) > epsilon:
            continue
            
        px, py, pz = placed_items_data[i, 0:3]
        pdx, pdy, pdz = placed_items_data[i, 3:6]
        p_priority = int(placed_items_data[i, 12])

        # Check if items are adjacent (touching but not overlapping)
        # Check overlap in each dimension
        x_overlap = (x < px + pdx + epsilon) and (x + dx > px - epsilon)
        y_overlap = (y < py + pdy + epsilon) and (y + dy > py - epsilon)
        z_overlap = (z < pz + pdz + epsilon) and (z + dz > pz - epsilon)

        # Check if touching on each axis (within epsilon of each other)
        # For each axis, determine which side is touching
        x_touch_right = abs(x - (px + pdx)) < epsilon  # new item is to the right of existing
        x_touch_left = abs((x + dx) - px) < epsilon    # new item is to the left of existing
        x_touch = x_touch_right or x_touch_left

        y_touch_front = abs(y - (py + pdy)) < epsilon  # new item is in front of existing
        y_touch_back = abs((y + dy) - py) < epsilon    # new item is behind existing
        y_touch = y_touch_front or y_touch_back

        z_touch_top = abs(z - (pz + pdz)) < epsilon    # new item is on top of existing
        z_touch_bottom = abs((z + dz) - pz) < epsilon  # new item is below existing
        z_touch = z_touch_top or z_touch_bottom

        # Items are adjacent if they touch on one axis and overlap on the other two
        is_adjacent = False
        if x_touch and y_overlap and z_overlap:
            is_adjacent = True
        elif y_touch and x_overlap and z_overlap:
            is_adjacent = True
        elif z_touch and x_overlap and y_overlap:
            is_adjacent = True

        if is_adjacent:
            # Check pickup_priority compatibility
            if p_priority != item_priority and p_priority != item_priority + 1:
                return False  # Priority difference > 1, not allowed

            # Additional check when adjacent to P+1 item:
            # New item (P) must be in front of OR above the P+1 item
            if p_priority == item_priority + 1:
                is_valid_position = False

                # Check if new item is ABOVE the P+1 item
                # (touching on z-axis means overlapping on x and y axes)
                if z_touch_top and x_overlap and y_overlap:
                    # New item sits on top of existing - this is "above"
                    is_valid_position = True

                # Check if new item is IN FRONT of the P+1 item (toward door)
                if door_type == 1:  # Front door: "in front" = higher y
                    # Touching on y-axis means overlapping on x and z axes
                    if y_touch_front and x_overlap and z_overlap:
                        # New item is in front of existing (higher y)
                        is_valid_position = True
                elif door_type == 0:  # Side door: "in front" = higher x
                    # Touching on x-axis means overlapping on y and z axes
                    if x_touch_right and y_overlap and z_overlap:
                        # New item is in front of existing (higher x)
                        is_valid_position = True
                else:  # Pallet or default: allow horizontal adjacency
                    if (x_touch and y_overlap and z_overlap) or (y_touch and x_overlap and z_overlap):
                        is_valid_position = True

                if not is_valid_position:
                    return False  # P item is behind or below P+1 item

    return True  # All adjacent items have compatible pickup_priority


@numba.jit(nopython=True)
def check_support_and_stacking_numba(
    item_pos: np.ndarray,  # [x, y, z]
    item_dims: np.ndarray,  # [dx, dy, dz] where x=width, y=length, z=height
    item_type_id: int,  # candidate's cargo type id (int)
    item_weight: float,  # candidate's weight
    max_stack: int,  # candidate's Max Stack (e.g., 1,3,4, or -1 for unlimited)
    item_order_id_hash: float,  # candidate's order_id hash
    item_senddate_ts: float,  # candidate's senddate_ts
    placed_items_data: np.ndarray,  # rows: [x,y,z,dx,dy,dz,type_id,layer,max_stack,maxStackWeight,must_be_on_top,weight,pickup_priority,order_id_hash,senddate_ts]
    enforce_order_stacking: bool,  # whether to block older orders from stacking on newer ones
    epsilon: float,
    min_support_ratio: float = 0.7,  # minimum support ratio (default 70%)
) -> Tuple[bool, int]:
    """
    Enforce:
      1) Support ≥ min_support_ratio (default 70%) footprint.
      2) SAME-TYPE layer count <= candidate's max_stack (unless -1 = unlimited).
      3) If ANY supporter overlapped beneath has max_stack == 1, reject placement entirely
         (no item allowed on top of that supporter, regardless of type).
      4) Different-SKU max stack weight: if supporter SKU differs from item's,
         ensure item_weight ≤ supporter.maxStackWeight.
      5) Must-be-on-top: if supporter has must_be_on_top=True, nothing can be placed above it.
      6) Order-based stacking (optional): items from an earlier order (lower senddate_ts)
         cannot be placed on top of items from a later order (higher senddate_ts). Items
         from the same order can stack freely.
    Returns (ok, new_layer).
    """
    x, y, z = item_pos
    dx, dy, _ = item_dims

    total_support_area = 0.0
    same_type_max_layer_below = 0  # 0 => no same-type supporter directly underneath

    if z < epsilon:
        # On floor: fully supported
        total_support_area = dx * dy
    else:
        n = placed_items_data.shape[0]
        for i in range(n):
            px, py, pz = placed_items_data[i, 0:3]
            pdx, pdy, pdz = placed_items_data[i, 3:6]
            p_type = placed_items_data[i, 6]
            p_layer = placed_items_data[i, 7]
            p_max = placed_items_data[i, 8]
            p_max_stack_weight = placed_items_data[i, 9]
            p_must_be_on_top = placed_items_data[i, 10]
            p_order_id_hash = placed_items_data[i, 13]
            p_senddate_ts = placed_items_data[i, 14]

            # supporter must touch the candidate's bottom plane
            if abs((pz + pdz) - z) < epsilon:
                # overlap on X, Y
                overlap_x = min(x + dx, px + pdx) - max(x, px)
                if overlap_x > 0.0:
                    overlap_y = min(y + dy, py + pdy) - max(y, py)
                    if overlap_y > 0.0:
                        # Rule 5: Must-be-on-top - nothing can be placed above this item
                        if p_must_be_on_top > 0.5:
                            return False, -1

                        # Rule 3: if this supporter has max_stack == 1, nothing can be placed above it
                        if int(p_max) == 1:
                            return False, -1

                        if enforce_order_stacking:
                            # Rule 6: Order-based stacking - items from earlier orders cannot stack
                            # on items from later orders (different order_id with higher senddate_ts)
                            if abs(p_order_id_hash - item_order_id_hash) > epsilon:
                                # Different order_id - check senddate_ts
                                if item_senddate_ts < p_senddate_ts - epsilon:
                                    # Current item is from earlier order, supporter is from later order
                                    # This is not allowed
                                    return False, -1

                        # Rule 4: Different-SKU max stack weight check
                        if int(p_type) != int(item_type_id):
                            # Different SKU - check weight constraint
                            if item_weight > p_max_stack_weight + epsilon:
                                return False, -1

                        total_support_area += overlap_x * overlap_y

                        # Track same-type layer chain
                        if int(p_type) == int(item_type_id):
                            p_layer_i = int(p_layer)
                            if p_layer_i > same_type_max_layer_below:
                                same_type_max_layer_below = p_layer_i

    # Rule 1: Require at least min_support_ratio support
    if total_support_area < (dx * dy * min_support_ratio):
        return False, -1

    # Compute new same-type layer for the candidate
    new_layer = same_type_max_layer_below + 1

    # Rule 2: Enforce candidate's own max_stack (unless unlimited = -1)
    if int(max_stack) != -1 and new_layer > int(max_stack):
        return False, -1

    return True, int(new_layer)


# --- Modified BottomLeftFill Class ---
class BottomLeftFill:
    def __init__(
        self,
        container: Container,
        must_be_on_top: Optional[Dict[int, bool]] = None,
    ):
        self.container = container
        self.epsilon = 1e-5
        self.must_be_on_top = must_be_on_top or {}


    def find_best_position_for_item(
        self, item_to_place: Item
    ) -> Optional[Tuple[float, float, float, int, int]]:
        """
        Tries all valid rotations to find the best placement using a fully Numba-accelerated pipeline.
        Updated to enforce 'Max Stack' as SAME-TYPE layer count via check_support_and_stacking_numba.

        Returns:
            (x, y, z, rot, new_layer)  # NOTE: 5th value is *layer*, not stackLimit
        """
        original_rotation = item_to_place.rotation
        rotations_to_try = [0, 1] if item_to_place.isSideUp else [0, 1, 2, 3, 4, 5]
        door_type = getattr(self.container, 'door_type_int', -1)
        enforce_order_stacking = door_type != -1  # allow cross-order stacking on pallets
        door_axis_idx = 1 if door_type == 1 else (0 if door_type == 0 else None)

        # Track how far we have already occupied along the door axis so we can avoid
        # skipping stackable spots in earlier lanes.
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
            """
            Lower score = better. Primary key is how far we push the frontier along the
            door axis (y for front-door, x for side-door). Tie-breaker matches the
            previous fill order so behaviour stays deterministic.
            """
            if door_axis_idx is not None:
                frontier_after = max(current_frontier, pos[door_axis_idx] + dims[door_axis_idx])
            else:
                frontier_after = pos[2]  # pallet: keep lower z first

            if door_type == 1:
                tie = (pos[1], pos[2], pos[0])  # y, z, x
            elif door_type == 0:
                tie = (pos[0], pos[2], pos[1])  # x, z, y
            else:
                tie = (pos[2], pos[1], pos[0])  # z, y, x (pallet)
            return (round(frontier_after, 5),) + tuple(tie)

        # ---- Create a stable int mapping for cargo type ids (NumPy/Numba prefer ints) ----
        # Map seen type strings to small ints, consistent within this call.
        type_id_map = {}
        next_tid = 1

        def get_type_int(t: str) -> int:
            nonlocal next_tid
            if t not in type_id_map:
                type_id_map[t] = next_tid
                next_tid += 1
            return type_id_map[t]

        # Ensure candidate type id is in the map
        candidate_type_int = get_type_int(item_to_place.itemType_id)

        # ---- Build placed_items_data: [x, y, z, dx, dy, dz, type_id, layer, max_stack, maxStackWeight, must_be_on_top, weight, pickup_priority, order_id_hash, senddate_ts] ----
        num_placed = len(self.container.items)
        placed_items_data = np.zeros((num_placed, 15), dtype=np.float64)
        for i, p_item in enumerate(self.container.items):
            p_dims = p_item.get_rotated_dimensions()
            px, py, pz = p_item.position  # assumed already set for placed items
            placed_items_data[i, 0:3] = (px, py, pz)
            placed_items_data[i, 3:6] = p_dims
            placed_items_data[i, 6] = float(get_type_int(p_item.itemType_id))
            # If older items don't yet have .layer, default to 1 (floor/base layer for their type)
            placed_items_data[i, 7] = float(getattr(p_item, "layer", 1))
            placed_items_data[i, 8] = float(p_item.maxStack)
            # maxStackWeight for different-SKU stacking constraint
            placed_items_data[i, 9] = float(p_item.maxStackWeight if p_item.maxStackWeight else 1e9)
            # must_be_on_top flag (1.0 = True, 0.0 = False)
            placed_items_data[i, 10] = 1.0 if getattr(p_item, "must_be_on_top", False) else 0.0
            # weight for cross-SKU weight calculation
            placed_items_data[i, 11] = float(p_item.weight)
            # pickup_priority for adjacency constraint
            placed_items_data[i, 12] = float(getattr(p_item, "pickup_priority", 1))
            # order_id as hash for comparing same-order items
            placed_items_data[i, 13] = float(hash(getattr(p_item, "order_id", "")) % (2**31))
            # senddate_ts for comparing same-order items
            placed_items_data[i, 14] = float(getattr(p_item, "senddate_ts", 0))

        # Geometry-only view for helpers that don't need type/layer
        placed_geom = placed_items_data[:, :6]  # [x,y,z,dx,dy,dz] where x=width, y=length, z=height
        # Container bounds: [xmin, ymin, zmin, xmax, ymax, zmax] from origin and dimensions
        ox, oy, oz = self.container.origin
        container_bounds = np.array(
            [ox, oy, oz,
             ox + self.container.width,
             oy + self.container.length,
             oz + self.container.height],
            dtype=np.float64,
        )

        def cross_floor_positions(item_dims: np.ndarray) -> np.ndarray:
            """Generate extra floor candidates by combining extreme x/y edges of placed items.
            Helps fill thin floor gaps that single-axis extreme points miss.
            """
            if placed_geom.shape[0] == 0:
                return np.empty((0, 3), dtype=np.float64)

            xs = {ox}  # Start with origin x
            ys = {oy}  # Start with origin y
            for row in placed_geom:
                px, py, _, pdx, pdy, _ = row
                xs.add(px + pdx)
                ys.add(py + pdy)

            dx, dy, dz = item_dims
            results: List[Tuple[float, float, float]] = []
            for x in xs:
                if x + dx > container_bounds[3] + self.epsilon:  # xmax
                    continue
                for y in ys:
                    if y + dy > container_bounds[4] + self.epsilon:  # ymax
                        continue
                    # Floor only; z=origin z
                    if dz > container_bounds[5] + self.epsilon:  # zmax
                        continue
                    results.append((x, y, oz))

            if not results:
                return np.empty((0, 3), dtype=np.float64)
            # Deduplicate with a coarse grid to avoid explosion
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
            # getRotDim takes (width, length, height, rotation) and returns (x_dim, y_dim, z_dim)
            # where x=width, y=length, z=height
            item_dims_tuple = getRotDim(
                item_to_place.width, item_to_place.length, item_to_place.height, rot
            )
            item_dims = np.array(item_dims_tuple, dtype=np.float64)

            # Candidate positions (use geometry-only view to match your Numba helper expectations)
            # Pass door_type for proper filling order based on door position
            possible_positions = generate_and_filter_positions_numba(
                placed_geom, item_dims, container_bounds, self.epsilon, door_type
            )
            # Add extra cross-floor candidates to fill narrow gaps
            extra_floor = cross_floor_positions(item_dims)
            if extra_floor.size:
                possible_positions = np.vstack([possible_positions, extra_floor])

            # Try positions in sorted order; first valid is best
            for i in range(possible_positions.shape[0]):
                item_pos = possible_positions[i]

                # Respect "grounded" constraint (must sit on floor)
                if item_to_place.grounded and item_pos[2] > self.epsilon:
                    continue

                # Collision check (geometry-only)
                if check_collision_numba(
                    item_pos, item_dims, placed_geom, self.epsilon
                ):
                    continue

                # Priority adjacency check: items can only be adjacent to items with pickup_priority P or P+1
                # and must be in front of or above P+1 items
                # Only apply this constraint WITHIN the same order_id and senddate_ts
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

                # Max Stack rule (SAME-TYPE layers) + 70% support + different-SKU weight + must-be-on-top checks
                # Also check order-based stacking constraint
                is_valid, new_layer = check_support_and_stacking_numba(
                    item_pos=item_pos,
                    item_dims=item_dims,
                    item_type_id=int(candidate_type_int),
                    item_weight=float(item_to_place.weight),
                    max_stack=int(item_to_place.maxStack),
                    item_order_id_hash=float(hash(item_to_place.order_id) % (2**31)),
                    item_senddate_ts=float(item_to_place.senddate_ts),
                    placed_items_data=placed_items_data,  # [x,y,z,dx,dy,dz,type_id,layer,max_stack,maxStackWeight,must_be_on_top,weight,pickup_priority,order_id_hash,senddate_ts]
                    enforce_order_stacking=enforce_order_stacking,
                    epsilon=self.epsilon,
                )

                if not is_valid:
                    continue

                # Additional validation using global constraint functions
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





## code still produces some gaps because it places items as group.
## but it is much faster than the older version.

import copy, time, traceback
from datetime import datetime
import numpy as np
import pygad
from typing import List, Optional, Tuple, Literal, TypedDict, Dict
import numba
from numba import typed
from tqdm.auto import tqdm
from app import schemas

from collections import deque, defaultdict



door_type_map = {
    'side': 0,
    'front': 1
}

class Item:
    def __init__(
        self,
        id: str,
        order_id: str,
        itemType_id: str,
        length: float,
        width: float,
        height: float,
        weight: float,
        isSideUp: bool,
        maxStack: int,
        maxStackWeight: float,
        itemType: str,
        grounded: bool = False,
        pickup_priority: int = 1,
        plan_send_date: str = "",
    ):
        self.order_id: str = order_id
        self.id: str = id
        self.itemType_id: str = itemType_id
        self.itemType: str = itemType
        self.length: float = length
        self.width: float = width
        self.height: float = height
        self.weight: float = weight
        self.isSideUp: bool = isSideUp
        self.maxStack: int = maxStack
        self.maxStackWeight: float = maxStackWeight
        self.stackLimit: int = maxStack
        self.pickup_priority: int = pickup_priority
        self.grounded: bool = grounded
        self.position: Tuple[float, float, float] = None
        self.rotation: Literal[0, 1, 2, 3, 4, 5] = 0
        self.volume: float = length * width * height
        self.stack_weight = (maxStack-1)*weight
        self.plan_send_date: int = (
            datetime.strptime(plan_send_date, "%Y-%m-%dT%H:%M:%S").timestamp()
            if plan_send_date
            else 0
        )

    def get_rotated_dimensions(self) -> Tuple[float, float, float]:
        # Get item dimensions after rotation.
        match self.rotation:
            case 0:
                return (self.length, self.width, self.height)
            case 1:
                return (self.width, self.length, self.height)
            case 2:
                return (self.height, self.width, self.length)
            case 3:
                return (self.width, self.height, self.length)
            case 4:
                return (self.length, self.height, self.width)
            case 5:
                return (self.height, self.length, self.width)
            case _:
                return (self.length, self.width, self.height)


class Container:
    def __init__(
        self,
        id: str,
        type_id: str,
        length: float,
        width: float,
        height: float,
        max_weight: float,
        exlength: float,
        exwidth: float,
        exheight: float,
        exweight: float,
        pickup_priority: int = 1,
        door_position: Optional[str] = None ## front or side
    ):
        self.id = id
        self.type_id = type_id
        self.length = length
        self.width = width
        self.height = height
        self.exlength = exlength
        self.exwidth = exwidth
        self.exheight = exheight
        self.exweight = exweight
        self.max_weight = max_weight
        self.pickup_priority = pickup_priority
        self.items: List[Item] = []
        self.total_weight = 0.0
        self.volume = length * width * height
        self.door_position = door_position
        self.door_type_int = door_type_map.get(door_position, -1)


class ContainerLoadingSolution(TypedDict):
    fitness: float
    containers: List[Container]
    unused: List[Item]


@numba.jit(nopython=True, cache=True)
def get_rotated_dimensions_numba(
    length: float, width: float, height: float, rotation: int
) -> Tuple[float, float, float]:
    """Numba-compatible version of Item.get_rotated_dimensions."""
    if rotation == 0:
        return (length, width, height)
    elif rotation == 1:
        return (width, length, height)
    elif rotation == 2:
        return (height, width, length)
    elif rotation == 3:
        return (width, height, length)
    elif rotation == 4:
        return (length, height, width)
    elif rotation == 5:
        return (height, length, width)
    return (length, width, height)


# --- FAST candidate generator: returns UNSORTED positions; Python sorts them ---
@numba.jit(nopython=True, cache=True)
def generate_and_filter_positions_numba(
    placed_items_data: np.ndarray,
    item_dims: np.ndarray,
    container_dims: np.ndarray,
    epsilon: float,
    door_type_int: int  # 0=side, 1=front, else=neutral; kept for signature compatibility
) -> np.ndarray:
    """
    Generate candidate extreme-point positions for BLF.
    - Collect Z planes: floor (0) + every top face of placed items.
    - For each plane: cross product of unique X/Y edges (0, far wall, and edges around touching items).
    - Filter to container bounds.
    - Epsilon-aware de-duplication.
    - Returns positions UNSORTED (sorting is done efficiently in Python with np.lexsort).
    """
    l, w, h = item_dims
    cont_l, cont_w, cont_h = container_dims

    # 1) collect Z planes
    planes = typed.List()
    planes.append(0.0)
    n = placed_items_data.shape[0]
    for i in range(n):
        pz = placed_items_data[i, 2]
        ph = placed_items_data[i, 5]
        plane = pz + ph
        unique = True
        for k in range(len(planes)):
            if abs(planes[k] - plane) < epsilon:
                unique = False
                break
        if unique:
            planes.append(plane)

    # 2) raw candidates (legacy seeds + EPs)
    possible_positions = typed.List()
    possible_positions.append(np.array([0.0, 0.0, 0.0]))

    for i in range(n):
        px = placed_items_data[i, 0]
        py = placed_items_data[i, 1]
        pz = placed_items_data[i, 2]
        pl = placed_items_data[i, 3]
        pw = placed_items_data[i, 4]
        ph = placed_items_data[i, 5]
        # classic EPs on same plane as the item bottom/top
        possible_positions.append(np.array([px + pl, py,       pz]))
        possible_positions.append(np.array([px,       py + pw, pz]))
        possible_positions.append(np.array([px + pl, py + pw,  pz]))
        possible_positions.append(np.array([px,       py,      pz + ph]))

    # 3) grid corners per plane (both walls + item edges that touch the plane)
    for pidx in range(len(planes)):
        z_plane = planes[pidx]
        if z_plane + h > cont_h + epsilon:
            continue

        x_edges = typed.List()
        y_edges = typed.List()
        # always include both walls
        x_edges.append(0.0)
        y_edges.append(0.0)
        far_x = cont_l - l
        far_y = cont_w - w
        if far_x >= -epsilon:
            x_edges.append(far_x)
        if far_y >= -epsilon:
            y_edges.append(far_y)

        # add edges from items whose top == z_plane (or floor for z=0)
        for i in range(n):
            px = placed_items_data[i, 0]
            py = placed_items_data[i, 1]
            pz = placed_items_data[i, 2]
            pl = placed_items_data[i, 3]
            pw = placed_items_data[i, 4]
            ph = placed_items_data[i, 5]

            touches = (z_plane < epsilon) or (abs((pz + ph) - z_plane) < epsilon)
            if not touches:
                continue

            xe1 = px
            xe2 = px + pl
            add1 = True
            for t in range(len(x_edges)):
                if abs(x_edges[t] - xe1) < epsilon:
                    add1 = False
                    break
            if add1:
                x_edges.append(xe1)
            add2 = True
            for t in range(len(x_edges)):
                if abs(x_edges[t] - xe2) < epsilon:
                    add2 = False
                    break
            if add2:
                x_edges.append(xe2)

            ye1 = py
            ye2 = py + pw
            add3 = True
            for t in range(len(y_edges)):
                if abs(y_edges[t] - ye1) < epsilon:
                    add3 = False
                    break
            if add3:
                y_edges.append(ye1)
            add4 = True
            for t in range(len(y_edges)):
                if abs(y_edges[t] - ye2) < epsilon:
                    add4 = False
                    break
            if add4:
                y_edges.append(ye2)

        # cross product on this plane
        for xi in range(len(x_edges)):
            x = x_edges[xi]
            if x + l > cont_l + epsilon:
                continue
            for yi in range(len(y_edges)):
                y = y_edges[yi]
                if y + w > cont_w + epsilon:
                    continue
                possible_positions.append(np.array([x, y, z_plane]))

    # 4) in-bounds filter
    valid_positions = typed.List()
    for i in range(len(possible_positions)):
        x = possible_positions[i][0]
        y = possible_positions[i][1]
        z = possible_positions[i][2]
        if (x + l <= cont_l + epsilon and
            y + w <= cont_w + epsilon and
            z + h <= cont_h + epsilon):
            valid_positions.append(possible_positions[i])

    if len(valid_positions) == 0:
        return np.empty((0, 3), dtype=np.float64)

    valid_positions_np = np.empty((len(valid_positions), 3), dtype=np.float64)
    for i in range(len(valid_positions)):
        valid_positions_np[i, :] = valid_positions[i]
    m = valid_positions_np.shape[0]

    # 5) epsilon-aware de-dup (UNSORTED output; sort later in Python)
    if m <= 1:
        return valid_positions_np

    uniq = typed.List()
    uniq.append(valid_positions_np[0])
    for i in range(1, m):
        last = uniq[-1]
        cur  = valid_positions_np[i]
        if (abs(cur[0] - last[0]) > epsilon or
            abs(cur[1] - last[1]) > epsilon or
            abs(cur[2] - last[2]) > epsilon):
            uniq.append(cur)

    out = np.empty((len(uniq), 3), dtype=np.float64)
    for i in range(len(uniq)):
        out[i, :] = uniq[i]
    return out


@numba.jit(nopython=True, cache=True)
def check_collision_numba(
    item_pos: np.ndarray, item_dims: np.ndarray, placed_items_data: np.ndarray, epsilon: float
) -> bool:
    """Checks for collisions between a new item and already placed items using NumPy arrays."""
    x1, y1, z1 = item_pos
    l1, w1, h1 = item_dims

    for i in range(placed_items_data.shape[0]):
        x2, y2, z2, l2, w2, h2 = placed_items_data[i, :6]
        if (
            x1 < x2 + l2 - epsilon and x1 + l1 > x2 + epsilon and
            y1 < y2 + w2 - epsilon and y1 + w1 > y2 + epsilon and
            z1 < z2 + h2 - epsilon and z1 + h1 > z2 + epsilon
        ):
            return True
    return False


@numba.jit(nopython=True, cache=True)
def check_support_and_stacking_numba(
    item_pos: np.ndarray,          # [x, y, z]
    item_dims: np.ndarray,         # [l, w, h]
    item_type_id: int,             # candidate's SKU/type id (int)
    max_stack: int,                # candidate's Max Stack height (base layer = 1; -1 = unlimited)
    candidate_weight: float,       # candidate weight (for different-SKU weight check)
    candidate_senddate: float,     # candidate plan_send_date (epoch seconds; compare with 0.5s tol)
    candidate_priority: int,       # candidate pickup_priority (int)
    placed_items_data: np.ndarray, # rows: [x,y,z,l,w,h,type_id,layer,max_stack,weight,stack_weight,plan_send_date,pickup_priority]
    epsilon: float
) -> Tuple[bool, int]:
    """
    SAME-(plan_send_date, pickup_priority) STACKING:

      A) Support: requires ≥70% of the candidate's footprint supported (or floor).
         Support may only come from supporters that share (plan_send_date, pickup_priority).
      B) Cross-(plan_send_date, pickup_priority) overlap is forbidden: if z>0 and ANY overlapping
         supporter has a different (plan_send_date, pickup_priority), reject immediately.
      C) Height: new layer = 1 + max layer among same-(sd,pr) supporters below.
         Enforce candidate's own max_stack (base layer = 1).
      D) Hard lid: if ANY supporter (regardless of group/SKU) already reached its own
         max_stack (layer >= max_stack and max_stack != -1), reject immediately.
      E) Different-SKU weight: if a supporter is a different SKU (type_id differs),
         require candidate_weight <= supporter's stack_weight (if >=0).

    Notes:
      - Senddate is compared with absolute tolerance 0.5 seconds to avoid FP issues.
    """
    x, y, z = item_pos
    l, w, _ = item_dims
    cand_area = l * w

    total_support_area = 0.0
    same_group_max_layer_below = 0
    n = placed_items_data.shape[0]

    # Floor placement: consider fully supported
    if z < epsilon:
        total_support_area = cand_area
    else:
        for i in range(n):
            px = placed_items_data[i, 0]
            py = placed_items_data[i, 1]
            pz = placed_items_data[i, 2]
            pl = placed_items_data[i, 3]
            pw = placed_items_data[i, 4]
            ph = placed_items_data[i, 5]

            p_type  = int(placed_items_data[i, 6])
            p_layer = int(placed_items_data[i, 7])
            p_max   = int(placed_items_data[i, 8])
            # p_weight = placed_items_data[i, 9]  # not needed here
            p_msw   = placed_items_data[i,10]     # stack_weight (>=0 means active)
            p_sd    = placed_items_data[i,11]
            p_pr    = int(placed_items_data[i,12])

            # supporter must touch candidate's bottom plane
            if abs((pz + ph) - z) >= epsilon:
                continue

            # XY overlap with the candidate footprint
            ov_l = min(x + l, px + pl) - max(x, px)
            if ov_l <= 0.0:
                continue
            ov_w = min(y + w, py + pw) - max(y, py)
            if ov_w <= 0.0:
                continue

            # HARD LID: supporter at its own max stack ⇒ nothing above it
            if p_max != -1 and p_layer >= p_max:
                return False, -1

            same_sd = (abs(p_sd - candidate_senddate) < 0.5)
            same_pr = (p_pr == candidate_priority)
            if not (same_sd and same_pr):
                # Other groups neither help nor hurt here — just don’t count as support.
                continue

            # SAME (sd, pr) → contributes to support
            if p_type != item_type_id:
                if p_msw >= 0.0 and candidate_weight > p_msw + epsilon:
                    return False, -1

            total_support_area += ov_l * ov_w


            # Track tallest layer among same-(sd,pr) supporters
            if p_layer > same_group_max_layer_below:
                same_group_max_layer_below = p_layer

    # Need ≥70% support (from same-(sd,pr) supporters)
    if total_support_area + epsilon < (cand_area * 0.7):
        return False, -1

    # Height limit for the candidate (base layer = 1)
    new_layer = same_group_max_layer_below + 1
    if int(max_stack) != -1 and new_layer > int(max_stack):
        return False, -1

    return True, int(new_layer)



@numba.jit(nopython=True, cache=True)
def numba_center_items(items_data: np.ndarray, container_dims: np.ndarray) -> np.ndarray:
    """
    Calculates the centered positions for a set of items within a container.
    This function operates entirely on NumPy arrays for maximum speed.
    
    Args:
        items_data: A 2D array where each row is [x, y, z, length, width, height].
        container_dims: A 1D array with [container_length, container_width].

    Returns:
        A 2D array with the new [x, y, z] positions for each item.
    """
    if items_data.shape[0] == 0:
        return np.empty((0, 3), dtype=np.float64)

    # Find the bounding box of all items
    min_x = np.min(items_data[:, 0])
    min_y = np.min(items_data[:, 1])
    # The max extent is the item's position plus its dimension
    max_x = np.max(items_data[:, 0] + items_data[:, 3])
    max_y = np.max(items_data[:, 1] + items_data[:, 4])

    # Calculate the offset required to center the entire group of items
    x_offset = (container_dims[0] - (max_x - min_x)) / 2
    y_offset = (container_dims[1] - (max_y - min_y)) / 2

    # Apply the offset to calculate new positions
    new_positions = np.empty((items_data.shape[0], 3), dtype=np.float64)
    for i in range(items_data.shape[0]):
        x, y, z = items_data[i, :3]
        new_positions[i, 0] = x - min_x + x_offset
        new_positions[i, 1] = y - min_y + y_offset
        new_positions[i, 2] = z  # Z-axis (height) is not centered

    return new_positions

# -------------------------------------------------------------------------
# Bottom-Left-Only packer (replaces the GA). Deterministic greedy packing.
# -------------------------------------------------------------------------
class BottomLeftFill:
    def __init__(self, container: Container):
        self.container = container
        self.epsilon = 1e-5
        self.door_type_int = container.door_type_int

    def find_best_position_for_item(
        self,
        item_to_place: "Item",
        door_type_override: Optional[int] = None,
    ) -> Optional[Tuple[float, float, float, int, int]]:
        """
        Fast BLF placement for a single item.

        • Pallets (neutral containers: door_type not in {0,1}):
            - Fully vectorized candidate generation (Numba) once per rotation
            - Global sort by (z asc, x asc, y asc)
            - NEW: pre-rank stack-above-same-group (and optional same-SKU) positions
            - Reuses a cached 'placed_subset' per Z-plane to speed collision/support checks
            - Preserves ALL stacking/support rules:
            ≥70% support from same-(plan_send_date,pickup_priority), hard lid, different-SKU stack_weight,
            cross-group last-layer rule, grounded items.

        • Containers with doors (front/side): unchanged legacy behavior to preserve exact placement order.
        """
        original_rotation = item_to_place.rotation
        rotations_to_try = [0, 1] if item_to_place.isSideUp else [0, 1, 2, 3, 4, 5]

        # --- Prefer floor-maximizing rotation on neutral pallets (no doors) ---
        local_door_type = self.door_type_int if door_type_override is None else door_type_override
        if local_door_type not in (0, 1) and item_to_place.isSideUp:
            # Per-container memo for SKU → preferred rotation on the floor
            pref_map = getattr(self.container, "_preferred_rot_by_sku", {})
            if not hasattr(self.container, "_preferred_rot_by_sku"):
                self.container._preferred_rot_by_sku = pref_map

            # Compact int for SKU as already used in this class
            type_id_map = getattr(self.container, "_type_id_map", {})
            sku_int = type_id_map.get(item_to_place.itemType_id, len(type_id_map))
            if item_to_place.itemType_id not in type_id_map:
                type_id_map[item_to_place.itemType_id] = sku_int
                self.container._type_id_map = type_id_map

            # Detect if floor is still “fresh” (no items at z≈0); if so, compute best tiling
            placed = np.array([[*it.position, *it.get_rotated_dimensions()] for it in self.container.items], dtype=np.float64) if self.container.items else np.empty((0,6))
            floor_has_items = placed.shape[0] > 0 and np.any(placed[:, 2] < self.epsilon)

            if sku_int in pref_map:
                # Use remembered preference for this SKU
                pref = pref_map[sku_int]
                rotations_to_try = [pref] + [r for r in rotations_to_try if r != pref]
            elif not floor_has_items:
                # Compute per-rotation floor tiling counts and prefer the better one
                L, W = float(self.container.length), float(self.container.width)
                l0, w0, _ = get_rotated_dimensions_numba(item_to_place.length, item_to_place.width, item_to_place.height, 0)
                l1, w1, _ = get_rotated_dimensions_numba(item_to_place.length, item_to_place.width, item_to_place.height, 1)
                cnt0 = int(np.floor(L / l0)) * int(np.floor(W / w0))
                cnt1 = int(np.floor(L / l1)) * int(np.floor(W / w1))
                pref = 1 if cnt1 > cnt0 else 0
                pref_map[sku_int] = pref
                self.container._preferred_rot_by_sku = pref_map
                rotations_to_try = [pref] + [r for r in rotations_to_try if r != pref]

        # Ensure pallet-preference knobs exist (defaults True)
        if not hasattr(self, "STACK_SAME_GROUP_FIRST"):
            self.STACK_SAME_GROUP_FIRST = True
        if not hasattr(self, "STACK_SAME_SKU_FIRST"):
            self.STACK_SAME_SKU_FIRST = True

        # compact type-id mapping per-container (stable across calls)
        type_id_map: Dict[str, int] = getattr(self.container, "_type_id_map", {})
        if not hasattr(self.container, "_type_id_map"):
            self.container._type_id_map = type_id_map

        def get_type_int(t: str) -> int:
            if t in type_id_map:
                return type_id_map[t]
            nxt = len(type_id_map) + 1
            type_id_map[t] = nxt
            return nxt

        candidate_type_int = get_type_int(item_to_place.itemType_id)

        # Build 13-col placed_items_data (supports all constraints)
        num_placed = len(self.container.items)
        placed_items_data = np.zeros((num_placed, 13), dtype=np.float64)
        for i, p_item in enumerate(self.container.items):
            pL, pW, pH = p_item.get_rotated_dimensions()
            px, py, pz = p_item.position
            placed_items_data[i, 0:3]  = (px, py, pz)
            placed_items_data[i, 3:6]  = (pL, pW, pH)
            placed_items_data[i, 6]    = float(get_type_int(p_item.itemType_id))
            placed_items_data[i, 7]    = float(getattr(p_item, "layer", 1))
            placed_items_data[i, 8]    = float(p_item.maxStack)
            placed_items_data[i, 9]    = float(getattr(p_item, "weight", 0.0))
            placed_items_data[i, 10]   = float(getattr(p_item, "stack_weight", -1.0))
            placed_items_data[i, 11]   = float(getattr(p_item, "plan_send_date", 0.0))
            placed_items_data[i, 12]   = float(getattr(p_item, "pickup_priority", 1))

        # Geometry-only slice for collision (faster)
        placed_geom = placed_items_data[:, :6]  # [x,y,z,l,w,h]

        container_dims = np.array(
            [self.container.length, self.container.width, self.container.height],
            dtype=np.float64
        )
        local_door_type = self.door_type_int if door_type_override is None else door_type_override

        # --- last-layer rule context (unchanged) ---
        prev_group_key    = getattr(self.container, "_prev_group_key", None)
        prev_last_layer   = getattr(self.container, "_prev_last_layer_ids", set())
        current_group_key = getattr(self.container, "_current_group_key", None)

        def violates_last_layer_rule(item_pos: np.ndarray, item_dims: np.ndarray) -> bool:
            z = float(item_pos[2])
            if z <= self.epsilon:
                return False
            x, y = float(item_pos[0]), float(item_pos[1])
            l, w, _ = float(item_dims[0]), float(item_dims[1]), float(item_dims[2])
            for p in self.container.items:
                px, py, pz = p.position
                pL, pW, pH = p.get_rotated_dimensions()
                if abs((pz + pH) - z) > self.epsilon:
                    continue
                ov_l = min(x + l, px + pL) - max(x, px)
                if ov_l <= 0.0:
                    continue
                ov_w = min(y + w, py + pW) - max(y, py)
                if ov_w <= 0.0:
                    continue
                p_group = getattr(p, "_group_key", None)
                if p_group != current_group_key:
                    if (prev_group_key is None) or (p_group != prev_group_key) or (id(p) not in prev_last_layer):
                        return True
            return False

        # Candidate group attributes
        cand_sd = float(getattr(item_to_place, "plan_send_date", 0.0))
        cand_pr = int(getattr(item_to_place, "pickup_priority", 1))

        # Helper: pre-filter placed rows for a given Z plane & item height (kept identical)
        def plane_subset(placed: np.ndarray, z_plane: float, h: float, eps: float) -> np.ndarray:
            pz  = placed[:, 2]
            ph  = placed[:, 5]
            top = pz + ph
            # keep rows that vertically overlap [z_plane, z_plane+h] or have top == z_plane (supporters)
            mask = (pz < z_plane + h + eps) & (top > z_plane - eps)
            return placed[mask]

        for rot in rotations_to_try:
            lwh = get_rotated_dimensions_numba(
                item_to_place.length, item_to_place.width, item_to_place.height, rot
            )
            item_dims = np.array(lwh, dtype=np.float64)

            # ---------------- PALLET PATH (neutral) — with pre-ranking ----------------
            if local_door_type not in (0, 1):
                # Generate all candidates once (unsorted), then global sort by (z, x, y)
                positions = generate_and_filter_positions_numba(
                    placed_geom, item_dims, container_dims, self.epsilon, int(-1)
                )
                if positions.shape[0] == 0:
                    continue
                order = np.lexsort((positions[:, 1], positions[:, 0], positions[:, 2]))
                positions = positions[order]

                # ---------- NEW PRE-RANKING: favor stacking-above-same-group (and same-SKU) ----------
                fav_idx, other_idx = [], []
                last_z_rank = None
                subset_rank = None
                for i in range(positions.shape[0]):
                    pos = positions[i]

                    # don't favor non-floor if the item itself must be grounded
                    if item_to_place.grounded and pos[2] > self.epsilon:
                        other_idx.append(i)
                        continue

                    z_plane = float(pos[2])
                    if (last_z_rank is None) or (abs(z_plane - last_z_rank) > self.epsilon):
                        subset_rank = plane_subset(placed_items_data, z_plane, float(item_dims[2]), self.epsilon)
                        last_z_rank = z_plane

                    prefer = False
                    if z_plane > self.epsilon and subset_rank.shape[0] > 0 and self.STACK_SAME_GROUP_FIRST:
                        x, y = float(pos[0]), float(pos[1])
                        l, w = float(item_dims[0]), float(item_dims[1])

                        for r in range(subset_rank.shape[0]):
                            px, py, pz, pl, pw, ph, p_type, p_layer, p_max, p_w, p_msw, p_sd, p_pr = subset_rank[r]
                            # must sit exactly on supporters at this plane
                            if abs((pz + ph) - z_plane) >= self.epsilon:
                                continue
                            # same (plan_send_date, pickup_priority)
                            if not (abs(p_sd - cand_sd) < 0.5 and int(p_pr) == int(cand_pr)):
                                continue
                            # optionally: same SKU column first
                            if self.STACK_SAME_SKU_FIRST and int(p_type) != int(candidate_type_int):
                                continue
                            # fast “inside rectangle” check (strong support likelihood)
                            if (x + l <= px + pl + self.epsilon and
                                y + w <= py + pw + self.epsilon and
                                x >= px - self.epsilon and y >= py - self.epsilon):
                                prefer = True
                                break

                    (fav_idx if prefer else other_idx).append(i)

                order_idx = np.array(fav_idx + other_idx, dtype=np.int64)

                # Cache the 13-col subset for each z-plane to reduce checks
                last_z = None
                placed_subset_13 = None  # full 13-col
                for ii in range(order_idx.shape[0]):
                    item_pos = positions[int(order_idx[ii])]

                    # Grounded?
                    if item_to_place.grounded and item_pos[2] > self.epsilon:
                        continue

                    # reuse per-plane filtered set
                    z_plane = float(item_pos[2])
                    if (last_z is None) or (abs(z_plane - last_z) > self.epsilon):
                        placed_subset_13 = plane_subset(placed_items_data, z_plane, float(item_dims[2]), self.epsilon)
                        last_z = z_plane

                    # Collision on geometry-only view (slice columns 0:6)
                    if placed_subset_13.shape[0] > 0:
                        if check_collision_numba(item_pos, item_dims, placed_subset_13[:, :6], self.epsilon):
                            continue
                    # Cross-group last-layer rule
                    if violates_last_layer_rule(item_pos, item_dims):
                        continue

                    # Full stacking/support constraints
                    is_valid, new_layer = check_support_and_stacking_numba(
                        item_pos,
                        item_dims,
                        int(candidate_type_int),
                        int(item_to_place.maxStack),
                        float(getattr(item_to_place, "weight", 0.0)),
                        cand_sd, cand_pr,
                        placed_subset_13,
                        self.epsilon,
                    )
                    if is_valid:
                        item_to_place.rotation = original_rotation
                        return (float(item_pos[0]), float(item_pos[1]), float(item_pos[2]), int(rot), int(new_layer))

                # try next rotation
                continue

            # ---------------- CONTAINER PATH (front/side doors) — UNCHANGED ----------------
            positions = generate_and_filter_positions_numba(
                placed_items_data, item_dims, container_dims, self.epsilon, int(local_door_type)
            )
            if positions.shape[0] == 0:
                continue

            # Preserve legacy door-aware ordering
            if local_door_type == 0:
                # side door: z DESC, y ASC, x ASC
                order = np.lexsort((positions[:, 0], positions[:, 1], -positions[:, 2]))
                positions = positions[order]
            else:
                # front door: z DESC, x ASC, y ASC
                order = np.lexsort((positions[:, 1], positions[:, 0], -positions[:, 2]))
                positions = positions[order]

            primary_is_x = (local_door_type == 1)
            def primary_of(x: float, y: float) -> float:
                return x if primary_is_x else y

            if num_placed == 0:
                frontier = 0.0
            else:
                if primary_is_x:
                    frontier = max(p.position[0] + p.get_rotated_dimensions()[0] for p in self.container.items)
                else:
                    frontier = max(p.position[1] + p.get_rotated_dimensions()[1] for p in self.container.items)
            frontier = float(frontier)

            # Is this the first item of this group in this container?
            is_new_group_here = not any(
                getattr(p, "_group_key", None) == current_group_key for p in self.container.items
            )

            m = positions.shape[0]
            if is_new_group_here:
                idx_after  = [i for i in range(m) if primary_of(positions[i, 0], positions[i, 1]) + self.epsilon >= frontier]
                idx_before = [i for i in range(m) if i not in idx_after]
                ordered_indices = idx_after + idx_before
            else:
                ordered_indices = list(range(m))

            # Door-aware plane subset is dynamic per candidate (z varies)
            for i in ordered_indices:
                item_pos = positions[i]

                if item_to_place.grounded and item_pos[2] > self.epsilon:
                    continue

                z_plane = float(item_pos[2])
                placed_subset = plane_subset(placed_items_data, z_plane, float(item_dims[2]), self.epsilon)

                if check_collision_numba(item_pos, item_dims, placed_subset[:, :6], self.epsilon):
                    continue
                if violates_last_layer_rule(item_pos, item_dims):
                    continue

                is_valid, new_layer = check_support_and_stacking_numba(
                    item_pos,
                    item_dims,
                    int(candidate_type_int),
                    int(item_to_place.maxStack),
                    float(getattr(item_to_place, "weight", 0.0)),
                    cand_sd, cand_pr,
                    placed_subset,
                    self.epsilon,
                )
                if is_valid:
                    item_to_place.rotation = original_rotation
                    return (float(item_pos[0]), float(item_pos[1]), float(item_pos[2]), int(rot), int(new_layer))

        # No feasible placement
        item_to_place.rotation = original_rotation
        item_to_place.position = None
        return None


class MultiContainerLoadingBLF:
    """
    Pure bottom-left-filled packer, pickup_priority- & group-aware:
      - Group strictly by (plan_send_date|pickup_priority) [sd|pr] (canonical baseline).
      - Within a group: heavier-first.
      - Groups ordered: plan_send_date DESC, pickup_priority DESC, heavier groups first on ties.
      - Monotonic across containers for door-aware containers (unchanged).
      - For neutral pallets only: SKU-affinity + gap-aware selection to reduce SKU scatter
        and fill floor gaps before opening new pallets.
      - Honors 70% support from same (sd,pr), per-item maxStack (base=1), hard-lid,
        different-SKU stack_weight, grounded items.
      - Uses UPDATED find_best_position_for_item() (floor-maximizing rotation + per-SKU memo).
    """

    def __init__(self, containers: List["Container"], items: List["Item"], centered: bool = True):
        # Work on deep copies so original inputs remain unchanged
        self.containers = [copy.deepcopy(c) for c in containers]
        self.items = [copy.deepcopy(i) for i in items]
        self.centered = centered
        self.epsilon = 1e-5 

        self.MAX_STICKY_SCAN = 10
        self.MAX_GAP_PROBE   = 10
        self.MAX_EMPTY_SCAN  = 10
        self.MAX_OTHERS_SCAN = 10

        
        # ---- existing knobs you already have are fine; add these new ones ----
        self.SKIP_GAP_WHEN_MANY_EMPTIES = True
        self.EMPTY_SKIP_GAP_THRESHOLD   = 5000   # tune: if there are >= this many empties, skip gap-probe
        self.EMPTY_TRIES_PER_ITEM       = 5      # how many distinct empties to try per item in the fast path

        self.STACK_SAME_GROUP_FIRST = True
        self.STACK_SAME_SKU_FIRST   = True

        # ---- precompute and cache neutral/non-neutral indices once ----
        self.neutral_idxs = [i for i, c in enumerate(self.containers) if self._is_neutral_pallet(c)]
        self.non_neutral_idxs = [i for i in range(len(self.containers)) if i not in self.neutral_idxs]

        # ---- O(1) empty-pallet allocator: pop from the left, no scanning ----
        self.empty_queue = deque([i for i in self.neutral_idxs if not self.containers[i].items])

        # ---- per-SKU anchor pallet (usually the last pallet we used for that SKU) ----
        self.sku_anchor = {}  # sku_int -> container index



        # Ensure required fields exist on containers
        for c in self.containers:
            if not hasattr(c, "items") or c.items is None:
                c.items = []
            if not hasattr(c, "total_weight"):
                c.total_weight = 0.0
            if not hasattr(c, "volume"):
                c.volume = c.length * c.width * c.height
            if not hasattr(c, "assigned_group"):
                c.assigned_group = None

        # Ensure items have minimal required attributes
        for it in self.items:
            if not hasattr(it, "rotation"):
                it.rotation = 0
            if not hasattr(it, "position"):
                it.position = None
            if not hasattr(it, "stackLimit"):
                it.stackLimit = it.maxStack if getattr(it, "maxStack", -1) != -1 else 10**9
            if not hasattr(it, "volume"):
                it.volume = it.length * it.width * it.height
            if not hasattr(it, "pickup_priority"):
                it.pickup_priority = 1

        # --- NEW: maps for pallet-only SKU affinity ---
        from collections import defaultdict
        self._sku_pallets = defaultdict(list)                       # sku_int -> [pallet_idx]
        self._sku_pallet_counts = defaultdict(lambda: defaultdict(int))  # sku_int -> pallet_idx -> count
        self._type_id_map = {}                                      # itemType_id -> compact int

    # ======== Utility helpers ========

    def _on_place_update_structures(self, ci: int, sku: int, was_empty: bool):
        """Update fast-path structures after placing an item on container `ci`."""
        if was_empty:
            # we popped this from empty_queue before placing; do not push it back
            pass
        # remember the latest good pallet for this SKU
        self.sku_anchor[sku] = ci


    def _is_neutral_pallet(self, cont: "Container") -> bool:
        # Neutral pallet = door_type not side(0) or front(1)
        return getattr(cont, "door_type_int", None) not in (0, 1)

    def _sku_int(self, itemType_id: str) -> int:
        m = self._type_id_map
        if itemType_id not in m:
            m[itemType_id] = len(m)
        return m[itemType_id]

    def _lowest_plane_z(self, pallet_idx: int) -> float:
        c = self.containers[pallet_idx]
        if not c.items:
            return 0.0
        return float(min(it.position[2] for it in c.items))

    def _free_floor_area(self, pallet_idx: int) -> float:
        c = self.containers[pallet_idx]
        L, W = float(c.length), float(c.width)
        if not c.items:
            return L * W
        eps = self.epsilon
        area = L * W
        for it in c.items:
            if it.position[2] < eps:
                l, w, _ = it.get_rotated_dimensions()
                area -= (l * w)
        return max(area, 0.0)

    def _mark_sku_pallet(self, sku: int, pallet_idx: int):
        if pallet_idx not in self._sku_pallets[sku]:
            self._sku_pallets[sku].append(pallet_idx)
        self._sku_pallet_counts[sku][pallet_idx] += 1

    # ======== Legacy helpers kept intact (used elsewhere) ========

    def _primary_frontier(self, container: "Container") -> float:
        """Farthest-used coordinate along the primary axis."""
        if not getattr(container, "items", None):
            return 0.0
        eps = self.epsilon
        if container.door_type_int == 1:  # front door → X primary
            mx = 0.0
            for it in container.items:
                L, W, H = it.get_rotated_dimensions()
                x, y, z = it.position
                v = x + L
                if v > mx:
                    mx = v
            return float(mx)
        else:                              # side door → Y primary
            my = 0.0
            for it in container.items:
                L, W, H = it.get_rotated_dimensions()
                x, y, z = it.position
                v = y + W
                if v > my:
                    my = v
            return float(my)

    def _overlap_xy_area(self, ax: float, ay: float, aL: float, aW: float,
                            bx: float, by: float, bL: float, bW: float) -> float:
        """Rectangle overlap area in XY."""
        ovL = min(ax + aL, bx + bL) - max(ax, bx)
        if ovL <= 0.0:
            return 0.0
        ovW = min(ay + aW, by + bW) - max(ay, by)
        if ovW <= 0.0:
            return 0.0
        return ovL * ovW

    # ======== Group key: canonical sd|pr only (no SKU in key) ========

    def _group_key(self, it: "Item") -> str:
        sd = int(getattr(it, "plan_send_date", 0))
        pr = int(getattr(it, "pickup_priority", 1))
        return f"sd:{sd}|pr:{pr}"

    # ======== Transition helpers (unchanged) ========

    def _compute_last_stack_supporters(self, container: "Container", finished_group_key: str):
        eps = self.epsilon
        F = self._primary_frontier(container)
        ids = set()

        def is_topmost(base_it: "Item") -> bool:
            bx, by, bz = base_it.position
            bL, bW, bH = base_it.get_rotated_dimensions()
            for other in container.items:
                if other is base_it:
                    continue
                ox, oy, oz = other.position
                oL, oW, oH = other.get_rotated_dimensions()
                if oz < bz + bH - eps:
                    continue
                if self._overlap_xy_area(bx, by, bL, bW, ox, oy, oL, oW) > eps:
                    return False
            return True

        for it in container.items:
            if self._group_key(it) != finished_group_key:
                continue
            x, y, z = it.position
            L, W, H = it.get_rotated_dimensions()
            on_band = False
            if container.door_type_int == 1:
                on_band = abs((x + L) - F) <= eps
            else:
                on_band = abs((y + W) - F) <= eps
            if not on_band:
                continue
            if is_topmost(it):
                ids.add(id(it))

        setattr(container, "_transition_supporters_ids", ids)
        setattr(container, "_transition_supporters_group", finished_group_key)

    # ======== Sorting & centering (unchanged) ========

    def _sort_items(self) -> List["Item"]:
        def key_fn(x):
            sid = str(getattr(x, "id", ""))
            return (-x.pickup_priority, -getattr(x, "weight", 0.0), sid)
        return sorted(self.items, key=key_fn)

    def _center_items_in_container(self, container: "Container"):
        if not container.items:
            return
        arr = np.zeros((len(container.items), 6), dtype=np.float64)  # x,y,z,l,w,h
        for i, it in enumerate(container.items):
            L, W, H = it.get_rotated_dimensions()
            arr[i, 0:3] = np.array(it.position, dtype=np.float64)
            arr[i, 3:6] = np.array([L, W, H], dtype=np.float64)

        new_pos = numba_center_items(arr, np.array([container.length, container.width], dtype=np.float64))
        for i, it in enumerate(container.items):
            it.position = (float(new_pos[i, 0]), float(new_pos[i, 1]), float(new_pos[i, 2]))

    def _container_indices_lifo(self, last_used_idx: Optional[int]) -> List[int]:
        n = len(self.containers)
        if n == 0:
            return []
        if last_used_idx is None or last_used_idx < 0 or last_used_idx >= n:
            return list(range(n))
        return [last_used_idx] + [i for i in range(n) if i != last_used_idx]

    # ======== Frontier prep (unchanged) ========

    def _prepare_frontier_for_group(self, container: "Container", group_key: str):
        eps = self.epsilon
        primary_is_x = (container.door_type_int == 1)

        def merge_intervals(iv, end_limit):
            if not iv:
                return []
            iv.sort(key=lambda t: t[0])
            merged = []
            s, e = iv[0]
            for a, b in iv[1:]:
                if a <= e + eps:
                    if b > e: e = b
                else:
                    merged.append((max(0.0, s), min(end_limit, e)))
                    s, e = a, b
            merged.append((max(0.0, s), min(end_limit, e)))
            return merged

        def complement(iv, end_limit):
            if not iv:
                return [(0.0, end_limit)]
            bays = []
            cur = 0.0
            for a, b in iv:
                if a > cur + eps:
                    bays.append((cur, a))
                cur = max(cur, b)
            if cur < end_limit - eps:
                bays.append((cur, end_limit))
            return bays

        if not container.items:
            frontier = 0.0
            prev_gkey = getattr(container, "_last_group_key", None)
            last_layer_ids = set()
            free_bays = [(0.0, container.width if primary_is_x else container.length)]
        else:
            if primary_is_x:
                frontier = max(it.position[0] + it.get_rotated_dimensions()[0] for it in container.items)
            else:
                frontier = max(it.position[1] + it.get_rotated_dimensions()[1] for it in container.items)

            prev_gkey = getattr(container, "_last_group_key", None)
            last_layer_ids = set()
            occupied = []

            if prev_gkey is not None:
                for it in container.items:
                    gk = getattr(it, "_group_key", None)
                    if gk != prev_gkey:
                        continue
                    L, W, _ = it.get_rotated_dimensions()
                    x, y, _ = it.position
                    far = (x + L) if primary_is_x else (y + W)
                    if abs(far - frontier) <= eps:
                        last_layer_ids.add(id(it))
                        if primary_is_x:
                            occupied.append((y, y + W))
                        else:
                            occupied.append((x, x + L))

            sec_limit = container.width if primary_is_x else container.length
            occ_merged = merge_intervals(occupied, sec_limit)
            free_bays = complement(occ_merged, sec_limit)

        container._frontier_primary = float(frontier)
        container._prev_group_key = prev_gkey
        container._prev_last_layer_ids = last_layer_ids
        container._current_group_key = group_key
        container._free_bays_secondary = free_bays

    # ======== NEW: gap-aware candidate probe (neutral pallets only) ========

    def _gap_candidates_for_item(
        self,
        item: "Item",
        group_key: str,
        neutral_idxs: List[int],
        max_probe: Optional[int] = None,
    ) -> List[int]:
        """
        Probe non-empty neutral pallets that could place `item` on their current floor (z≈lowest).
        Early-exit when we have lots of empties to avoid O(#pallets) probing.
        """
        # Skip gap-probing entirely if we have lots of empties available.
        if getattr(self, "SKIP_GAP_WHEN_MANY_EMPTIES", True):
            if len(self.empty_queue) >= int(getattr(self, "EMPTY_SKIP_GAP_THRESHOLD", 1000)):
                return []

        if max_probe is None:
            max_probe = int(getattr(self, "MAX_GAP_PROBE", 4))

        # Cheap geometric/height bounds
        L0, W0, H0 = float(item.length), float(item.width), float(item.height)
        min_footprint = min(L0 * W0, L0 * H0, W0 * H0)
        min_height    = min(L0, W0, H0)

        cands: List[Tuple[int, float, float]] = []
        eps = self.epsilon

        for i in neutral_idxs:
            cont = self.containers[i]
            if not cont.items:
                continue  # only gaps on non-empty pallets

            # weight headroom
            if cont.total_weight + float(getattr(item, "weight", 0.0)) > cont.max_weight + eps:
                continue

            # height at current lowest plane
            z0 = self._lowest_plane_z(i)
            if (float(cont.height) - z0) + eps < min_height:
                continue

            # free floor area vs best-case footprint
            if self._free_floor_area(i) + eps < min_footprint:
                continue

            # group frontier prep + probe (pure)
            self._prepare_frontier_for_group(cont, group_key)
            blf = BottomLeftFill(cont)
            pos = blf.find_best_position_for_item(item)
            if pos is None:
                continue

            x, y, z, rot, layer = pos
            if abs(z - z0) < eps:
                l, w, _ = item.get_rotated_dimensions()
                waste = self._free_floor_area(i) - (l * w)
                cands.append((i, z, waste))
                if len(cands) >= max_probe:
                    break

        cands.sort(key=lambda t: (t[1], t[2]))
        return [i for (i, _, _) in cands]

    # ======== NEW: build container try-order for an item (pallet-only changes) ========
    def _containers_for_item_order(self, item: "Item", group_key: str) -> List[int]:
        """
        Build the container try-order for a neutral-pallet placement.
        Change: empties are now placed AFTER partially filled pallets,
        so we always backfill before opening a new pallet.
        """
        sku = self._sku_int(str(getattr(item, "itemType_id", "__unknown__")))
        n = len(self.containers)

        MAX_STICKY_SCAN = int(getattr(self, "MAX_STICKY_SCAN", 4))
        MAX_GAP_PROBE   = int(getattr(self, "MAX_GAP_PROBE",   4))
        MAX_EMPTY_SCAN  = int(getattr(self, "MAX_EMPTY_SCAN",  3))
        MAX_OTHERS_SCAN = int(getattr(self, "MAX_OTHERS_SCAN", 4))

        # no neutral pallets → original order
        if not self.neutral_idxs:
            return list(range(n))

        # If many empties exist, we will still compute hints,
        # but they will be placed AFTER non-empty candidates.
        many_empties = (
            getattr(self, "SKIP_GAP_WHEN_MANY_EMPTIES", True)
            and len(self.empty_queue) >= int(getattr(self, "EMPTY_SKIP_GAP_THRESHOLD", 1000))
        )

        # Sticky (current SKU on pallet)
        sticky_all = [i for i in self._sku_pallets.get(sku, []) if i in self.neutral_idxs]
        sticky_all.sort(key=lambda i: (self._lowest_plane_z(i), -self._free_floor_area(i)))
        sticky = sticky_all[:MAX_STICKY_SCAN]

        # Gap-first (probe non-empty pallets likely to have a floor gap)
        gap_first = []
        if not many_empties:
            gap_first = self._gap_candidates_for_item(
                item, group_key, self.neutral_idxs, max_probe=MAX_GAP_PROBE
            )

        # Empties (hint list only; packer decides when to pop)
        empty_hint = []
        if len(self.empty_queue) and MAX_EMPTY_SCAN > 0:
            it = iter(self.empty_queue)
            for _ in range(min(MAX_EMPTY_SCAN, len(self.empty_queue))):
                empty_hint.append(next(it))

        # Other non-empty neutral pallets not covered above
        others = [
            i for i in self.neutral_idxs
            if i not in sticky and i not in gap_first and i not in empty_hint
            and self.containers[i].items
        ]

        # Non-neutral containers come last
        non_pallets = self.non_neutral_idxs

        # IMPORTANT CHANGE: empties moved AFTER other non-empties
        return sticky + gap_first + others[:MAX_OTHERS_SCAN] + empty_hint + non_pallets

    
    # ======== Door-aware monotonic packing (unchanged) ========

    def _pack_group_monotonic_across_containers(
        self,
        gitems: List["Item"],
        start_ci: int,
        group_key: str,
    ) -> Tuple[int, List["Item"]]:
        for it in gitems:
            setattr(it, "_group_key", group_key)

        ci = max(0, start_ci)
        k  = 0
        nC = len(self.containers)

        while k < len(gitems) and ci < nC:
            container = self.containers[ci]
            blf = BottomLeftFill(container)

            self._prepare_frontier_for_group(container, group_key)

            it = gitems[k]
            if container.total_weight + it.weight > container.max_weight + self.epsilon:
                ci += 1
                continue

            best = blf.find_best_position_for_item(it)
            if best is None:
                ci += 1
                continue

            x, y, z, rot, new_layer = best
            it.position = (x, y, z)
            it.rotation = rot
            it.layer = int(new_layer)
            it.stackLimit = int(new_layer)
            container.items.append(it)
            container.total_weight += it.weight
            container._last_group_key = group_key
            k += 1

        leftovers = gitems[k:]
        return (min(ci, nC - 1) if nC > 0 else -1, leftovers)

    # ======== NEW: Neutral pallet packing with SKU-affinity + gap-aware order ========

    def _pack_group_neutral_backfill(
        self,
        gitems: List["Item"],
        start_ci: int,
        group_key: str,
    ) -> Tuple[int, List["Item"]]:
        
        for it in gitems:
            setattr(it, "_group_key", group_key)

        remaining: List["Item"] = list(gitems)
        leftovers: List["Item"] = []

        last_used_idx: Optional[int] = start_ci if start_ci is not None and start_ci >= 0 else None

        while remaining:
            progressed = False
            keep: List["Item"] = []

            for it in remaining:
                placed = False
                sku = self._sku_int(str(getattr(it, "itemType_id", "__unknown__")))
                wt  = float(getattr(it, "weight", 0.0))

                # 0) Fast path: try last-used pallet
                if last_used_idx is not None:
                    cont = self.containers[last_used_idx]
                    if self._is_neutral_pallet(cont) and (cont.total_weight + wt <= cont.max_weight + self.epsilon):
                        self._prepare_frontier_for_group(cont, group_key)
                        best = BottomLeftFill(cont).find_best_position_for_item(it)
                        if best is not None:
                            x, y, z, rot, new_layer = best
                            was_empty = (len(cont.items) == 0)
                            it.position = (float(x), float(y), float(z))
                            it.rotation = int(rot)
                            it.layer = int(new_layer)
                            it.stackLimit = int(new_layer)
                            cont.items.append(it)
                            cont.total_weight += wt
                            cont._last_group_key = group_key
                            self._mark_sku_pallet(sku, last_used_idx)
                            self._on_place_update_structures(last_used_idx, sku, was_empty=True if was_empty else False)
                            placed = True
                            progressed = True

                # 1) Fast path: try SKU anchor
                if (not placed) and (sku in self.sku_anchor):
                    ci = self.sku_anchor[sku]
                    cont = self.containers[ci]
                    if self._is_neutral_pallet(cont) and (cont.total_weight + wt <= cont.max_weight + self.epsilon):
                        self._prepare_frontier_for_group(cont, group_key)
                        best = BottomLeftFill(cont).find_best_position_for_item(it)
                        if best is not None:
                            x, y, z, rot, new_layer = best
                            was_empty = (len(cont.items) == 0)
                            it.position = (float(x), float(y), float(z))
                            it.rotation = int(rot)
                            it.layer = int(new_layer)
                            it.stackLimit = int(new_layer)
                            cont.items.append(it)
                            cont.total_weight += wt
                            cont._last_group_key = group_key
                            self._mark_sku_pallet(sku, ci)
                            self._on_place_update_structures(ci, sku, was_empty=True if was_empty else False)
                            placed = True
                            progressed = True
                            last_used_idx = ci

                # 2) Fast path: if many empties, pop a couple from deque and try
                many_empties = (
                    getattr(self, "SKIP_GAP_WHEN_MANY_EMPTIES", True)
                    and len(self.empty_queue) >= int(getattr(self, "EMPTY_SKIP_GAP_THRESHOLD", 1000))
                )
                if (not placed) and many_empties:
                    tries = int(getattr(self, "EMPTY_TRIES_PER_ITEM", 2))
                    popped = []
                    for _ in range(min(tries, len(self.empty_queue))):
                        ci = self.empty_queue.popleft()
                        popped.append(ci)

                        cont = self.containers[ci]
                        # quick weight guard
                        if cont.total_weight + wt > cont.max_weight + self.epsilon:
                            # keep it empty for other (lighter) items
                            self.empty_queue.append(ci)
                            continue

                        # try BLF on this empty pallet
                        self._prepare_frontier_for_group(cont, group_key)
                        best = BottomLeftFill(cont).find_best_position_for_item(it)
                        if best is None:
                            # not suitable for this item → still empty, push back
                            self.empty_queue.append(ci)
                            continue

                        # success
                        x, y, z, rot, new_layer = best
                        was_empty = True  # by construction
                        it.position = (float(x), float(y), float(z))
                        it.rotation = int(rot)
                        it.layer = int(new_layer)
                        it.stackLimit = int(new_layer)
                        cont.items.append(it)
                        cont.total_weight += wt
                        cont._last_group_key = group_key
                        self._mark_sku_pallet(sku, ci)
                        self._on_place_update_structures(ci, sku, was_empty=True)
                        placed = True
                        progressed = True
                        last_used_idx = ci
                        # Do NOT push ci back (it's no longer empty)
                        # Push back any other popped-but-unused empties
                        for r in popped:
                            if r != ci:
                                self.empty_queue.append(r)
                        popped = []
                        break

                    # if none placed, push back all popped empties
                    for r in popped:
                        self.empty_queue.append(r)

                # 3) Normal capped order (sticky/gap/empty-hint/others/non-pallets)
                if not placed:
                    ci_order = self._containers_for_item_order(it, group_key)
                    for ci in ci_order:
                        # avoid retrying the last_used if we already tried it
                        if last_used_idx is not None and ci == last_used_idx:
                            continue

                        cont = self.containers[ci]
                        if not self._is_neutral_pallet(cont):
                            continue  # neutral path only

                        if cont.total_weight + wt > cont.max_weight + self.epsilon:
                            continue

                        was_empty = (len(cont.items) == 0)

                        self._prepare_frontier_for_group(cont, group_key)
                        best = BottomLeftFill(cont).find_best_position_for_item(it)
                        if best is None:
                            continue

                        x, y, z, rot, new_layer = best
                        it.position = (float(x), float(y), float(z))
                        it.rotation = int(rot)
                        it.layer = int(new_layer)
                        it.stackLimit = int(new_layer)
                        cont.items.append(it)
                        cont.total_weight += wt
                        cont._last_group_key = group_key
                        self._mark_sku_pallet(sku, ci)
                        self._on_place_update_structures(ci, sku, was_empty=True if was_empty else False)

                        placed = True
                        progressed = True
                        last_used_idx = ci
                        break

                if not placed:
                    keep.append(it)

            if not progressed:
                leftovers.extend(keep)
                break

            remaining = keep

        return (last_used_idx if last_used_idx is not None else -1, leftovers)


    # ======== Optional diagnostic helpers (unchanged) ========

    def _collect_segments_by_group(self):
        segments_by_group = {}
        group_stats = {}

        for c in self.containers:
            if not getattr(c, "items", None):
                continue

            per_group = {}
            for it in c.items:
                g = self._group_key(it)
                per_group.setdefault(g, []).append(it)

            for g, items in per_group.items():
                min_x = 1e30; min_y = 1e30; max_x = -1e30; max_y = -1e30
                weight_sum = 0.0
                for it in items:
                    L, W, H = it.get_rotated_dimensions()
                    x, y, z = it.position
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x + L > max_x: max_x = x + L
                    if y + W > max_y: max_y = y + W
                    weight_sum += float(getattr(it, "weight", 0.0))
                seg = {
                    "items": items,
                    "min_x": float(min_x),
                    "min_y": float(min_y),
                    "sx": float(max_x - min_x),
                    "sy": float(max_y - min_y),
                    "weight": weight_sum,
                }
                segments_by_group.setdefault(g, []).append(seg)

                for it in items:
                    pr = int(getattr(it, "pickup_priority", 1))
                    w  = float(getattr(it, "weight", 0.0))
                    if g not in group_stats:
                        group_stats[g] = {"min_pr": pr, "total_w": w}
                    else:
                        if pr < group_stats[g]["min_pr"]:
                            group_stats[g]["min_pr"] = pr
                        group_stats[g]["total_w"] += w

        return segments_by_group, group_stats

    def _clear_all_containers(self):
        for c in self.containers:
            c.items = []
            c.total_weight = 0.0
            if hasattr(c, "assigned_group"):
                c.assigned_group = None

    def _place_segment_xy(self, container: "Container", seg, origin_x: float, origin_y: float):
        dx = origin_x - seg["min_x"]
        dy = origin_y - seg["min_y"]
        for it in seg["items"]:
            x, y, z = it.position
            it.position = (x + dx, y + dy, z)
            container.items.append(it)
            container.total_weight += float(getattr(it, "weight", 0.0))

    def _snapshot_container(self, container: "Container"):
        return {"count": len(container.items), "weight": container.total_weight}

    def _next_empty_container_index(self, start_from: int) -> int:
        for i in range(max(0, start_from), len(self.containers)):
            if len(self.containers[i].items) == 0:
                return i
        return -1

    def _revert_container(self, container: "Container", snap):
        while len(container.items) > snap["count"]:
            container.items.pop()
        container.total_weight = snap["weight"]

    def _try_place_group_in_container(self, container: "Container", group_items: List["Item"]) -> bool:
        # unchanged
        snap = self._snapshot_container(container)
        originals = []
        blf = BottomLeftFill(container)

        for it in group_items:
            if container.total_weight + it.weight > container.max_weight + self.epsilon:
                self._revert_container(container, snap)
                for item, pos, rot, sl, lyr in originals:
                    item.position, item.rotation = pos, rot
                    item.stackLimit = sl
                    if lyr is not None:
                        item.layer = lyr
                return False

            originals.append((
                it,
                it.position,
                it.rotation,
                getattr(it, "stackLimit", 10**9),
                getattr(it, "layer", None)
            ))

            best = blf.find_best_position_for_item(it, door_type_override=None)
            if best is None:
                self._revert_container(container, snap)
                for item, pos, rot, sl, lyr in originals:
                    item.position, item.rotation = pos, rot
                    item.stackLimit = sl
                    if lyr is not None:
                        item.layer = lyr
                return False

            x, y, z, rot, new_layer = best
            it.position = (x, y, z)
            it.rotation = rot
            it.layer = int(new_layer)
            it.stackLimit = int(new_layer)
            container.items.append(it)
            container.total_weight += it.weight

        return True

    # ======== XY compaction (unchanged) ========

    def _build_vertical_components(self, container: "Container"):
        items = container.items
        n = len(items)
        if n == 0:
            return []

        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        eps = self.epsilon

        for i in range(n):
            xi, yi, zi = items[i].position
            Li, Wi, Hi = items[i].get_rotated_dimensions()
            top_i = zi + Hi
            for j in range(i + 1, n):
                xj, yj, zj = items[j].position
                Lj, Wj, Hj = items[j].get_rotated_dimensions()
                top_j = zj + Hj
                if (min(xi + Li, xj + Lj) - max(xi, xj) > eps and
                    min(yi + Wi, yj + Wj) - max(yi, yj) > eps):
                    if abs(top_i - zj) < eps or abs(top_j - zi) < eps:
                        union(i, j)

        comps_map = {}
        for idx in range(n):
            r = find(idx)
            comps_map.setdefault(r, []).append(idx)

        comps = []
        for idxs in comps_map.values():
            min_x = 1e30; min_y = 1e30; max_x = -1e30; max_y = -1e30
            for k in idxs:
                it = items[k]
                L, W, _ = it.get_rotated_dimensions()
                x, y, _ = it.position
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x + L > max_x: max_x = x + L
                if y + W > max_y: max_y = y + W
            comps.append({
                "indices": idxs,
                "min_x": float(min_x), "max_x": float(max_x),
                "min_y": float(min_y), "max_y": float(max_y),
                "dx": 0.0, "dy": 0.0
            })
        return comps

    def _compact_components_axis(self, comps, axis: int):
        eps = self.epsilon

        def bbox(c):
            return (c["min_x"] + c["dx"], c["max_x"] + c["dx"],
                    c["min_y"] + c["dy"], c["max_y"] + c["dy"])

        if axis == 0:
            order = sorted(comps, key=lambda c: bbox(c)[0])
        else:
            order = sorted(comps, key=lambda c: bbox(c)[2])

        placed = []
        for c in order:
            cx0, cx1, cy0, cy1 = bbox(c)
            if axis == 0:
                allowed_min = 0.0
                for p in placed:
                    px0, px1, py0, py1 = bbox(p)
                    if min(cy1, py1) - max(cy0, py0) > eps:
                        if px1 > allowed_min:
                            allowed_min = px1
                shift = allowed_min - cx0
                if abs(shift) > eps:
                    c["dx"] += shift
            else:
                allowed_min = 0.0
                for p in placed:
                    px0, px1, py0, py1 = bbox(p)
                    if min(cx1, px1) - max(cx0, px0) > eps:
                        if py1 > allowed_min:
                            allowed_min = py1
                shift = allowed_min - cy0
                if abs(shift) > eps:
                    c["dy"] += shift

            placed.append(c)

    def _compact_container_xy(self, container: "Container"):
        if not container.items:
            return

        eps = self.epsilon
        L = float(container.length)
        W = float(container.width)

        def bbox(c):
            return (c["min_x"] + c["dx"], c["max_x"] + c["dx"],
                    c["min_y"] + c["dy"], c["max_y"] + c["dy"])

        def overlap_1d(a0, a1, b0, b1):
            return (min(a1, b1) - max(a0, b0)) > eps

        comps = self._build_vertical_components(container)
        front_door = (container.door_type_int == 1)

        def rank(x, y):
            return (x, y) if front_door else (y, x)

        for _round in range(16):
            total_move = 0.0
            if front_door:
                order = sorted(comps, key=lambda c: (c["min_x"] + c["dx"], c["min_y"] + c["dy"]))
            else:
                order = sorted(comps, key=lambda c: (c["min_y"] + c["dy"], c["min_x"] + c["dx"]))
            placed = []
            for c in order:
                cx0, cx1, cy0, cy1 = bbox(c)
                w = cx1 - cx0
                h = cy1 - cy0

                x_limits = [0.0]
                for p in placed:
                    px0, px1, py0, py1 = bbox(p)
                    if overlap_1d(cy0, cy1, py0, py1):
                        x_limits.append(px1)

                candidates = []
                for xl in x_limits:
                    new_x0 = min(cx0, max(0.0, xl))
                    new_x1 = new_x0 + w
                    y_limits = [0.0]
                    for p in placed:
                        px0, px1, py0, py1 = bbox(p)
                        if overlap_1d(new_x0, new_x1, px0, px1):
                            y_limits.append(py1)
                    new_y0 = min(cy0, max(y_limits))
                    candidates.append((new_x0, new_y0))

                y_limits = [0.0]
                for p in placed:
                    px0, px1, py0, py1 = bbox(p)
                    if overlap_1d(cx0, cx1, px0, px1):
                        y_limits.append(py1)

                for yl in y_limits:
                    new_y0 = min(cy0, max(0.0, yl))
                    new_y1 = new_y0 + h
                    x_limits2 = [0.0]
                    for p in placed:
                        px0, px1, py0, py1 = bbox(p)
                        if overlap_1d(new_y0, new_y1, py0, py1):
                            x_limits2.append(px1)
                    new_x0 = min(cx0, max(x_limits2))
                    candidates.append((new_x0, new_y0))

                new_x0, new_y0 = min(candidates, key=lambda t: rank(t[0], t[1]))
                if new_x0 < 0.0: new_x0 = 0.0
                if new_y0 < 0.0: new_y0 = 0.0

                s_x = new_x0 - cx0
                s_y = new_y0 - cy0
                if s_x > 0.0: s_x = 0.0
                if s_y > 0.0: s_y = 0.0

                if abs(s_x) > eps or abs(s_y) > eps:
                    c["dx"] += s_x
                    c["dy"] += s_y
                    total_move += (-s_x) + (-s_y)

                placed.append(c)

            if total_move <= 1e-9:
                break

        for c in comps:
            dx, dy = c["dx"], c["dy"]
            if abs(dx) < eps and abs(dy) < eps:
                continue
            for idx in c["indices"]:
                it = container.items[idx]
                x, y, z = it.position
                it.position = (x + dx, y + dy, z)

        min_x = 1e30; min_y = 1e30; max_x = -1e30; max_y = -1e30
        for it in container.items:
            Lx, Wy, _ = it.get_rotated_dimensions()
            x, y, _ = it.position
            if x < min_x: min_x = x
            if y < min_y: min_y = y
            if x + Lx > max_x: max_x = x + Lx
            if y + Wy > max_y: max_y = y + Wy

        fix_dx = 0.0
        fix_dy = 0.0
        if min_x < -self.epsilon:             fix_dx = -min_x
        if min_y < -self.epsilon:             fix_dy = -min_y
        if max_x + fix_dx > L + self.epsilon: fix_dx -= (max_x + fix_dx) - L
        if max_y + fix_dy > W + self.epsilon: fix_dy -= (max_y + fix_dy) - W

        if abs(fix_dx) > self.epsilon or abs(fix_dy) > self.epsilon:
            for it in container.items:
                x, y, z = it.position
                it.position = (x + fix_dx, y + fix_dy, z)

    # ======== Feasibility checks & run() (unchanged except neutral path uses new function) ========

    def _item_fits_any_container(self, it: "Item") -> bool:
        eps = self.epsilon if hasattr(self, "epsilon") else 1e-5
        rotations = [0, 1] if getattr(it, "isSideUp", False) else [0, 1, 2, 3, 4, 5]

        for c in self.containers:
            cL, cW, cH = float(c.length), float(c.width), float(c.height)
            for r in rotations:
                L, W, H = get_rotated_dimensions_numba(it.length, it.width, it.height, int(r))
                if (L <= cL + eps) and (W <= cW + eps) and (H <= cH + eps):
                    return True
        return False

    def _quick_feasibility_exit(self):
        unfit = [it for it in self.items if not self._item_fits_any_container(it)]
        if len(unfit) > 0:
            return {"containers": [], "unused": list(self.items)}

        total_items_w = float(sum(float(getattr(it, "weight", 0.0)) for it in self.items))
        total_caps_w  = float(sum(float(getattr(c, "max_weight", 0.0)) for c in self.containers))
        if total_items_w > total_caps_w + (self.epsilon if hasattr(self, "epsilon") else 1e-5):
            return {"containers": [], "unused": list(self.items)}
        return None

    def _sort_items_within_group(self, subset: List["Item"]) -> List["Item"]:
        def key_fn(x):
            return (-float(getattr(x, "weight", 0.0)), str(getattr(x, "id", "")))
        return sorted(subset, key=key_fn)

    def run(self):
        early = self._quick_feasibility_exit()
        if early is not None:
            return early

        unused: List["Item"] = []

        # Groups by sd|pr (canonical)
        groups_map: Dict[str, List["Item"]] = {}
        for it in self.items:
            groups_map.setdefault(self._group_key(it), []).append(it)

        # Sort within group: heavier first
        for g, items in groups_map.items():
            groups_map[g] = self._sort_items_within_group(items)

        # Order groups: plan_send_date DESC, pickup_priority DESC, heavier group first on ties
        def group_sort_key(kv):
            gname, items = kv
            if items:
                sd = int(getattr(items[0], "plan_send_date", 0))
                pr = int(getattr(items[0], "pickup_priority", 1))
            else:
                sd = 0; pr = 1
            total_w = sum(float(getattr(x, "weight", 0.0)) for x in items)
            sku_rep = str(getattr(items[0], "itemType_id", "__unknown__")) if items else "__unknown__"
            return (-sd, -pr, -total_w, sku_rep)

        ordered_groups = [kv for kv in sorted(groups_map.items(), key=group_sort_key)]

        all_neutral = all(self._is_neutral_pallet(c) for c in self.containers)

        gid_counter = 1
        ci = 0
        for gname, gitems in ordered_groups:
            for it in gitems:
                it.group_id = int(gid_counter)

            if ci >= len(self.containers):
                unused.extend(gitems)
                gid_counter += 1
                continue

            if all_neutral:
                # NEW: pallet-only affinity + gap-aware neutral packing
                last_ci, leftovers = self._pack_group_neutral_backfill(gitems, ci, gname)
            else:
                # Unchanged: door-aware monotonic packing
                last_ci, leftovers = self._pack_group_monotonic_across_containers(gitems, ci, gname)

            if leftovers:
                unused.extend(leftovers)
            ci = max(last_ci, ci)
            gid_counter += 1

        if self.centered:
            for c in self.containers:
                self._center_items_in_container(c)

        used = [c for c in self.containers if c.items]

        print(f'total containers: {len(used)}')
        print('finished simulation')
        
        return {"containers": used, "unused": unused}



def prepare_products(products: List[schemas.ModelProduct]) -> List[Item]:
    ind_items = [item for item in products for _ in range(item.qty)]

    model_items = [
        Item(
            id=str(id),
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
            id=str(id) + str(pallet.palletid),
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
    model_containers = [
        Container(
            id=str(id),
            type_id=container.package_id,
            length=container.load_length,
            width=container.load_width,
            height=container.load_height,
            exlength=container.package_length,
            exwidth=container.package_width,
            exheight=container.package_height,
            exweight=container.package_weight,
            max_weight=container.load_weight,
            pickup_priority=container.pickup_priority,
            door_position=container.door_position,
        )
        for id, container in enumerate(ind_containers)
    ]

    print(model_containers[0].door_position)
    return model_containers


def prepare_palletitems(pallets: List[Container]) -> List[Item]:
    model_items = [
        Item(
            id=pallet.id,
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
            pickup_priority=pallet.pickup_priority,
        )
        for pallet in pallets
        if len(pallet.items) > 0
    ]
    return model_items


class simulation_result(TypedDict):
    containers: list[Container] 
    unused: list[Item]

def simulate(model_items: List[Item], model_containers: List[Container], centered=True) -> simulation_result:
    model_containers.sort(key=lambda c: c.volume, reverse=True)

    optimizer = MultiContainerLoadingBLF(
        model_containers, model_items, centered=centered
    )

    try:
        solution = optimizer.run()
        return solution
    
    except Exception as e:
        # print(e.__traceback__)
        print(e)
        traceback.print_exc() 
        return None
    

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, inf
from datetime import datetime
from typing import Any, List, Optional, Tuple, Dict, Set
from functools import lru_cache

import os

ROTATION_PATTERNS = ((0, 1, 2), (1, 0, 2), (2, 1, 0), (1, 2, 0), (0, 2, 1), (2, 0, 1))
ORIENTATION_PATTERNS = (
    (0, 0, 0),
    (0, 90, 0),
    (0, 0, 90),
    (90, 0, 90),
    (90, 0, 0),
    (90, -90, 0),
)


def getRotDim(
    width: float, length: float, height: float, rotation: int
) -> tuple[float, float, float]:
    dimensions = width, length, height
    rotation = rotation or 0
    pattern = (
        ROTATION_PATTERNS[rotation]
        if 0 <= rotation < len(ROTATION_PATTERNS)
        else (0, 1, 2)
    )
    return dimensions[pattern[0]], dimensions[pattern[1]], dimensions[pattern[2]]


def getOrien(rotation: int) -> tuple[float, float, float]:
    rotation = rotation if 0 <= rotation < len(ORIENTATION_PATTERNS) else 0
    return ORIENTATION_PATTERNS[rotation]


EPS = 1e-6


def sku_signature(item: "Item") -> Tuple:
    return (
        item.order_id,
        item.itemType_id,
        round(item.length, 4),
        round(item.width, 4),
        round(item.height, 4),
        round(item.weight, 4),
        item.isSideUp,
        item.maxStack,
        item.pickup_priority,
        item.grounded,
        item.itemType,
        getattr(item, "color", None),
        item.senddate_ts,
    )


@lru_cache(maxsize=256)
def priority_sort_key(value: float) -> float:
    return value


@dataclass
class Item:
    id: int
    order_id: str
    itemType_id: str
    length: float
    width: float
    height: float
    weight: float
    isSideUp: bool
    itemType: str
    color: Optional[str] = None
    maxStack: int = -1
    grounded: bool = False
    pickup_priority: int = 1
    plan_send_date: str = ""
    rotation: int = 0
    must_be_on_top: bool = False
    maxStackWeight: Optional[float] = None
    position: Optional[Tuple[float, float, float]] = None
    layer: int = 1  # Track which layer this item is on (1-indexed)
    final_rank: int = 0  # Global ranking for placement order
    pallet_id: Optional[int] = None  # Original pallet ID for pallet-container simulation
    volume: float = field(init=False)
    senddate_ts: int = field(init=False)

    def __post_init__(self) -> None:
        self.stackLimit = self.maxStack

        if self.stackLimit < 0:
            self.stackLimit = 10000
        self.volume = self.length * self.width * self.height
        if not self.maxStackWeight:
            self.maxStackWeight = (self.stackLimit - 1) * self.weight

        if self.maxStackWeight < 0:
            self.maxStackWeight = 1000000

        if self.plan_send_date:
            try:
                dt = datetime.strptime(self.plan_send_date, "%Y-%m-%dT%H:%M:%S")
                # Use UTC to ensure deterministic timestamps across different timezones
                # Convert to Unix timestamp assuming the input is in UTC
                epoch = datetime(1970, 1, 1)
                self.senddate_ts = int((dt - epoch).total_seconds())
            except ValueError:
                self.senddate_ts = 0
        else:
            self.senddate_ts = 0

    def get_rotated_dimensions(
        self, rotation: Optional[int] = None
    ) -> Tuple[float, float, float]:
        """Returns (x_dim, y_dim, z_dim) where x=width, y=length, z=height."""
        r = self.rotation if rotation is None else rotation
        return getRotDim(self.width, self.length, self.height, r)


door_type_map = {
    "side": 0,
    "front": 1,
}


@dataclass
class Container:
    id: int
    type_id: str
    length: float
    width: float
    height: float
    max_weight: float
    exlength: float
    exwidth: float
    exheight: float
    exweight: float
    pickup_priority: int = 1
    door_position: Optional[str] = None
    items: List[Item] = field(default_factory=list)
    total_weight: float = 0.0
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        self.volume = self.length * self.width * self.height
        dp_raw = getattr(self, "door_position", None)
        if isinstance(dp_raw, str):
            dp = dp_raw.strip().lower()
            # Treat any declared door string as using front-door logic
            self.door_type_int = 1 if dp else -1
        else:
            self.door_type_int = -1


@lru_cache(maxsize=8)
def _get_rotations_cached(is_side_up: bool) -> List[int]:
    """Cached helper for allowed rotations based on isSideUp flag."""
    return [0, 1] if is_side_up else [0, 1, 2, 3, 4, 5]


def allowed_rotations(item: Item) -> List[int]:
    return _get_rotations_cached(item.isSideUp)


@dataclass
class OrientationCache:
    """Precomputes permitted rotations and footprint areas per item."""

    rotations: List[int]
    dimensions: Dict[int, Tuple[float, float, float]]
    areas: Dict[int, float]

    @classmethod
    def build(cls, item: Item) -> "OrientationCache":
        rots = allowed_rotations(item)
        dims = {rot: item.get_rotated_dimensions(rot) for rot in rots}
        areas = {rot: d[0] * d[1] for rot, d in dims.items()}
        return cls(rotations=rots, dimensions=dims, areas=areas)


@dataclass
class Placement:
    item: Item
    x: float
    y: float
    z: float
    rotation: int
    dims: Tuple[float, float, float]
    supporters: List[Item] = field(default_factory=list)
    layer_level: int = 1

    @property
    def footprint(self) -> Tuple[float, float]:
        return (self.dims[0], self.dims[1])

    @property
    def top(self) -> float:
        return self.z + self.dims[2]

    @property
    def bounds(self) -> Tuple[float, float, float, float, float, float]:
        return (
            self.x,
            self.y,
            self.z,
            self.x + self.dims[0],
            self.y + self.dims[1],
            self.z + self.dims[2],
        )


@dataclass
class PlacementTemplate:
    position: Tuple[float, float, float]
    dims: Tuple[float, float, float]
    rotation: int
    layer_level: int
    sku_key: Tuple


def clone_item(item: Item) -> Item:
    return Item(
        id=item.id,
        order_id=item.order_id,
        itemType_id=item.itemType_id,
        length=item.length,
        width=item.width,
        height=item.height,
        weight=item.weight,
        isSideUp=item.isSideUp,
        itemType=item.itemType,
        color=item.color,
        maxStack=item.maxStack,
        grounded=item.grounded,
        pickup_priority=item.pickup_priority,
        plan_send_date=item.plan_send_date,
        must_be_on_top=item.must_be_on_top,
        maxStackWeight=item.maxStackWeight,
        final_rank=item.final_rank,
        pallet_id=getattr(item, 'pallet_id', None),
    )


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


def create_packer(
    container: Container,
    orientation_cache: Dict[int, OrientationCache],
    must_be_on_top: Optional[Dict[int, bool]] = None,
    co_loc_groups: Optional[Dict[str, Set[int]]] = None,
):
    """Factory function to create appropriate packer based on container door type."""
    # Lazy import to avoid circular dependency
    from .packers import PalletPacker, DoorContainerPacker

    if os.environ.get("PACKER_DEBUG_FLOW", "0") == "1":
        print(
            f"[DEBUG] create_packer: door_type_int={container.door_type_int} door_position={getattr(container, 'door_position', None)}",
            flush=True,
        )

    if container.door_type_int == -1:
        return PalletPacker(container, orientation_cache, must_be_on_top, co_loc_groups)
    else:
        return DoorContainerPacker(
            container, orientation_cache, must_be_on_top, co_loc_groups
        )


def create_mixed_sku_packer(
    container: Container,
    orientation_cache: Dict[int, OrientationCache],
    must_be_on_top: Optional[Dict[int, bool]] = None,
    co_loc_groups: Optional[Dict[str, Set[int]]] = None,
    use_balanced: bool = True,
):
    """
    Factory function to create a packer optimized for mixed-SKU pallets.

    Args:
        container: The container/pallet to pack into
        orientation_cache: Pre-computed orientation data for items
        must_be_on_top: Dict of item IDs that must be placed on top
        co_loc_groups: Co-location groups for items that should be placed together
        use_balanced: If True, use balanced weight distribution algorithm

    Returns:
        A packer instance (MixedSkuPalletPacker or PalletPacker)
    """
    # Lazy import to avoid circular dependency
    from .packers import PalletPacker, MixedSkuPalletPacker

    if os.environ.get("PACKER_DEBUG_FLOW", "0") == "1":
        print(
            f"[DEBUG] create_mixed_sku_packer: use_balanced={use_balanced}",
            flush=True,
        )

    if use_balanced and container.door_type_int == -1:
        return MixedSkuPalletPacker(
            container, orientation_cache, must_be_on_top, co_loc_groups
        )
    else:
        return PalletPacker(container, orientation_cache, must_be_on_top, co_loc_groups)

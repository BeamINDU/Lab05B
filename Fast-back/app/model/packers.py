"""
Packers module - provides packing algorithms for pallets and containers.

This module re-exports all packer classes and utilities from their respective modules:
- common_packers: Shared utilities (MaxRects2D, FirstLayerPlanner, Rect, etc.)
- blf_packer: BottomLeftFill algorithm
- pallet_packer: PalletPacker for pallets (door_type_int == -1)
- container_packer: DoorContainerPacker for containers with doors
- balanced_packer: Balanced weight distribution for mixed-SKU pallets
"""

from __future__ import annotations

# Re-export from common_packers
from .common_packers import (
    Rect,
    MaxRects2D,
    FirstLayerPlanner,
    get_supporters,
    clone_container,
)

# Re-export from blf_packer
from .blf_packer import (
    BottomLeftFill,
    _generate_positions_numba,
)

# Re-export from pallet_packer
from .pallet_packer import PalletPacker

# Re-export from container_packer
from .container_packer import DoorContainerPacker

# Re-export from balanced_packer (mixed-SKU support)
from .balanced_packer import (
    QuadrantBalancer,
    WeightDistributionTracker,
    # ItemGroup,
    MixedSkuPalletPacker,
)

# Re-export numba functions from geometry for backward compatibility
from .geometry import (
    generate_and_filter_positions_numba,
    check_collision_numba,
    check_priority_adjacency_numba,
    check_support_and_stacking_numba,
)

__all__ = [
    # Common utilities
    "Rect",
    "MaxRects2D",
    "FirstLayerPlanner",
    "get_supporters",
    "clone_container",
    # BLF algorithm
    "BottomLeftFill",
    "_generate_positions_numba",
    # Packers
    "PalletPacker",
    "DoorContainerPacker",
    # Balanced packer (mixed-SKU)
    "QuadrantBalancer",
    "WeightDistributionTracker",
    # "ItemGroup",
    "MixedSkuPalletPacker",
    # Numba functions
    "generate_and_filter_positions_numba",
    "check_collision_numba",
    "check_priority_adjacency_numba",
    "check_support_and_stacking_numba",
]

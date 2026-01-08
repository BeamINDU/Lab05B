from typing import Any, Optional, List
from pydantic import BaseModel, Field, model_serializer
from app.schemas import partial_model


# ========== Common Models ==========


class Position(BaseModel):
    x: float
    y: float
    z: float


class Orientation(BaseModel):
    x: float
    y: float
    z: float


class PackageDetail(BaseModel):
    package_id: int
    package_code: str
    package_name: str
    package_width: float
    package_length: float
    package_height: float
    package_weight: float
    load_width: float
    load_length: float
    load_height: float
    load_weight: float


class Package(BaseModel):
    package_type: Optional[str] = None
    package_detail: List[PackageDetail]


class VehicleBase(BaseModel):
    vehicle_id: int
    vehicle_type_id: int
    vehicle_type_name: str
    vehicle_name: str
    model: str
    license_plate: str
    # truck_size: Optional[str] = None
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    height_mm: Optional[float] = None
    container_id: int
    container_name: str
    door_position: Optional[str] = "back"
    container_width: float
    container_length: float
    container_height: float
    container_weight: Optional[float] = 0  # Only in main vehicle
    load_width: float
    load_length: float
    load_height: float
    load_weight: float
    # vehicle_type: Optional[str] = None  # Used in response
    # max_volume_m3: Optional[float] = None  # Only in trailer


class LogisticBase(BaseModel):
    job_selection_type_id: int
    job_selection_type_name: str
    max_moves: float


class OrderBase(BaseModel):
    orders_id: int
    orders_no: str


# ========== Request Models ==========


class ProductRequest(BaseModel):
    product_id: int
    product_no: str
    product_name: str
    quantity: Optional[int] = None
    weight: float
    w_mm: float
    l_mm: float
    h_mm: float
    stack_limit: Optional[int] = Field(None, exclude_none=False)
    is_do_not_stack: bool
    is_side_up: bool
    qty_per_box: int


class OrderRequest(OrderBase, BaseModel):
    order_operation_type: str
    products: List[ProductRequest]


class JobDetailRequest(BaseModel):
    seq: int
    orders: List[OrderRequest]


class JobSelectionDetailRequest(VehicleBase, BaseModel):
    job_id: int
    job_name: str
    # vehicle_des: str
    trailer_vehicle: Optional[VehicleBase] = None
    total_distance: float
    total_weight: float
    total_time: str
    job_detail: List[JobDetailRequest]


# ========== Response Models ==========


class ProductResponse(ProductRequest, BaseModel):
    item_no: int
    position: Position
    orientation: Orientation

    @model_serializer(when_used="json")
    def sort_model(self) -> dict[str, Any]:
        # return dict(sorted(self.model_dump().items()))
        return {
            "item_no": self.item_no,
            "product_id": self.product_id,
            "product_no": self.product_no,
            "product_name": self.product_name,
            "weight": self.weight,
            "w_mm": self.w_mm,
            "l_mm": self.l_mm,
            "h_mm": self.h_mm,
            "stack_limit": self.stack_limit,
            "is_do_not_stack": self.is_do_not_stack,
            "is_side_up": self.is_side_up,
            "position": self.position,
            "orientation": self.orientation,
        }


class OrderResponse(OrderBase, BaseModel):
    products: List[ProductResponse]


@partial_model
class PackageOptimization(PackageDetail, BaseModel):
    package_seq: int
    package_type: str
    position: Position
    orientation: Orientation
    orders: List[OrderResponse]

    @model_serializer(when_used="json")
    def sort_model(self) -> dict[str, Any]:
        data = {
            "package_seq": self.package_seq,
            "package_type": self.package_type,
            "package_id": self.package_id,
            "package_code": self.package_code,
            "package_name": self.package_name,
            "package_width": self.package_width,
            "package_length": self.package_length,
            "package_height": self.package_height,
            "package_weight": self.package_weight,
            "load_width": self.load_width,
            "load_length": self.load_length,
            "load_height": self.load_height,
            "load_weight": self.load_weight,
            "position": self.position,
            "orientation": self.orientation,
            "orders": self.orders,
        }
        return {k: v for k, v in data.items() if v is not None}


class VehicleResponse(VehicleBase, BaseModel):
    utilize_weight: str
    utilize_weight_percent: float
    utilize_cap: str
    utilize_cap_percent: float
    package_opt: List[PackageOptimization]

    @model_serializer(when_used="json")
    def sort_model(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "vehicle_type_id": self.vehicle_type_id,
            "vehicle_type_name": self.vehicle_type_name,
            "vehicle_name": self.vehicle_name,
            "model": self.model,
            "license_plate": self.license_plate,
            # "width_m": self.width_m,
            # "length_m": self.length_m,
            # "height_m": self.height_m,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "container_width": self.container_width,
            "container_length": self.container_length,
            "container_height": self.container_height,
            "container_weight": self.container_weight,
            "load_width": self.load_width,
            "load_length": self.load_length,
            "load_height": self.load_height,
            "load_weight": self.load_weight,
            "door_position": self.door_position,
            "utilize_weight": self.utilize_weight,
            "utilize_weight_percent": self.utilize_weight_percent,
            "utilize_cap": self.utilize_cap,
            "utilize_cap_percent": self.utilize_cap_percent,
            "package_opt": self.package_opt,
        }


class JobSelectionDetailResponse(BaseModel):
    job_id: int
    job_name: str
    vehicle: List[VehicleResponse]  # Can have multiple vehicles (main + trailer)


class LogisticsRequest(LogisticBase, BaseModel):
    package: Package
    job_selection_detail: List[JobSelectionDetailRequest]


class LogisticsResponse(LogisticBase, BaseModel):
    job_selection_detail: List[JobSelectionDetailResponse]

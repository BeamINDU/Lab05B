from copy import deepcopy
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, create_model
from pydantic.fields import FieldInfo
from typing import Any, Optional, Union
from datetime import datetime
from typing import Literal, TypedDict, ClassVar

from pydantic_core import PydanticUndefined
from app import models


def to_camel(string: str) -> str:
    """Helper function to convert snake_case to camelCase"""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def partial_model(model: type[BaseModel]):
    def make_field_optional(
        field: FieldInfo, default: Any = None
    ) -> tuple[Any, FieldInfo]:
        new = deepcopy(field)
        if default:
            new.default = default
        elif new.default is PydanticUndefined:
            new.default = None
        new.annotation = Optional[field.annotation]  # type: ignore
        return new.annotation, new

    return create_model(
        f"Partial{model.__name__}",
        __base__=model,
        __module__=model.__module__,
        **{
            field_name: make_field_optional(field_info)
            for field_name, field_info in model.model_fields.items()
        },
    )


class updateResponse(BaseModel):
    message: str


class deleteResponse(BaseModel):
    message: str


class restoreResponse(BaseModel):
    message: str


class uploadResponse(BaseModel):
    message: str


# ----Product-----
class ProductBase(BaseModel):
    product_id: int
    product_code: str = Field(alias=AliasChoices("product_code", "Product Code"))
    product_name: str = Field(alias=AliasChoices("product_name", "Product Name"))
    product_width: float = Field(
        alias=AliasChoices("product_width", "Width", "Width (mm)")
    )
    product_length: float = Field(
        alias=AliasChoices("product_length", "Length", "Length (mm)")
    )
    product_height: float = Field(
        alias=AliasChoices("product_height", "Height", "Height (mm)")
    )
    product_weight: float = Field(
        alias=AliasChoices("product_weight", "Weight", "Weight (kg)")
    )
    qty_per_box: Optional[int] = None
    weight_per_box: Optional[float] = None
    is_stack: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_stack", "Stack")
    )
    max_stack: Optional[int] = Field(
        default=None, alias=AliasChoices("max_stack", "Max Stack Layers")
    )
    stack_weight: Optional[float] = Field(
        default=None,
        alias=AliasChoices(
            "stack_weight",
            "Max Stack Weight",
            "Max Stack Weight (kg)",
        ),
    )
    is_fragile: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_fragile", "Fragile")
    )
    is_side_up: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_side_up", "Side up")
    )
    is_on_top: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_on_top", "Always on top")
    )
    color: Optional[str] = "#000000"
    created_by: Optional[str] = "system"
    created_date: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_date: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    deleted_date: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True
        coerce_numbers_to_str = True


class ProductCreate(ProductBase, BaseModel):
    product_id: Optional[int] = None

    class Config:
        str_strip_whitespace = True


@partial_model
class ProductUpdate(ProductCreate, BaseModel):
    pass


class ProductAvaliable(ProductBase):
    used_count: Optional[int] = None
    available_qty: Optional[int] = None


class ProductsResponse(BaseModel):
    items: list[ProductBase]
    total_count: int


class PackageBase(BaseModel):
    package_id: int
    package_name: str = Field(alias=AliasChoices("package_name", "Package Name"))
    package_code: str = Field(alias=AliasChoices("package_code", "Package Code"))
    package_type: models.PackageType

    package_width: float = Field(
        alias=AliasChoices("package_width", "Width", "Width (mm)")
    )
    package_height: float = Field(
        alias=AliasChoices("package_height", "Height", "Height (mm)")
    )
    package_length: float = Field(
        alias=AliasChoices("package_length", "Length", "Length (mm)")
    )
    package_weight: float = Field(
        alias=AliasChoices("package_weight", "Weight", "Weight (kg)")
    )
    load_width: float = Field(
        alias=AliasChoices("load_width", "Load Width", "Load Width (mm)")
    )
    load_height: float = Field(
        alias=AliasChoices("load_height", "Load Height", "Load Height (mm)")
    )
    load_length: float = Field(
        alias=AliasChoices("load_length", "Load Length", "Load Length (mm)")
    )
    load_weight: float = Field(
        alias=AliasChoices("load_weight", "Load Weight", "Load Weight (kg)")
    )
    package_size: str = Field(
        default="Custom", alias=AliasChoices("package_size", "Container Size")
    )
    created_by: Optional[str] = "system"
    created_date: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_date: Optional[datetime] = None
    color: Optional[str] = "#000000"
    is_deleted: Optional[bool] = False
    deleted_date: Optional[datetime] = None

    door_position: Optional[models.DoorPosition] = Field(
        default=None, alias=AliasChoices("door_position", "Door position")
    )
    have_partition: Optional[bool] = None
    have_stackable: Optional[bool] = None
    number_of_stack: Optional[int] = None

    is_fragile: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_fragile", "Fragile")
    )
    is_side_up: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_side_up", "Side up")
    )
    is_on_top: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_on_top", "Always on top")
    )
    is_stack: Optional[bool] = Field(
        default=False, alias=AliasChoices("is_stack", "Do not stack")
    )
    max_stack: Optional[int] = Field(
        default=None, alias=AliasChoices("max_stack", "Max Stack Layers")
    )
    stack_weight: Optional[float] = Field(
        default=None,
        alias=AliasChoices(
            "stack_weight",
            "Max Stack Weight",
            "Max Stack Weight (kg)",
        ),
    )

    class Config:
        from_attributes = True
        populate_by_name = True
        coerce_numbers_to_str = True


class PackageAvaliable(PackageBase, BaseModel):
    used_count: Optional[int] = None
    available_qty: Optional[int] = None


class PackageCreate(PackageBase, BaseModel):
    package_id: ClassVar[None] = None

    class Config:
        str_strip_whitespace = True


@partial_model
class PackageUpdate(PackageBase, BaseModel):
    pass


class PackageResponse(BaseModel):
    items: list[PackageAvaliable]
    total_count: int


# ----ShipContainer-----
class ShipContainerBase(PackageBase, BaseModel):
    package_type: Literal[models.PackageType.container] = models.PackageType.container
    door_position: models.DoorPosition = Field(
        default=models.DoorPosition.front,
        alias=AliasChoices("door_position", "Door position"),
    )
    is_fragile: ClassVar[None] = None
    is_side_up: ClassVar[None] = None
    is_on_top: ClassVar[None] = None
    is_stack: ClassVar[None] = None
    max_stack: ClassVar[None] = None
    stack_weight: ClassVar[None] = None


class ShipContainerAvaliable(ShipContainerBase, BaseModel):
    used_count: Optional[int] = None
    available_qty: Optional[int] = None


class ShipContainerCreate(ShipContainerBase, BaseModel):
    package_id: ClassVar[None] = None

    class Config:
        str_strip_whitespace = True


@partial_model
class ShipContainerUpdate(ShipContainerBase, BaseModel):
    pass


# ----Carton-----
class CartonBase(PackageBase, BaseModel):
    package_type: Literal[models.PackageType.carton] = models.PackageType.carton

    package_code: str = Field(
        alias=AliasChoices("package_code", "cartoncode", "Carton Code")
    )
    package_name: str = Field(
        alias=AliasChoices("package_name", "cartonname", "Carton Name")
    )
    package_width: float = Field(
        alias=AliasChoices("package_width", "cartonwidth", "Width", "Width (mm)")
    )
    package_height: float = Field(
        alias=AliasChoices("package_height", "cartonheight", "Height", "Height (mm)")
    )
    package_length: float = Field(
        alias=AliasChoices("package_length", "cartonlength", "Length", "Length (mm)")
    )
    package_weight: float = Field(
        alias=AliasChoices("package_weight", "cartonweight", "Weight", "Weight (kg)")
    )
    door_position: ClassVar[None] = None
    have_partition: ClassVar[None] = None
    have_stackable: ClassVar[None] = None
    number_of_stack: ClassVar[None] = None


class CartonAvaliable(CartonBase, BaseModel):
    used_count: Optional[int] = None
    available_qty: Optional[int] = None


class CartonCreate(CartonBase, BaseModel):
    package_id: ClassVar[None] = None

    class Config:
        str_strip_whitespace = True


@partial_model
class CartonUpdate(CartonBase, BaseModel):
    pass


# ----Pallet-----
class PalletBase(PackageBase, BaseModel):
    package_code: str = Field(
        alias=AliasChoices("package_code", "palletcode", "Pallet Code")
    )
    package_name: str = Field(
        alias=AliasChoices("package_name", "palletname", "Pallet Name")
    )
    package_width: float = Field(
        alias=AliasChoices("package_width", "palletwidth", "Width", "Width (mm)")
    )
    package_height: float = Field(
        alias=AliasChoices("package_height", "palletheight", "Height", "Height (mm)")
    )
    package_length: float = Field(
        alias=AliasChoices("package_length", "palletlength", "Length", "Length (mm)")
    )
    package_weight: float = Field(
        alias=AliasChoices("package_weight", "palletweight", "Weight", "Weight (kg)")
    )
    package_size: str = Field(
        default="Custom",
        alias=AliasChoices("package_size", "palletsize", "Pallet Size"),
    )

    door_position: ClassVar[None] = None
    have_partition: ClassVar[None] = None
    have_stackable: ClassVar[None] = None
    number_of_stack: ClassVar[None] = None

    is_fragile: ClassVar[None] = None
    is_side_up: ClassVar[None] = None
    is_on_top: ClassVar[None] = None
    is_stack: ClassVar[None] = None
    max_stack: ClassVar[None] = None
    stack_weight: ClassVar[None] = None


class PalletAvaliable(PalletBase, BaseModel):
    used_count: Optional[int] = None
    available_qty: Optional[int] = None


class PalletCreate(PalletBase, BaseModel):
    package_id: ClassVar[None] = None

    class Config:
        str_strip_whitespace = True


@partial_model
class PalletUpdate(PalletBase, BaseModel):
    pass


# --------------------------------------
class OrderListCreate(ProductUpdate, BaseModel):
    color: Optional[str] = "#000000"
    pickup_priority: float = Field(default=1, alias=AliasChoices("pickup_priority", "Priority"))


class OrderCreate(BaseModel):
    orders_name: str = Field(alias=AliasChoices("orders_name", "Order Name"))
    orders_number: str = Field(alias=AliasChoices("orders_number", "Order No."))
    plan_send_date: datetime = Field(alias=AliasChoices("plan_send_date", "Send Date"))
    deliveryby: str = Field(
        default="deliveryUser", alias=AliasChoices("deliveryby", "Delivery by")
    )
    created_by: str = Field(default="system", alias="created_by")
    products: list[OrderListCreate]

    class Config:
        str_strip_whitespace = True


class OrderExcel(BaseModel):
    orders_name: str = Field(alias=AliasChoices("orders_name", "Order Name"))
    orders_number: str = Field(alias=AliasChoices("orders_number", "Order No."))
    plan_send_date: datetime = Field(alias=AliasChoices("plan_send_date", "Send Date"))
    deliveryby: str = Field(
        default="deliveryUser", alias=AliasChoices("deliveryby", "Delivery by")
    )
    pickup_priority: float = Field(default=1, alias=AliasChoices("pickup_priority", "Priority"))
    product_code: Optional[str] = Field(
        default=None, alias=AliasChoices("product_code", "Product Code")
    )
    created_by: str = Field(default="system", alias="created_by")
    qty: int = Field(default=1, alias=AliasChoices("qty", "Qty"))

    class Config:
        str_strip_whitespace = True


class OrderRead(BaseModel):
    orders_id: Union[int, str]
    orders_number: Optional[str] = None
    orders_name: str
    created_by: str
    deliveryby: str
    plan_send_date: datetime
    created_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None  # ตั้งค่าเริ่มต้นเป็น None
    products: Optional[list[OrderListCreate]] = None  # ใช้ Schema ใหม่

    class Config:
        from_attributes = True


class OrderUpdate(BaseModel):
    orders_number: Optional[str] = None
    orders_name: Optional[str] = None
    plan_send_date: Optional[datetime] = None
    deleted_products: Optional[list[int]] = None  # ฟิลด์ใหม่สำหรับรายการสินค้าที่ถูกลบ
    new_products: Optional[list[OrderListCreate]] = None  # เพิ่มฟิลด์นี้
    existing_products: Optional[list[OrderListCreate]] = None  # เพิ่มสินค้าที่มีอยู่แล้ว

    class Config:
        str_strip_whitespace = True
        from_attributes = True


class OrdersResponse(BaseModel):
    items: list[OrderRead]
    total_count: int


class ModelProduct(BaseModel):
    orders_id: int
    product_id: int
    product_code: str
    product_name: str
    product_length: float
    product_width: float
    product_height: float
    product_weight: float
    color: str
    qty: int = 1
    is_stack: bool = False
    is_fragile: bool = False
    is_on_top: bool = False
    is_side_up: bool = False
    max_stack: int = -1
    stack_weight: float = -1
    pickup_priority: int = 1
    plan_send_date: str = ""


class ModelPallet(BaseModel):
    palletid: int
    palletname: str
    palletcode: str
    palletlength: float
    palletwidth: float
    palletheight: float
    palletweight: float
    load_length: float
    load_width: float
    load_height: float
    load_weight: float
    color: str
    qty: int = 1
    pickup_priority: int = 1


class ModelContainer(BaseModel):
    package_id: int
    package_name: str
    package_code: str
    package_length: float
    package_width: float
    package_height: float
    package_weight: float
    load_length: float
    load_width: float
    load_height: float
    load_weight: float
    color: str
    qty: int = 1
    pickup_priority: int = 1
    door_position: str = None


class SimbatchdetailBase(BaseModel):
    batchdetailid: Optional[int] = None
    batchid: Optional[int] = None
    simulate_id: Optional[int] = None
    orders_id: Optional[int] = None
    mastertype: Literal["sim_batch", "product"]
    masterid: Optional[int] = None
    x: float
    y: float
    z: float
    rotation: Optional[int] = 0

    class Config:
        from_attributes = True


class SimbatchBase(BaseModel):
    batchid: Optional[int] = None
    simulate_id: Optional[int] = None
    batchtype: Literal["pallet", "container", "palletoncontainer"]
    batchmasterid: Optional[int] = None
    total_weight: Optional[float] = 0
    total_volume: Optional[float] = 0
    details: list[SimbatchdetailBase]

    class Config:
        from_attributes = True


class SimulateBase(BaseModel):
    simulate_id: Optional[int]
    simulatetype: Optional[str]
    simulate_status: Optional[models.Status]
    pdf_status: Optional[models.Status]
    simulate_by: Optional[str]
    start_datetime: Optional[datetime]
    snapshot_data: Optional[str]
    batches: Optional[list[SimbatchBase]]
    task_id: Optional[str]
    pdf_task_id: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class SimDetail(SimbatchdetailBase, BaseModel):
    mastertype: Literal["product", "sim_batch"] = "product"
    masterid: Optional[int] = Field(
        alias=AliasChoices("masterid", "batchmasterid", "product_id")
    )
    name: str = Field(
        alias=AliasChoices("name", "product_name"),
        default_factory=lambda data: f"Sim Batch {data.get('batchid')}",
    )
    code: Optional[str] = Field(alias=AliasChoices("code", "product_code"))
    color: str
    length: float = Field(alias=AliasChoices("length", "product_length"))
    width: float = Field(alias=AliasChoices("width", "product_width"))
    height: float = Field(alias=AliasChoices("height", "product_height"))
    weight: float = Field(alias=AliasChoices("weight", "product_weight"))
    load_length: Optional[float] = None
    load_width: Optional[float] = None
    load_height: Optional[float] = None
    max_stack: Optional[int] = None
    is_fragile: Optional[bool] = None
    is_on_top: Optional[bool] = None
    is_stack: Optional[bool] = None
    is_side_up: Optional[bool] = None
    batchtype: Optional[str] = None
    orders: Optional[list["SimOrder"]] = None

    model_config = ConfigDict(extra="allow")


class SimOrder(BaseModel):
    orders_id: int
    orders_name: str = Field(
        default_factory=lambda data: f"Order {data.get('orders_id')}",
    )
    orders_number: str = Field(
        default_factory=lambda data: f"ORD-{data.get('orders_id')}",
    )
    products: list[SimDetail]


class SimBatch(SimbatchBase, BaseModel):
    batchname: str
    name: str = Field(alias=AliasChoices("name", "palletname", "package_name"))
    code: str = Field(alias=AliasChoices("code", "palletcode", "package_code"))
    length: float = Field(
        alias=AliasChoices("length", "palletlength", "package_length")
    )
    width: float = Field(alias=AliasChoices("width", "palletwidth", "package_width"))
    height: float = Field(
        alias=AliasChoices("height", "palletheight", "package_height")
    )
    weight: float = Field(
        alias=AliasChoices("weight", "palletweight", "package_weight")
    )
    load_length: float
    load_width: float
    load_height: float
    load_weight: float
    color: str
    door_position: Optional[str] = None
    details: list[SimOrder | SimDetail]
    masterid: Optional[int] = Field(alias=AliasChoices("masterid", "batchmasterid"))

    model_config = ConfigDict(extra="allow")


class SimulationRequest(BaseModel):
    orders: list[OrderRead]
    pallets: Optional[list[PalletAvaliable]] = None
    containers: Optional[list[PackageAvaliable]] = None
    simulatetype: Literal["pallet", "container", "pallet_container"]


class SimulationPayload(BaseModel):
    orders: list[OrderRead]
    products: list[ModelProduct]
    pallets: Optional[list[ModelPallet]] = None
    containers: Optional[list[ModelContainer]] = None


class SimulationGetResponse(BaseModel):
    data: Optional[list[SimBatch]] = None
    error: Optional[str] = None
    simulate_by: str
    start_datetime: datetime
    simulatetype: str
    simulate_status: str


class SimulationPayloadDict(TypedDict):
    orders: list[OrderRead]
    products: list[ModelProduct]
    pallets: Optional[list[ModelPallet]]
    containers: Optional[list[ModelContainer]]


class drawObj(BaseModel):
    mastertype: Literal["product", "sim_batch", "pallet", "container"] = "product"
    x: float
    z: float
    y: float
    length: float
    width: float
    height: float
    load_length: Optional[float] = None
    load_width: Optional[float] = None
    load_height: Optional[float] = None
    rotation: Optional[int] = 0
    color: str
    clipping: Optional[list["drawObj"]] = []

    model_config = ConfigDict(extra="allow")

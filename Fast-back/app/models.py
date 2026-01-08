from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "tbm_product"

    product_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_code: Mapped[str]
    product_name: Mapped[str]
    product_width: Mapped[float]
    product_length: Mapped[float]
    product_height: Mapped[float]
    product_weight: Mapped[float]

    qty_per_box: Mapped[Optional[int]]
    weight_per_box: Mapped[Optional[float]]

    is_stack: Mapped[bool] = mapped_column(default=False)
    max_stack: Mapped[Optional[int]]
    stack_weight: Mapped[Optional[float]]

    is_fragile: Mapped[bool] = mapped_column(default=False)
    is_side_up: Mapped[bool] = mapped_column(default=False)
    is_on_top: Mapped[bool] = mapped_column(default=False)

    color: Mapped[str] = mapped_column(String(7), default="#000000")
    created_by: Mapped[Optional[str]]
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[Optional[str]]
    updated_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ux_products_productcode_active",
            "product_code",
            "product_name",
            unique=True,
            postgresql_where=(is_deleted == False),
        ),
    )


class PackageType(str, enum.Enum):
    pallet = "pallet"
    carton = "carton"
    container = "container"


class DoorPosition(str, enum.Enum):
    front = "front"
    side = "side"
    top = "top"


class PackageBase(Base):
    __tablename__ = "tbm_package"

    package_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_name: Mapped[str]
    package_code: Mapped[str]
    package_type: Mapped[str] = mapped_column(default=PackageType.container)

    door_position: Mapped[Optional[str]] = mapped_column(default=DoorPosition.front)
    have_partition: Mapped[Optional[bool]] = mapped_column(default=False)
    have_stackable: Mapped[Optional[bool]] = mapped_column(default=False)
    number_of_stack: Mapped[Optional[int]] = mapped_column(default=0)

    package_size: Mapped[Optional[str]]
    package_width: Mapped[float]
    package_length: Mapped[float]
    package_height: Mapped[float]
    package_weight: Mapped[float]
    load_width: Mapped[float]
    load_length: Mapped[float]
    load_height: Mapped[float]
    load_weight: Mapped[float]

    is_stack: Mapped[Optional[bool]] = mapped_column(default=False)
    max_stack: Mapped[Optional[int]]
    stack_weight: Mapped[Optional[float]]

    is_fragile: Mapped[Optional[bool]] = mapped_column(default=False)
    is_side_up: Mapped[Optional[bool]] = mapped_column(default=False)
    is_on_top: Mapped[Optional[bool]] = mapped_column(default=False)

    color: Mapped[str] = mapped_column(String(7), default="#000000")
    created_by: Mapped[Optional[str]]
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[Optional[str]]
    updated_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ux_container_containercode_active",
            "package_type",
            "package_code",
            "package_name",
            unique=True,
            postgresql_where=(is_deleted == False),
        ),
    )


class Order(Base):
    __tablename__ = "tb_orders"

    orders_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    orders_number: Mapped[str]
    orders_name: Mapped[str]
    plan_send_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actual_send_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[Optional[str]]
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[Optional[str]]
    updated_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    orders_detail: Mapped[List["OrdersDetail"]] = relationship(
        "OrdersDetail",
        primaryjoin="and_(Order.orders_id==OrdersDetail.orders_id, OrdersDetail.is_deleted==False)",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    simulate_products: Mapped[List["SimulateProduct"]] = relationship(
        "SimulateProduct",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        Index(
            "ux_orders_ordernumber_active",
            "orders_number",
            unique=True,
            postgresql_where=(is_deleted == False),
        ),
    )


class OrdersDetail(Base):
    __tablename__ = "tb_orders_detail"
    orders_detail_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    orders_id: Mapped[int] = mapped_column(ForeignKey("tb_orders.orders_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("tbm_product.product_id"))
    qty: Mapped[int]
    pickup_priority: Mapped[int] = mapped_column(default=1)
    dropoff_priority: Mapped[int] = mapped_column(default=1)

    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order: Mapped["Order"] = relationship(
        "Order",
        primaryjoin="and_(Order.orders_id==OrdersDetail.orders_id, Order.is_deleted==False)",
        back_populates="orders_detail",
    )
    product: Mapped[Product] = relationship(
        "Product",
        primaryjoin="and_(Product.product_id==OrdersDetail.product_id, Product.is_deleted==False)",
        lazy="joined",
    )


class Status(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class Simulate(Base):
    __tablename__ = "tb_simulate"

    simulate_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    simulate_status: Mapped[Status] = mapped_column(
        ENUM(Status, name="status_enum_type")
    )
    simulate_by: Mapped[str]
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    snapshot_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    pdf_status: Mapped[Optional[Status]] = mapped_column(
        ENUM(Status, name="status_enum_type")
    )
    task_id: Mapped[Optional[str]]
    error_message: Mapped[Optional[str]]
    pdf_task_id: Mapped[Optional[str]]
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    simulate_details: Mapped[List["Simulatedetail"]] = relationship(
        back_populates="simulate", cascade="all, delete-orphan"
    )
    simulate_containments: Mapped[List["SimulateContainment"]] = relationship(
        back_populates="simulate", cascade="all, delete-orphan"
    )
    simulate_products: Mapped[List["SimulateProduct"]] = relationship(
        back_populates="simulate", cascade="all, delete-orphan"
    )


class Simulatedetail(Base):
    __tablename__ = "tb_simulate_detail"

    simulate_detail_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    simulate_id: Mapped[int] = mapped_column(ForeignKey("tb_simulate.simulate_id"))
    package_id: Mapped[int] = mapped_column(ForeignKey("tbm_package.package_id"))
    package_name: Mapped[str]
    package_type: Mapped[str]
    door_position: Mapped[str]
    have_partition: Mapped[Optional[bool]] = mapped_column(default=False)
    have_stackable: Mapped[Optional[bool]] = mapped_column(default=False)
    number_of_stack: Mapped[Optional[int]] = mapped_column(default=0)

    package_width: Mapped[float]
    package_length: Mapped[float]
    package_height: Mapped[float]
    package_weight: Mapped[float]
    load_width: Mapped[float]
    load_length: Mapped[float]
    load_height: Mapped[float]
    load_weight: Mapped[float]

    color: Mapped[str] = mapped_column(String(7), default="#000000")

    rotation: Mapped[Integer] = mapped_column(Integer)
    position_x: Mapped[float]
    position_y: Mapped[float]
    position_z: Mapped[float]

    utilize_weight: Mapped[float]
    utilize_weight_percent: Mapped[float]
    utilize_capacity: Mapped[float]
    utilize_cap_percent: Mapped[float]

    simulate: Mapped["Simulate"] = relationship(back_populates="simulate_details")

    containments_as_parent: Mapped[List["SimulateContainment"]] = relationship(
        back_populates="parent_detail",
        foreign_keys="[SimulateContainment.parent_package_id]",
        cascade="all, delete-orphan",
    )
    containment_as_child: Mapped[Optional["SimulateContainment"]] = relationship(
        back_populates="child_detail",
        foreign_keys="[SimulateContainment.child_package_id]",
    )
    products: Mapped[List["SimulateProduct"]] = relationship(back_populates="simulate_detail")
    # order: Mapped["Order"] = relationship(
    #     primaryjoin="and_(Order.orders_id==Simulatedetail.orders_id, Order.is_deleted==False)",
    #     back_populates="simulatedetails",
    # )


class SimulateContainment(Base):
    __tablename__ = "tb_simulate_containment"

    containment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    simulate_id: Mapped[int] = mapped_column(ForeignKey("tb_simulate.simulate_id"))
    parent_package_id: Mapped[int] = mapped_column(
        ForeignKey("tb_simulate_detail.simulate_detail_id")
    )
    child_package_id: Mapped[int] = mapped_column(
        ForeignKey("tb_simulate_detail.simulate_detail_id")
    )

    simulate: Mapped["Simulate"] = relationship(back_populates="simulate_containments")

    parent_detail: Mapped["Simulatedetail"] = relationship(
        back_populates="containments_as_parent",
        foreign_keys="[SimulateContainment.parent_package_id]",
    )
    child_detail: Mapped["Simulatedetail"] = relationship(
        back_populates="containment_as_child",
        foreign_keys="[SimulateContainment.child_package_id]",
    )


class SimulateProduct(Base):
    __tablename__ = "tb_simulate_product"

    simulate_product_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    simulate_id: Mapped[int] = mapped_column(ForeignKey("tb_simulate.simulate_id"))
    simulate_detail_id: Mapped[int] = mapped_column(
        ForeignKey("tb_simulate_detail.simulate_detail_id")
    )
    order_id: Mapped[int] = mapped_column(ForeignKey("tb_orders.orders_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("tbm_product.product_id"))

    rotation: Mapped[Integer] = mapped_column(Integer)
    position_x: Mapped[float]
    position_y: Mapped[float]
    position_z: Mapped[float]

    simulate: Mapped["Simulate"] = relationship(back_populates="simulate_products")
    simulate_detail: Mapped["Simulatedetail"] = relationship(back_populates="products")
    order: Mapped["Order"] = relationship(back_populates="simulate_products")
    product: Mapped["Product"] = relationship()


# class User(Base):
#     __tablename__ = "user"
#     userid = mapped_column(
#         Integer, primary_key=True, index=True, autoincrement=True, nullable=False
#     )

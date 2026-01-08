from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func, _typing
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, select, update
from psycopg2 import errors
from app import models, schemas, utils, factories
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, TypedDict


# ----Product-----
def read_products(db: Session, skip=0, limit: int = None) -> list[schemas.ProductBase]:
    results = db.scalars(
        select(models.Product)
        .filter(models.Product.is_deleted == False)
        .order_by(models.Product.product_id.asc())
        .offset(skip)
        .limit(limit)
    ).all()
    product_pydantic = [
        schemas.ProductBase.model_validate(product) for product in results
    ]

    # Format the response
    return product_pydantic


# def read_products_qty(
#     db: Session, skip=0, limit: int = None, skipOrderid: str = -1, filterqty=False
# ) -> list[schemas.ProductAvaliable]:
#     used_count_subquery = (
#         db.query(
#             models.OrdersDetail.product_id,
#             func.sum(models.OrdersDetail.qty).label("total"),
#         )
#         .filter(models.OrdersDetail.is_deleted == False)
#         .filter(models.OrdersDetail.orders_id != skipOrderid)
#         .group_by(models.OrdersDetail.product_id)
#         .subquery()
#     )

#     results: list[tuple[models.Product, int]] = (
#         db.query(
#             models.Product,
#             func.coalesce(used_count_subquery.c.total, 0).label("total"),
#         )
#         .outerjoin(
#             used_count_subquery,
#             models.Product.product_id == used_count_subquery.c.product_id,
#         )
#         .filter(models.Product.is_deleted == False)
#         .order_by(models.Product.product_id.asc())
#         .offset(skip)
#         .limit(limit)
#         .all()
#     )

#     # Format the response
#     response_data: list[schemas.ProductAvaliable] = []
#     for product, used_count in results:
#         available_qty = (product.qty or 0) - used_count
#         if filterqty and available_qty <= 0:
#             continue

#         product_pydantic = schemas.ProductBase.model_validate(product)

#         product_avaliable = schemas.ProductAvaliable(
#             **product_pydantic.model_dump(),
#             used_count=used_count,
#             available_qty=available_qty,
#         )
#         response_data.append(product_avaliable)
#     return response_data


def insert_product(db: Session, product: schemas.ProductCreate) -> models.Product:
    new_product = models.Product(
        **product.model_dump(exclude={"created_date", "color"}),
        created_date=datetime.now(timezone(timedelta(hours=7))),
        color=product.color or get_distinct_color(models.Product, db),
    )
    db.add(new_product)
    return new_product


def update_product(
    db: Session, product: schemas.ProductUpdate, product_id: int
) -> schemas.updateResponse:
    db.execute(
        update(models.Product)
        .where(models.Product.product_id == product_id)
        .values(
            **product.model_dump(exclude_unset=True),
            updated_date=datetime.now(timezone(timedelta(hours=7))),
            updated_by="system",
        )
    )

    # db_product = db.scalar(
    #     select(models.Product).filter(
    #         models.Product.is_deleted == False, models.Product.product_id == product_id
    #     )
    # )
    # if not db_product:
    #     raise HTTPException(status_code=404, detail="Product not found")

    # for key, value in product.model_dump(exclude_unset=True).items():
    #     # print(f"Updating {key} to {value}")
    #     setattr(db_product, key, value)

    # db_product.updated_date = datetime.now(timezone(timedelta(hours=7)))
    # db_product.updated_by = "system"
    db.commit()
    return {"message": "Product updated successfully"}


def delete_product(db: Session, product_id: str):
    try:
        product = (
            db.query(models.Product)
            .filter(models.Product.product_id == product_id)
            .first()
        )
        if not product:
            return None
        db.delete(product)
        db.commit()
        return product
    except Exception as e:
        return None


def soft_delete_product(db: Session, product_ids: list[int]) -> schemas.deleteResponse:
    db.execute(
        update(models.Product)
        .where(models.Product.product_id.in_(product_ids))
        .values(
            is_deleted=True, deleted_date=datetime.now(timezone(timedelta(hours=7)))
        )
    )
    db.commit()
    return {"message": "Product soft-deleted successfully"}


def restore_product(db: Session, product_id: str) -> schemas.restoreResponse:
    product: models.Product = (
        db.query(models.Product)
        .filter(
            models.Product.product_id == product_id, models.Product.is_deleted == True
        )
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=404, detail="Product not found or not soft-deleted"
        )

    product.is_deleted = False
    product.deleted_date = None
    product.created_date = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    db.refresh(product)
    return {"message": "Product restored successfully"}


# ------Packages--------
def read_packages(
    db: Session,
    packageType: models.PackageType,
    skip=0,
    limit: int = None,
) -> list[schemas.PackageBase]:
    factory = factories.PackageFactory.get_factory(packageType)
    results = db.scalars(
        select(models.PackageBase)
        .filter(models.PackageBase.is_deleted == False)
        .order_by(models.PackageBase.package_id.asc())
        .offset(skip)
        .limit(limit)
    ).all()
    package_pydantic = [factory.create_base(package.__dict__) for package in results]

    return package_pydantic


def insert_package(db: Session, package: schemas.PackageCreate) -> models.PackageBase:
    factory = factories.PackageFactory.get_factory(package.package_type)
    package = factory.create_create_model(package.model_dump())
    new_package = models.PackageBase(
        **package.model_dump(exclude={"created_date", "color"}),
        created_date=datetime.now(timezone(timedelta(hours=7))),
        color=package.color
        or get_distinct_color(models.PackageBase, db, package.package_type),
    )
    db.add(new_package)
    return new_package


def update_package(
    db: Session, package: schemas.PackageUpdate, package_id: int
) -> schemas.updateResponse:
    db.execute(
        update(models.PackageBase)
        .where(models.PackageBase.package_id == package_id)
        .values(
            **package.model_dump(exclude_unset=True),
            updated_date=datetime.now(timezone(timedelta(hours=7))),
            updated_by="system",
        )
    )
    db.commit()
    return {"message": "Package updated successfully"}


def soft_delete_packages(db: Session, package_ids: list[int]) -> schemas.deleteResponse:
    db.execute(
        update(models.PackageBase)
        .where(models.PackageBase.package_id.in_(package_ids))
        .values(
            is_deleted=True, deleted_date=datetime.now(timezone(timedelta(hours=7)))
        )
    )
    db.commit()
    return {"message": "package soft-deleted successfully"}


def restore_package(db: Session, package_id: str) -> schemas.restoreResponse:
    db_container: models.PackageBase = (
        db.query(models.PackageBase)
        .filter(models.PackageBase.package_id == package_id)
        .first()
    )
    if not db_container:
        raise HTTPException(status_code=404, detail="container not found")

    db_container.is_deleted = False
    db_container.deleted_date = None
    db_container.created_date = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    return {"message": "container restored successfully"}


# -------------------------------
def create_order_with_products(db: Session, order: schemas.OrderCreate):
    try:
        db_order = models.Order(**order.model_dump(exclude={"products"}))
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        order_items: list[models.OrdersDetail] = []
        # add products to order
        for product in order.products:
            db_product = (
                db.query(models.Product)
                .filter(
                    models.Product.is_deleted == False,
                    models.Product.product_id == product.product_id,
                )
                .first()
            )
            if not db_product:
                raise HTTPException(
                    status_code=404, detail=f"Product ID {product.product_id} not found"
                )

            # check deleted
            db_order_item: models.OrdersDetail = (
                db.query(models.OrdersDetail)
                .filter(
                    models.OrdersDetail.is_deleted == True,
                    models.OrdersDetail.orders_id == db_order.orders_id,
                    models.OrdersDetail.product_id == product.product_id,
                )
                .first()
            )

            if db_order_item:
                for key, value in product.model_dump(exclude_unset=True).items():
                    setattr(db_order_item, key, value)
                db_order_item.is_deleted = False
                db_order_item.deleted_date = None
            else:
                db_order_item = models.OrdersDetail(
                    orders_id=db_order.orders_id,
                    product_id=product.product_id,
                    qty=product.qty,
                    pickup_priority=product.pickup_priority,
                )
                db.add(db_order_item)
            order_items.append(
                schemas.OrderListCreate.model_validate(
                    {
                        **db_product.__dict__,
                        "product_id": db_order_item.product_id,
                        "qty": db_order_item.qty,
                        "pickup_priority": db_order_item.pickup_priority,
                    }
                )
            )
        db.commit()

        response = schemas.OrderRead.model_validate(db_order)
        response.products = order_items

        return response

    except SQLAlchemyError as e:
        print("Error during product creation:", e.orig)  # Debug Exception
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(status_code=500, detail="Order already exists.")
        raise HTTPException(
            status_code=500, detail="Error during order creation: " + str(e.orig)
        )


def get_orders(
    db: Session, skip: int = 0, limit: int = None
) -> list[schemas.OrderRead]:
    orders: list[models.Order] = (
        db.query(models.Order)
        .filter(models.Order.is_deleted == False)
        .options(
            joinedload(
                models.Order.items.and_(models.OrdersDetail.is_deleted == False)
            ).subqueryload(
                models.OrdersDetail.product.and_(models.Product.is_deleted == False)
            )
        )
        .order_by(models.Order.orders_id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for order in orders:
        order_dict = order.__dict__
        order_dict["products"] = [
            {
                **item.product.__dict__,
                "qty": item.qty,
                "pickup_priority": item.pickup_priority,
            }
            for item in order.items
            if item.product
        ]

        result.append(schemas.OrderRead.model_validate(order_dict))
    return result


def get_order_by_id(db: Session, order_id: int) -> schemas.OrderRead:
    order: models.Order = (
        db.query(models.Order)
        .filter(models.Order.orders_id == order_id, models.Order.is_deleted == False)
        .options(
            joinedload(
                models.Order.items.and_(models.OrdersDetail.is_deleted == False)
            ).subqueryload(
                models.OrdersDetail.product.and_(models.Product.is_deleted == False)
            )
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Return data with proper handling for `null` values
    return schemas.OrderRead.model_validate(
        {
            **order.__dict__,
            "products": [
                {
                    **item.product.__dict__,
                    "qty": item.qty,
                    "pickup_priority": item.pickup_priority,
                }
                for item in order.items
                if item.product
            ],
        }
    )


def soft_delete_order(db: Session, orders_id: str) -> schemas.deleteResponse:
    db_order: models.Order = (
        db.query(models.Order).filter(models.Order.orders_id == orders_id).first()
    )
    if not db_order:
        raise HTTPException(status_code=404, detail="order not found")

    db_order.is_deleted = True
    db_order.deleted_date = datetime.now(timezone(timedelta(hours=7)))

    db_order_list: list[models.OrdersDetail] = (
        db.query(models.OrdersDetail)
        .filter(
            models.OrdersDetail.orders_id == orders_id,
            models.OrdersDetail.is_deleted == False,
        )
        .all()
    )

    for product in db_order_list:
        product.is_deleted = True
        product.deleted_date = datetime.now(timezone(timedelta(hours=7)))

    db.commit()
    db.refresh(db_order)
    return {"message": "order soft-deleted successfully"}


def save_simulation_batches_internal(
    data: list[schemas.SimbatchBase], simulate_id: int, db: Session
):
    temp_batchid: Dict[str, models.Simbatch] = {}
    # sort so palletoncontainer is first
    data.sort(key=lambda x: 0 if x.batchtype == "palletoncontainer" else 1)

    for batch_data in data:
        if len(batch_data.details) <= 0:
            # skip empty batch
            continue

        #  create batch
        new_batch = models.Simbatch(
            simulate_id=simulate_id,
            batchtype=batch_data.batchtype,
            batchmasterid=batch_data.batchmasterid,
            total_weight=batch_data.total_weight,
        )
        db.add(new_batch)
        db.flush()

        if batch_data.batchtype == "palletoncontainer":
            temp_batchid[batch_data.batchid] = new_batch

        for detail in batch_data.details:
            mastertype = detail.mastertype
            if mastertype == "product":
                new_detail = models.Simbatchdetail(
                    batchid=new_batch.batchid,
                    simulate_id=simulate_id,
                    mastertype=mastertype,
                    masterid=detail.masterid,
                    x=detail.x,
                    y=detail.y,
                    z=detail.z,
                    rotation=detail.rotation,
                    orders_id=detail.orders_id,
                )
                db.add(new_detail)
            elif mastertype == "sim_batch":
                # pallet with products on it (pallet container)
                if not temp_batchid.get(detail.masterid):
                    raise Exception("temporary batchid not found")
                new_detail = models.Simbatchdetail(
                    batchid=new_batch.batchid,
                    simulate_id=simulate_id,
                    mastertype="sim_batch",
                    masterid=temp_batchid[detail.masterid].batchid,
                    x=detail.x,
                    y=detail.y,
                    z=detail.z,
                    rotation=detail.rotation,
                )
                db.add(new_detail)
    db.commit()
    return simulate_id


# def getProductInBatch(
#     orders_dict: Dict[str, schemas.SimOrder],
#     simbatch: schemas.SimBatch,
#     detail: models.Simbatchdetail,
#     db: Session | None = None,
#     snapshot: utils.reformated_snapshot = None,
# ):
#     productMaster = (
#         snapshot.get("products", {}).get(str(detail.masterid)) if snapshot else None
#     )
#     if not productMaster:
#         if not db:
#             raise Exception(f"master for product with id {detail.masterid} not found.")
#         product_entry = (
#             db.query(models.Product)
#             .filter(
#                 models.Product.is_deleted == False,
#                 models.Product.product_id == detail.masterid,
#             )
#             .first()
#         )
#         productMaster = (
#             schemas.ProductBase.model_validate(product_entry) if product_entry else None
#         )

#     if not productMaster:
#         raise HTTPException(
#             status_code=500,
#             detail=f"product master with id {detail.masterid} not found",
#         )

#     # position = json.loads(detail.position) if detail.position else [0, 0, 0]
#     product = schemas.SimDetail(
#         mastertype="product",
#         batchdetailid=detail.batchdetailid,
#         x=detail.x,
#         y=detail.y,
#         z=detail.z,
#         rotation=(detail.rotation if detail.rotation is not None else 0),
#         **productMaster.model_dump(exclude={"qty"}),
#     )

#     if detail.orders_id not in orders_dict:
#         orderMaster = (
#             snapshot.get("orders").get(str(detail.orders_id)) if snapshot else None
#         )
#         if not orderMaster:
#             if not db:
#                 print(snapshot)
#                 raise Exception(
#                     f"master for order with id {detail.masterid} not found."
#                 )
#             order_entry: models.Order = (
#                 db.query(models.Order)
#                 .filter(models.Order.orders_id == detail.orders_id)
#                 .first()
#             )
#             orderMaster = (
#                 schemas.OrderRead.model_validate(order_entry) if order_entry else None
#             )

#         orders_dict[detail.orders_id] = schemas.SimOrder(
#             products=[], **orderMaster.model_dump(exclude={"products"})
#         )

#     orders_dict[detail.orders_id].products.append(product)
#     simbatch.total_volume += product.length * product.width * product.height
#     return orders_dict


# def convert_simulation_format(
#     data: list[schemas.SimbatchBase],
#     snapshot: utils.reformated_snapshot | None,
#     db: Session | None = None,
# ) -> list[schemas.SimBatch]:
#     data.sort(key=lambda x: 0 if x.batchtype == "palletoncontainer" else 1)

#     # pallet on container simbatch with id as key
#     palletContainerSimbatchs: Dict[str, schemas.SimBatch] = {}
#     response_data: list[schemas.SimBatch] = []

#     for batch in data:

#         batch_master_type = (
#             "containers" if batch.batchtype == "container" else "pallets"
#         )
#         master: schemas.ModelPallet | schemas.ModelContainer | None = (
#             snapshot.get(batch_master_type, {}).get(f"{batch.batchmasterid}")
#             if snapshot
#             else None
#         )

#         if not master:
#             if not db:
#                 raise Exception(
#                     f"master for {batch.batchtype} not found for id {batch.batchmasterid}."
#                 )
#             if batch.batchtype == "container":
#                 master_entry: models.Container = (
#                     db.query(models.Container)
#                     .filter(
#                         models.Container.is_deleted == False,
#                         models.Container.package_id == batch.batchmasterid,
#                     )
#                     .first()
#                 )
#                 master = (
#                     schemas.PackageBase.model_validate(master_entry)
#                     if master_entry
#                     else None
#                 )
#             else:
#                 master_entry: models.Pallet = (
#                     db.query(models.Pallet)
#                     .filter(
#                         models.Pallet.is_deleted == False,
#                         models.Pallet.palletid == batch.batchmasterid,
#                     )
#                     .first()
#                 )
#                 master = (
#                     schemas.PalletBase.model_validate(master_entry)
#                     if master_entry
#                     else None
#                 )

#         if not master:
#             raise HTTPException(status_code=500, detail="master not found")

#         batch_response = schemas.SimBatch(
#             batchname=f"Batch {batch.batchid}",
#             **batch.model_dump(exclude={"details"}),
#             **master.model_dump(exclude={"qty"}),
#             details=[],
#         )

#         # orders found in each batch
#         orders_dict = {}

#         # pallet found in each batch
#         pallet_list = []

#         for detail in batch.details:
#             if detail.mastertype == "product":
#                 orders_dict = getProductInBatch(
#                     orders_dict, batch_response, detail, db, snapshot
#                 )

#             elif detail.mastertype == "sim_batch":
#                 foundSimbatch: schemas.SimBatch | None = palletContainerSimbatchs.get(
#                     detail.masterid
#                 )
#                 if not foundSimbatch:
#                     raise Exception(
#                         f"batchid {detail.masterid} not found for pallet on container"
#                     )

#                 simpallet = schemas.SimDetail(
#                     **foundSimbatch.model_dump(),
#                     **detail.model_dump(exclude={"batchid", "simulate_id", "masterid"}),
#                     orders=foundSimbatch.details,
#                 )

#                 pallet_list.append(simpallet)
#                 batch_response.total_volume += (
#                     simpallet.length * simpallet.width * simpallet.height
#                 ) + foundSimbatch.total_volume
#         batch_response.details.extend(list(orders_dict.values()))

#         batch_response.details.extend(pallet_list)

#         if batch.batchtype == "palletoncontainer":
#             palletContainerSimbatchs[batch.batchid] = batch_response
#             continue

#         response_data.append(batch_response)
#     return response_data


# def prepare_simulation_payload(
#     payload: schemas.SimulationRequest, db: Session | None = None
# ) -> schemas.SimulationPayload:
#     simulation_payload = schemas.SimulationPayload(
#         orders=payload.orders, products=utils.convert_modelproduct(payload.orders)
#     )
#     match payload.simulatetype:
#         case "pallet":
#             if not payload.pallets:
#                 if not db:
#                     raise Exception("pallets not found for pallet simluation.")
#                 payload.pallets = read_pallets(db, filterqty=True)
#             simulation_payload.pallets = utils.convert_modelpallet(payload.pallets)
#         case "container":
#             if not payload.containers:
#                 if not db:
#                     raise Exception("containers not found for container simluation.")
#                 payload.containers = read_packages(db, filterqty=True)
#             simulation_payload.containers = utils.convert_modelcontainer(
#                 payload.containers
#             )
#         case "pallet_container":
#             if not payload.pallets:
#                 if not db:
#                     raise Exception(
#                         "pallets not found for pallet container simluation."
#                     )
#                 payload.pallets = read_pallets(db, filterqty=True)
#             if not payload.containers:
#                 if not db:
#                     raise Exception(
#                         "containers not found for pallet container simluation."
#                     )
#                 payload.containers = read_packages(db, filterqty=True)
#             simulation_payload.pallets = utils.convert_modelpallet(payload.pallets)
#             simulation_payload.containers = utils.convert_modelcontainer(
#                 payload.containers
#             )
#         case _:
#             raise HTTPException(status_code=400, detail="simulation type not found.")
#     return simulation_payload


def get_distinct_color(
    table: models.Product | models.PackageBase,
    db: Session,
    excludes: list[str] = [],
    packageType: models.PackageType = None,
) -> str:
    colors: list[str] = []
    if packageType:
        colors = db.scalars(
            select(table.color).filter(
                table.is_deleted == False, table.package_type == packageType
            )
        ).all()
    else:
        colors = db.scalars(select(table.color).filter(table.is_deleted == False)).all()
    colors.extend(excludes)
    colors.extend(["#000000", "#ffffff"])

    return utils.new_color(colors)

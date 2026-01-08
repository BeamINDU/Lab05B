import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from ..database import get_db
from sqlalchemy.orm import Session
from .. import models, schemas, crud
from datetime import datetime, timedelta, timezone
import pandas as pd

router = APIRouter(tags=["Orders"])


@router.post("/", response_model=schemas.OrderRead)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    try:
        response = crud.create_order_with_products(db, order)
        return response
    except HTTPException as e:
        db.rollback()
        print(e.detail)
        raise e
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


@router.get("/", response_model=schemas.OrdersResponse)
def read_orders(skip: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    try:
        orders = crud.get_orders(db, skip=skip, limit=limit)
        total_count = (
            db.query(models.Order).filter(models.Order.is_deleted == False).count()
        )
        return {"items": orders, "total_count": total_count}
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


@router.get("/{orders_id}", response_model=schemas.OrderRead)
def read_order(orders_id: str, db: Session = Depends(get_db)):
    try:
        # ลองแปลง `orders_id` เป็น `int`
        order_id = int(orders_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid order ID format"
        )  # แจ้งข้อผิดพลาดหากแปลงไม่ได้

    # เรียกใช้ฟังก์ชัน `get_order_by_id` ใน `crud.py`
    order = crud.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@router.put("/{orders_id}")
async def update_order(
    orders_id: str, order: schemas.OrderUpdate, db: Session = Depends(get_db)
):
    try:
        # ตรวจสอบคำสั่งซื้อ
        db_order: models.Order = (
            db.query(models.Order)
            .filter(models.Order.orders_id == orders_id, models.Order.is_deleted == False)
            .first()
        )
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")

        # อัปเดต Order Name และ Send Date
        if order.orders_number:
            db_order.orders_number = order.orders_number
        if order.orders_name:
            db_order.orders_name = order.orders_name
        if order.plan_send_date:
            db_order.plan_send_date = order.plan_send_date

        # ลบสินค้าที่อยู่ใน deleted_products
        if order.deleted_products:
            for deleted_item in order.deleted_products:
                try:
                    product_id = int(deleted_item)

                    product: models.OrdersDetail = (
                        db.query(models.OrdersDetail)
                        .filter(
                            models.OrdersDetail.orders_id == orders_id,
                            models.OrdersDetail.product_id == product_id,
                            models.OrdersDetail.is_deleted == False,
                        )
                        .first()
                    )

                    if not product:
                        # product not found
                        continue

                    product.is_deleted = True
                    product.deleted_date = datetime.now(timezone(timedelta(hours=7)))
                    # db.delete(product)

                except Exception as e:
                    print(f"Error processing deleted_products: {e}")

        # อัปเดตสินค้าที่มีอยู่แล้ว
        if order.existing_products:
            for product_data in order.existing_products:
                db_product: models.OrdersDetail = (
                    db.query(models.OrdersDetail)
                    .filter(
                        models.OrdersDetail.orders_id == orders_id,
                        models.OrdersDetail.product_id == product_data.product_id,
                        models.OrdersDetail.is_deleted == False,
                    )
                    .first()
                )

                if db_product:
                    # อัปเดตสินค้าเดิม
                    db_product.qty = product_data.qty
                    db_product.pickup_priority = product_data.pickup_priority

        # เพิ่มสินค้าใหม่
        if order.new_products:
            for product_data in order.new_products:
                # check deleted
                new_product: models.OrdersDetail = (
                    db.query(models.OrdersDetail)
                    .filter(
                        models.OrdersDetail.is_deleted == True,
                        models.OrdersDetail.orders_id == db_order.orders_id,
                        models.OrdersDetail.product_id == product_data.product_id,
                    )
                    .first()
                )

                if new_product:
                    for key, value in product_data.dict(exclude_unset=True).items():
                        setattr(new_product, key, value)
                    new_product.is_deleted = False
                    new_product.deleted_date = None
                else:
                    new_product = models.OrdersDetail(
                        orders_id=orders_id,
                        product_id=product_data.product_id,
                        qty=product_data.qty,
                        pickup_priority=product_data.pickup_priority,
                    )
                    db.add(new_product)

        db_order.updated_date = datetime.now(timezone(timedelta(hours=7)))

        db.commit()
        db.refresh(db_order)
        return db_order
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


@router.delete("/{orders_id}", response_model=schemas.deleteResponse)
def delete_order(orders_id: str, db: Session = Depends(get_db)):
    try:
        return crud.soft_delete_order(db, orders_id)
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


@router.post("/upload/")
async def upload_orders(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        df = pd.read_excel(file.file)

        df_replaced = df.replace({np.nan: None})

        orders_data = df_replaced.to_dict(orient="records")

        new_orders: set = set()

        for order_excel in orders_data:
            order_excel_data = schemas.OrderExcel(**order_excel)

            db_product = (
                db.query(models.Product)
                .filter(
                    models.Product.is_deleted == False,
                    models.Product.product_code == order_excel_data.product_code,
                )
                .first()
            )
            if not db_product:
                raise Exception(
                    f"Product Code {order_excel_data.product_code} not found"
                )

            order: models.Order = (
                db.query(models.Order)
                .filter(
                    models.Order.is_deleted == False,
                    models.Order.orders_number == order_excel_data.orders_number,
                )
                .first()
            )
            if order_excel_data.orders_number not in new_orders and order:
                print(new_orders)
                raise Exception(
                    f"Order Number {order_excel_data.orders_number} already exists."
                )

            if order:
                for key, value in order_excel_data.model_dump(
                    exclude_unset=True
                ).items():
                    setattr(order, key, value)

                order.created_date = datetime.now(timezone(timedelta(hours=7)))
                order.is_deleted = False
                order.deleted_date = None
                new_orders.add(order_excel_data.orders_number)
            else:
                order = models.Order(
                    **order_excel_data.model_dump(
                        exclude={"pickup_priority", "product_code", "qty"}
                    ),
                    created_date=datetime.now(timezone(timedelta(hours=7))),
                )
                db.add(order)
                new_orders.add(order_excel_data.orders_number)
            db.commit()
            db.refresh(order)

            new_order_item = models.OrdersDetail(
                orders_id=order.orders_id,
                product_id=db_product.product_id,
                qty=order_excel_data.qty,
                pickup_priority=order_excel_data.pickup_priority,
            )
            db.add(new_order_item)

        db.commit()
        return {"message": "Orders uploaded successfully"}
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=500, detail=f"Failed to upload orders: {e}")

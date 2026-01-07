import json
from psycopg2 import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session,joinedload
from . import models, schemas
from uuid import uuid4
import uuid
from .models import Pallet,Container
from .schemas import OrderListCreate, PalletCreate,ContainerCreate
from fastapi import  Depends, HTTPException
from datetime import datetime
from uuid import UUID
from .database import get_db

# อ่านสินค้าทั้งหมด
def get_products(db: Session, skip: int = 0, limit: int = 10):
    try:
        # Query ข้อมูลที่ is_deleted == False
        query = db.query(models.Product).filter(models.Product.is_deleted == False)
        
        total_count = query.count()  # นับจำนวนทั้งหมดที่ไม่ถูกลบ
        products = query.offset(skip).limit(limit).all()  # ใช้ Pagination
        
        print(f"Products Retrieved: {len(products)}, Total Count: {total_count}")  # Debug Log
        return {"items": products, "total_count": total_count}
    except Exception as e:
        print("Error in get_products:", e)
        raise


# อ่านสินค้าตาม ID
def get_products(db: Session, skip: int = 0, limit: int = None):
    return db.query(models.Product).filter(models.Product.is_deleted == False).offset(skip).limit(limit).all()

# เพิ่มสินค้าใหม่
def create_product(db: Session, product: schemas.ProductCreate):
    existing_product = db.query(models.Product).filter(models.Product.productcode == product.productcode).first()
    if existing_product:
        raise HTTPException(status_code=400, detail="Product code already exists")
        
    new_product = models.Product(
        productid=str(uuid.uuid4()),  # สร้าง productid ใหม่
        productcode=product.productcode, 
        productname=product.productname,
        productwidth=product.productwidth,
        productheight=product.productheight,
        productlength=product.productlength,
        productweight=product.productweight,
        qtt=product.qtt,
        isfragile=product.isfragile,
        issideup=product.issideup,
        istop=product.istop,
        notstack=product.notstack,
        maxstack=product.maxstack,
        create_by=product.create_by,
        create_date=product.create_date, 
        color=product.color  # เพิ่มฟิลด์ color
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

# อัปเดตสินค้า
def update_product(db: Session, productid: str, product: schemas.ProductUpdate):
    db_product = db.query(models.Product).filter(models.Product.productid == productid).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # ตรวจสอบ productcode ซ้ำ
    if product.productcode:
        existing_product = db.query(models.Product).filter(
            models.Product.productcode == product.productcode,
            models.Product.productid != productid  # ยกเว้นตัวที่กำลังอัปเดต
        ).first()
        if existing_product:
            raise HTTPException(status_code=400, detail="Product code already exists")
    
    for key, value in product.dict(exclude_unset=True).items():
        setattr(db_product, key, value)

    db.commit()
    db.refresh(db_product)
    return db_product



# ลบสินค้า
def delete_product(db: Session, productid: str):
    try:
        print(f"Deleting product with ID: {productid}")  # Debug
        product = db.query(models.Product).filter(models.Product.productid == productid).first()
        if not product:
            print("Product not found in database.")  # Debug
            return None
        db.delete(product)
        db.commit()
        print("Product deleted from database.")  # Debug
        return product
    except Exception as e:
        print(f"Error in delete_product: {e}")  # Debug
        return None
from datetime import datetime

def soft_delete_product(db: Session, productid: str):
    product = db.query(models.Product).filter(models.Product.productid == productid, models.Product.is_deleted == False).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_deleted = True
    product.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return {"message": "Product soft-deleted successfully"}

def restore_product(db: Session, productid: str):
    product = db.query(models.Product).filter(models.Product.productid == productid, models.Product.is_deleted == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or not soft-deleted")

    product.is_deleted = False
    product.deleted_at = None
    db.commit()
    db.refresh(product)
    return {"message": "Product restored successfully"}

#----Pallet-----

# ดึงข้อมูล Pallet ตาม ID
def get_pallets(db: Session):
    pallets = db.query(models.Pallet).filter(models.Pallet.is_deleted == False).all()
    return [pallet.__dict__ for pallet in pallets]  # แปลงเป็น dict

def get_pallet_by_id(db: Session, palletid: str):
    try:
        return db.query(Pallet).filter(Pallet.palletid == palletid, Pallet.is_deleted == False).first()
    except Exception as e:
        print(f"Error in get_pallet_by_id: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
def update_pallet(db: Session, palletid: str, pallet: schemas.PalletUpdate):
    # ค้นหา Pallet ตาม palletid
    db_pallet = db.query(models.Pallet).filter(models.Pallet.palletid == palletid).first()
    
    # หากไม่พบ Pallet ให้แจ้งข้อผิดพลาด
    if not db_pallet:
        raise HTTPException(status_code=404, detail="Pallet not found")

    # ตรวจสอบความซ้ำซ้อนของ palletcode หากมีการส่งค่าใหม่มา
    if pallet.palletcode:
        existing_pallet = db.query(models.Pallet).filter(
            models.Pallet.palletcode == pallet.palletcode,
            models.Pallet.palletid != palletid  # ยกเว้น Pallet เดิมที่กำลังอัปเดต
        ).first()
        if existing_pallet:
            raise HTTPException(status_code=400, detail="Pallet code already exists")

    # อัปเดตฟิลด์ที่ส่งมาใน request เท่านั้น
    for key, value in pallet.dict(exclude_unset=True).items():
        setattr(db_pallet, key, value)  # ใช้ setattr เพื่ออัปเดตค่าแบบไดนามิก

    # เพิ่มการอัปเดตวันที่ (ถ้ามี)
    db_pallet.update_date = datetime.utcnow()

    # บันทึกการเปลี่ยนแปลง
    db.commit()
    db.refresh(db_pallet)

    return db_pallet

# เพิ่ม Pallet
def create_pallet(db: Session, pallet: PalletCreate):
    try:
        db_pallet = Pallet(**pallet.dict())
        db.add(db_pallet)
        db.commit()
        db.refresh(db_pallet)
        return db_pallet
    except Exception as e:
        print(f"Error in create_pallet: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")

def soft_delete_pallet(db: Session, palletid: str):
    print(f"Soft deleting pallet with ID: {palletid}")  # Debug
    db_pallet = db.query(models.Pallet).filter(models.Pallet.palletid == palletid).first()
    if not db_pallet:
        print("Pallet not found!")  # Debug
        raise HTTPException(status_code=404, detail="Pallet not found")

    db_pallet.is_deleted = True
    db_pallet.update_date = datetime.utcnow()
    db.commit()
    db.refresh(db_pallet)
    return {"message": "Pallet soft-deleted successfully"}


def restore_pallet(db: Session, palletid: str):
    db_pallet = db.query(models.Pallet).filter(models.Pallet.palletid == palletid).first()
    if not db_pallet:
        raise HTTPException(status_code=404, detail="Pallet not found")

    db_pallet.is_deleted = False
    db_pallet.update_date = datetime.utcnow()
    db.commit()
    return {"message": "Pallet restored successfully"}

#------Container--------

def create_container(db: Session, container: ContainerCreate):
    try:
        db_container = Container(**container.dict())
        db.add(db_container)
        db.commit()
        db.refresh(db_container)
        return db_container
    except Exception as e:
        print(f"Error in create_container: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")

def soft_delete_container(db: Session, containerid: str):
    print(f"Soft deleting container with ID: {containerid}")  # Debug
    db_container = db.query(models.Container).filter(models.Container.containerid == containerid).first()
    if not db_container:
        print("container not found!")  # Debug
        raise HTTPException(status_code=404, detail="container not found")

    db_container.is_deleted = True
    db_container.update_date = datetime.utcnow()
    db.commit()
    db.refresh(db_container)
    return {"message": "container soft-deleted successfully"}


def restore_container(db: Session, containerid: str):
    db_container = db.query(models.Container).filter(models.Container.containerid == containerid).first()
    if not db_container:
        raise HTTPException(status_code=404, detail="container not found")

    db_container.is_deleted = False
    db_container.update_date = datetime.utcnow()
    db.commit()
    return {"message": "container restored successfully"}

#-------------------------------
def create_order_with_products(db: Session, order: schemas.OrderCreate):
    try:
        # ตรวจสอบ order_number ซ้ำ
        existing_order = db.query(models.Order).filter(models.Order.order_number == order.order_number).first()
        if existing_order:
            raise HTTPException(status_code=400, detail="Order number already exists")

        # สร้างคำสั่งซื้อใหม่
        db_order = models.Order(
            order_number=order.order_number,
            order_name=order.order_name,
            create_by=order.create_by,
            deliveryby=order.deliveryby,
            send_date=order.send_date,
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # เพิ่มสินค้าในคำสั่งซื้อ
        for product in order.products:
            db_product = db.query(models.Product).filter(models.Product.productid == product.productid).first()
            if not db_product:
                raise HTTPException(status_code=404, detail=f"Product ID {product.productid} not found")
            
            db_order_item = models.OrderList(
                orderid=db_order.orderid,
                productid=product.productid,
                qtt=product.qtt,
                send_date=product.send_date,
            )
            db.add(db_order_item)

        db.commit()

        # เตรียม response ที่ส่งกลับ
        return schemas.OrderRead(
            orderid=db_order.orderid,
            order_number=db_order.order_number,
            order_name=db_order.order_name,
            create_by=db_order.create_by,
            deliveryby=db_order.deliveryby,
            send_date=db_order.send_date,
            create_date=db_order.create_date,
            update_date=db_order.update_date,
            products=[
                schemas.OrderListCreate(
                    productid=item.productid,
                    productcode=db_product.productcode,  # กรอกค่า product ที่สัมพันธ์
                    productname=db_product.productname,
                    qtt=item.qtt,
                    productlength=db_product.productlength,
                    productwidth=db_product.productwidth,
                    productheight=db_product.productheight,
                    productweight=db_product.productweight,
                    color=db_product.color,
                    send_date=item.send_date,
                )
                for item in db.query(models.OrderList).filter(models.OrderList.orderid == db_order.orderid).all()
            ]
        )

    except Exception as e:
        db.rollback()
        print(f"Error in create_order_with_products: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while creating the order")

def get_orders(db: Session, skip: int = 0, limit: int = 100):
    orders = (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderList.product))
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for order in orders:
        result.append({
            "orderid": order.orderid,
            "order_number": order.order_number,
            "order_name": order.order_name,
            "create_by": order.create_by,
            "deliveryby": order.deliveryby,
            "send_date": order.send_date,
            "create_date": order.create_date,
            "update_date": order.update_date,
            "products": [
                {
                    "productid": item.product.productid ,
                    "productcode": item.product.productcode,
                    "productname": item.product.productname,
                    "qtt": item.qtt,
                    "productlength": item.product.productlength,
                    "productwidth": item.product.productwidth,
                    "productheight": item.product.productheight,
                    "productweight": item.product.productweight,
                    "color": item.product.color,
                    "send_date": item.send_date,
                }
                for item in order.items
            ]
        })
    return result



def get_order_by_id(db: Session, order_id: int):
    order = (
        db.query(models.Order)
        .filter(models.Order.orderid == order_id)
        .options(
            joinedload(models.Order.items).joinedload(models.OrderList.product)  # โหลดข้อมูล product
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Return data with proper handling for `null` values
    return schemas.OrderRead(
        orderid=order.orderid,
        order_number=order.order_number,
        order_name=order.order_name,
        create_by=order.create_by,
        deliveryby=order.deliveryby,
        send_date=order.send_date,
        create_date=order.create_date,
        update_date=order.update_date or None,
        products=[
            schemas.OrderListCreate(
                productid=item.product.productid ,
                productcode=item.product.productcode ,
                productname=item.product.productname ,
                qtt=item.qtt,
                productlength=item.product.productlength ,
                productwidth=item.product.productwidth ,
                productheight=item.product.productheight ,
                productweight=item.product.productweight ,
                color=item.product.color ,
                send_date=item.send_date,
            )
            for item in order.items
        ]
,
    )

# def get_order_by_id(db: Session, uuid_ids: UUID):
#     return db.query(models.Order).filter(models.Order.orderid == uuid_ids).first()

def save_simulation_batches_internal(data: dict, db: Session):
    try:
        print(f"📥 Simulation Result Data: {data}")

        for batch_data in data.get("data", []):
            batchtype = batch_data.get("batchtype", "").lower()

            if batchtype not in ["pallet", "container", "palletoncontainer"]:
                raise HTTPException(status_code=400, detail=f" batchtype {batchtype} ไม่ถูกต้อง")

            #  หาค่า orderid จาก product ใน batch
            first_detail = next((d for d in batch_data["details"] if "orderid" in d), None)
            
            #  กรณีเป็น `palletoncontainer` ต้องหา `orderid` จากสินค้าภายใน
            if not first_detail:
                for detail in batch_data["details"]:
                    if detail.get("mastertype") == "sim_batch" and "sim_batch" in detail:
                        first_detail = next(
                            (prod for prod in detail["sim_batch"]["details"] if prod.get("orderid")),
                            None
                        )
                        if first_detail:
                            break

            if not first_detail:
                print(f"⏩ ข้าม batch เพราะไม่มี orderid: {batch_data}")
                continue

            #  หา simulateid จาก orderid
            simulate_entry = (
                db.query(models.Simulate.simulateid)
                .join(models.Simulatedetail)
                .order_by(models.Simulate.simulatedatetime.desc())
                .limit(1)
                .first()
            )

            if not simulate_entry:
                latest_simulate = db.query(models.Simulate.simulateid).order_by(models.Simulate.simulateid.desc()).first()
                if latest_simulate:
                    simulateid = latest_simulate.simulateid
                    print(f" ใช้ simulateid ล่าสุด: {simulateid}")
                else:
                    raise HTTPException(status_code=404, detail=f" ไม่พบ simulateid สำหรับ orderid: {first_detail['orderid']}")

            else:
                simulateid = simulate_entry.simulateid

            print(f"🔹 ใช้ simulateid: {simulateid}")

            #  สร้าง batch
            new_batch = models.Simbatch(
                simulateid=simulateid,
                batchtype=batchtype
            )
            db.add(new_batch)
            db.flush()
            db.refresh(new_batch)

            print(f"สร้าง batch ใหม่ batchid: {new_batch.batchid}, batchtype: {batchtype}")

            for detail in batch_data.get("details", []):
                mastertype = detail.get("mastertype")
                masterid = detail.get("masterid", None)
                total_weight = detail.get("total_weight", 0.0)
                position = detail.get("position", None)
                rotation = detail.get("rotation", None)
                orderid = detail.get("orderid", None)

                if masterid is None and mastertype != "sim_batch":
                    print(f"ข้าม detail เพราะไม่มี masterid: {detail}")
                    continue

                if mastertype == "sim_batch":
                    #  กรณี palletoncontainer (sim_batch)
                    print(f" กำลังบันทึก palletoncontainer (sim_batch)")

                    nested_batch = models.Simbatch(
                        simulateid=simulateid,
                        batchtype="palletoncontainer",
                    )
                    db.add(nested_batch)
                    db.flush()
                    db.refresh(nested_batch)

                    print(f" สร้าง sim_batch batchid: {nested_batch.batchid} (palletoncontainer)")

                    for nested_detail in detail.get("sim_batch", {}).get("details", []):
                        db.add(models.Simbatchdetail(
                            batchid=nested_batch.batchid,
                            simulateid=simulateid,
                            mastertype=nested_detail["mastertype"],
                            masterid=str(nested_detail["masterid"]),
                            position=json.dumps(nested_detail.get("position", [0, 0, 0])),
                            rotation=int(nested_detail.get("rotation", 0)),
                            orderid=int(nested_detail.get("orderid", 0)) if "orderid" in nested_detail else None,
                        ))

                    #  เพิ่ม sim_batch เข้าไปเป็น child ของ container
                    db.add(models.Simbatchdetail(
                        batchid=new_batch.batchid,
                        simulateid=simulateid,
                        mastertype="sim_batch",
                        masterid=str(nested_batch.batchid),
                        position=json.dumps(position) if position else None,
                        rotation=int(rotation) if rotation is not None else None,
                    ))

                else:
                    new_detail = models.Simbatchdetail(
                        batchid=new_batch.batchid,
                        simulateid=simulateid,
                        mastertype=mastertype,
                        masterid=str(masterid),
                        position=json.dumps(position) if position else None,
                        rotation=int(rotation) if rotation is not None else None,
                        orderid=int(orderid) if orderid is not None else None,
                    )
                    db.add(new_detail)

            db.commit()
            print(f" บันทึก batch สำเร็จ: {new_batch.batchid}")

        return {"message": "บันทึก batch และ detail สำเร็จ"}

    except Exception as e:
        db.rollback()
        print(f" Error during save_simulation_batches: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {e}")

    finally:
        db.close()


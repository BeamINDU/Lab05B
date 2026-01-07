import json
from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException,Query,APIRouter,UploadFile, File
from psycopg2 import IntegrityError
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import engine, Base, get_db
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import uuid
from .schemas import PalletCreate, PalletUpdate
from .crud import soft_delete_pallet,restore_pallet,soft_delete_container,restore_container
from datetime import datetime
from typing import List
from app.simulation.main import router as simulation_router
import requests
from uuid import UUID
from pydantic import BaseModel
from typing import List, Dict, Any, Union
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()  # โหลดค่าจากไฟล์ .env

# สร้างตาราง
Base.metadata.create_all(bind=engine)
BASE_URL = os.getenv("SIMULATION_API_BASE_URL", "http://13.212.22.165:8000")
BASE_PATH = os.getenv("PYTHONPATH", ".")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # เพิ่ม URL Frontend ที่อนุญาต
    allow_credentials=True,
    allow_methods=["*"],  # อนุญาตทุก HTTP Methods (เช่น GET, POST, DELETE, PUT)
    allow_headers=["*"],  # อนุญาตทุก Headers
)

app.include_router(simulation_router, prefix="/simulation")


@app.get("/products/")
def read_products(skip: int = 0, limit: int = None, db: Session = Depends(get_db)):
    try:
        products = (
            db.query(models.Product)
            .filter(models.Product.is_deleted == False)  # ไม่ดึงข้อมูลที่ลบแบบ soft delete
            .offset(skip)
            .limit(limit)
            .all()
        )
        total_count = (
            db.query(models.Product)
            .filter(models.Product.is_deleted == False)
            .count()
        )
        return {"items": products, "total_count": total_count}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# @app.get("/products/", response_model=list[schemas.Product])
# def read_products(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
#     try:
#         products = crud.get_products(db, skip=skip, limit=limit)
#         return products  # `response_model` จะช่วยแปลงข้อมูล SQLAlchemy เป็น JSON
#     except Exception as e:
#         print(f"Error: {e}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/products/")
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    try:
        print("Payload received:", product.dict(by_alias=True))
        new_product = models.Product(
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
            color=product.color,
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        print("Product successfully created:", new_product)
        return {"message": "Product created successfully", "product": new_product}
    except Exception as e:
        print("Error during product creation:", e)  # Debug Exception
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.put("/products/{productid}")
async def update_product(productid: str, product: schemas.ProductUpdate, db: Session = Depends(get_db)):
    print("Received Product ID:", productid)
    print("Received Payload:", product.dict())
    
    # ดึงข้อมูล Product จาก DB
    db_product = db.query(models.Product).filter(models.Product.productid == productid).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # อัปเดตฟิลด์ที่ส่งมา
    for key, value in product.dict(exclude_unset=True).items():
        print(f"Updating {key} to {value}")  # Log การอัปเดต
        setattr(db_product, key, value)

    db.commit()
    db.refresh(db_product)
    print("Updated Product in DB:", db_product)
    return db_product




# @app.delete("/products/{productid}")
# def delete_product(productid: str, db: Session = Depends(get_db)):
#     try:
#         print(f"Attempting to delete product with ID: {productid}")  # Debug
#         deleted_product = crud.delete_product(db, productid=productid)
#         if not deleted_product:
#             print("Product not found.")  # Debug
#             raise HTTPException(status_code=404, detail="Product not found")
#         print("Product deleted successfully.")  # Debug
#         return {"message": "Product deleted successfully"}
#     except Exception as e:
#         print(f"Error occurred while deleting product: {e}")  # Debug
#         raise HTTPException(status_code=500, detail="Internal Server Error")

@app.delete("/products/{productid}")
def soft_delete_product(productid: str, db: Session = Depends(get_db)):
    try:
        result = crud.soft_delete_product(db, productid)
        print(f"Product Soft Deleted: {result}")
        return result
    except Exception as e:
        print(f"Error in soft_delete_product: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.put("/products/{productid}/restore")
def restore_product_api(productid: str, db: Session = Depends(get_db)):
    try:
        result = crud.restore_product(db, productid)
        print(f"Product Restored: {result}")
        return result
    except Exception as e:
        print(f"Error in restore_product_api: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ----------------Pallet-----------------
@app.get("/pallets/")
def read_pallets(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    try:
        pallets = (
            db.query(models.Pallet)
            .filter(models.Pallet.is_deleted == False)
            .offset(skip)
            .limit(limit)
            .all()
        )
        total_count = db.query(models.Pallet).filter(models.Pallet.is_deleted == False).count()
        return {"items": pallets, "total_count": total_count}
    except Exception as e:
        print(f"Error in read_pallets: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/pallets/")
def read_pallets(db: Session = Depends(get_db)):
    try:
        pallets = (
            db.query(models.Pallet)
            .filter(models.Pallet.is_deleted == False)
            .all()
        )
        total_count = len(pallets)
        return {"items": pallets, "total_count": total_count}
    except Exception as e:
        print(f"Error in read_pallets: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/pallets", response_model=schemas.PalletUpdate)
def create_pallet(pallet: schemas.PalletCreate, db: Session = Depends(get_db)):
    try:
        print("Payload received:", pallet.dict())  # Debug Payload

        new_pallet = models.Pallet(
            palletcode=pallet.palletcode,
            palletname=pallet.palletname,
            palletwidth=pallet.palletwidth,
            palletheight=pallet. palletheight,
            palletlength=pallet. palletlength,
            palletweight=pallet.palletweight,
            loadwidth=pallet.loadwidth,
            loadheight=pallet.loadheight,
            loadlength=pallet.loadlength,
            loadweight=pallet.loadweight,
            qtt=pallet.qtt,
            createby=pallet.createby,
            createdate=pallet.createdate,
            updateby=pallet.updateby,
            updatedate=pallet.updatedate,
            color=pallet.color,
            palletsize = pallet.palletsize,
        )
        db.add(new_pallet)
        db.commit()
        db.refresh(new_pallet)
        return new_pallet
    except Exception as e:
        print(f"Error in create_pallet: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
@app.put("/pallets/{palletid}")
def update_pallet(palletid: str, pallet: schemas.PalletUpdate, db: Session = Depends(get_db)):
    db_pallet = db.query(models.Pallet).filter(models.Pallet.palletid == palletid).first()
    if not db_pallet:
        raise HTTPException(status_code=404, detail="Pallet not found")

    # Update the fields
    for key, value in pallet.dict(exclude_unset=True).items():
        setattr(db_pallet, key, value)

    db_pallet.updatedate = datetime.utcnow()  # อัปเดตวันที่
    db.commit()
    db.refresh(db_pallet)
    return db_pallet

@app.delete("/pallets/{palletid}")
def delete_pallet(palletid: str, db: Session = Depends(get_db)):
    return soft_delete_pallet(db, palletid)


@app.put("/pallets/{palletid}/restore")
def restore_pallet_api(palletid: str, db: Session = Depends(get_db)):
    return restore_pallet(db, palletid)


#--------container------
@app.get("/containers/")
def read_container(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    try:
        container = (
            db.query(models.Container)
            .filter(models.Container.is_deleted == False)
            .offset(skip)
            .limit(limit)
            .all()
        )
        total_count = db.query(models.Container).filter(models.Container.is_deleted == False).count()
        return {"items": container, "total_count": total_count}
    except Exception as e:
        print(f"Error in read_container: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/containers/")
def read_container(db: Session = Depends(get_db))->dict[tuple,int]:
    try:
        container = (
            db.query(models.Container)
            .filter(models.Container.is_deleted == False)
            .all()
        )
        total_count = len(container)
        return {"items": container, "total_count": total_count}
    except Exception as e:
        print(f"Error in read_container: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/containers", response_model=schemas.ContainerUpdate)
def create_container(container: schemas.ContainerCreate, db: Session = Depends(get_db)):
    try:

        new_container = models.Container(
            containercode=container.containercode,
            containername=container.containername,
            containerwidth=container.containerwidth,
            containerheight=container. containerheight,
            containerlength=container. containerlength,
            containerweight=container.containerweight,
            loadwidth=container.loadwidth,
            loadheight=container.loadheight,
            loadlength=container.loadlength,
            loadweight=container.loadweight,
            qtt=container.qtt,
            createby=container.createby,
            createdate=container.createdate,
            updateby=container.updateby,
            updatedate=container.updatedate,
            color=container.color,
            containersize = container.containsize,
        )
        db.add(new_container)
        db.commit()
        db.refresh(new_container)
        return new_container
    except Exception as e:
        print(f"Error in create_container: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@app.put("/containers/{containerid}")
def update_container(containerid: str, container: schemas.ContainerUpdate, db: Session = Depends(get_db)):
    db_container = db.query(models.Container).filter(models.Container.containerid == containerid).first()
    if not db_container:
        raise HTTPException(status_code=404, detail="container not found")

    # Update the fields
    for key, value in container.dict(exclude_unset=True).items():
        setattr(db_container, key, value)

    db_container.updatedate = datetime.utcnow()  # อัปเดตวันที่
    db.commit()
    db.refresh(db_container)
    return db_container

@app.delete("/containers/{containerid}")
def delete_container(containerid: str, db: Session = Depends(get_db)):
    return soft_delete_container(db, containerid)


@app.put("/containers/{containerid}/restore")
def restore_container_api(containerid: str, db: Session = Depends(get_db))->dict:
    return restore_container(db, containerid)

#-------------------------------
@app.post("/orders/", response_model=schemas.OrderRead)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    response = crud.create_order_with_products(db, order)
    print("Response Data:", response)  # Debugging
    return response


@app.get("/orders/", response_model=schemas.OrdersResponse)
def read_orders(skip: int = 0, db: Session = Depends(get_db)):
    orders = crud.get_orders(db, skip=skip)
    total_count = db.query(models.Order).count()
    return {"items": orders, "total_count": total_count}

@app.get("/orders/{orderid}", response_model=schemas.OrderRead)
def read_order(orderid: str, db: Session = Depends(get_db)):
    try:
        # ลองแปลง `orderid` เป็น `int`
        order_id = int(orderid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID format")  # แจ้งข้อผิดพลาดหากแปลงไม่ได้
    
    # เรียกใช้ฟังก์ชัน `get_order_by_id` ใน `crud.py`
    order = crud.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    print("Order Data to Return:", order.dict())  # Debug Log
    return order

@app.put("/orders/{orderid}")
async def update_order(orderid: str, order: schemas.OrderUpdate, db: Session = Depends(get_db)):
    try:
        print(f"Received Order ID: {orderid}")
        print(f"Received Payload: {order.dict()}")

        # ตรวจสอบคำสั่งซื้อ
        db_order = db.query(models.Order).filter(models.Order.orderid == orderid).first()
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")

        # อัปเดต Order Name และ Send Date
        if order.order_name:
            db_order.order_name = order.order_name
        if order.send_date:
            db_order.send_date = order.send_date

        # ลบสินค้าที่อยู่ใน deleted_products
        if order.deleted_products:
            print(f"Deleted products payload: {order.deleted_products}")  # Debug Payload

            for deleted_item in order.deleted_products:
                try:
                    # แยก productid และ index ออกจาก string เช่น "8-3"
                    productid, index = deleted_item.split("-")
                    productid = int(productid)  # แปลง productid เป็น integer
                    index = int(index)  # แปลง index เป็น integer

                    # ดึงสินค้าทั้งหมดที่ตรงกับ productid และ orderid
                    products = db.query(models.OrderList).filter(
                        models.OrderList.orderid == orderid,
                        models.OrderList.productid == productid
                    ).order_by(models.OrderList.detailid).all()

                    # ตรวจสอบว่า index อยู่ในขอบเขต
                    if index >= len(products):
                        print(f"Invalid index {index} for productid {productid}. Available indices: 0-{len(products) - 1}")
                        continue

                    # ลบสินค้าที่ตรงกับ index
                    product_to_delete = products[index]
                    print(f"Deleting product: {product_to_delete.detailid} at index {index}")
                    db.delete(product_to_delete)

                    db.commit()  # Commit หลังการลบสินค้า
                    print(f"Deleted product successfully: {product_to_delete.detailid}")

                except Exception as e:
                    print(f"Error processing deleted_products: {e}")

        # อัปเดตสินค้าที่มีอยู่แล้ว
        if order.existing_products:
            for product_data in order.existing_products:
                db_product = db.query(models.OrderList).filter(
                    models.OrderList.orderid == orderid,
                    models.OrderList.productid == product_data.productid
                ).first()

                if db_product:
                    # อัปเดตสินค้าเดิม
                    db_product.qtt = product_data.qtt
                    db_product.send_date = product_data.send_date

        # เพิ่มสินค้าใหม่
        if order.new_products:
            for product_data in order.new_products:
                new_product = models.OrderList(
                    orderid=orderid,
                    productid=product_data.productid,
                    qtt=product_data.qtt,
                    send_date=product_data.send_date,
                )
                db.add(new_product)

        db.commit()
        db.refresh(db_order)
        print("Updated Order Successfully:", db_order)
        return db_order
    except Exception as e:
        print(f"Error updating order: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


@app.delete("/orders/{orderid}")
def delete_order(orderid: str, db: Session = Depends(get_db)):
    db_order = db.query(models.Order).filter(models.Order.orderid == orderid).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # ลบคำสั่งซื้อ
    db.delete(db_order)
    db.commit()
    return {"message": "Order deleted successfully"}

# @app.post("/simulate/{orderid}")
# def simulate_order(orderid: str):
#     try:
#         # ดึงข้อมูล Order จาก API หลัก
#         order_response = requests.get(f"http://localhost:8000/orders/{orderid}")
#         if order_response.status_code != 200:
#             raise HTTPException(status_code=500, detail="Error fetching order details")
#         order = order_response.json()

#         # แปลงข้อมูลสินค้าใน Order เป็นรูปแบบ Simulation
#         simulation_items = []
#         for item in order["products"]:
#             item_details_response = requests.get(f"http://localhost:8000/products/{item['productid']}")
#             if item_details_response.status_code == 200:
#                 item_details = item_details_response.json()
#                 simulation_items.append({
#                     "id": item["productid"],
#                     "length": item_details["productlength"],
#                     "width": item_details["productwidth"],
#                     "height": item_details["productheight"],
#                     "weight": item_details["productweight"],
#                     "amount": item["qtt"],
#                     "color": item_details.get("color", "#FFFFFF"),
#                     "isTop": item_details.get("istop", False),
#                     "isSideUp": item_details.get("issideup", False),
#                     "priority": 1  # ปรับตามความต้องการ
#                 })
#             else:
#                 # ถ้าไม่สามารถดึงข้อมูลสินค้าได้
#                 raise HTTPException(status_code=500, detail=f"Error fetching product details for {item['productid']}")

#         # ดึงข้อมูล Containers จาก API หลัก
#         containers_response = requests.get("http://localhost:8000/containers/")
#         if containers_response.status_code == 200:
#             containers = containers_response.json()["items"]
#         else:
#             raise HTTPException(status_code=500, detail="Error fetching containers")

#         simulation_containers = [
#             {
#                 "id": container["containerid"],
#                 "length": container["containerlength"],
#                 "width": container["containerwidth"],
#                 "height": container["containerheight"],
#                 "max_weight": container["containerweight"],
#                 "priority": 1  # ปรับตามความต้องการ
#             }
#             for container in containers
#         ]

#         # เรียกใช้ลอจิก Simulation
#         result = simulate_logic(simulation_items, simulation_containers)
#         return result

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# def simulate_logic(items, containers):
#     # ลอจิก Simulation หรือเรียกใช้ฟังก์ชัน GA
#     # ตัวอย่างผลลัพธ์จำลอง
#     return {"message": "Simulation successful", "items": items, "containers": containers}
SIMULATION_URL = f"{BASE_URL}/simulation/simulate/"
# router = APIRouter()

class SimulationRequest(BaseModel):
    order_ids: List[Union[int, str]]  # รองรับทั้ง int และ str
    simulate_id: int
import traceback
@app.post("/simulate-orders/")
def simulate_orders(
    payload: SimulationRequest, 
    simulation_type: str = Query(..., enum=["pallet", "container", "pallet_container"]), 
    db: Session = Depends(get_db)
):
    try:
        # --- ดึงข้อมูล Orders ---
        order_ids = db.query(models.Simulatedetail.orderid).filter(
            models.Simulatedetail.simulateid == payload.simulate_id
        ).all()
        
        orders = db.query(models.Order).filter(
            models.Order.orderid.in_([oid[0] for oid in order_ids])
        ).all()

        if not orders:
            raise HTTPException(status_code=404, detail="No orders found")

        # --- สร้างข้อมูล products ---
        products = []
        for order in orders:
            for item in order.items:
                if item.product:
                    products.append({
                        "orderid": int(order.orderid),
                        "productid": int(item.product.productid),
                        "productname": item.product.productname,
                        "productlength": float(item.product.productlength),
                        "productwidth": float(item.product.productwidth),
                        "productheight": float(item.product.productheight),
                        "productweight": float(item.product.productweight),
                        "qtt": int(item.qtt),  
                        "notStack": bool(item.product.notstack),
                        "isFragile": bool(item.product.isfragile),
                        "isTop": bool(item.product.istop),
                        "isSideUp": bool(item.product.issideup),
                        "maxStack": int(item.product.maxstack),
                        "priority": 1,
                    })

        # --- ดึงข้อมูล Simulation ---
        query_url = f"{BASE_URL}/simulation/query-data/{payload.simulate_id}"
        print(f"🔍 Fetching simulation data from: {query_url}")

        query_response = requests.get(query_url, timeout=10)
        
        if query_response.status_code != 200:
            raise HTTPException(status_code=query_response.status_code, detail="Error fetching simulation query data")

        query_data = query_response.json()
        print(f"📥 Query Data: {json.dumps(query_data, indent=2)}")

        # ตรวจสอบว่ามีข้อมูลพาเลทหรือคอนเทนเนอร์สำหรับ Simulation หรือไม่
        if simulation_type == "pallet" and "pallets" not in query_data:
            raise HTTPException(status_code=400, detail="No pallets found for simulation")
        if simulation_type == "container" and "containers" not in query_data:
            raise HTTPException(status_code=400, detail="No containers found for simulation")
        if simulation_type == "pallet_container" and ("pallets" not in query_data or "containers" not in query_data):
            raise HTTPException(status_code=400, detail="Pallets or Containers missing for simulation")

        # --- สร้าง payload สำหรับ Simulation ---
        simulation_payload = {"products": products}
        simulate_url = f"{BASE_URL}/simulation/simulate/{simulation_type}"

        if "pallets" in query_data:
            simulation_payload["pallets"] = [
                {
                    "palletid": int(p["palletid"]),
                    "palletname": p["palletname"],
                    "palletlength": float(p["palletlength"]),
                    "palletwidth": float(p["palletwidth"]),
                    "palletheight": float(p["palletheight"]),
                    "palletweight": float(p["palletweight"]),
                    "loadlength": float(p["loadlength"]),
                    "loadwidth": float(p["loadwidth"]),
                    "loadheight": float(p["loadheight"]),
                    "loadweight": float(p["loadweight"]),
                    "qtt": int(p["qtt"]) if "qtt" in p else 1,
                    "priority": int(p["priority"]) if "priority" in p else 1,
                }
                for p in query_data["pallets"]
            ]

        if "containers" in query_data:
            simulation_payload["containers"] = [
                {
                    "containerid": c["containerId"],
                    "containername": c["containerName"],
                    "containerlength": c["containerLength"],
                    "containerwidth": c["containerWidth"],
                    "containerheight": c["containerHeight"],
                    "containerweight": c["containerWeight"],
                    "loadlength": c["loadLength"],
                    "loadwidth": c["loadWidth"],
                    "loadheight": c["loadHeight"],
                    "loadweight": c["loadWeight"],
                    "qtt": c["qtt"],
                    "priority": c["priority"],
                }
                for c in query_data["containers"]
            ]

        # --- Debugging Log ---
        print(f"🚀 Sending request to {simulate_url}")
        print(f"📦 Payload Sent: {json.dumps(simulation_payload, indent=2)}")

        try:
            # --- ส่ง Request ไปที่ Simulation API ---
            simulate_response = requests.post(simulate_url, json=simulation_payload, timeout=3000)
            simulate_response.raise_for_status()  # ตรวจสอบ HTTP Status Code
            simulation_result = simulate_response.json()

            # --- Handle กรณี Simulation ล้มเหลว ---
            if "error" in simulation_result:
                print(f"❌ Simulation Failed: {simulation_result['error']}")
                raise HTTPException(status_code=400, detail=f"Simulation failed: {simulation_result['error']}")

            return {
                "message": "Simulation successful",
                "simulation_result": simulation_result
            }

        except requests.exceptions.RequestException as e:
            print(f"❌ Error during request: {e}")
            raise HTTPException(status_code=500, detail=f"Error contacting simulation API: {e}")

    except Exception as e:
        db.rollback()
        print(f"❌ Unexpected Error during simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error during simulation: {e}")


#---------------------API-SIMU----------------
class SimulationPreSaveRequest(BaseModel):
    simulatetype: str
    order_ids: List[int]

@app.post("/simulation/pre-save/")
def pre_save_simulation(
    request: SimulationPreSaveRequest,  # ✅ ใช้ Pydantic Model
    db: Session = Depends(get_db)
):
    try:
        print(f"📥 Received: simulatetype={request.simulatetype}, order_ids={request.order_ids}")

        # ตรวจสอบ `order_ids` ต้องมีค่าอย่างน้อย 1 รายการ
        if not request.order_ids:
            raise HTTPException(status_code=400, detail="order_ids ต้องมีค่าอย่างน้อย 1 รายการ")

        # ✅ แปลง `simulatetype` ให้เป็นตัวพิมพ์เล็ก
        simulatetype = request.simulatetype.lower()

        # ✅ บันทึก simulate entry
        simulate_entry = models.Simulate(
            simulatetype=simulatetype,
            status="Pending",
            simulateby="Admin",
            simulatedatetime=datetime.utcnow()
        )
        db.add(simulate_entry)
        db.commit()
        db.refresh(simulate_entry)
        simulateid = simulate_entry.simulateid

        # ✅ บันทึก order ลง simulatedetail
        for order_id in request.order_ids:
            new_detail = models.Simulatedetail(
                simulateid=simulate_entry.simulateid,
                orderid=order_id
            )
            db.add(new_detail)

        db.commit()

        return {"simulateId": simulate_entry.simulateid, "message": "บันทึกข้อมูล simulate เรียบร้อย"}

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {e}")
    

@app.get("/simulation/query-data/{simulate_id}")
def query_simulation_data(simulate_id: int, db: Session = Depends(get_db)):
    orders = db.query(models.Simulatedetail).filter(models.Simulatedetail.simulateid == simulate_id).all()
    if not orders:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูล Simulation")

    order_ids = [order.orderid for order in orders]
    query_result = db.query(models.Order).filter(models.Order.orderid.in_(order_ids)).all()

    products = []
    for order in query_result:
        for item in order.items:
            products.append({
                "orderid": str(order.orderid),
                "productid": str(item.productid),
                "productname": item.product.productname,
                "productlength": item.product.productlength,
                "productwidth": item.product.productwidth,
                "productheight": item.product.productheight,
                "productweight": item.product.productweight,
                "qtt": item.qtt,
                "notStack": item.product.notstack,
                "isFragile": item.product.isfragile,
                "isTop": item.product.istop,
                "isSideUp": item.product.issideup,
                "maxStack": item.product.maxstack,
                "priority": 1
            })

    simulatetype = orders[0].simulate.simulatetype.lower()

    response_data = {"products": products}

    if simulatetype in ["pallet", "pallet_container"]:
        pallets = db.query(models.Pallet).filter(models.Pallet.is_deleted == False).all()
        if pallets:
            response_data["pallets"] = [
                {
                    "palletid": str(c.palletid),
                    "palletname": c.palletname,
                    "palletlength": c.palletlength,
                    "palletwidth": c.palletwidth,
                    "palletheight": c.palletheight,
                    "palletweight": c.palletweight,
                    "loadlength": c.loadlength,
                    "loadwidth": c.loadwidth,
                    "loadheight": c.loadheight,
                    "loadweight": c.loadweight,
                    "qtt": c.qtt,
                    "priority": 1
                }
                for c in pallets
            ]

    if simulatetype in ["container", "pallet_container"]:
        containers = db.query(models.Container).filter(models.Container.is_deleted == False).all()
        if containers:
            response_data["containers"] = [
                {
                    "containerId": str(c.containerid),
                    "containerName": c.containername,
                    "containerLength": c.containerlength,
                    "containerWidth": c.containerwidth,
                    "containerHeight": c.containerheight,
                    "containerWeight": c.containerweight,
                    "loadLength": c.loadlength,
                    "loadWidth": c.loadwidth,
                    "loadHeight": c.loadheight,
                    "loadWeight": c.loadweight,
                    "qtt": 1,
                    "priority": 1
                }
                for c in containers
            ]

    return response_data  


    # else:
    #     raise HTTPException(status_code=400, detail="simulatetype ไม่ถูกต้อง")
    

# @app.post("/simulation/save-batches/")
# def save_simulation_batches(simulateid: int, data: dict, db: Session = Depends(get_db)):
#     try:
#         simulate_entry = db.query(models.Simulate).filter(models.Simulate.simulateid == simulateid).first()
#         if not simulate_entry:
#             raise HTTPException(status_code=404, detail=" ไม่พบ simulateId ในระบบ")

#         simulatetype = simulate_entry.simulatetype
#         response_data = []  #  เก็บ batch ที่สร้างสำเร็จไว้ส่งกลับไปใน response

#         #  ใช้ dictionary mapping batchid
#         batchid_mapping = {}

#         for batch_data in data.get("data", []):
#             if batch_data["simulatetype"].lower() != simulatetype.lower():
#                 raise HTTPException(status_code=400, detail=f" simulatetype {batch_data['simulatetype']} ไม่ตรงกับ {simulatetype}")

#             batch_simulateid = batch_data.get("simulateid", simulateid)

#             #  ไม่ใช้ batchid ที่มาจาก payload (ให้ database สร้าง)
#             new_batch = models.Simbatch(
#                 simulateid=batch_simulateid,
#                 simulatetype=batch_data["simulatetype"],
#                 batchtypeid=batch_data["batchtypeid"]
#             )

#             db.add(new_batch)
#             db.flush()  #  ให้ database สร้าง batchid อัตโนมัติ
#             db.refresh(new_batch)  #  ดึง batchid ที่เพิ่งสร้างขึ้นมา

#             print(f" Created new batch with batchid: {new_batch.batchid}")

#             #  Mapping batchid ที่ใช้ใน response
#             batchid_mapping[batch_data["batchid"]] = new_batch.batchid

#             #  บันทึกข้อมูลลง sim_batch_detail
#             for item in batch_data["items"]:
#                 new_detail = models.Simbatchdetail(
#                     batchid=new_batch.batchid,  #  ใช้ batchid ที่ database กำหนด
#                     simulateid=batch_simulateid,
#                     orderid=int(item.get("orderid", item.get("orderId"))),
#                     mastertype=item["mastertype"],
#                     masterid=str(item["masterid"]),
#                     position=item["position"],
#                     rotation=int(item["rotation", 0])
#                 )
#                 db.add(new_detail)

#             #  เก็บ batch ที่สร้างไว้ใน response
#             response_data.append({
#                 "batchid": batch_data["batchid"],  #  ส่ง batchid ที่รับมา
#                 "db_batchid": new_batch.batchid,  #  เพิ่ม batchid ที่ Database กำหนด
#                 "simulatetype": new_batch.simulatetype,
#                 "batchtypeid": new_batch.batchtypeid
#             })

#         db.commit()
#         return {"message": " บันทึก batch และ detail สำเร็จ!", "batches": response_data, "batchid_mapping": batchid_mapping}  #  ส่ง batchid กลับไปให้ Frontend

#     except Exception as e:
#         db.rollback()
#         print(f" Error during save_simulation_batches: {e}")
#         raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดใน save_simulation_batches: {e}")

@app.get("/simulation/simulate/{simulateid}")
def get_simulation_data(simulateid: int, db: Session = Depends(get_db)):
    try:
        simulate_entry = db.query(models.Simulate).filter(models.Simulate.simulateid == simulateid).first()
        if not simulate_entry:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล simulateId")

        batches = db.query(models.Simbatch).filter(models.Simbatch.simulateid == simulateid).all()

        response_data = []
        for batch in batches:
            batch_details = db.query(models.Simbatchdetail).filter(models.Simbatchdetail.batchid == batch.batchid).all()

            batch_response = {
                "batchid": batch.batchid,
                "batchname": f"Batch {batch.batchid}",
                "batchtype": batch.batchtype.lower(),
                "color": "#FFFFFF",
                "length": None,
                "width": None,
                "height": None,
                "loadlength": None,
                "loadwidth": None,
                "loadheight": None,
                "details": []
            }

            orders_dict = {}  # จัดกลุ่ม `orderid`
            pallets_dict = {}  # จัดกลุ่ม `pallet` ที่อยู่ใน container

            for detail in batch_details:
                if detail.mastertype == "container":
                    container = db.query(models.Container).filter(models.Container.containerid == detail.masterid).first()
                    if container:
                        batch_response["length"] = container.containerlength
                        batch_response["width"] = container.containerwidth
                        batch_response["height"] = container.containerheight
                        batch_response["loadlength"] = container.loadlength
                        batch_response["loadwidth"] = container.loadwidth
                        batch_response["loadheight"] = container.loadheight

                elif detail.mastertype == "pallet":
                    pallet = db.query(models.Pallet).filter(models.Pallet.palletid == detail.masterid).first()
                    if pallet:
                        batch_response["length"] = pallet.palletlength
                        batch_response["width"] = pallet.palletwidth
                        batch_response["height"] = pallet.palletheight
                        batch_response["loadlength"] = pallet.loadlength
                        batch_response["loadwidth"] = pallet.loadwidth
                        batch_response["loadheight"] = pallet.loadheight

                elif detail.mastertype == "product":
                    # ✅ ดึงข้อมูล product
                    product = db.query(models.Product).filter(models.Product.productid == detail.masterid).first()
                    if product:
                        position = json.loads(detail.position) if detail.position else [0, 0, 0]
                        product_entry = {
                            "batchdetailid": detail.batchdetailid,
                            "name": product.productname,
                            "code": str(product.productid),
                            "color": product.color or "#FFFFFF",
                            "length": product.productlength,
                            "width": product.productwidth,
                            "height": product.productheight,
                            "isfragile": product.isfragile,
                            "issideUp": product.issideup,
                            "istop": product.istop,
                            "notstack": product.notstack,
                            "masterid": product.productid,
                            "mastertype": "product",
                            "maxstack": product.maxstack or -1,
                            "position": position,
                            "rotation": detail.rotation if detail.rotation is not None else 0,
                        }

                    if detail.orderid not in orders_dict:
                        # ✅ ค้นหา Order ตาม orderid
                        order_entry = db.query(models.Order).filter(models.Order.orderid == detail.orderid).first()

                        # ✅ ถ้ามีข้อมูล ให้ใช้จาก Database, ถ้าไม่มีให้ใช้ค่า Default
                        order_name = order_entry.order_name if order_entry else f"Order {detail.orderid}"
                        order_number = order_entry.order_number if order_entry else f"ORD-{detail.orderid}"

                        orders_dict[detail.orderid] = {
                            "orderid": detail.orderid,
                            "ordername": order_name,
                            "ordernumber": order_number,
                            "products": []
                        }

                    orders_dict[detail.orderid]["products"].append(product_entry)


            # ✅ เพิ่มข้อมูลคำสั่งซื้อที่อยู่ใน batch นี้
            batch_response["details"].extend(list(orders_dict.values()))

            # ✅ เพิ่ม pallet ที่อยู่ใน batch นี้
            batch_response["details"].extend(list(pallets_dict.values()))

            # ✅ ถ้า `length` ยังไม่มีค่า ให้ใช้ default (เฉพาะกรณีที่ดึงค่าจาก DB ไม่ได้)
            batch_response["length"] = batch_response["length"] if batch_response["length"] is not None else 5
            batch_response["width"] = batch_response["width"] if batch_response["width"] is not None else 5
            batch_response["height"] = batch_response["height"] if batch_response["height"] is not None else 3.5
            batch_response["loadlength"] = batch_response["loadlength"] if batch_response["loadlength"] is not None else 4
            batch_response["loadwidth"] = batch_response["loadwidth"] if batch_response["loadwidth"] is not None else 4
            batch_response["loadheight"] = batch_response["loadheight"] if batch_response["loadheight"] is not None else 3


            response_data.append(batch_response)

        return {"data": response_data}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/simulation/simulate/palletoncontainer/{simulateid}")
def get_palletoncontainer_data(simulateid: int, db: Session = Depends(get_db)):
    try:
        # ✅ ตรวจสอบ simulateId ว่ามีอยู่จริง
        simulate_entry = db.query(models.Simulate).filter(models.Simulate.simulateid == simulateid).first()
        if not simulate_entry:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล simulateId")

        # ✅ ดึง batch ที่เป็น container และมี sim_batch อยู่ข้างใน
        container_batches = db.query(models.Simbatch).filter(
            models.Simbatch.simulateid == simulateid,
            models.Simbatch.batchtype == "container"
        ).all()

        response_data = []
        for container_batch in container_batches:
            container_details = db.query(models.Simbatchdetail).filter(models.Simbatchdetail.batchid == container_batch.batchid).all()

            if not container_details:
                continue  # ข้าม batch ที่ไม่มีรายละเอียด

            # ✅ ดึงข้อมูล container
            container_info = {
                "batchid": container_batch.batchid,
                "batchname": f"Batch {container_batch.batchid}",
                "batchtype": container_batch.batchtype.lower(),
                "color": "#FFFFFF",
                "length": None,
                "width": None,
                "height": None,
                "loadlength": None,
                "loadwidth": None,
                "loadheight": None,
                "details": []
            }

            sim_batch_entries = []

            for container_detail in container_details:
                if container_detail.mastertype == "container":
                    container = db.query(models.Container).filter(models.Container.containerid == container_detail.masterid).first()
                    if container:
                        container_info.update({
                            "length": container.containerlength,
                            "width": container.containerwidth,
                            "height": container.containerheight,
                            "loadlength": container.loadlength,
                            "loadwidth": container.loadwidth,
                            "loadheight": container.loadheight
                        })

                elif container_detail.mastertype == "sim_batch":
                    # ✅ ดึงข้อมูล `palletoncontainer`
                    nested_batch = db.query(models.Simbatch).filter(
                        models.Simbatch.batchid == container_detail.masterid,
                        models.Simbatch.batchtype == "palletoncontainer"
                    ).first()

                    if nested_batch:
                        nested_details = db.query(models.Simbatchdetail).filter(models.Simbatchdetail.batchid == nested_batch.batchid).all()
                        nested_orders = {}
                        pallet_info = None  # ใช้เก็บข้อมูล pallet

                        for nested_detail in nested_details:
                            if nested_detail.mastertype == "pallet":
                                pallet = db.query(models.Pallet).filter(models.Pallet.palletid == nested_detail.masterid).first()
                                if pallet:
                                    pallet_info = {
                                        "length": pallet.palletlength,
                                        "width": pallet.palletwidth,
                                        "height": pallet.palletheight,
                                        "loadlength": pallet.loadlength,
                                        "loadwidth": pallet.loadwidth,
                                        "loadheight": pallet.loadheight
                                    }

                            elif nested_detail.mastertype == "product":
                                product = db.query(models.Product).filter(models.Product.productid == nested_detail.masterid).first()
                                if product:
                                    position = json.loads(nested_detail.position) if nested_detail.position else [0, 0, 0]

                                    nested_product_entry = {
                                        "batchdetailid": nested_detail.batchdetailid,
                                        "name": product.productname,
                                        "code": str(product.productid),
                                        "color": product.color or "#FFFFFF",
                                        "length": product.productlength,
                                        "width": product.productwidth,
                                        "height": product.productheight,
                                        "isfragile": product.isfragile,
                                        "issideUp": product.issideup,
                                        "istop": product.istop,
                                        "notstack": product.notstack,
                                        "masterid": product.productid,
                                        "mastertype": "product",
                                        "maxstack": product.maxstack or -1,
                                        "position": position,
                                        "rotation": nested_detail.rotation if nested_detail.rotation else 0,
                                    }


                                    if nested_detail.orderid not in nested_orders:
                                        order_entry = db.query(models.Order).filter(models.Order.orderid == nested_detail.orderid).first()
                                        order_name = order_entry.order_name if order_entry else f"Order {nested_detail.orderid}"
                                        order_number = order_entry.order_number if order_entry else f"ORD-{nested_detail.orderid}"  

                                        nested_orders[nested_detail.orderid] = {
                                            "orderid": nested_detail.orderid,
                                            "ordername": order_name,
                                            "ordernumber": order_number,
                                            "products": []
                                        }

                                    nested_orders[nested_detail.orderid]["products"].append(nested_product_entry)

                        # ✅ เพิ่ม `sim_batch` เข้าไปใน `container`
                        sim_batch_entry = {
                            "mastertype": "sim_batch",
                            "batchdetailid": nested_batch.batchid,
                            "code": str(nested_batch.batchid),
                            "name": f"Sim Batch {nested_batch.batchid}",
                            "color": "#FFFFFF",
                            "position": [0, 0, 0],
                            "rotation": 0,
                            "orders": list(nested_orders.values())
                        }

                        # ✅ ถ้ามี pallet ที่อยู่ใน palletoncontainer กำหนดค่าให้ sim_batch
                        if pallet_info:
                            sim_batch_entry.update(pallet_info)

                        sim_batch_entries.append(sim_batch_entry)

            container_info["details"].extend(sim_batch_entries)
            response_data.append(container_info)

        return {"data": response_data}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/products/upload/")
async def upload_products(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # อ่านไฟล์ Excel ด้วย Pandas
        df = pd.read_excel(file.file)

        # แปลง DataFrame เป็นรายการของ dictionary
        products_data = df.to_dict(orient="records")

        # วนลูปเพิ่มข้อมูลลงฐานข้อมูล
        for product in products_data:
            new_product = models.Product(
                productcode=product.get("productcode"),
                productname=product.get("productname"),
                productwidth=product.get("productwidth"),
                productheight=product.get("productheight"),
                productlength=product.get("productlength"),
                productweight=product.get("productweight"),
                qtt=product.get("qtt"),
                isfragile=product.get("isfragile", False),
                issideup=product.get("issideup", False),
                istop=product.get("istop", False),
                notstack=product.get("notstack", False),
                maxstack=product.get("maxstack"),
                create_by=product.get("create_by", "system"),
                color=product.get("color", "#000000"),
            )
            db.add(new_product)

        db.commit()
        return {"message": "Products uploaded successfully!"}
    except Exception as e:
        print(f"Error uploading products: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload products")

@app.post("/pallets/upload/")
async def upload_pallets(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # อ่านไฟล์ Excel
        df = pd.read_excel(file.file)

        # กำหนด Batch Size
        BATCH_SIZE = 100

        # วนลูปเพิ่มข้อมูลทีละ Batch
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            for _, row in batch.iterrows():
                new_pallet = models.Pallet(
                    palletcode=row.get("palletcode"),
                    palletname=row.get("palletname"),
                    palletwidth=row.get("palletwidth"),
                    palletheight=row.get("palletheight"),
                    palletlength=row.get("palletlength"),
                    palletweight=row.get("palletweight"),
                    loadwidth=row.get("loadwidth"),
                    loadheight=row.get("loadheight"),
                    loadlength=row.get("loadlength"),
                    loadweight=row.get("loadweight"),
                    qtt=row.get("qtt"),
                    createby=row.get("createby", "system"),
                    createdate=datetime.utcnow(),
                    color=row.get("color", "#FFFFFF"),
                )
                db.add(new_pallet)
            db.commit()  # Commit หลังจากเพิ่มข้อมูลแต่ละ Batch

        return {"message": "Pallets uploaded successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error uploading pallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload pallets")
    
@app.post("/containers/upload/")
async def upload_containers(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # อ่านไฟล์ Excel
        df = pd.read_excel(file.file)

        # กำหนด Batch Size
        BATCH_SIZE = 100

        # วนลูปเพิ่มข้อมูลทีละ Batch
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            for _, row in batch.iterrows():
                new_container = models.Container(
                    containercode=row.get("containercode"),
                    containername=row.get("containername"),
                    containerwidth=row.get("containerwidth"),
                    containerheight=row.get("containerheight"),
                    containerlength=row.get("containerlength"),
                    containerweight=row.get("containerweight"),
                    loadwidth=row.get("loadwidth"),
                    loadheight=row.get("loadheight"),
                    loadlength=row.get("loadlength"),
                    loadweight=row.get("loadweight"),
                    qtt=row.get("qtt"),
                    createby=row.get("createby", "system"),
                    createdate=datetime.utcnow(),
                    color=row.get("color", "#FFFFFF"),
                )
                db.add(new_container)
            db.commit()  # Commit หลังจากเพิ่มข้อมูลแต่ละ Batch

        return {"message": "Containers uploaded successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error uploading containers: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload containers")
    


@app.post("/orders/upload/")
async def upload_orders(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # อ่านไฟล์ Excel
        df = pd.read_excel(file.file)

        # วนลูปเพิ่มข้อมูล Order
        for _, row in df.iterrows():
            # ตรวจสอบว่าสินค้าของ Order มีอยู่ในระบบหรือไม่
            product = db.query(models.Product).filter(models.Product.productid == row.get("productid")).first()
            if not product:
                raise HTTPException(status_code=400, detail=f"Product ID {row.get('productid')} not found")

            # สร้าง Order ใหม่
            new_order = models.Order(
                order_number=row.get("order_number"),
                order_name=row.get("order_name"),
                create_by=row.get("create_by", "system"),
                deliveryby=row.get("deliveryby"),
                send_date=row.get("send_date"),
                create_date=datetime.utcnow(),
            )
            db.add(new_order)
            db.commit()
            db.refresh(new_order)

            # เพิ่มรายการสินค้า (OrderList)
            new_order_item = models.OrderList(
                orderid=new_order.orderid,
                productid=row.get("productid"),
                qtt=row.get("qtt"),
                send_date=row.get("send_date"),
            )
            db.add(new_order_item)
        
        db.commit()  # Commit ทั้งหมดหลังจากเพิ่มข้อมูล
        return {"message": "Orders uploaded successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error uploading orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload orders")


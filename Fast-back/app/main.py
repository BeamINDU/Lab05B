from fastapi import FastAPI
from .database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from .routes import (
    products_routes,
    packages_routes,
    orders_routes,
    simulate_routes,
    reports_routes,
    tasks_routes,
)


load_dotenv()  # โหลดค่าจากไฟล์ .env

# สร้างตาราง
Base.metadata.create_all(bind=engine)
BASE_PATH = os.getenv("PYTHONPATH", ".")
FRONT_URL = os.getenv("FRONT_URL", "http://192.168.11.97:3000")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        FRONT_URL,
    ],  # เพิ่ม URL Frontend ที่อนุญาต
    allow_credentials=True,
    allow_methods=["*"],  # อนุญาตทุก HTTP Methods (เช่น GET, POST, DELETE, PUT)
    allow_headers=["*"],  # อนุญาตทุก Headers
)


app.include_router(simulate_routes, prefix="/simulation")
app.include_router(products_routes, prefix="/products")
app.include_router(packages_routes, prefix="/packages")
app.include_router(orders_routes, prefix="/orders")
app.include_router(reports_routes, prefix="/reports")
app.include_router(tasks_routes, prefix="/tasks")

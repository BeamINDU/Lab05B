from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Double, ForeignKey,Table
from datetime import datetime
from .database import Base
from sqlalchemy.dialects.postgresql import UUID,JSONB
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.schema import ForeignKeyConstraint



class Product(Base):
	__tablename__ = "product"

	productid = Column(Integer, primary_key=True, autoincrement=True)  # ชื่อฟิลด์ต้องตรงกับฐานข้อมูล
	productcode = Column(String(255), nullable=False)
	productname = Column(String, nullable=False)
	productwidth = Column(Float, nullable=False)
	productheight = Column(Float, nullable=False)
	productlength = Column(Float, nullable=False)
	productweight = Column(Float, nullable=False)
	qtt = Column(Integer, nullable=False)
	isfragile = Column(Boolean, default=False)
	issideup = Column(Boolean, default=False)
	istop = Column(Boolean, default=False)
	notstack = Column(Boolean, default=False)
	maxstack = Column(Integer, nullable=True)
	create_by = Column(String, nullable=True)
	create_date = Column(DateTime, default=None)
	update_by = Column(String, nullable=True)
	update_date = Column(DateTime, default=None)
	color = Column(String(255), default="#000000")  # เพิ่มฟิลด์นี้
	is_deleted = Column(Boolean, default=False) 
	deleted_at = Column(DateTime, nullable=True) 



class Pallet(Base):
	__tablename__ = "pallet"
	__table_args__ = {"extend_existing": True}  # เพิ่ม extend_existing=True

	palletid = Column(Integer, primary_key=True, index=True, nullable=False)
	palletname = Column(String, nullable=False)
	palletwidth = Column(Float, nullable=True)
	palletheight = Column(Float, nullable=True)
	palletlength = Column(Float, nullable=True)
	palletweight = Column(Float, nullable=True)
	loadwidth = Column(Float, nullable=True)
	loadheight = Column(Float, nullable=True)
	loadlength = Column(Float, nullable=True)
	loadweight = Column(Float, nullable=True)
	qtt = Column(Float, nullable=True)
	createby = Column(String, nullable=True)
	updateby = Column(String, nullable=True)
	updatedate = Column(DateTime, nullable=True)
	createdate = Column(DateTime, nullable=True)
	palletcode = Column(String, nullable=True)
	palletsize = Column(String,nullable=True)
	is_deleted = Column(Boolean, default=False)
	color = Column(String(255), nullable=True)
	deleted_at = Column(DateTime, nullable=True)

class Container(Base):
	__tablename__ = "container"
	
	containerid = Column(Integer, primary_key=True, nullable=False)
	containername = Column(String, nullable=False)
	containerwidth = Column(Float, nullable=True)
	containerheight = Column(Float, nullable=True)
	containerlength = Column(Float, nullable=True)
	containerweight = Column(Float, nullable=True)
	loadwidth = Column(Float, nullable=True)
	loadheight = Column(Float, nullable=True)
	loadlength = Column(Float, nullable=True)
	loadweight = Column(Float, nullable=True)
	qtt = Column(Integer, nullable=True)
	createby = Column(String, nullable=True)
	updateby = Column(String, nullable=True)
	updatedate = Column(DateTime, nullable=True)
	createdate = Column(DateTime, nullable=True)
	containercode = Column(String, nullable=True)
	containersize = Column(String , nullable = True)
	is_deleted = Column(Boolean, default=False)
	color = Column(String(255), nullable=True)
	deleted_at = Column(DateTime, nullable=True)


class Order(Base):
	__tablename__ = "orders"

	orderid = Column(Integer, primary_key=True, nullable=False)
	order_number = Column(String)
	order_name = Column(String, nullable=False)
	create_by = Column(String, nullable=False)
	deliveryby = Column(String, nullable=False)
	send_date = Column(DateTime, nullable=False)
	create_date = Column(DateTime, default=datetime.utcnow)
	update_date = Column(DateTime, onupdate=datetime.utcnow)
	
	simulatedetails = relationship("Simulatedetail", back_populates="order", cascade="all, delete-orphan")
	# เพิ่ม relationship ไปยัง OrderList
	items = relationship(
		"OrderList", 
		back_populates="order", 
		cascade="all, delete-orphan"
	)
      

	
class OrderList(Base):
    __tablename__ = "order_detail"
    __table_args__ = (
        ForeignKeyConstraint(["orderid"], ["orders.orderid"]),
        ForeignKeyConstraint(["productid"], ["product.productid"]),
    )
    orderid = Column(Integer, ForeignKey("orders.orderid"))
    productid = Column(Integer, ForeignKey("product.productid"))
    qtt = Column(Integer, nullable=False)
    send_date = Column(DateTime, nullable=True)
    order_name = Column(String, nullable=True)
    detailid = Column(Integer, primary_key=True, autoincrement=True)

    # ความสัมพันธ์
    order = relationship("Order", back_populates="items")
    product = relationship("Product", lazy="joined")  

class Simbatch(Base):
    __tablename__ = "sim_batch"

    batchid = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    simulateid = Column(Integer, ForeignKey("simulate.simulateid"), nullable=False)
    batchtype = Column(String, nullable=False)  
    head = Column(Integer,nullable=True)
    simulate = relationship("Simulate", back_populates="batches")
    details = relationship("Simbatchdetail", back_populates="batch", cascade="all, delete-orphan")





class Simbatchdetail(Base):
    __tablename__ = "sim_batch_detail"

    batchdetailid = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    batchid = Column(Integer, ForeignKey("sim_batch.batchid"), nullable=False)
    simulateid = Column(Integer, ForeignKey("simulate.simulateid"), nullable=False)
    orderid = Column(Integer, ForeignKey("orders.orderid") ,nullable=False)
    mastertype = Column(String(255), nullable=False)  # ระบุว่าเป็น Product หรืออื่นๆ
    masterid = Column(String, nullable=False)  # Product ID หรือ Container ID
    position = Column(JSONB, nullable=False)  # ✅ เปลี่ยนเป็น JSONB แทน String
    rotation = Column(Integer, nullable=False, default=0)  # ทิศทางของสินค้า
    total_weight = Column(Float, nullable=False, default=0.0)  

    batch = relationship("Simbatch", back_populates="details")


class Simulate(Base):
    __tablename__ = "simulate"

    simulateid = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    simulatetype = Column(String, nullable=False)
    status = Column(String, nullable=False)
    simulateby = Column(String, nullable=False)
    simulatedatetime = Column(DateTime, nullable=False)

    # ความสัมพันธ์กับ Simulatedetail (1 ต่อ หลาย)
    details = relationship("Simulatedetail", back_populates="simulate", cascade="all, delete-orphan")
    batches = relationship("Simbatch", back_populates="simulate", cascade="all, delete-orphan")

class Simulatedetail(Base):
    __tablename__ = "simulate_detail"

    simdetailid = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    simulateid = Column(Integer, ForeignKey("simulate.simulateid"), nullable=False)
    orderid = Column(Integer, ForeignKey("orders.orderid"), nullable=False)  # ✅ เพิ่ม ForeignKey

    # ความสัมพันธ์กับ Simulate (หลาย ต่อ 1)
    simulate = relationship("Simulate", back_populates="details")
    order = relationship("Order", back_populates="simulatedetails")  # เพิ่ม Relationship

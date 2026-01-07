from pydantic import BaseModel, Field
from typing import Optional, Union
from sqlalchemy import DateTime
from datetime import datetime
from typing import List

def to_camel(string: str) -> str:
    """Helper function to convert snake_case to camelCase"""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])
class ProductCreate(BaseModel):
    productcode: str = Field(alias="productCode")
    productname: str = Field(alias="productName")
    productwidth: float = Field(alias="productWidth")
    productheight: float = Field(alias="productHeight")
    productlength: float = Field(alias="productLength")
    productweight: float = Field(alias="productWeight")
    qtt: int
    isfragile: bool = Field(default=False, alias="isFragile")
    issideup: bool = Field(default=False, alias="isSideUp")
    istop: bool = Field(default=False, alias="isTop")
    notstack:bool= Field(default=False, alias="notstack")
    maxstack:int
    create_by: str = Field(default="system", alias="createby")
    color: Optional[str] = "#000000"

    class Config:
        populate_by_name = True
        from_attributes = True

class ProductUpdate(BaseModel):
    productid: Optional[str] = None  
    productcode: Optional[str] = Field(None, alias="productCode")
    productname: Optional[str] = Field(None, alias="productName")
    productwidth: Optional[float] = Field(None, alias="productWidth")
    productheight: Optional[float] = Field(None, alias="productHeight")
    productlength: Optional[float] = Field(None, alias="productLength")
    productweight: Optional[float] = Field(None, alias="productWeight")
    qtt: Optional[int] = None
    isfragile: Optional[bool] = Field(None, alias="isFragile")
    issideup: Optional[bool] = Field(None, alias="isSideUp")
    istop: Optional[bool] = Field(None, alias="isTop")
    notstack: Optional[bool] = Field(None, alias="notstack")
    maxstack: Optional[int] = None
    color: Optional[str] = Field(default="#000000")

    class Config:
        orm_mode = True
        populate_by_name = True  # ✅ ต้องใส่เพื่อให้ alias ทำงาน
        alias_generator = to_camel  # ✅ แปลง `snake_case` เป็น `camelCase` อัตโนมัติ

class Product(BaseModel):
    productid: str
    productcode: Optional[str]
    productname: str
    productwidth: float
    productheight: float
    productlength: float
    productweight: float
    qtt: int
    isfragile: Optional[bool] = False
    issideup: Optional[bool] = False
    istop: Optional[bool] = False
    notstack:Optional[bool] = False
    maxstack:int
    create_by: Optional[str] = "system"  # ตั้งค่าเริ่มต้นเป็น "system" หากไม่มีข้อมูลจาก frontend
    create_date: Optional[datetime] = None
    update_by: Optional[str] = None
    update_date: Optional[datetime] = None
    color: Optional[str] = "#000000"  # เพิ่มฟิลด์นี้


    class Config:
        from_attributes = True


#----Pallet-----
class PalletBase(BaseModel):
    palletid: str
    palletcode: str
    palletname: str
    palletwidth: Optional[float]
    palletheight: Optional[float]
    palletlength: Optional[float]
    palletweight: Optional[float]
    loadwidth: Optional[float]
    loadheight: Optional[float]
    loadlength: Optional[float]
    loadweight: Optional[float]
    qtt: Optional[float]
    createby: Optional[str]
    createdate: Optional[datetime]
    updateby: Optional[str]
    updatedate: Optional[datetime]
    color: Optional[str] = "#000000"
    palletsize : Optional[str]


class PalletCreate(BaseModel):
    palletcode: str 
    palletname: str
    palletwidth: Optional[float] = None
    palletheight: Optional[float] = None
    palletlength: Optional[float] = None
    palletweight: Optional[float] = None
    loadwidth: Optional[float] = None
    loadheight: Optional[float] = None
    loadlength: Optional[float] = None
    loadweight: Optional[float] = None
    qtt: Optional[float] = None
    createby: Optional[str] = "system"
    createdate: Optional[datetime] = None
    updateby: Optional[str] = None
    updatedate: Optional[datetime] = None
    color: Optional[str] = "#000000"
    palletsize : Optional[str] = "Custom"

    class Config:
        from_attributes = True

class PalletUpdate(BaseModel):
    palletname: Optional[str] = None  # เปลี่ยนให้ palletname เป็น Optional
    palletwidth: Optional[float] = None
    palletheight: Optional[float] = None
    palletlength: Optional[float] = None
    palletweight: Optional[float] = None
    loadwidth: Optional[float] = None
    loadheight: Optional[float] = None
    loadlength: Optional[float] = None
    loadweight: Optional[float] = None
    qtt: Optional[float] = None
    createby: Optional[str] = None
    updateby: Optional[str] = None
    updatedate: Optional[datetime] = None
    createdate: Optional[datetime] = None
    palletcode: Optional[str] = None
    palletsize : Optional[str] = None
    is_deleted: Optional[bool] = False
    color: Optional[str] = "#000000"
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

#-------Container----------
class ContainerBase(BaseModel):
    containerid: str
    containercode: str
    containername: str
    containerwidth: Optional[float]
    containerheight: Optional[float]
    containerlength: Optional[float]
    containerweight: Optional[float]
    loadwidth: Optional[float]
    loadheight: Optional[float]
    loadlength: Optional[float]
    loadweight: Optional[float]
    qtt: Optional[int]
    containersize: Optional[str]
    createby: Optional[str]
    createdate: Optional[datetime]
    updateby: Optional[str]
    updatedate: Optional[datetime]
    color: Optional[str] = "#000000"


class ContainerCreate(BaseModel):
    containercode: str 
    containername: str
    containerwidth: Optional[float] = None
    containerheight: Optional[float] = None
    containerlength: Optional[float] = None
    containerweight: Optional[float] = None
    loadwidth: Optional[float] = None
    loadheight: Optional[float] = None
    loadlength: Optional[float] = None
    loadweight: Optional[float] = None
    qtt: Optional[int] = None
    containsize: Optional[str] = "Custom"
    createby: Optional[str] = "system"
    createdate: Optional[datetime] = None
    updateby: Optional[str] = None
    updatedate: Optional[datetime] = None
    color: Optional[str] = "#000000"

    class Config:
        from_attributes = True

class ContainerUpdate(BaseModel):
    containername: Optional[str] = None  # เปลี่ยนให้ containername เป็น Optional
    containerwidth: Optional[float] = None
    containerheight: Optional[float] = None
    containerlength: Optional[float] = None
    containerweight: Optional[float] = None
    loadwidth: Optional[float] = None
    loadheight: Optional[float] = None
    loadlength: Optional[float] = None
    loadweight: Optional[float] = None
    qtt: Optional[int] = None
    containersize: Optional[str] = None
    createby: Optional[str] = None
    updateby: Optional[str] = None
    updatedate: Optional[datetime] = None
    createdate: Optional[datetime] = None
    containercode: Optional[str] = None
    is_deleted: Optional[bool] = False
    color: Optional[str] = "#000000"
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

#--------------------------------------
class OrderListCreate(BaseModel):
    productid: Union[int, str]  # รองรับทั้ง `int` และ `str`
    productcode: Optional[str] = None
    productname: Optional[str] = None
    qtt: int
    productlength: Optional[float] = None
    productwidth: Optional[float] = None
    productheight: Optional[float] = None
    productweight: Optional[float] = None
    color: Optional[str] = None
    send_date: Optional[datetime] = None  # เปลี่ยนเป็น Optional
    class Config:
        orm_mode = True

class OrderCreate(BaseModel):
    order_name: str
    order_number: Optional[str] = None  
    create_by: str
    deliveryby: str
    send_date: datetime
    products: List[OrderListCreate]
class OrderRead(BaseModel):
    orderid: Union[int, str]
    order_number: Optional[str] = None
    order_name: str
    create_by: str
    deliveryby: str
    send_date: datetime
    create_date: Optional[datetime]
    update_date: Optional[datetime] = None  # ตั้งค่าเริ่มต้นเป็น None
    products: Optional[List[OrderListCreate]] = None  # ใช้ Schema ใหม่

    class Config:
        orm_mode = True

class OrderUpdate(BaseModel):
    order_name: Optional[str] = None
    send_date: Optional[datetime] = None
    products: Optional[List[OrderListCreate]] = None  # ใช้ Schema ของ Products ที่คุณมีอยู่แล้ว
    deleted_products: Optional[List[Union[str, dict]]] = None  # ฟิลด์ใหม่สำหรับรายการสินค้าที่ถูกลบ
    new_products: Optional[List[OrderListCreate]] = None  # เพิ่มฟิลด์นี้
    existing_products: Optional[List[OrderListCreate]] = None  # เพิ่มสินค้าที่มีอยู่แล้ว

    class Config:
        orm_mode = True


class OrderRequest(BaseModel):
    orderid: str

class OrdersResponse(BaseModel):
    items: List[OrderRead]
    total_count: int

class SimBatchCreate(BaseModel):
    simulateid: int
    simulateType: str  # Pallet หรือ Container
    batchTypeId: int  # เก็บ palletid หรือ containerid

class SimBatchDetailCreate(BaseModel):
    batchid: int
    simulateid: int
    orderid: str
    masterType: str  # "Product"
    masterid: int
    position: List[float]  # ค่าพิกัด
    rotation: int

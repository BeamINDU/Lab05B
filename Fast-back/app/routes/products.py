import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy import func, select
from ..database import get_db
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from psycopg2 import errors
from .. import models, schemas, crud
import pandas as pd

router = APIRouter(tags=["Products"])


@router.get("/", response_model=schemas.ProductsResponse)
def read_products(skip: int = 0, limit: int = None, db: Session = Depends(get_db)):
    try:
        total_count = db.scalar(
            select(func.count())
            .select_from(models.Product)
            .filter(models.Product.is_deleted == False)
        )
        return {
            "items": crud.read_products(db, skip, limit),
            "total_count": total_count,
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/new-color/")
def get_distinct_productcolor(db: Session = Depends(get_db)):
    try:
        return crud.get_distinct_color(models.Product, db)

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/", response_model=schemas.ProductBase)
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    try:
        # new_product = crud.upsert_product(db, product)
        new_product = crud.insert_product(db, product)
        db.commit()
        return new_product
    except IntegrityError as e:
        print("Error during product creation:", e.orig)
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(status_code=500, detail="Product already exists.")
        raise HTTPException(
            status_code=500, detail=f"Error during product creation: {str(e.orig)}"
        )


@router.put("/{product_id}", response_model=schemas.updateResponse)
async def update_product(
    product_id: str, product: schemas.ProductUpdate, db: Session = Depends(get_db)
):
    try:
        result = crud.update_product(db, product, product_id)
        return result
    except IntegrityError as e:
        print("Error during product creation:", e.orig)
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(
                status_code=500, detail=[{"msg": "Product already exists."}]
            )
        raise HTTPException(
            status_code=500,
            detail=[{"msg": "Error during product creation: " + str(e.orig)}],
        )


@router.delete("/", response_model=schemas.deleteResponse)
def delete_product(product_ids: list[int], db: Session = Depends(get_db)):
    try:
        result = crud.soft_delete_product(db, product_ids)
        return result
    except Exception as e:
        print(f"Error in soft delete product: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/{product_id}/restore", response_model=schemas.restoreResponse)
def restore_product_api(product_id: str, db: Session = Depends(get_db)):
    try:
        result = crud.restore_product(db, product_id)
        return result
    except Exception as e:
        print(f"Error in restore_product_api: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/upload/", response_model=schemas.uploadResponse)
async def upload_products(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file.file)
        elif file.filename.endswith(".xlsx") or file.filename.endswith(".xls"):
            df = pd.read_excel(file.file)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only CSV and Excel supported.",
            )

        df_replaced = df.replace({np.nan: None})

        products_data = df_replaced.to_dict(orient="records")

        new_colors = []

        for product in products_data:
            product_clean = {k: v for k, v in product.items() if v is not None}

            if product_clean.get("color") is None:
                product_clean["color"] = crud.get_distinct_color(
                    models.Product, db, new_colors
                )

            new_colors.append(product_clean["color"])

            crud.insert_product(db, schemas.ProductCreate(**product_clean))
        db.commit()
        return {"message": "Products uploaded successfully!"}
    except IntegrityError as e:
        # print("Error during product creation:", e.orig)
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(status_code=500, detail="Product already exists.")
        raise HTTPException(
            status_code=500, detail=f"Error during product creation: {str(e.orig)}"
        )
    except Exception as e:
        print(f"Error uploading products: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload products")

import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy import select
from ..database import get_db
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from psycopg2 import errors
from app import models, schemas, crud, factories
import pandas as pd

router = APIRouter(tags=["Packages"])


@router.get("/{packageType}", response_model=schemas.PackageResponse)
def read_packages(
    packageType: models.PackageType,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    try:
        total_count = db.scalar(
            select(func.count())
            .select_from(models.PackageBase)
            .filter(
                models.PackageBase.is_deleted == False,
                models.PackageBase.package_type == packageType,
            )
        )
        return {
            "items": crud.read_packages(db, packageType, skip, limit),
            "total_count": total_count,
        }
    except Exception as e:
        print(f"Error in reading packages: {e}")
        raise HTTPException(status_code=500, detail=f"Error in reading packages: {e}")


@router.get("/{packageType}/new-color/")
def get_distinct_packagecolor(
    packageType: models.PackageType, db: Session = Depends(get_db)
):
    try:
        return crud.get_distinct_color(models.PackageBase, db, packageType=packageType)

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/", response_model=schemas.PackageBase)
def create_packages(package: schemas.PackageCreate, db: Session = Depends(get_db)):
    try:
        # new_package = crud.upsert_package(db, package)
        new_package = crud.insert_package(db, package)
        db.commit()
        return new_package
    except IntegrityError as e:
        print("Error during package creation:", e.orig)  # Debug Exception
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(status_code=500, detail="Package already exists.")
        raise HTTPException(
            status_code=500, detail=f"Error during package creation: {str(e.orig)}"
        )
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=500, detail=f"Error during package creation: {e}"
        )


@router.put("/{package_id}", response_model=schemas.updateResponse)
def update_package(
    package_id: str, package: schemas.PackageUpdate, db: Session = Depends(get_db)
):
    try:
        result = crud.update_package(db, package, package_id)
        return result
    except IntegrityError as e:
        print("Error during package update:", e.args)  # Debug Exception
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(
                status_code=500,
                detail=[{"msg": "Package already exists.", "error": e.args}],
            )
        raise HTTPException(
            status_code=500,
            detail=[{"msg": "Error during package update: " + str(e.orig)}],
        )
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=500, detail=f"Error during package update: {e}")


@router.delete("/", response_model=schemas.deleteResponse)
def delete_packages(package_id: list[int], db: Session = Depends(get_db)):
    return crud.soft_delete_packages(db, package_id)


@router.put("/{package_id}/restore", response_model=schemas.restoreResponse)
def restore_package_api(package_id: str, db: Session = Depends(get_db)) -> dict:
    return crud.restore_package(db, package_id)


@router.post("/{packageType}/upload/", response_model=schemas.uploadResponse)
async def upload_packages(
    packageType: models.PackageType,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
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

        package_data = df_replaced.to_dict(orient="records")

        factory = factories.PackageFactory.get_factory(packageType)

        new_colors = []

        for package in package_data:
            package_clean = {k: v for k, v in package.items() if v is not None}

            if package_clean.get("color") is None:
                package_clean["color"] = crud.get_distinct_color(
                    models.PackageBase, db, new_colors, packageType
                )

            new_colors.append(package_clean["color"])

            crud.insert_package(db, factory.create_create_model(package_clean))
        db.commit()

        return {"message": "Packages uploaded successfully"}
    except IntegrityError as e:
        print("Error during package creation:", e.orig)  # Debug Exception
        db.rollback()
        if isinstance(e.orig, errors.UniqueViolation):
            raise HTTPException(status_code=500, detail="Package already exists.")
        raise HTTPException(
            status_code=500, detail=f"Error during package creation: {str(e.orig)}"
        )
    except Exception as e:
        db.rollback()
        print(f"Error uploading packages: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload packages")

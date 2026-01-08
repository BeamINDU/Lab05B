# ใช้ Python 3.10 เป็น Base Image
FROM python:3.11.9


# ตั้งค่า Working Directory
WORKDIR /app

# คัดลอกไฟล์ requirements และติดตั้ง dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y libopenblas-dev && \
    pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมดไปยัง Container
COPY . .

# เปิดพอร์ต 8000
EXPOSE 8000

ENV NUMBA_CACHE_DIR=/tmp/numba_cache
RUN mkdir -p /tmp/numba_cache && chmod -R 777 /tmp/numba_cache


# คำสั่งรัน FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--reload"]



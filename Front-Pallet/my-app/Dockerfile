# ใช้ Node.js เป็น Base Image
FROM node:22

# ตั้งค่าที่ทำงานใน Container
WORKDIR /app

# Copy ไฟล์ package.json และ package-lock.json (ถ้ามี)
COPY package.json package-lock.json ./

# ติดตั้ง dependencies ด้วย npm
RUN npm install --legacy-peer-deps --no-optional --only=production

# Copy โค้ดทั้งหมดเข้าไปใน Container
COPY . .

# สร้าง Production Build (ถ้าใช้ Next.js)
RUN npm run build

# เปิดพอร์ตสำหรับเซิร์ฟเวอร์
EXPOSE 3000

# คำสั่งรันแอป
CMD ["npm", "start"]

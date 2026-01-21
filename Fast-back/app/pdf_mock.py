from fpdf import FPDF
from datetime import datetime

def create_report(simdata: dict, simId: int):
    """
    สร้าง PDF จาก Mock Data (Lab05B nested structure)
    
    Args:
        simdata: dict - ข้อมูลจาก get_simulation_data() (mock)
        simId: int - simulate_id
    """
    
    pdf = PDF()
    pdf.add_page()
    
    # หน้า 1: Summary
    create_summary_page(pdf, simdata, simId)
    
    # หน้า 2+: Package details
    data = simdata.get("data", [])
    for package in data:
        pdf.add_page()
        render_package_detail(pdf, package)
    
    # บันทึกไฟล์
    pdf.output(f"/pdf/{simId}.pdf")
    print(f"✅ PDF created: /pdf/{simId}.pdf")


def create_summary_page(pdf: FPDF, simdata: dict, simId: int):
    """สร้างหน้าสรุป"""
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Lab05B Simulation Report", ln=True, align="C")
    pdf.ln(10)
    
    # Simulation info
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Simulation Information:", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 10)
    info = [
        ("Simulate ID:", str(simId)),
        ("Simulate By:", simdata.get("simulate_by", "Unknown")),
        ("Type:", simdata.get("simulatetype", "Unknown")),
        ("Date:", str(simdata.get("start_datetime", "Unknown"))[:19]),
        ("Status:", simdata.get("simulate_status", "Unknown")),
    ]
    
    for label, value in info:
        pdf.cell(60, 8, label, border=1)
        pdf.cell(0, 8, value, border=1, ln=True)
    
    pdf.ln(10)
    
    # Package summary
    data = simdata.get("data", [])
    total_packages = count_packages(data)
    total_products = count_products(data)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Summary:", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Total Packages: {total_packages}", ln=True)
    pdf.cell(0, 8, f"Total Products: {total_products}", ln=True)


def render_package_detail(pdf: FPDF, package: dict, level: int = 0):
    """แสดงรายละเอียด package (recursive)"""
    indent = "  " * level
    
    # Package header
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"{indent}Package: {package.get('package_name', 'Unknown')}", ln=True)
    
    # Package details
    pdf.set_font("Arial", "", 9)
    details = [
        f"Type: {package.get('package_type', 'Unknown')}",
        f"Code: {package.get('package_code', 'N/A')}",
        f"Dimensions: {package.get('package_length')} x {package.get('package_width')} x {package.get('package_height')} mm",
        f"Weight: {package.get('package_weight')} kg",
        f"Utilization: {package.get('utilize_weight_percent', 0):.1f}% (Weight), {package.get('utilize_cap_percent', 0):.1f}% (Volume)",
    ]
    
    for detail in details:
        pdf.cell(0, 6, f"{indent}  {detail}", ln=True)
    
    pdf.ln(3)
    
    # Orders
    orders = package.get('orders', [])
    if orders:
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 8, f"{indent}  Orders:", ln=True)
        
        for order in orders:
            pdf.set_font("Arial", "", 9)
            pdf.cell(0, 6, f"{indent}    - {order.get('orders_name', 'Unknown')} ({order.get('orders_number', 'N/A')})", ln=True)
            
            products = order.get('products', [])
            if products:
                pdf.set_font("Arial", "", 8)
                pdf.cell(0, 5, f"{indent}      Products: {len(products)} items", ln=True)
        
        pdf.ln(3)
    
    # Child packages (recursive)
    children = package.get('child_detail', [])
    for child in children:
        render_package_detail(pdf, child, level + 1)


def count_packages(data: list) -> int:
    """นับจำนวน packages ทั้งหมด"""
    count = 0
    for package in data:
        count += 1
        count += count_packages(package.get('child_detail', []))
    return count


def count_products(data: list) -> int:
    """นับจำนวน products ทั้งหมด"""
    count = 0
    for package in data:
        orders = package.get('orders', [])
        for order in orders:
            count += len(order.get('products', []))
        count += count_products(package.get('child_detail', []))
    return count


class PDF(FPDF):
    """Custom PDF class with header and footer"""
    
    def header(self):
        self.set_font("Arial", "B", 10)
        self.cell(0, 10, "Lab05B - Pallet Optimization Report", border=0, ln=True, align="C")
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
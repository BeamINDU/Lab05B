"use client";

import React from "react";
import jsPDF from "jspdf";

interface Product {
  id: number;
  name: string;
  color: string;
}

interface PalletDetail {
  id: string;
  palletNo: string;
  palletname: string;
  orderNo: string;
  products: Product[];
}

interface ExportPDFData {
  createOrderBy: string;
  createOrderDate: string;
  sendDate: string;
  simulateBy: string;
  simulateDate: string;
  palletDetails: PalletDetail[];
}

interface ExportPDFProps {
  data: ExportPDFData;
  canvasImage: string | null; // รูป 3D ที่อัปเดตล่าสุด
  captureImage: () => string | null; // ฟังก์ชันจับภาพ 3D
}

const ExportPDF: React.FC<ExportPDFProps> = ({
  data,
  canvasImage,
  captureImage,
}) => {
  const generatePDF = (): void => {
    const updatedImage =
      typeof captureImage === "function" ? captureImage() : canvasImage; // ตรวจสอบว่า captureImage เป็นฟังก์ชัน
    const pdf = new jsPDF("p", "mm", "a4");
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const margin = 10;
    const tableWidth = pageWidth / 2 - margin * 2;

    console.log("Generating PDF...");

    // **Header Section**
    pdf.setFontSize(18);
    pdf.text("Work sheet", pageWidth / 2, 15, { align: "center" });

    pdf.setFontSize(12);
    pdf.text(`Create Order By: ${data.createOrderBy}`, margin, 30);
    pdf.text(`Create Order Date: ${data.createOrderDate}`, margin + 60, 30);
    pdf.text(`Send Date: ${data.sendDate}`, margin + 120, 30);
    pdf.text(`Simulate By: ${data.simulateBy}`, margin, 40);
    pdf.text(`Simulate Date: ${data.simulateDate}`, margin + 60, 40);

    console.log("Header section completed.");

    // **Pallet Details Section**
    data.palletDetails.forEach((pallet, index) => {
      if (index > 0) pdf.addPage();

      pdf.line(margin, 45, pageWidth - margin, 45);
      pdf.setFontSize(14);
      pdf.text("Pallet Detail", pageWidth / 2, 50, { align: "center" });

      pdf.setFontSize(12);
      pdf.text(`No.: ${pallet.id}`, margin, 60);
      pdf.text(`Pallet No: ${pallet.palletNo}`, margin + 40, 60);
      pdf.text(`Pallet Name: ${pallet.palletname}`, margin + 100, 60);
      pdf.text(`Order No: ${pallet.orderNo}`, margin, 70);

      pdf.line(margin, 75, pageWidth - margin, 75);
      pdf.text("ID", margin, 80);
      pdf.text("Product Name", margin + 20, 80);
      pdf.text("Color", margin + tableWidth - 20, 80);

      let currentY = 90;
      pallet.products.forEach((product) => {
        pdf.text(`${product.id}`, margin, currentY);
        pdf.text(`${product.name}`, margin + 20, currentY);

        // Add color block
        pdf.setFillColor(product.color);
        pdf.rect(margin + tableWidth - 20, currentY - 5, 6, 6, "F");

        currentY += 10;
      });

      // Add 3D Model image on the right
      if (updatedImage) {
        const imageX = pageWidth / 2 + margin;
        const imageY = 60;
        const imageWidth = pageWidth / 2 - margin * 2;
        const imageHeight = Math.min(100, pageHeight - imageY - 20);
        pdf.addImage(
          updatedImage,
          "PNG",
          imageX,
          imageY,
          imageWidth,
          imageHeight
        );
      } else {
        pdf.text(
          "3D Model section could not be captured.",
          pageWidth / 2 + margin,
          currentY
        );
      }

      pdf.setFontSize(10);
      pdf.text(
        `Page ${index + 1} of ${data.palletDetails.length}`,
        pageWidth / 2,
        pageHeight - 10,
        { align: "center" }
      );
    });

    pdf.save("Work_sheet_with_3D.pdf");
  };

  return (
    <button
      onClick={generatePDF}
      className="px-4 py-2 bg-[#004798] text-white rounded hover:bg-blue-800"
    >
      Print
    </button>
  );
};

export default ExportPDF;

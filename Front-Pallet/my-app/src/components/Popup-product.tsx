"use client";
import React, { useState, useEffect } from "react";
import Image from "next/image";
// import { notStrictEqual } from "assert";

type ProductData = {
  productid?: string;
  productcode: string;
  productname: string;
  productwidth: string;
  productheight: string;
  productlength: string;
  productweight: string;
  qtt: number;
  isfragile: boolean;
  issideup: boolean;
  istop: boolean;
  notstack: boolean;
  maxstack: number;
  create_by: string;
  color: string;
};

type ModalProductFormProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Product) => void;
  productData?: Product;
  fetchProducts: () => void;
};

const ModalProductForm: React.FC<ModalProductFormProps> = ({
  isOpen,
  onClose,
  // onSave,
  productData,
  fetchProducts,
}) => {
  const [formData, setFormData] = useState<ProductData>({
    productcode: "",
    productname: "",
    productwidth: "",
    productheight: "",
    productlength: "",
    productweight: "",
    qtt: 0,
    isfragile: false,
    issideup: false,
    istop: false,
    notstack: false, // Correct casing for backend
    maxstack: 0, // Correct casing for backend
    create_by: "system",
    color: "#000000",
  });

  // const [error, setError] = useState<string | null>(null);

  const symbols = [
    { value: "isfragile", icon: "/icon/fragile.svg" },
    { value: "issideup", icon: "/icon/side_up.svg" },
    { value: "istop", icon: "/icon/top.svg" },
    { value: "notstack", icon: "/icon/top.svg" },
  ];
  const apiUrl = process.env.NEXT_PUBLIC_API_URL; 

  useEffect(() => {
    if (productData) {
      // console.log("Product data loaded into form:", productData); // Debug
      setFormData({
        productcode: productData.productcode || "",
        productname: productData.productname || "",
        productwidth: `${productData.productwidth}` || "",
        productheight: `${productData.productheight}` || "",
        productlength: `${productData.productlength}` || "",
        productweight: `${productData.productweight}` || "",
        qtt: productData.qtt || 1,
        isfragile: productData.isfragile || false,
        issideup: productData.issideup || false,
        istop: productData.istop || false,
        notstack: productData.notstack || false,
        maxstack: productData.maxstack || 1,
        create_by: productData.create_by || "admin",
        color: productData.color || "#000000",
      });
    } else {
      setFormData({
        productcode: "",
        productname: "",
        productwidth: "",
        productheight: "",
        productlength: "",
        productweight: "",
        qtt: 1,
        isfragile: false,
        issideup: false,
        istop: false,
        notstack: false,
        maxstack: 1,
        create_by: "admin",
        color: "#000000",
      });
    }
  }, [productData]);

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
  
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox"
        ? checked
        : name === "productcode" // กรณีพิเศษสำหรับ productcode
        ? value
        : isNaN(Number(value))
        ? value
        : Number(value),
    }));
  };
  
  

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Convert formData to camelCase for the backend
    const payload = {
      productCode: formData.productcode,
      productName: formData.productname,
      productWidth: parseFloat(formData.productwidth),
      productHeight: parseFloat(formData.productheight),
      productLength: parseFloat(formData.productlength),
      productWeight: parseFloat(formData.productweight),
      qtt: formData.qtt,
      isFragile: formData.isfragile,
      isSideUp: formData.issideup,
      isTop: formData.istop,
      notstack: formData.notstack,
      maxstack: formData.maxstack,
      createby: formData.create_by,  
      color: formData.color,
    };
    // console.log("Payload being sent:", payload);

    try {
      let response;
      if (productData?.productid) {
        response = await fetch(
          `${apiUrl}/products/${productData.productid}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }
        );
      } else {
        response = await fetch(`${apiUrl}/products/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      if (response.ok) {
        const data = await response.json();
        console.log("Success:", data);
        fetchProducts(); // Reload the product list
        onClose(); // Close the modal
      } else {
        const errorData = await response.json();
        console.error("Failed to save product:", errorData);
      }
    } catch (error) {
      console.error("Error saving product:", error);
    }
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
      <div className="bg-[#e2e8f0] rounded-lg shadow-lg w-[90%] max-w-4xl p-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">Product Setting</h2>
          <button
            onClick={onClose}
            className="text-gray-600 hover:text-gray-900 text-xl"
          >
            ✖
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black">
                  Product Code <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="productcode"
                  value={formData.productcode || ""}
                  onChange={handleChange}
                  required
                  className="mt-1 w-4/6 px-3 py-2 border border-gray-400 text-center rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-12">
                  Height <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="productheight"
                  value={formData.productheight}
                  onChange={handleChange}
                  required
                  min="0"
                  className="mt-1 w-1/2 px-3 py-2 border border-gray-400 text-center rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
                <label className="text-sm font-bold">cm</label>
              </div>

              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-11">
                  Weight <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="productweight"
                  value={formData.productweight}
                  onChange={handleChange}
                  required
                  min="0"
                  className="mt-1 w-1/2 px-3 py-2 text-center border border-gray-400 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
                <label className="text-sm font-bold">kg</label>
              </div>

              <div className="flex items-center space-x-4 mt-4">
                <label className="block text-sm font-bold text-black pr-12">
                  Color
                </label>
                <div className="flex items-center space-x-2 "></div>
                <input
                  type="color"
                  name="color"
                  value={formData.color}
                  onChange={handleChange}
                  className="w-8 h-8 border border-gray-300 rounded-md"
                />
                <input
                  type="text"
                  value={formData.color}
                  readOnly
                  className="p-2 w-36 bg-gray-300 text-black text-center rounded-md"
                />
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex space-x-5 items-center">
                <label className="block text-sm font-bold text-black">
                  Product Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="productname"
                  value={formData.productname}
                  onChange={handleChange}
                  required
                  className="mt-1 w-4/6 px-3 py-2 border border-gray-400 text-center rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-16">
                  Width <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="productwidth"
                  value={formData.productwidth}
                  onChange={handleChange}
                  required
                  min="0"
                  className="mt-1 w-1/2 px-3 py-2 border border-gray-400 text-center  rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
                <label className="text-sm font-bold">cm</label>
              </div>

              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-14">
                  Length <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="productlength"
                  value={formData.productlength}
                  onChange={handleChange}
                  required
                  min="0"
                  className="mt-1 w-1/2 px-3 py-2 border border-gray-400 text-center rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-10">
                  maxstack <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="maxstack"
                  value={formData.maxstack}
                  onChange={handleChange}
                  required
                  min="0"
                  className="mt-1 w-1/2 px-3 py-2 border border-gray-400 text-center rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between mt-10">
            <div className="flex items-center space-x-8 mt-8">
              {symbols.map((symbol) => (
                <label
                  key={symbol.value}
                  className="flex items-center space-x-2"
                >
                  <input
                    type="checkbox"
                    name={`${symbol.value}`}
                    checked={
                      formData[
                        `${symbol.value}` as keyof ProductData
                      ] as boolean
                    }
                    onChange={handleChange}
                  />
                  <Image
                    src={symbol.icon}
                    alt={symbol.value}
                    width={24}
                    height={24}
                  />
                </label>
              ))}
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                className="flex items-center justify-center space-x-2 px-4 py-2 bg-[#004798] text-white rounded hover:bg-blue-950 w-36 h-11"
              >
                <span>Save</span>
                <Image
                  src="/icon/save.svg"
                  alt="Save Icon"
                  width={24}
                  height={24}
                />
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ModalProductForm;

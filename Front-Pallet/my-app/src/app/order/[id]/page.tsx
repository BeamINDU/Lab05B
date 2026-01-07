"use client";

import { useParams, useRouter } from "next/navigation";
import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import Image from "next/image";

type Product = {
  productid: string;
  productcode: string;
  productname: string;
  qtt: number;
  productlength?: number;
  productwidth?: number;
  productheight?: number;
  productweight?: number;
  color?: string;
  send_date?:Date;
  detailid?:string | number;
};

type Order = {
  orderid: string;
  order_number: string;
  order_name: string;
  send_date: string;
  products: Product[];
};

const OrderDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  // const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [deletedProducts, setDeletedProducts] = useState<string[]>([]);
  const [availableProducts, setAvailableProducts] = useState<Product[]>([]);
  const [isAddProductModalOpen, setIsAddProductModalOpen] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL; 
  
  const fetchProducts = useCallback(async () => {
    try {
      const response = await fetch(`${apiUrl}/products/`);
      const data = await response.json();
      setAvailableProducts(data.items || []);
    } catch (error) {
      console.error("Error fetching products:", error);
    }
  }, [apiUrl]); 
  
  useEffect(() => {
    if (id) {
      axios
        .get(`${apiUrl}/orders/${id}`)
        .then((response) => {
          setOrder(response.data);
        })
        .catch((error) => {
          console.error("Error fetching order details:", error);
        })
        .finally(() => setLoading(false));
    }
    fetchProducts(); 
    axios
      .get(`${apiUrl}/products/`)
      .then((response) => {
        setAvailableProducts(response.data.items || []);
      })
      .catch((error) => {
        console.error("Error fetching products:", error);
      });
  }, [apiUrl, fetchProducts, id]);

  const handleOpenAddProductModal = () => {
    setIsAddProductModalOpen(true);
  };

  const handleCloseAddProductModal = () => {
    setIsAddProductModalOpen(false);
  };

  const handleAddSelectedProduct = (selectedProductId: string) => {
    const productToAdd = availableProducts.find(
      (product) => product.productid === selectedProductId
    );
  
    if (productToAdd && order) {
      // เพิ่มสินค้าโดยไม่เปลี่ยน productid
      const newProduct = {
        ...productToAdd,
        detailid: `${productToAdd.productid}-${Date.now()}`, // เพิ่ม unique detailid สำหรับสินค้าแต่ละชิ้น
      };
  
      setOrder({
        ...order,
        products: [...order.products, newProduct],
      });
    }
    setIsAddProductModalOpen(false);
  };
  

  const handleBack = () => {
    router.push("/order");
  };

  // const removeSelectedProducts = () => {
  //   setOrder((prevOrder) =>
  //     prevOrder
  //       ? {
  //           ...prevOrder,
  //           products: prevOrder.products.filter(
  //             (product) => !selectedProductIds.includes(product.productid)
  //           ),
  //         }
  //       : null
  //   );
  //   setSelectedProductIds([]);
  // };
  const handleSave = async () => {
    if (!order) return;
  
    try {
      const newProducts = order.products.filter(
        (product) =>
          product.detailid && product.detailid.toString().includes("-")
      );
  
      const existingProducts = order.products.filter(
        (product) => !product.detailid || !product.detailid.toString().includes("-")
      ).map((product) => ({
        productid: product.productid,
        productcode: product.productcode,
        productname: product.productname,
        qtt: product.qtt,
        productlength: product.productlength,
        productwidth: product.productwidth,
        productheight: product.productheight,
        productweight: product.productweight,
        color: product.color,
        send_date: product.send_date || order.send_date,
      }));
  
      // ลบสินค้าที่ซ้ำกัน
      const uniqueExistingProducts = Array.from(
        new Map(
          existingProducts.map((product) => [product.productid, product])
        ).values()
      );
  
      // กรองค่าที่ไม่ถูกต้องออกจาก deleted_products
      const validDeletedProducts = deletedProducts.filter((id) => id !== null);
  
      const payload = {
        order_name: order.order_name,
        send_date: order.send_date,
        new_products: newProducts,
        existing_products: uniqueExistingProducts,
        deleted_products: validDeletedProducts,
      };
  
      console.log("Payload being sent:", JSON.stringify(payload, null, 2));
  
      const response = await axios.put(
        `${apiUrl}/orders/${order.orderid}`,
        payload
      );
  
      if (response.status === 200) {
        alert("Order updated successfully!");
        setDeletedProducts([]);
      } else {
        console.error("Failed to update order:", response.data);
      }
    } catch (error) {
      console.error("Error updating order:", error);
    }
  };
  
  
  const handleProductChange = async (
    productId: string,
    field: keyof Product,
    newValue: string | number | boolean | Date | undefined
  ) => {
    if (field === "qtt" && typeof newValue === "number") {
      // ค้นหาสินค้าในสต็อก
      const productInStock = availableProducts.find(
        (product) => product.productid === productId
      );
  
      // ค้นหาสินค้าเดิมใน Order
      const existingProduct = order?.products.find(
        (product) => product.productid === productId
      );
  
      if (!productInStock || !existingProduct) return;
  
      // **คำนวณความแตกต่างของ qtt (เพิ่มหรือลด)**
      const qttDifference = newValue - existingProduct.qtt; // ค่าที่เปลี่ยนไป
  
      // **ตรวจสอบว่าผู้ใช้กำลังเพิ่ม qtt เกินจำนวนที่เหลือในสต็อก**
      if (qttDifference > 0 && qttDifference > productInStock.qtt) {
        alert(
          `ไม่สามารถกำหนดจำนวนเกินกว่าสินค้าที่มีอยู่ (${productInStock.qtt})`
        );
        return;
      }
  
      // **คำนวณ qtt ใหม่ใน Product Master**
      const updatedStockQtt = productInStock.qtt - qttDifference;
  
      try {
        // ✅ อัปเดต qtt ใน Product Master
        await fetch(`${apiUrl}/products/${productId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ qtt: updatedStockQtt }),
        });
  
        // ✅ อัปเดตค่าของสินค้าหากผ่านเงื่อนไข
        setOrder((prevOrder) =>
          prevOrder
            ? {
                ...prevOrder,
                products: prevOrder.products.map((product) =>
                  product.productid === productId ? { ...product, [field]: newValue } : product
                ),
              }
            : null
        );
  
        // ✅ โหลดค่าใหม่ใน Product Master
        await fetchProducts();
      } catch (error) {
        console.error("Error updating product qtt:", error);
      }
    }
  };
  
  
  const handleDeleteProducts = () => {
    if (!order) return;
  
    // ลบสินค้าที่เลือกออกจากรายการใน Local State
    const updatedProducts = order.products.filter(
      (_, index) =>
        !selectedProducts.includes(`${order.products[index].productid}-${index}`)
    );
  
    // อัปเดต state สำหรับ order
    setOrder({
      ...order,
      products: updatedProducts,
    });
  
    // เพิ่ม `deleted_products` สำหรับส่งไป Backend
    const deleted = selectedProducts.map((uniqueId) => uniqueId);
    setDeletedProducts((prev) => [...prev, ...deleted]);
  
    // ล้างการเลือกสินค้า
    setSelectedProducts([]);
  };
  
  
  
  const handleSelectProduct = (uniqueId: string) => {
    setSelectedProducts((prevSelected) =>
      prevSelected.includes(uniqueId)
        ? prevSelected.filter((id) => id !== uniqueId)
        : [...prevSelected, uniqueId]
    );
  };
  

  if (loading) return <p>Loading...</p>;
  if (!order) return <p>No order details found.</p>;

  return (
    <div className="flex h-full space-x-4">
      <div className="w-full h-[950px] mb-4 bg-[#e2e8f0]">
        <h1 className="text-xl font-bold text-gray-700 mb-6">Order Detail</h1>

        <div className="mb-4 ml-6">
          <div className="flex items-center mb-4">
            <label className="w-1/6 font-bold">Order No.</label>
            <input
              type="text"
              value={order.order_number}
              readOnly
              className="w-1/3 h-11 p-2 border rounded-lg"
            />
          </div>
          <div className="flex items-center mb-4">
            <label className="w-1/6 font-bold">Order Name</label>
            <input
              type="text"
              value={order.order_name}
              onChange={(e) =>
                setOrder((prevOrder) =>
                  prevOrder
                    ? { ...prevOrder, order_name: e.target.value }
                    : null
                )
              }
              className="w-1/3 h-11 p-2 border rounded-lg"
            />
          </div>
          <div className="flex items-center mb-4">
            <label className="w-1/6 font-bold">Send Date</label>
            <input
              type="date"
              value={new Date(order.send_date).toISOString().split("T")[0]}
              onChange={(e) =>
                setOrder((prevOrder) =>
                  prevOrder ? { ...prevOrder, send_date: e.target.value } : null
                )
              }
              className="w-1/3 h-11 p-2 border rounded-lg"
            />
          </div>
          <div className="flex justify-end mr-6 font-bold mb-6 space-x-4">
            <button
              onClick={handleBack}
              className="px-4 py-2 bg-white rounded-lg border-2 border-slate-300 hover:bg-gray-300 w-36 h-11 hover:border-black"
            >
              Back
            </button>
            <button
              onClick={handleSave}
              className="flex items-center justify-center space-x-2 px-4 py-2 bg-[#004798] text-white rounded-lg hover:bg-blue-950 w-36 h-11"
            >
              <span>Save</span>
              <Image
                src="/icon/save.svg"
                alt="Save Icon"
                width={24}
                height={24}
              />
            </button>
            <button
              onClick={handleDeleteProducts}
              disabled={selectedProducts.length === 0}
              className={`flex items-center justify-center space-x-2 px-4 py-2 rounded-lg w-36 h-11 ${
                selectedProducts.length > 0
                  ? "bg-[#e63946] text-white hover:bg-red-700"
                  : "bg-gray-300 text-gray-500 cursor-not-allowed"
              }`}
            >
              <span>Delete</span>
              <Image
                src="/icon/delete.svg"
                alt="Delete Icon"
                width={24}
                height={24}
              />
            </button>
          </div>
        </div>
        <div className="p-6">
          <table className="bg-white w-full border-collapse border border-gray-300 rounded-lg overflow-hidden shadow-md">
            <thead>
              <tr className="bg-[#c1d9ff]">
                <th className="py-4 px-4 text-center"></th>

                <th className="py-4 px-4 text-center">No.</th>
                <th className="py-4 px-4 text-center">Product Code</th>
                <th className="py-4 px-4 text-center">Product Name</th>
                <th className="py-4 px-4 text-center">qtt</th>
                <th className="py-4 px-4 text-center">Length</th>
                <th className="py-4 px-4 text-center">Width</th>
                <th className="py-4 px-4 text-center">Height</th>
                <th className="py-4 px-4 text-center">Weight</th>
                <th className="py-4 px-4 text-center">Color</th>
              </tr>
            </thead>
            <tbody>
              {order.products.map((product, index) => (
                <tr key={`${product.productid}-${index}`} className="border-t">
                  <td className="py-2 px-4 text-center">
                    <input
                      type="checkbox"
                      checked={selectedProducts.includes(`${product.productid}-${index}`)}
                      onChange={() => handleSelectProduct(`${product.productid}-${index}`)}
                      />
                  </td>
                  <td className="py-2 px-4 text-center">{index + 1}</td>
                  <td className="py-2 px-4 text-center">
                    {product.productcode}
                  </td>
                  <td className="py-2 px-4 text-center">
                    {product.productname}
                  </td>
                  <td className="py-2 px-4 text-center">
                    <input
                      type="number"
                      value={product.qtt}
                      onChange={(e) =>
                        handleProductChange(
                          product.productid,
                          "qtt",
                          parseInt(e.target.value)
                        )
                      }
                      className="w-14 border rounded px-2"
                    />
                  </td>
                  <td className="py-2 px-4 text-center">
                    {product.productlength}
                  </td>
                  <td className="py-2 px-4 text-center">
                    {product.productwidth}
                  </td>
                  <td className="py-2 px-4 text-center">
                    {product.productheight}
                  </td>
                  <td className="py-2 px-4 text-center">
                    {product.productweight}
                  </td>
                  <td className="py-2 px-4 text-center">
                    <div
                      style={{
                        backgroundColor: product.color || "#ffffff",
                        width: "20px",
                        height: "20px",
                        borderRadius: "50%",
                        margin: "0 auto",
                      }}
                    ></div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            onClick={handleOpenAddProductModal}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            + Add Product
          </button>
          {isAddProductModalOpen && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
              <div className="bg-white rounded-lg shadow-lg p-6 w-[500px]">
                <h2 className="text-xl font-bold mb-4">Select Product</h2>
                <ul className="overflow-y-auto max-h-[300px]">
                  {availableProducts.map((product) => (
                    <li
                      key={product.productid}
                      className="flex justify-between items-center py-2 border-b"
                    >
                      <span>{product.productname}</span>
                      <button
                        onClick={() =>
                          handleAddSelectedProduct(product.productid)
                        }
                        className="px-4 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                      >
                        Add
                      </button>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={handleCloseAddProductModal}
                  className="mt-4 px-4 py-2 bg-gray-300 rounded-lg hover:bg-gray-400"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default OrderDetailPage;

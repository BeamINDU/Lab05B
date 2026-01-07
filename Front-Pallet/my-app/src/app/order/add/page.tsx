"use client";

import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import React, { useState, useEffect } from "react";
import axios from "axios";

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
};

type Order = {
  orderid: string;
  order_number: string;
  order_name: string;
  sendDate: string;
  products: Product[];
};

const OrderDetailPage: React.FC = () => {
  // const { name } = useParams<{ name: string }>();
  const { orderid } = useParams<{ orderid: string }>();
  const router = useRouter();
  const [productList, setProductList] = useState<Product[]>([]);
  const [order, setOrder] = useState<Order | null>(null);
  const [isProductModalOpen, setIsProductModalOpen] = useState<boolean>(false);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [loading, setLoading] = useState(true);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL; 

  useEffect(() => {
    axios
      .get(`${apiUrl}/products`)
      .then((response) => {
        const items: Product[] = response.data.items || [];
        setProductList(items);
      })
      .catch((error) => {
        console.error("Error fetching products:", error);
      });
  }, [apiUrl]);

  useEffect(() => {
    if (orderid) {
      axios
        .get(`${apiUrl}/orders/${orderid}`)
        .then((response) => {
          setOrder(response.data);
        })
        .catch((error) => {
          console.error("Error fetching order details:", error);
          alert("Failed to fetch order details.");
        });
    }
  }, [apiUrl, orderid]);

  const addProductToOrder = (product: Product) => {
    setOrder((prevOrder) =>
      prevOrder
        ? {
            ...prevOrder,
            products: [...prevOrder.products, { ...product, qtt: 1 }],
          }
        : null
    );
    setIsProductModalOpen(false);
  };

  const handleCheckboxChange = (productId: string) => {
    setSelectedProductIds((prev) =>
      prev.includes(productId)
        ? prev.filter((id) => id !== productId)
        : [...prev, productId]
    );
  };

  const removeSelectedProducts = () => {
    setOrder((prevOrder) =>
      prevOrder
        ? {
            ...prevOrder,
            products:
              prevOrder.products?.filter(
                (p) => !selectedProductIds.includes(p.productid)
              ) || [],
          }
        : null
    );
    setSelectedProductIds([]);
  };

  const handleSave = () => {
    if (!order) return;

    const payload = {
      order_number: order.order_number,
      order_name: order.order_name,
      create_by: "admin",
      deliveryby: "deliveryUser",
      send_date: new Date(order.sendDate).toISOString(),
      products: order.products.map((product) => ({
        productid: product.productid,
        qtt: product.qtt|| 1,
        send_date: new Date(order.sendDate).toISOString(),
      })),
    };

    console.log("Payload Sent:", payload);

    axios
      .post(`${apiUrl}/orders/`, payload)
      .then(() => {
        alert("Order saved successfully!");
        router.push("/order");
      })
      .catch((error) => console.error("Error saving order:", error));
  };
  useEffect(() => {
    if (orderid) {
      axios
        .get(`${apiUrl}/orders/${orderid}`)
        .then((response) => {
          setOrder(response.data);
        })
        .catch((error) => console.error("Error fetching order:", error))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [apiUrl, orderid]);
  const handleBack = () => {
    router.push("/order");
  };

  return (
    <div className="flex h-full space-x-4">
      <div className="w-full h-[950px] mb-4 bg-[#e2e8f0]">
        <h1 className="text-2xl font-bold mb-4 mt-6 ml-6">Order Detail</h1>

        <div className="">
          <div className="mb-4 ml-6 ">
            <div className="flex items-center mb-4">
              <label className="w-1/6 font-bold">
                Order No. <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={order?.order_number || ""}
                onChange={(e) =>
                  setOrder((prevOrder) =>
                    prevOrder
                      ? { ...prevOrder, order_number: e.target.value }
                      : {
                          orderid: "",
                          order_name: "",
                          sendDate: "",
                          products: [],
                          order_number: e.target.value,
                        }
                  )
                }
                className="w-1/3 h-11 p-2 border rounded-lg"
              />
            </div>

            <div className="flex items-center mb-4">
              <label className="w-1/6 font-bold">
                Order Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={order?.order_name || ""}
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
              <label className="w-1/6 font-bold">
                Send Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={order?.sendDate || ""}
                onChange={(e) =>
                  setOrder((prevOrder) =>
                    prevOrder
                      ? { ...prevOrder, sendDate: e.target.value }
                      : null
                  )
                }
                className="w-1/3 h-11 p-2 border rounded-lg"
              />
            </div>
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
              onClick={removeSelectedProducts}
              disabled={selectedProductIds.length === 0}
              className="flex items-center justify-center space-x-2 px-4 py-2 bg-[#004798] text-white rounded-lg hover:bg-blue-950 w-36 h-11"
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
                <th></th>
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
              {order?.products?.length ? (
                order.products.map((product, index) => (
                  <tr key={product.productid || index} className="border-t">
                    <td className="py-2 px-4 text-center">
                      <input
                        type="checkbox"
                        checked={selectedProductIds.includes(
                          product.productid
                        )}
                        onChange={() =>
                          handleCheckboxChange(product.productid)
                        }
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
                      {product.qtt}
                    </td>
                    <td className="py-2 px-4 text-center">
                      {product.productlength || "N/A"}
                    </td>
                    <td className="py-2 px-4 text-center">
                      {product.productwidth || "N/A"}
                    </td>
                    <td className="py-2 px-4 text-center">
                      {product.productheight || "N/A"}
                    </td>
                    <td className="py-2 px-4 text-center">
                      {product.productweight}
                    </td>
                    <td className="py-2 px-4 text-center">
                      <span
                        className="inline-block w-6 h-6 rounded-md"
                        style={{ backgroundColor: product.color }}
                      />
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="py-2 px-4 text-center" colSpan={10}>
                    add products.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="mt-4 flex justify-start">
            <button
              onClick={() => setIsProductModalOpen(true)}
              className="bg-blue-900 text-white px-4 py-2 rounded hover:bg-blue-950"
            >
              Add Product
            </button>
          </div>
        </div>
      </div>

      {isProductModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-white rounded-lg shadow-md p-6 w-[500px]">
            <h2 className="text-xl font-bold mb-4">Select Product</h2>
            <ul className="overflow-y-auto max-h-[300px]">
              {productList.map((product) => (
                <li
                  key={product.productid}
                  className="p-2 border-b cursor-pointer hover:bg-gray-100"
                  onClick={() => addProductToOrder(product)}
                >
                  {product.productname} ({product.productcode})
                </li>
              ))}
            </ul>
            <button
              onClick={() => setIsProductModalOpen(false)}
              className="mt-4 bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default OrderDetailPage;

"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import React, { useState, useEffect } from "react";
import axios from "axios";
import OrderExcelUpload from "@/components/Excel/orderexcel";
type Order = {
  orderid: string;
  order_number: string;
  order_name: string;
  send_date: string;
  create_by: string;
  deliveryby: string;
  orderupdate?: string;
};

const OrderPage: React.FC = () => {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]); // ใช้ State เพื่อจัดการรายการคำสั่งซื้อ
  const [currentPage, setCurrentPage] = useState<number>(1); // หน้าปัจจุบัน
  const [totalOrders, setTotalOrders] = useState<number>(0); // สำหรับเก็บ total_count

  const itemsPerPage = 10; // จำนวนรายการต่อหน้า
  const totalPages = Math.ceil(totalOrders / itemsPerPage);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    axios
      .get(`${apiUrl}/orders/`)
      .then((response) => {
        console.log("Response data:", response.data);
        setOrders(response.data.items || []); // เก็บ items
        setTotalOrders(response.data.total_count || 0); // เก็บ total_count
      })
      .catch((error) => {
        console.error("Error fetching orders:", error);
      });
  }, [apiUrl]);

  const fetchOrders = () => {
    axios
      .get(`${apiUrl}/orders/`)
      .then((response) => {
        console.log("Response data:", response.data);
        setOrders(response.data.items || []); // เก็บ items
        setTotalOrders(response.data.total_count || 0); // เก็บ total_count
      })
      .catch((error) => {
        console.error("Error fetching orders:", error);
      });
  };

  const handleDelete = (orderId: string) => {
    axios
      .delete(`${apiUrl}/orders/${orderId}`)
      .then(() => {
        alert("Order deleted successfully!");
        setOrders(orders.filter((order) => order.orderid !== orderId)); // อัปเดต State
      })
      .catch((error) => {
        console.error("Error deleting order:", error);
        alert("Failed to delete order. Please try again.");
      });
  };

  const formatDate = (dateString: string) => {
    const options: Intl.DateTimeFormatOptions = {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    };
    return new Date(dateString).toLocaleDateString("en-GB", options);
  };

  const navigateToAddOrder = () => {
    router.push("/order/add");
  };

  const navigateToDetail = (orderId: string) => {
    if (!orderId) {
      console.error("Order ID is missing!"); // Debug error
      return;
    }
    console.log("Navigating to detail with ID:", orderId);
    router.push(`/order/${orderId}`);
  };

  const currentOrders = orders.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  return (
    <div className="flex h-screen space-x-4">
      <div className="w-full  h-screen min-h-screen mb-4 bg-[#e2e8f0]">
        <h1 className="text-2xl font-bold mt-8 mb-6 ml-12">Order List</h1>
        <table className="ml-8 w-11/12 max-w-[1530px] h-3/4 max-h-[711.84px] border-collapse border-spacing-0 border bg-white border-gray-300 rounded-lg overflow-hidden shadow-md">
          <thead>
            <tr className="bg-[#c1d9ff]">
              <th className="py-4 px-4 text-center">No.</th>
              <th className="py-4 px-4 text-center">Order No.</th>
              <th className="py-4 px-4 text-center">Order Name</th>
              <th className="py-4 px-4 text-center">Send Date</th>
              <th className="py-4 px-4 text-center">Created By</th>
              <th className="py-4 px-4 text-center">Delivery By</th>
              <th className="py-4 px-4 text-center">Order Update</th>
              <th className="py-4 px-4 text-center"></th>
            </tr>
          </thead>
          <tbody>
            {currentOrders.map((order, index) => (
              <tr key={order.orderid} className="border-b">
                <td className="py-2 px-4 text-center">
                  {(currentPage - 1) * itemsPerPage + index + 1}
                </td>
                <td className="py-2 px-4 text-center">{order.order_number}</td>
                <td className="py-2 px-4 text-center">{order.order_name}</td>
                <td className="py-2 px-4 text-center">
                  {formatDate(order.send_date)}
                </td>
                <td className="py-2 px-4 text-center">{order.create_by}</td>
                <td className="py-2 px-4 text-center">{order.deliveryby}</td>
                <td className="py-2 px-4 text-center">{order.orderupdate}</td>
                <td className="py-2 px-4 text-center">
                  <div className="flex justify-center space-x-2">
                    <button
                      onClick={() => navigateToDetail(order.orderid)}
                      className="flex items-center justify-center px-4 py-2 bg-[#004798] text-white rounded hover:bg-blue-950 w-20 h-9"
                    >
                      Detail
                    </button>
                    <button
                      onClick={() => handleDelete(order.orderid)}
                      className="flex items-center justify-center space-x-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 w-20 h-9"
                    >
                      <span>Delete</span>
                      <Image
                        src="/icon/delete.svg"
                        alt="Delete Icon"
                        width={20}
                        height={20}
                      />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {Array.from({
              length: Math.max(0, itemsPerPage - currentOrders.length),
            }).map((_, index) => (
              <tr key={`empty-${index}`} className="border-b">
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
                <td className="py-6 px-4 text-center"></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-between items-center mt-4 w-11/12 max-w-[1500px]">
        <div className="flex ml-8 space-x-4">
          <button
            onClick={navigateToAddOrder}
            className="bg-blue-900 text-white px-4 py-2 rounded hover:bg-blue-950"
          >
            + Add
          </button>
          <OrderExcelUpload onUpload={fetchOrders} />
        </div>
        <div className="flex items-center space-x-4">
          <button
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((prev) => prev - 1)}
            className={`w-8 h-8 flex items-center justify-center rounded-full border border-gray-300 ${
              currentPage === 1
                ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                : "bg-white text-gray-700 hover:bg-blue-500 hover:text-white"
            }`}
          >
            <span className="material-icons">chevron_left</span>
          </button>
          <span className="text-gray-700 font-bold">
            Page {currentPage} / {totalPages}
          </span>
          <button
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((prev) => prev + 1)}
            className={`w-8 h-8 flex items-center justify-center rounded-full border border-gray-300 ${
              currentPage === totalPages
                ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                : "bg-white text-gray-700 hover:bg-blue-500 hover:text-white"
            }`}
          >
            <span className="material-icons">chevron_right</span>
          </button>
        </div>
        </div>

      </div>
    </div>
  );
};

export default OrderPage;

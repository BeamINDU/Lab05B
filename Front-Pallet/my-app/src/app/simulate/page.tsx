"use client";

import { useRouter } from "next/navigation";
import React, { useState, useEffect } from "react";
import Image from "next/image";
// import { Product, Container, Pallet } ;

type Order = {
  orderid: string;
  order_number: string;
  order_name: string;
  send_date: string;
  create_by: string;
  deliveryby: string;
  order_update: string;
};
type ApiOrder = {
  orderid: string;
  order_number: string;
  order_name: string;
  send_date: string;
  create_by: string;
  deliveryby: string;
  create_date: string;
  update_date: string;
  products?: Product[]; // If you know the product structure, replace `any[]` with a proper type
};

const SimulateOrdersPage: React.FC = () => {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]); // List of available orders
  const [selectedOrders, setSelectedOrders] = useState<string[]>([]); // Selected orders
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const [, setPallets] = useState<Pallet[]>([]);
  const [, setContainers] = useState<Container[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  // Fetch orders data
  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const response = await fetch(`${apiUrl}/orders/`);
        const data = await response.json();

        // Transform backend data
        const transformedOrders: Order[] = data.items.map((order: ApiOrder) => ({
          orderid: order.orderid,
          order_number: order.order_number,
          order_name: order.order_name,
          send_date: order.send_date,
          create_by: order.create_by,
          deliveryby: order.deliveryby,
          create_date: order.create_date,
          update_date: order.update_date,
          products: order.products || [], // Ensure products array is always present
        }));

        setOrders(transformedOrders);
      } catch (error) {
        console.error("Error fetching orders:", error);
      }
    };

    fetchOrders();
  }, [apiUrl]);

  useEffect(() => {
    const fetchPalletsAndContainers = async () => {
      try {
        const palletsResponse = await fetch(`${apiUrl}/pallets/`);
        const palletsData = await palletsResponse.json();
        console.log("Pallets After Update:", palletsData.items); 
        setPallets(palletsData.items || []);
  
        const containersResponse = await fetch(`${apiUrl}/containers/`);
        const containersData = await containersResponse.json();
        setContainers(containersData.items || []);
  
      } catch (error) {
        console.error("Error fetching pallets and containers:", error);
      }
    };
  
    fetchPalletsAndContainers();
  }, [apiUrl]);
  
  
  const handleCheckboxChange = (orderId: string) => {
    setSelectedOrders((prev) =>
      prev.includes(orderId)
        ? prev.filter((id) => id !== orderId)
        : [...prev, orderId]
    );
  };

  const handleSimulateOrders = async (simulationType: "pallet" | "container" | "pallet_container") => {
    if (selectedOrders.length === 0) {
        alert("กรุณาเลือกอย่างน้อย 1 Order");
        return;
    }
    setIsLoading(true);
    try {
        const orderIds = selectedOrders.map(order => Number(order));

        console.log("📤 ส่งค่าไปที่ /simulation/pre-save/:", { simulatetype: simulationType, order_ids: orderIds });

        const preSaveResponse = await fetch(`${apiUrl}/simulation/pre-save/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                simulatetype: simulationType.toLowerCase(),
                order_ids: orderIds,
            }),
        });

        if (!preSaveResponse.ok) {
            const errorData = await preSaveResponse.json();
            console.error("❌ Error in pre-save:", errorData);
            throw new Error(`Error in pre-save: ${preSaveResponse.status}, ${JSON.stringify(errorData.detail)}`);
        }

        const preSaveData = await preSaveResponse.json();
        const simulateId = Number(preSaveData.simulateId);

        console.log("ได้รับ Simulate ID:", simulateId);

        console.log("กำลังส่งข้อมูลไปที่ /simulate-orders/", {
            simulate_id: simulateId,
            order_ids: orderIds
        });

        const simulateResponse = await fetch(`${apiUrl}/simulate-orders/?simulation_type=${simulationType}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                simulate_id: simulateId,
                order_ids: orderIds,
            }),
        });

        if (!simulateResponse.ok) {
            const errorData = await simulateResponse.json();
            console.error("Error in simulate-orders:", errorData);
            throw new Error(`Error in simulate-orders: ${simulateResponse.status}, ${JSON.stringify(errorData.detail)}`);
        }



        router.push(`/simulate/${simulationType}/${simulateId}`);


    } catch (error) {
        console.error("Simulation failed:", error);
        alert(`Simulation failed: ${error}`);
    } finally {
  }
};

if (isLoading) {
  return (
    <div className="flex flex-col items-center justify-center w-full h-screen">
    <h2 className="text-xl font-bold text-gray-700">Please wait...model is generating</h2>
      <Image src="/image/loading.gif" alt="Loading..." width={64} height={64} />
  </div>
  );
}

  return (
    <div className="flex h-screen">
      <div className="w-full  h-screen min-h-screen mb-4 bg-[#e2e8f0]">
        <h1 className="text-2xl font-bold mt-8 mb-6 ml-12">Simulate</h1>
        <table className="ml-8 w-11/12 max-w-[1530px] h-3/4 max-h-[711.84px] border-collapse border-spacing-0 border bg-white border-gray-300 rounded-lg overflow-hidden shadow-md">
          <thead className="bg-[#c1d9ff]">
            <tr>
              <th className="py-4 px-4"></th>
              <th className="py-4 px-4 text-center">No.</th>
              <th className="py-4 px-4 text-center">Order No.</th>
              <th className="py-4 px-4 text-center">Order Name</th>
              <th className="py-4 px-4 text-center">Send Date</th>
              <th className="py-4 px-4 text-center">Create By</th>
              <th className="py-4 px-4 text-center">Delivery By</th>
              <th className="py-4 px-4 text-center">Order Update</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order, index) => (
              <tr key={order.orderid} className="border-b">
                <td className="py-3 px-4 text-center">
                  <input
                    type="checkbox"
                    checked={selectedOrders.includes(order.orderid)}
                    onChange={() => handleCheckboxChange(order.orderid)}
                  />
                </td>
                <td className="py-3 px-4 text-center">{index + 1}</td>
                <td className="py-3 px-4 text-center">{order.order_number}</td>
                <td className="py-3 px-4 text-center">{order.order_name}</td>
                <td className="py-3 px-4 text-center">{order.send_date}</td>
                <td className="py-3 px-4 text-center">{order.create_by}</td>
                <td className="py-3 px-4 text-center">{order.deliveryby}</td>
                <td className="py-3 px-4 text-center">{order.order_update}</td>
              </tr>
            ))}
            {/* เติมแถวเปล่าให้ครบ 10 แถว */}
            {Array.from({ length: Math.max(0, 10 - orders.length) }).map(
              (_, index) => (
                <tr key={`empty-${index}`} className="border-b">
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-4"></td>
                </tr>
              )
            )}
          </tbody>
        </table>
        <div className="flex justify-start gap-4 mt-4 ml-8">
          <button
            onClick={() => handleSimulateOrders("pallet")}
            className={`bg-[#004798] text-white px-6 py-2 rounded-lg font-bold hover:bg-[#003366] ${
              selectedOrders.length === 0 ? "opacity-50 cursor-not-allowed" : ""
            }`}
            disabled={selectedOrders.length === 0}
          >
            Pallet Simulate
          </button>
          <button
            onClick={() => handleSimulateOrders("container")}
            className={`bg-[#004798] text-white px-6 py-2 rounded-lg font-bold hover:bg-[#003366] ${
              selectedOrders.length === 0 ? "opacity-50 cursor-not-allowed" : ""
            }`}
            disabled={selectedOrders.length === 0}
          >
            Container Simulate
          </button>
          <button
            onClick={() => handleSimulateOrders("pallet_container")}
            className={`bg-[#004798] text-white px-6 py-2 rounded-lg font-bold hover:bg-[#003366] ${
              selectedOrders.length === 0 ? "opacity-50 cursor-not-allowed" : ""
            }`}
            disabled={selectedOrders.length === 0}
          >
            Pallet-Container Simulate
          </button>
        </div>
      </div>
    </div>
  );
};

export default SimulateOrdersPage;

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import SimCanvas, {
  SimBatch,
  SimPallet,
  SimProduct,
} from "@/components/3DScene/SimCanvas";
import Image from "next/image";
import DetailSection from "@/components/DetailSection";

type ParamsType = {
  simulateid?: string;
};

const PalletSimulatePage: React.FC = () => {
  const params = useParams<ParamsType>();
  const simulateid = params.simulateid ? Number(params.simulateid) : null;
  const router = useRouter();
  const [loading, setLoading] = useState<boolean>(true);
  const [data, setData] = useState<SimBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<SimBatch | undefined>(
    undefined
  );
  const [selectedIdx] = useState<number>(0);
  const [selectedItem, setSelectedItem] = useState<
    SimProduct | SimPallet | undefined
  >();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        if (!simulateid) {
          console.error("simulateid หายไปจาก URL");
          return;
        }

        console.log("📤 กำลังส่ง Request:", { simulateid });

        // 📌 ดึงข้อมูล Simulation จาก API
        const response = await fetch(
          `${apiUrl}/simulation/simulate/${simulateid}`
        );
        if (!response.ok) {
          throw new Error(`Simulation API Error: ${response.status}`);
        }
        const simulationResult = await response.json();
        console.log("✅ Simulation Data:", simulationResult);

        if (!simulationResult.data || !Array.isArray(simulationResult.data)) {
          throw new Error(
            "simulationResult.data ไม่ใช่ array หรือเป็น undefined"
          );
        }

        setData(simulationResult.data);
        if (simulationResult.data.length > 0) {
          setSelectedBatch(simulationResult.data[0]);
        } else {
          console.warn("⚠️ ไม่มีข้อมูล batch สำหรับแสดงผล");
        }
      } catch (error) {
        console.error("Error fetching simulation data:", error);
        setData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [apiUrl, simulateid]);

  useEffect(() => {
    if (data.length > 0) {
      setSelectedBatch(data.find((batch) => batch.batchid === selectedIdx)); // ✅ ใช้ find() แทน index
    }
  }, [selectedIdx, data]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-screen">
        <h2 className="text-xl font-bold text-gray-700">
          Please wait...model is generating
        </h2>
        <Image
          src="/image/loading.gif"
          alt="Loading..."
          width={64}
          height={64}
        />
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full bg-gray-100">
      {/* Sidebar */}
      <div className="w-1/3 p-4 bg-[#E2E8F0] shadow-md rounded-lg">
        <h2 className="text-xl font-bold mb-4">Pallet Simulate</h2>
        <div className="overflow-hidden border rounded-lg">
          <table className="w-full border-collapse bg-gray-50">
            <thead>
              <tr className="bg-blue-200 text-left">
                <th className="py-2 px-4"> </th>
                <th className="py-2 px-4">No.</th>
                <th className="py-2 px-4">Batch ID</th>
                <th className="py-2 px-4">Batch Type</th>
                <th className="py-2 px-4">Batch Name</th>
              </tr>
            </thead>
            <tbody>
              {data.map((batch, index) => (
                <tr
                  key={batch.batchid}
                  className="cursor-pointer hover:bg-gray-100"
                >
                  <td className="py-2 px-4">
                    <input
                      type="checkbox"
                      id={`batch-${batch.batchid}`}
                      checked={selectedBatch?.batchid === batch.batchid}
                      onChange={() => setSelectedBatch(batch)}
                    />
                  </td>
                  <td className="py-2 px-4">{index + 1}</td>
                  <td className="py-2 px-4">{batch.batchid}</td>
                  <td className="py-2 px-4">Pallet</td>
                  <td className="py-2 px-4">{batch.batchname}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <DetailSection
          details={
            selectedBatch?.details.map((detail, orderIndex) => {
              if ("ordernumber" in detail) {
                return {
                  ordernumber: detail.ordernumber,
                  products: detail.products.map((product, productIndex) => ({
                    no: product.no ?? productIndex + 1,
                    name: product.name,
                    color: product.color,
                  })),
                };
              } else {
                return {
                  ordernumber: `Batch-${orderIndex + 1}`,
                  products:
                    detail.orders?.flatMap((order) =>
                      order.products.map((product, productIndex) => ({
                        no: product.no ?? productIndex + 1,
                        name: product.name,
                        color: product.color,
                      }))
                    ) ?? [],
                };
              }
            }) ?? []
          }
        />
      </div>

      {/* 3D Simulation Canvas */}
      <div className="w-2/3 p-4 relative bg-white">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold">SIMULATION ID: {simulateid}</h2>
          <div className="flex gap-2">
            <button
              onClick={() => router.back()}
              className="px-4 py-2 bg-white rounded hover:bg-gray-200"
            >
              Back
            </button>
            <button
              onClick={() =>
                router.push(`/previewpdf?simulateid=${simulateid}`)
              }
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-700"
            >
              Print
            </button>
          </div>
        </div>

        <div className="h-[80%] w-full border rounded-lg shadow-md">
          {selectedBatch ? (
            <SimCanvas
              dataState={[selectedBatch, setSelectedBatch]}
              selectedItemState={[selectedItem, setSelectedItem]}
            />
          ) : (
            <p className="text-center text-gray-500">
              No simulation data available
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default PalletSimulatePage;

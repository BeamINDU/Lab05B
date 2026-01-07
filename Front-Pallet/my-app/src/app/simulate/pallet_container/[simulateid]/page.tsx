"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import SimCanvas, {
  SimBatch,
  SimPallet,
  SimProduct,
} from "@/components/3DScene/SimCanvas";
import Image from "next/image";
import DetailPCSection from "@/components/Detail-Section-PC";

type ParamsType = {
  simulateid?: string;
};

const PalletonContainerSimulatePage: React.FC = () => {
  const params = useParams<ParamsType>();
  const simulateid = params.simulateid ? Number(params.simulateid) : null;
  const router = useRouter();
  const [loading, setLoading] = useState<boolean>(true);
  const [data, setData] = useState<SimBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<SimBatch | undefined>(
    undefined
  );
  const [selectedItem, setSelectedItem] = useState<
    SimProduct | SimPallet | undefined
  >();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        if (!simulateid) {
          return;
        }

        const response = await fetch(
          `${apiUrl}/simulation/simulate/palletoncontainer/${simulateid}`
        );
        if (!response.ok) {
          throw new Error(`Simulation API Error: ${response.status}`);
        }
        const simulationResult = await response.json();

        if (!simulationResult.data || !Array.isArray(simulationResult.data)) {
          throw new Error(
            "simulationResult.data ไม่ใช่ array หรือเป็น undefined"
          );
        }

        setData(simulationResult.data);
        if (simulationResult.data.length > 0) {
          setSelectedBatch(simulationResult.data[0]);
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
    <div className="flex h-screen w-full">
      {/* Sidebar */}
      <div className="w-1/3 p-4 bg-[#e2e8f0] shadow-md rounded-lg">
        <div className="mb-6">
          <h2 className="text-xl font-bold mb-ุ">Pallet_Container Simulate</h2>
          <div className="flex flex-col gap-2 w-full">
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
                    <td className="py-2 px-4">Container</td>
                    <td className="py-2 px-4">{batch.batchname}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DetailPCSection
            details={
              selectedBatch?.details.map((detail) => {
                if (
                  "mastertype" in detail &&
                  detail.mastertype === "sim_batch"
                ) {
                  return {
                    batchdetailid: detail.batchdetailid,
                    name: detail.name,
                    mastertype: detail.mastertype,
                    orders: detail.orders.map((order) => ({
                      orderid: order.orderid,
                      ordername: order.ordername,
                      ordernumber: order.ordernumber,
                      products: order.products.map((product, productIndex) => ({
                        no: product.no ?? productIndex + 1, // ✅ ป้องกัน undefined
                        name: product.name,
                        color: product.color,
                        batchdetailid: product.batchdetailid, // ✅ เพิ่มฟิลด์ที่ขาด
                        code: product.code,
                        length: product.length,
                        width: product.width,
                        height: product.height,
                      })),
                    })),
                  };
                } else {
                  return {
                    batchdetailid: -1, // ✅ ค่า default เพราะ SimOrder ไม่มี batchdetailid
                    name: `Order-${detail.orderid}`,
                    mastertype: "order",
                    orders: [
                      {
                        orderid: detail.orderid,
                        ordername: detail.ordername,
                        ordernumber: detail.ordernumber,
                        products: detail.products.map(
                          (product, productIndex) => ({
                            no: product.no ?? productIndex + 1,
                            name: product.name,
                            color: product.color,
                            batchdetailid: product.batchdetailid, // ✅ เพิ่มฟิลด์ที่ขาด
                            code: product.code,
                            length: product.length,
                            width: product.width,
                            height: product.height,
                          })
                        ),
                      },
                    ],
                  };
                }
              }) ?? []
            }
          />
        </div>
      </div>

      {/* 3D Simulation Canvas */}
      <div className="w-2/3 p-4 relative">
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

export default PalletonContainerSimulatePage;

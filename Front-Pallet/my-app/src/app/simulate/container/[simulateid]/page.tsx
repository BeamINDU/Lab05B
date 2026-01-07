"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import SimCanvas, {
  SimBatch,
  SimPallet,
  SimProduct,
} from "@/components/3DScene/SimCanvas";
import DetailSection from "@/components/DetailSection";

const ContainerSimulatePage: React.FC = () => {
  const params = useParams<{ simulateid?: string }>();
  const simulateid = params.simulateid ? Number(params.simulateid) : null;
  const router = useRouter();
  const [, setLoading] = useState<boolean>(true);
  const [data, setData] = useState<SimBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<SimBatch | undefined>();
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [selectedItem, setSelectedItem] = useState<SimProduct | SimPallet | undefined>();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      if (!simulateid) return;

      try {
        const response = await fetch(
          `${apiUrl}/simulation/simulate/${simulateid}`
        );
        const simulationResult = await response.json();
        if (Array.isArray(simulationResult.data)) {
          setData(simulationResult.data);
          setSelectedBatchId(simulationResult.data[0]?.batchid || null);
        }
      } catch (error) {
        console.error("Error fetching simulation data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [apiUrl, simulateid]);

  useEffect(() => {
    if (data.length > 0 && selectedBatchId !== null) {
      setSelectedBatch(data.find((batch) => batch.batchid === selectedBatchId));
    }
  }, [selectedBatchId, data]);

  return (
    <div className="flex h-screen w-full">
      {/* Sidebar */}
      <div className="w-1/3 p-4 bg-[#e2e8f0]">
        <div className="mb-6">
          <h2 className="text-xl font-bold mb-4">Container Simulate</h2>
          <table className="w-full border-collapse border bg-white rounded-lg shadow-md">
            <thead>
              <tr className="bg-blue-200">
                <th className="py-2 px-4 text-left"> </th>
                <th className="py-2 px-4 text-left">No.</th>
                <th className="py-2 px-4 text-left">Batch ID</th>
                <th className="py-2 px-4 text-left">Batch Type</th>
                <th className="py-2 px-4 text-left">Batch Name</th>
              </tr>
            </thead>
            <tbody>
              {data.map((batch, index) => (
                <tr key={batch.batchid} className="cursor-pointer">
                  <td className="py-2 px-4">
                    <input
                      type="checkbox"
                      name="batchSelection"
                      checked={selectedBatchId === batch.batchid}
                      onChange={() => setSelectedBatchId(batch.batchid)}
                    />
                  </td>
                  <td className="py-2 px-4">{index + 1}</td>
                  <td className="py-2 px-4">{batch.batchid}</td>
                  <td className="py-2 px-4">{batch.batchtype}</td>
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
                    no: productIndex + 1,
                    name: product.name,
                    color: product.color,
                  })),
                };
              } else {
                return {
                  ordernumber: `Batch-${orderIndex + 1}`, // ✅ สร้าง ordernumber เอง
                  products:
                    detail.orders?.flatMap((order) =>
                      order.products.map((product, productIndex) => ({
                        no: productIndex + 1,
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

export default ContainerSimulatePage;

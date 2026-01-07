import React, { useState } from "react";

type Product = {
  batchdetailid: number;
  name: string;
  code: string;
  color: string;
  length: number;
  width: number;
  height: number;
};

type OrderDetail = {
  orderid: number;
  ordername: string;
  ordernumber: string;
  products?: Product[];
};

type SimBatchDetail = {
  batchdetailid: number;
  mastertype: string;
  name: string;
  orders?: OrderDetail[];
};

type DetailPCSectionProps = {
  details?: SimBatchDetail[];
};

const DetailPCSection: React.FC<DetailPCSectionProps> = ({ details = [] }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const ordersPerPage = 1; // ✅ แสดงทีละ 1 Order ต่อหน้า
  const totalOrders = details.reduce((acc, batch) => acc + (batch.orders?.length || 0), 0);
  const totalPages = Math.ceil(totalOrders / ordersPerPage) || 1;

  // ดึง Batch และ Order ตามหน้า
  const paginatedOrders: { batch: SimBatchDetail; order: OrderDetail }[] = [];
  let count = 0;

  for (const batch of details) {
    if (batch.orders) {
      for (const order of batch.orders) {
        count++;
        if (count > (currentPage - 1) * ordersPerPage && count <= currentPage * ordersPerPage) {
          paginatedOrders.push({ batch, order });
        }
        if (paginatedOrders.length >= ordersPerPage) break;
      }
    }
    if (paginatedOrders.length >= ordersPerPage) break;
  }

  return (
    <div className="bg-[#e2e8f0] p-4">
      <h2 className="text-xl font-bold mb-4">Detail</h2>

      {paginatedOrders.map(({ batch, order }) => (
        <div key={order.orderid} className="mb-6 border border-gray-300 rounded-lg p-4 bg-white">
          <h3 className="text-lg font-bold mb-2">Batch ID: {batch.batchdetailid} - {batch.name}</h3>
          <h4 className="font-semibold mb-2">Order No: {order.ordernumber}</h4>
          <div className="rounded-md overflow-hidden">
            <div className="max-h-[482px] overflow-y-auto scrollbar-hide">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="py-2 px-4 text-center w-1/5">No.</th>
                    <th className="py-2 px-4 text-center w-3/5">Product Name</th>
                    <th className="py-2 px-4 text-center w-1/5">Color</th>
                  </tr>
                </thead>
                <tbody>
                  {order.products?.map((product, index) => (
                    <tr key={product.batchdetailid} className="text-center">
                      <td className="py-2 px-4 w-1/5">{index + 1}</td>
                      <td className="py-2 px-4 w-3/5">{product.name}</td>
                      <td className="py-2 px-4 w-1/5">
                        <div className="w-6 h-6 mx-auto border border-gray-300 rounded" style={{ backgroundColor: product.color }}></div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ))}

      <div className="flex justify-between mt-4">
        <button
          onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
          disabled={currentPage === 1}
          className="px-3 py-1 bg-gray-300 rounded-md disabled:opacity-50"
        >
          ◀ Prev
        </button>
        <span>Page {currentPage} of {totalPages}</span>
        <button
          onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
          disabled={currentPage === totalPages}
          className="px-3 py-1 bg-gray-300 rounded-md disabled:opacity-50"
        >
          Next ▶
        </button>
      </div>
    </div>
  );
};

export default DetailPCSection;

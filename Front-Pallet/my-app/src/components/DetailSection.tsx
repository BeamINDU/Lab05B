import React, { useEffect, useState } from "react";



type OrderDetail = {
  ordernumber: string;
  products: {
    no: number;
    name: string;
    color: string;
  }[];
};

type DetailSectionProps = {
  details?: OrderDetail[];
};

const DetailSection: React.FC<DetailSectionProps> = ({ details = [] }) => {
  const ordersPerPage = 1;
  const [currentOrderPage, setCurrentOrderPage] = useState(1);

  useEffect(() => {
    if (details.length > 0) {
      setCurrentOrderPage(1);
    }
  }, [details]);

  if (details.length === 0) {
    return <p className="text-gray-500">No order details available.</p>;
  }

  const totalOrderPages = Math.ceil(details.length / ordersPerPage);
  const paginatedOrders = details.slice(
    (currentOrderPage - 1) * ordersPerPage,
    currentOrderPage * ordersPerPage
  );

  return (
    <div className="bg-[#e2e8f0] p-4 ">
      <h2 className="text-xl font-bold mb-4">Detail</h2>

      {paginatedOrders.map((order) => (
        <div key={order.ordernumber} className="mb-6 border p-3 rounded-lg bg-white">
          <h3 className="font-semibold">Order No: {order.ordernumber}</h3>
          <div className="max-h-[482px] overflow-y-auto">
          {/* เพิ่ม Scroll แค่ใน tbody */}
            <table className="w-full border-collapse">
              <thead >
                <tr>
                  <th className="py-2 px-4 text-center ">No</th>
                  <th className="py-2 px-4 text-center ">Product Name</th>
                  <th className="py-2 px-4 text-center ">Color</th>
                </tr>
              </thead>
              <tbody>
                {order.products.map((product, index) => (
                  <tr key={product.no} className="text-center">
                    <td className="py-2 px-4 ">{index + 1}</td>
                    <td className="py-2 px-4">{product.name}</td>
                    <td className="py-2 px-4 ">
                      <div className="w-6 h-6 mx-auto border border-gray-300 rounded" style={{ backgroundColor: product.color }}></div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
      ))}

      {/* Pagination เฉพาะ Order */}
      <div className="flex justify-between items-center mt-4">
        <button
          onClick={() => setCurrentOrderPage((prev) => Math.max(prev - 1, 1))}
          disabled={currentOrderPage === 1}
          className="px-3 py-1 bg-gray-300 rounded-md disabled:opacity-50"
        >
          ◀ Prev
        </button>
        <span>Page {currentOrderPage} of {totalOrderPages}</span>
        <button
          onClick={() => setCurrentOrderPage((prev) => Math.min(prev + 1, totalOrderPages))}
          disabled={currentOrderPage === totalOrderPages}
          className="px-3 py-1 bg-gray-300 rounded-md disabled:opacity-50"
        >
          Next ▶
        </button>
      </div>
    </div>
  );
};

export default DetailSection;

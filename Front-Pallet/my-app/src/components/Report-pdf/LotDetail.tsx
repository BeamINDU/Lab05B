import React from "react";

interface LotDetailProps {
  lotDetails: {
    palletNo: string;
    orderNo: string;
    productName: string;
    quantity: number;
  }[];
}

const LotDetail: React.FC<LotDetailProps> = ({ lotDetails }) => {
  return (
    <div>
      <h2>Lot Detail</h2>
      <table className="w-full border-collapse border bg-white rounded-lg shadow-md">
        <thead>
          <tr className="bg-gray-200">
            <th>No</th>
            <th>Pallet No</th>
            <th>Order No</th>
            <th>Product Name</th>
            <th>Quantity</th>
          </tr>
        </thead>
        <tbody>
          {lotDetails.map((lot, index) => (
            <tr key={index}>
              <td>{index + 1}</td>
              <td>{lot.palletNo}</td>
              <td>{lot.orderNo}</td>
              <td>{lot.productName}</td>
              <td>{lot.quantity}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default LotDetail;

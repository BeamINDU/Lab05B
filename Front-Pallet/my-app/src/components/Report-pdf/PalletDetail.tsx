import React from "react";

interface Product {
  id: number;
  name: string;
  color: string;
}

interface PalletDetailProps {
  pallet: {
    no: string;
    palletNo: string;
    palletName: string;
    orderNo: string;
    products: Product[];
    image: string; // ภาพ 3D
  };
}

const PalletDetail: React.FC<PalletDetailProps> = ({ pallet }) => {
  return (
    <div>
      <h2>Pallet Detail</h2>
      <p>No.: {pallet.no}</p>
      <p>Pallet No: {pallet.palletNo}</p>
      <p>Pallet Name: {pallet.palletName}</p>
      <p>Order No: {pallet.orderNo}</p>

      <table className="w-full border-collapse border bg-white rounded-lg shadow-md">
        <thead>
          <tr className="bg-gray-200">
            <th>ID</th>
            <th>Product Name</th>
            <th>Color</th>
          </tr>
        </thead>
        <tbody>
          {pallet.products.map((product, index) => (
            <tr key={index}>
              <td>{product.id}</td>
              <td>{product.name}</td>
              <td>
                <div
                  style={{
                    backgroundColor: product.color,
                    width: "20px",
                    height: "20px",
                  }}
                ></div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <img src={pallet.image} alt="3D Model" width="400" />
    </div>
  );
};

export default PalletDetail;

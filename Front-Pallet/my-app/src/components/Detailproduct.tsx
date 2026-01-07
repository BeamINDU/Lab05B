import React, { useState, useEffect } from "react";

// type Product = {
//   productid?: string;
//   productlength?: number;
//   productwidth?: number;
//   productheight?: number;
//   productweight?: number;
//   create_date?: string;
//   create_by?: string;
//   update_date?: string;
//   update_by?: string;
//   qtt?: number;
// };

type DetailPanelProps = {
  product?: Product;
  onUpdateqtt: (productId: string, newqtt: number) => void;
};

const DetailPanel: React.FC<DetailPanelProps> = ({ product, onUpdateqtt }) => {
  const [qtt, setqtt] = useState<number>(0);

  // Update the qtt state when the product changes
  useEffect(() => {
    if (product) {
      setqtt(product.qtt || 0);
    }
  }, [product]);

  // Handle qtt input changes
  const handleqttChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newqtt = parseInt(e.target.value, 10) || 0;
    setqtt(newqtt);

    // Call PUT request immediately when value changes
    if (product?.productid) {
      onUpdateqtt(product.productid, newqtt);
    }
  };

  if (!product) {
    return (
      <div className="w-1/3 bg-gray-100 p-6 rounded-lg shadow-md">
        <p className="text-gray-500">
          Please select a product to view details.
        </p>
      </div>
    );
  }

  return (
    <div className="w-1/3 bg-[#e2e8f0] p-6 rounded-lg shadow-md">
      <h2 className="text-lg font-bold mb-6">Detail</h2>
      {product ? (
        <div className="space-y-4">
          {/* Product Length */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Product Length <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={product.productlength || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Product Width */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Product Width <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={product.productwidth || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Product Height */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Product Height <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={product.productheight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Product Weight */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Product Weight <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={product.productweight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">kg</span>
            </div>
          </div>

          {/* Other Fields */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Create Date:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={product.create_date || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Create By:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={product.create_by || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Update Date:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={product.update_date || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Update By:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={product.update_by || "-"}
              readOnly
            />
          </div>

          {/* qtt Field */}
          <div>
            <label className="block text-sm font-bold">qtt (qtt):</label>
            <input
              type="number"
              value={qtt}
              onChange={handleqttChange}
              className="p-2 border rounded-md w-full"
            />
          </div>
        </div>
      ) : (
        <div className="text-gray-500 text-sm">
          Please select a product to view details.
        </div>
      )}
    </div>
  );
};

export default DetailPanel;

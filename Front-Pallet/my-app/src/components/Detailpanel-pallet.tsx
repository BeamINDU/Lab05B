import React, { useEffect, useState } from "react";

type Pallet = {
  palletid?: string;
  palletname?: string;
  palletlength?: number;
  palletwidth?: number;
  palletheight?: number;
  palletweight?: number;
  loadlength?: number;
  loadwidth?: number;
  loadheight?: number;
  loadweight?: number;
  createdate?: string;
  createby?: string;
  updatedate?: string;
  updateby?: string;
  qtt?: number;
};

type DetailPanelPalletProps = {
  pallet?: Pallet;
  onUpdateQtt: (palletid: string, newQtt: number) => void;
};

const DetailPanel_Pallet: React.FC<DetailPanelPalletProps> = ({
  pallet,
  onUpdateQtt,
}) => {
  const [qtt, setQtt] = useState<number>(pallet?.qtt || 1);
  const [updateDate] = useState(pallet?.updatedate || new Date().toISOString());

  useEffect(() => {
    if (pallet) {
      setQtt(pallet.qtt || 1);
      console.log("Updated Pallet qtt:", pallet.qtt);
    }
  }, [pallet]);

  const handleQttChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newQtt = parseInt(e.target.value, 10) || 1;
    setQtt(newQtt);

    if (pallet?.palletid) {
      onUpdateQtt(pallet.palletid, newQtt);
    }
  };

  
  return (
    <div className="w-1/3 bg-[#e2e8f0] p-6 rounded-lg shadow-md">
      <h2 className="text-lg font-bold mb-6">Detail</h2>
      {pallet ? (
        <div className="space-y-4">
          {/* Pallet Size */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Pallet Size <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.palletname || "-"}
                readOnly
              />
            </div>
          </div>

          {/* Pallet Length */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Pallet Length <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.palletlength || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Pallet Width */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Pallet Width <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.palletwidth || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Pallet Height */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Pallet Height <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.palletheight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Pallet Weight */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Pallet Weight <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.palletweight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">kg</span>
            </div>
          </div>

          {/* Load Pallet Dimensions */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Pallet Length <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.loadlength || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Pallet Width <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.loadwidth || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Pallet Height <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.loadheight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Pallet Weight <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={pallet.loadweight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">kg</span>
            </div>
          </div>

          {/* Metadata */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Create Date:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={pallet.createdate || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Create By:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={pallet.createby || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Update Date:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={updateDate}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Update By:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={pallet.updateby || "-"}
              readOnly
            />
          </div>
          <div>
            <label className="block text-sm font-bold">
              Quantity (qtt) <span className="text-red-500">*</span>:
            </label>
            <input
              type="number"
              min="1"
              className="p-2 border rounded-md w-full"
              value={qtt}
              onChange={handleQttChange}
            />
          </div>
        </div>
      ) : (
        <div className="text-gray-500 text-sm">
          Please select a pallet to view details.
        </div>
      )}
    </div>
  );
};

export default DetailPanel_Pallet;

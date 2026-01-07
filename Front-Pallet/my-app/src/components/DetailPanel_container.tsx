import React, { useEffect, useState } from "react";


type DetailPanelContainerProps = {
  container?: Container;
  onUpdateQtt: (containerId: number, newQtt: number) => void;

};

const DetailPanel_Container: React.FC<DetailPanelContainerProps> = ({ container, onUpdateQtt }) => {
  const [qtt, setQtt] = useState<number>(0);
  
  useEffect(() => {
    if (container) {
      setQtt(container.qtt || 0);
    }
  }, [container]);


  const handleQttChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newQtt = Math.max(parseInt(e.target.value, 10) || 0, 0);
    setQtt(newQtt);

    // ✅ ตรวจสอบว่า containerid มีอยู่จริงก่อนเรียก API
    if (container?.containerid !== undefined) {
      onUpdateQtt(container.containerid, newQtt);
    }
  };

  if (!container) {
    return (
      <div className="w-1/3 bg-gray-100 p-6 rounded-lg shadow-md">
        <p className="text-gray-500">Please select a container to view details.</p>
      </div>
    );
  }
  return (
    <div className="w-1/3 bg-[#e2e8f0] p-6 rounded-lg shadow-md">
      <h2 className="text-lg font-bold mb-6">Detail</h2>
      {container ? (
        <div className="space-y-4">
          {/* Container Size */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Container Size <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.containername || "-"}
                readOnly
              />
            </div>
          </div>

          {/* Container Length */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Container Length <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.containerlength || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Container Width */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Container Width <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.containerwidth || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Container Height */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Container Height <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.containerheight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>

          {/* Container Weight */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Container Weight <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.containerweight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">kg</span>
            </div>
          </div>

          {/* Load Container Dimensions */}
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Container Length <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.loadlength || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Container Width <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.loadwidth || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Container Height <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.loadheight || "-"}
                readOnly
              />
              <span className="ml-2 text-sm">cm</span>
            </div>
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">
              Load Container Weight <span className="text-red-500">*</span>:
            </label>
            <div className="flex items-center w-2/3">
              <input
                className="w-full p-2 rounded-md bg-[#c6c4c4] text-gray-700"
                value={container.loadweight || "-"}
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
              value={container.createdate || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Create By:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={container.createby || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Update Date:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={container.updatedate || "-"}
              readOnly
            />
          </div>
          <div className="flex items-center">
            <label className="w-1/3 font-bold text-sm">Update By:</label>
            <input
              className="w-2/3 p-2 rounded-md bg-[#c6c4c4] text-gray-700"
              value={container.updateby || "-"}
              readOnly
            />
          </div>
          <div>
          <label className="block text-sm font-bold">Quantity (qtt):</label>
          <input
            type="number"
            value={qtt}
            onChange={handleQttChange}
            className="p-2 border rounded-md w-full"
          />
        </div>
        </div>
      ) : (
        <div className="text-gray-500 text-sm">
          Please select a container to view details.
        </div>
      )}
    </div>
  );
};

export default DetailPanel_Container;

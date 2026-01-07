import React, { useState, useEffect } from "react";
import Image from "next/image";

type PalletData = {
  palletcode?: string;
  palletname?: string;
  palletwidth?: string;
  palletheight?: string;
  palletlength?: string;
  palletweight?: string;
  loadwidth?: string;
  loadheight?: string;
  loadlength?: string;
  loadweight?: string;
  palletsize?: string | undefined;
  color?: string;
  isCustom?: boolean;
};

type ModalPalletFormProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: PalletData) => void;
  palletData?: PalletData;
};
const ModalPalletForm: React.FC<ModalPalletFormProps> = ({
  onClose,
  onSave,
  palletData,
}) => {
  const [formData, setFormData] = useState<PalletData>({
    palletcode: "",
    palletname: "",
    palletwidth: "",
    palletheight: "",
    palletlength: "",
    palletweight: "",
    loadwidth: "",
    loadheight: "",
    loadlength: "",
    loadweight: "",
    palletsize: "Custom", 
    color: "#1CFD24", 
    isCustom: true, // Flag สำหรับ Custom
  });
  useEffect(() => {
    if (palletData) {
      const standardSizes = ["Standard: S", "Standard: M", "Standard: L"];
      setFormData((prev) => ({
        palletcode: palletData.palletcode || "",
        palletname: palletData.palletname || "",
        palletwidth: palletData.palletwidth || "",
        palletheight: palletData.palletheight || "",
        palletlength: palletData.palletlength || "",
        palletweight: palletData.palletweight || "",
        loadwidth: palletData.loadwidth || "",
        loadheight: palletData.loadheight || "",
        loadlength: palletData.loadlength || "",
        loadweight: palletData.loadweight || "",
        color: palletData.color || "#1CFD24",
        palletsize: palletData.palletsize ?? prev.palletsize ?? "Custom",
        isCustom: !standardSizes.includes(palletData.palletsize ?? "Custom"),
      }));
    }
  }, [palletData]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;

    if (name === "palletsize") {
      const standardSizes = ["Standard: S", "Standard: M", "Standard: L"];

      if (value === "Custom") {
        setFormData((prev) => ({
          ...prev,
          palletsize: value,
          isCustom: true,
          palletwidth: "",
          palletheight: "",
          palletlength: "",
          palletweight: "",
        }));
      } else {
        const sizes = {
          "Standard: S": {
            palletwidth: "100", // เปลี่ยนให้เป็น string
            palletheight: "50",
            palletlength: "80",
            palletweight: "20",
          },
          "Standard: M": {
            palletwidth: "120",
            palletheight: "70",
            palletlength: "100",
            palletweight: "25",
          },
          "Standard: L": {
            palletwidth: "140",
            palletheight: "90",
            palletlength: "120",
            palletweight: "30",
          },
        };
        setFormData((prev) => ({
          ...prev,
          palletsize: value,
          isCustom: !standardSizes.includes(value),
          ...sizes[value as keyof typeof sizes],
        }));
      }
    } else {
      setFormData((prev) => ({
        ...prev,
        [name]: value,
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const payload = { ...formData };
    delete payload.isCustom; 
    console.log("Payload before PUT:", payload); // Debug Payload
    onSave(payload);
  };
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
      <div className="bg-[#e2e8f0] rounded-lg shadow-lg w-[80%] max-w-6xl p-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">Pallet Setting</h2>
          <button
            onClick={onClose}
            className="text-gray-600 hover:text-gray-900 text-xl"
          >
            ✖
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-4">
              <div className="flex space-x-5 items-center">
                <label className="block text-sm font-bold text-black pr-3">
                  Pallet Code <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="palletcode"
                  value={formData.palletcode}
                  onChange={handleChange}
                  required
                  className="w-4/6 px-3 py-2 border border-gray-400 rounded-md"
                />
              </div>
              <div className="flex space-x-6 items-center">
                <label className="block text-sm font-bold pr-14 text-black">
                  Size <span className="text-red-500">*</span>
                </label>
                <select
                  name="palletsize"
                  value={formData.palletsize}
                  onChange={handleChange}
                  className="w-4/6 px-3 py-2 border border-gray-400 rounded-md"
                >
                  <option value="Standard: S">Standard: S</option>
                  <option value="Standard: M">Standard: M</option>
                  <option value="Standard: L">Standard: L</option>
                  <option value="Custom">Custom</option>
                </select>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-12">
                  Height <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="palletheight"
                  value={formData.palletheight}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-11">
                  Weight <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="palletweight"
                  value={formData.palletweight}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">kg</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-5">
                  Load Height
                </label>
                <input
                  type="number"
                  name="loadheight"
                  value={formData.loadheight}
                  onChange={handleChange}
                  min="0"
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex items-center space-x-4">
                <label className="block text-sm font-bold text-black pr-4">
                  Load Weight
                </label>
                <input
                  type="number"
                  name="loadweight"
                  value={formData.loadweight}
                  onChange={handleChange}
                  min="0"
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">kg</label>
              </div>
            </div>

            {/* Column ขวา */}
            <div className="space-y-4">
              <div className="flex items-center space-x-4">
                <label className="block text-sm font-bold text-black pr-5">
                  Pallet Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="palletname"
                  value={formData.palletname}
                  onChange={handleChange}
                  required
                  className="w-4/6 px-3 py-2 border border-gray-400 rounded-md"
                />
              </div>
              <div className="flex items-center space-x-6">
                <label className="block text-sm font-bold text-black pr-14">
                  Color <span className="text-red-500">*</span>
                </label>
                <input
                  type="color"
                  name="color"
                  value={formData.color}
                  onChange={handleChange}
                  className="w-10 h-10 border border-gray-400 rounded-md"
                />
                <input
                  type="text"
                  value={formData.color}
                  readOnly
                  className="p-2 w-36 bg-gray-300 text-black text-center rounded-md"
                />
              </div>
              <div className="flex items-center space-x-4">
                <label className="block text-sm font-bold text-black pr-16">
                  Width<span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="palletwidth"
                  value={formData.palletwidth}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex items-center space-x-4">
                <label className="block text-sm font-bold text-black pr-14">
                  Length<span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="palletlength"
                  value={formData.palletlength}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400  rounded-md"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-8">
                  Load Width
                </label>
                <input
                  type="number"
                  name="loadwidth"
                  value={formData.loadwidth}
                  onChange={handleChange}
                  min="0"
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex items-center space-x-4">
                <label className="block text-sm font-bold text-black pr-6">
                  Load Length
                </label>
                <input
                  type="number"
                  name="loadlength"
                  value={formData.loadlength}
                  onChange={handleChange}
                  min="0"
                  className="w-1/2 px-3 py-2 border border-gray-400 rounded-md"
                />
                <label className="text-sm font-bold">cm</label>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end mt-6 mr-12">
            <button
              type="submit"
              className="flex items-center justify-center space-x-2 px-4 py-2 bg-[#004798] text-white rounded hover:bg-blue-950 w-36 h-11"
            >
              <span>Save</span>
              <Image
                src="/icon/save.svg" // ไฟล์ไอคอนต้องอยู่ในโฟลเดอร์ public
                alt="Save Icon"
                width={24}
                height={24}
              />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ModalPalletForm;

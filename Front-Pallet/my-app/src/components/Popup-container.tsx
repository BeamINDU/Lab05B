/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useState, useEffect } from "react";
import Image from "next/image";
type ContainerData = {
  containerid: number | null;  // เปลี่ยนจาก `undefined` เป็น `number | null`
  containercode?: string;
  containername?: string;
  containerwidth?: string;
  containerheight?: string;
  containerlength?: string;
  containerweight?: string;
  loadwidth?: string;
  loadheight?: string;
  loadlength?: string;
  loadweight?: string;
  size?: string;
  qtt?:number;
  color?: string;
  isCustom?: boolean;
  createby?:string;
  containersize?:string;

};

type ModalContainerFormProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: Container) => void;
  containerData?: Container;
};

const ModalContainerForm: React.FC<ModalContainerFormProps> = ({
  isOpen,
  onClose,
  onSave,
  containerData,
}) => {
  const [formData, setFormData] = useState<ContainerData>({
    containerid:null,
    containercode: "",
    containername: "",
    containerwidth: "",
    containerheight: "",
    containerlength: "",
    containerweight: "",
    loadwidth: "",
    loadheight: "",
    loadlength: "",
    loadweight: "",
    containersize: "Custom",
    color: "#1CFD24",
    isCustom: true,
  });

  useEffect(() => {
    if (containerData) {
      setFormData({
        containerid:null,
        containercode: containerData.containercode || "",
        containername: containerData.containername || "",
        containerwidth: '' + containerData.containerwidth || "",
        containerheight: '' +containerData.containerheight || "",
        containerlength: '' +containerData.containerlength || "",
        containerweight: '' +containerData.containerweight || "",
        loadwidth: `${containerData.loadwidth}` || "",
        loadheight: `${containerData.loadheight}` || "",
        loadlength: `${containerData.loadlength}` || "",
        loadweight: `${containerData.loadweight}` || "",
        color: `${containerData.color}` || "#1CFD24",
        containersize: `${containerData.containersize}` || "Custom",
        isCustom: `${containerData.containersize}` === "Custom",
      });
    }
  }, [containerData]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;

    if (name === "containersize") {
      if (value === "Custom") {
        setFormData((prev) => ({
          ...prev,
          containersize: value,
          isCustom: true,
          containerwidth: "",
          containerheight: "",
          containerlength: "",
          containerweight: "",
        }));
      } else {
        const sizes: Record<
          "Standard: S" | "Standard: M" | "Standard: L",
          {
            containerwidth: string;
            containerheight: string;
            containerlength: string;
            containerweight: string;
          }
        > = {
          "Standard: S": {
            containerwidth: "100",
            containerheight: "50",
            containerlength: "80",
            containerweight: "20",
          },
          "Standard: M": {
            containerwidth: "120",
            containerheight: "70",
            containerlength: "100",
            containerweight: "25",
          },
          "Standard: L": {
            containerwidth: "140",
            containerheight: "90",
            containerlength: "120",
            containerweight: "30",
          },
        };
        setFormData((prev) => ({
          ...prev,
          containersize: value,
          isCustom: false,
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

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const { isCustom, ...payload } = formData; 
  
    console.log("Payload before PUT:", payload); 
  
    onSave({
      containerid: formData.containerid ?? 0, 
      containercode: String(formData.containercode),
      containername: formData.containername ?? "",
      containerwidth: parseFloat(formData.containerwidth ?? "0"),
      containerheight: parseFloat(formData.containerheight ?? "0"),
      containerlength: parseFloat(formData.containerlength ?? "0"),
      containerweight: parseFloat(formData.containerweight ?? "0"),
      loadwidth: parseFloat(formData.loadwidth ?? "0"),
      loadheight: parseFloat(formData.loadheight ?? "0"),
      loadlength: parseFloat(formData.loadlength ?? "0"),
      loadweight: parseFloat(formData.loadweight ?? "0"),
      qtt: formData.qtt ?? 1,
      createby: formData.createby ?? "",
      updateby: "admin", //  กำหนดค่า updateby
      updatedate: new Date().toISOString(), //  กำหนดค่า updatedate
      color: formData.color ?? "#FFFFFF",
      containersize: formData.containersize ?? "Custom",
    });
  };
  
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
      <div className="bg-[#e2e8f0] rounded-lg shadow-lg w-[55%] max-w-6xl p-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">container Setting</h2>
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
              <div className="flex space-x-9 items-center">
                <label className="block text-sm font-bold text-black">
                  Container Code <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="containercode"
                  value={formData.containercode}
                  onChange={handleChange}
                  required
                  className="w-4/6 px-3 py-2 border border-gray-400  rounded-md"
                />
              </div>
              <div className="flex space-x-12 items-center">
                <label className="block text-sm font-bold text-black pr-16 ">
                  Size <span className="text-red-500">*</span>
                </label>
                <select
                  name="containersize"
                  value={formData.containersize}
                  onChange={handleChange}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                >
                  <option value="Standard: S">Standard: S</option>
                  <option value="Standard: M">Standard: M</option>
                  <option value="Standard: L">Standard: L</option>
                  <option value="Custom">Custom</option>
                </select>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-20">
                  Height  <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="containerheight"
                  value={formData.containerheight}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
              <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-[78px]">
                  Weight <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="containerweight"
                  value={formData.containerweight}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
              <label className="text-sm font-bold">kg</label>

              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-11">
                  Load Height <span className="text-red-500">*</span>
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
                <label className="block text-sm font-bold text-black pr-10">
                  Load Weight <span className="text-red-500">*</span>
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

            {/* Right Column */}
            <div className="space-y-4">
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-4">
                  Container Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="containername"
                  value={formData.containername}
                  onChange={handleChange}
                  required
                  className="w-4/6 px-3 py-2 border border-gray-400 rounded-md"
                />
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-24">
                  Color 
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
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-[87px]">
                  Width<span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="containerwidth"
                  value={formData.containerwidth}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
              <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-[75px]">
                  Length <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="containerlength"
                  value={formData.containerlength}
                  onChange={handleChange}
                  disabled={!formData.isCustom}
                  className="w-2/4 px-3 py-2 border border-gray-400 rounded-md"
                />
              <label className="text-sm font-bold">cm</label>
              </div>
              <div className="flex space-x-4 items-center">
                <label className="block text-sm font-bold text-black pr-12">
                  Load Width <span className="text-red-500">*</span>
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
                <label className="block text-sm font-bold text-black pr-10">
                  Load Length <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="loadlength"
                  value={formData.loadlength}
                  onChange={handleChange}
                  min="0"
                  className="w-2/4 px-3 py-2 border-gray-400 border rounded-md"
                />
              <label className="text-sm font-bold">cm</label>
              </div>
            </div>
          </div>

          {/* Load Dimensions */}
          {/* <div className="grid grid-cols-2 gap-6 mt-4">
            {["loadheight", "loadwidth", "loadlength", "loadweight"].map(
              (field, index) => (
                <div key={index}>
                  <label className="block text-sm font-bold text-black">
                    {field.replace("load", "Load ")} (cm)
                  </label>
                  <input
                    type="number"
                    name={field}
                    value={formData[field]}
                    onChange={handleChange}
                    min="0"
                    className="mt-1 w-2/4 px-3 py-2 border rounded-md"
                  />
                </div>
              )
            )}
          </div> */}

          {/* Save Button */}
          <div className="flex justify-end mt-6">
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

export default ModalContainerForm;

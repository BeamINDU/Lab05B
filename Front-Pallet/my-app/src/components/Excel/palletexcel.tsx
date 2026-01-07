import React from "react";

type ExcelUploadProps = {
  onUpload: () => void;
};

const PalletExcelUpload: React.FC<ExcelUploadProps> = ({ onUpload }) => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (file) {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`${apiUrl}/pallets/upload/`, {
          method: "POST",
          body: formData,
        });

        if (response.ok) {
          console.log("File uploaded successfully");
          onUpload(); // Callback to refresh the product list
        } else {
          console.error("Failed to upload file");
        }
      } catch (error) {
        console.error("Error uploading file:", error);
      }
    }
  };

  return (
    <div className="flex items-center space-x-4">
      <label
        htmlFor="excel-upload"
        className="bg-green-600 text-white px-4 py-2 rounded-md cursor-pointer"
      >
        Upload Excel
      </label>
      <input
        id="excel-upload"
        type="file"
        accept=".xlsx, .xls"
        onChange={handleFileUpload}
        className="hidden"
      />
    </div>
  );
};

export default PalletExcelUpload;

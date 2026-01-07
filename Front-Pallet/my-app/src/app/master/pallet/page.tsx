"use client";

import React, { useState, useEffect, useCallback } from "react";
import ModalPalletForm from "../../../components/Popup-pallet";
import DetailPanel_Pallet from "../../../components/Detailpanel-pallet";
import PalletExcelUpload from "@/components/Excel/palletexcel";
type PalletResponse = {
  items: Pallet[];
  total_count: number;
};
type PalletData = Partial<Pallet>;


const PalletPage: React.FC = () => {
  const [pallets, setPallets] = useState<Pallet[]>([]); // Pallets for the current page
  const [totalItems, setTotalItems] = useState<number>(0); // Total number of items in the database
  const [selectedPallet, setSelectedPallet] = useState<Pallet | undefined>();
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 10;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL; 

  const fetchPallets = useCallback(async () => {
    try {
      const response = await fetch(
        `${apiUrl}/pallets/?skip=${
          (currentPage - 1) * itemsPerPage
        }&limit=${itemsPerPage}`
      );
      if (!response.ok) throw new Error("Failed to fetch pallets");

      const data: PalletResponse = await response.json();
      setPallets(data.items); // Pallets for the current page
      setTotalItems(data.total_count); // Total number of items
    } catch (error) {
      console.error("Error fetching pallets:", error);
      setPallets([]);
    }
  }, [apiUrl, currentPage]);

  useEffect(() => {
    fetchPallets();
  }, [fetchPallets]);

  const openModal = (pallet: Pallet | undefined = undefined) => {
    setSelectedPallet(pallet);
    setIsEditing(!!pallet);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedPallet(undefined);
    setIsEditing(false);
  };

  const handleSavePallet = async (palletData: PalletData) => {
    try {
      const url = isEditing
        ? `${apiUrl}/pallets/${selectedPallet?.palletid}`
        : `${apiUrl}/pallets`;

      const method = isEditing ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(palletData),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to save pallet: ${errorText}`);
      }

      console.log("Pallet saved successfully!");
      await fetchPallets();
      closeModal();
    } catch (error: unknown) {
      if (error instanceof Error) {
        console.error("Error saving pallet:", error.message);
      } else {
        console.error("Unknown error occurred while saving pallet:", error);
      }
    }
  };

  const handleDeletePallet = async (palletid: string) => {
    if (!palletid) {
      console.error("palletid is undefined");
      return;
    }

    if (!window.confirm("Are you sure you want to delete this pallet?")) return;

    try {
      const response = await fetch(
        `${apiUrl}/pallets/${palletid}`,
        { method: "DELETE" }
      );

      if (!response.ok) throw new Error("Failed to soft delete pallet");

      console.log("Pallet deleted successfully");
      await fetchPallets();
    } catch (error: unknown) {
      if (error instanceof Error) {
        console.error("Error soft deleting pallet:", error.message);
      } else {
        console.error(
          "Unknown error occurred while soft deleting pallet:",
          error
        );
      }
    }
  };

  const totalPages = Math.ceil(totalItems / itemsPerPage);

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };
  const handleUpdateQtt = async (palletId: string, newQtt: number) => {
    try {
      const response = await fetch(`${apiUrl}/pallets/${palletId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ qtt: newQtt, updatedate: new Date().toISOString() }),
      });
  
      if (!response.ok) {
        throw new Error("Failed to update qtt");
      }
  
      const updatedPallet = await response.json();
  
      // อัปเดตข้อมูลใน state
      setPallets((prevPallets) =>
        prevPallets.map((p) =>
          p.palletid === updatedPallet.palletid ? updatedPallet : p
        )
      );
  
      if (selectedPallet?.palletid === updatedPallet.palletid) {
        setSelectedPallet(updatedPallet);
      }
  
      console.log("qtt updated successfully:", updatedPallet);
    } catch (error) {
      console.error("Error updating qtt:", error);
    }
  };
  
  
  return (
    <div className="flex h-full space-x-4">
      <div className="w-[1056px] h-[950px] mb-4 bg-slate-200">
        <h2 className="ml-12 text-xl font-extrabold mb-10 mt-4">Pallet List</h2>
        <table className="ml-6 mr-6 w-[1004.81px] h-[711.84px] border-collapse border-spacing-0 border bg-white border-gray-300 rounded-lg overflow-hidden shadow-md">
          <thead>
            <tr className="bg-[#c1d9ff]">
              <th className="px-4 py-4 text-center font-bold"></th>
              <th className="px-4 py-4 font-bold">No.</th>
              <th className="px-4 py-4 font-bold">Pallet Code</th>
              <th className="px-4 py-4 font-bold">Pallet Name</th>
              <th className="px-4 py-4 font-bold">Pallet Color</th>
              <th className="px-4 py-4 text-center font-bold"></th>
            </tr>
          </thead>
          <tbody>
            {pallets.map((pallet, index) => (
              <tr
                key={pallet.palletid}
                className="border-b border-[#d6d6d6] hover:bg-gray-50"
              >
                <td className="px-4 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={selectedPallet?.palletid === pallet.palletid}
                    onChange={() => {
                      setSelectedPallet((prevSelected) =>
                        prevSelected?.palletid === pallet.palletid
                          ? undefined
                          : pallet
                      );
                    }}
                  />
                </td>
                <td className="px-4 py-2 text-center">
                  {(currentPage - 1) * itemsPerPage + index + 1}
                </td>
                <td className="px-4 py-2 text-center">
                  {pallet.palletcode || "-"}
                </td>
                <td className="px-4 py-2 text-center">
                  {pallet.palletname || "-"}
                </td>
                <td className="px-4 py-2 text-center">
                  <div
                    className="w-6 h-6 mx-auto rounded-md"
                    style={{ backgroundColor: pallet.color || "#000000" }}
                  ></div>
                </td>
                <td className="px-4 py-2 text-center">
                  <div className="flex justify-center space-x-2">
                    <button
                      onClick={() => openModal(pallet)}
                      disabled={selectedPallet?.palletid !== pallet?.palletid}
                      className={`px-3 py-1 w-[80px] h-[36] rounded-md ${
                        selectedPallet?.palletid === pallet?.palletid
                          ? "bg-blue-500 text-white hover:bg-blue-500"
                          : "bg-gray-300 text-gray-500 cursor-not-allowed"
                      }`}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => {
                        handleDeletePallet(pallet.palletid);
                      }}
                      disabled={selectedPallet?.palletid !== pallet?.palletid}
                      className={`px-3 py-1 w-[80px] h-[36] rounded-md ${
                        selectedPallet?.palletid === pallet?.palletid
                          ? "bg-red-500 text-white hover:bg-red-600"
                          : "bg-gray-300 text-gray-500 cursor-not-allowed"
                      }`}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {Array.from({
              length: itemsPerPage - pallets.length,
            }).map((_, index) => (
              <tr key={`empty-row-${index}`}>
                <td className="px-4 py-3 text-center">&nbsp;</td>
                <td className="px-4 py-3 text-center">&nbsp;</td>
                <td className="px-4 py-3">&nbsp;</td>
                <td className="px-4 py-3">&nbsp;</td>
                <td className="px-4 py-3">&nbsp;</td>
                <td className="px-4 py-3">&nbsp;</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="flex justify-between items-center mt-4">
          <div className="flex space-x-4">
          <button
            onClick={() => {
              setIsEditing(false);
              openModal();
            }}
            className="bg-blue-900 ml-6 text-white px-4 py-2 rounded-md"
          >
            + Add Pallet
          </button>
          <PalletExcelUpload onUpload={fetchPallets} />
          </div>      
          <div className="flex items-center space-x-2 mr-6">
            <button
              onClick={handlePreviousPage}
              disabled={currentPage === 1}
              className={`w-8 h-8 flex items-center justify-center rounded-full border border-gray-300 ${
                currentPage === 1
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : "bg-white text-gray-700 hover:bg-blue-500 hover:text-white"
              }`}
            >
              <span className="material-icons">chevron_left</span>
            </button>
            <span className="text-gray-700 font-bold">
              Page {currentPage} / {totalPages}
            </span>
            <button
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
              className={`w-8 h-8 flex items-center justify-center rounded-full border border-gray-300 ${
                currentPage === totalPages
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : "bg-white text-gray-700 hover:bg-blue-500 hover:text-white"
              }`}
            >
              <span className="material-icons">chevron_right</span>
            </button>
          </div>
        </div>
      </div>
      <DetailPanel_Pallet pallet={selectedPallet} onUpdateQtt={handleUpdateQtt} />

      {isModalOpen && (
        <ModalPalletForm
          isOpen={isModalOpen}
          onClose={closeModal}
          onSave={handleSavePallet}
          palletData={selectedPallet} // รองรับ undefined ได้
        />
      )}
    </div>
  );
};

export default PalletPage;

"use client";

import React, { useState, useEffect, useCallback } from "react";
import ModalContainerForm from "../../../components/Popup-container";
import DetailPanel_Container from "../../../components/DetailPanel_container";
import ContainerExcelUpload from "@/components/Excel/containerexcel";


type ContainerResponse = {
  items: Container[];
  total_count: number;
};

const ContainerPage: React.FC = () => {
  const [containers, setContainers] = useState<Container[]>([]);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [selectedContainer, setSelectedContainer] = useState<Container | undefined>();
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 10;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL; 

  const fetchContainers = useCallback(async () => {
 
    try {
      const response = await fetch(
        `${apiUrl}/containers/?skip=${
          (currentPage - 1) * itemsPerPage
        }&limit=${itemsPerPage}`
      );
  
      if (!response.ok) throw new Error("Failed to fetch containers");
  
      const data: ContainerResponse = await response.json();
      setContainers(data.items);
      setTotalItems(data.total_count);
    } catch (error) {
      console.error("Error fetching containers:", error);
      setContainers([]);
    }
  }, [apiUrl, currentPage]);
  

  useEffect(() => {
    fetchContainers();
  }, [fetchContainers]);

  const openModal = (container: Container | undefined = undefined) => {
    setSelectedContainer(container);
    setIsEditing(!!container);
    setIsModalOpen(true);
  };
  
  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedContainer(undefined);
    setIsEditing(false);
  };

  const handleSaveContainer = async (payload: Container) => {
    const finalData: Container = {
      ...payload,
      containerid: selectedContainer?.containerid ,
    };
  
    try {
      const url = isEditing
        ? `${apiUrl}/containers/${selectedContainer?.containerid}`
        : `${apiUrl}/containers`;
  
      const method = isEditing ? "PUT" : "POST";
  
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(finalData),
      });
  
      if (!response.ok) {
        throw new Error("Failed to save container");
      }
  
      console.log("Data saved successfully!");
      await fetchContainers();
      closeModal();
    } catch (error: unknown) {
      if (error instanceof Error) {
        console.error("Error saving container:", error.message);
      } else {
        console.error("Unknown error occurred while saving container:", error);
      }
    }
  };

  const handleDeleteContainer = async (containerid: number | undefined) => {
    if (!containerid) {
      console.error("containerid is undefined");
      return;
    }

    try {
      console.log("Deleting container with ID:", containerid);
      const response = await fetch(
        `${apiUrl}/containers/${containerid}`,
        { method: "DELETE" }
      );

      if (!response.ok) throw new Error("Failed to soft delete container");

      console.log("Container deleted successfully");
      await fetchContainers();
    } catch (error: unknown) {
      if (error instanceof Error) {
        console.error("Error soft deleting container:", error.message);
      } else {
        console.error("Unknown error occurred while soft deleting container:", error);
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
  const handleUpdateQtt = async (containerId: number, newQtt: number) => {
    try {
      const response = await fetch(`${apiUrl}/containers/${String(containerId)}`, {  // ✅ แปลงเป็น string
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ qtt: newQtt, updatedate: new Date().toISOString() }),
      });
  
      if (!response.ok) {
        throw new Error("Failed to update qtt");
      }
  
      const updatedContainer = await response.json();
  
      // ✅ อัปเดตข้อมูลใน state
      setContainers((prevContainers) =>
        prevContainers.map((c) =>
          c.containerid === updatedContainer.containerid ? updatedContainer : c
        )
      );
  
      if (selectedContainer?.containerid === updatedContainer.containerid) {
        setSelectedContainer(updatedContainer);
      }
  
      console.log("qtt updated successfully:", updatedContainer);
    } catch (error) {
      console.error("Error updating qtt:", error);
    }
  };
  
  return (
    <div className="flex h-full space-x-4 ">
      <div className="w-[1056px] h-[950px] mb-4 bg-slate-200">
        <h2 className="ml-12 text-xl font-extrabold mb-10 mt-4">Container List</h2>
        <table className="ml-6 mr-6 w-[1004.81px] h-[711.84px] border-collapse border-spacing-0 border bg-white border-gray-300 rounded-lg overflow-hidden shadow-md">
          <thead>
            <tr className="bg-[#c1d9ff] ">
              <th className="px-4 py-4 text-center font-bold"></th>
              <th className="px-4 py-4 font-bold">No.</th>
              <th className="px-4 py-4 font-bold">Container Code</th>
              <th className="px-4 py-4 font-bold">Container Name</th>
              <th className="px-4 py-4 font-bold">Container Color</th>
              <th className="px-4 py-4 text-center font-bold"></th>
            </tr>
          </thead>
          <tbody>
            {containers.map((container, index) => (
              <tr
                key={container.containerid || index}
                className="border-b border-[#d6d6d6] hover:bg-gray-50"
              >
                <td className="px-4 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={
                      selectedContainer?.containerid === container.containerid
                    }
                    onChange={() => {
                      setSelectedContainer((prevSelected) =>
                        prevSelected?.containerid === container.containerid
                          ? undefined
                          : container
                      );
                    }}
                  />
                </td>
                <td className="px-4 py-2 text-center">
                  {(currentPage - 1) * itemsPerPage + index + 1}
                </td>
                <td className="px-4 py-2 text-center">
                  {container.containercode || "-"}
                </td>
                <td className="px-4 py-2 text-center">
                  {container.containername || "-"}
                </td>
                <td className="px-4 py-2  ">
                  <div
                    className="w-6 h-6 mx-auto rounded-md"
                    style={{ backgroundColor: container.color || "#000000" }}
                  ></div>
                </td>
                <td className="px-4 py-2 text-center">
                  <div className="flex justify-center space-x-2">
                    <button
                      onClick={() => openModal(container)}
                      disabled={
                        selectedContainer?.containerid !==
                        container?.containerid
                      }
                      className={`px-3 py-1 w-[80px] h-[36] rounded-md ${
                        selectedContainer?.containerid ===
                        container?.containerid
                          ? "bg-blue-500 text-white hover:bg-blue-500"
                          : "bg-gray-300 text-gray-500 cursor-not-allowed"
                      }`}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => {
                        handleDeleteContainer(container.containerid);
                      }}
                      disabled={
                        selectedContainer?.containerid !==
                        container?.containerid
                      }
                      className={`px-3 py-1 w-[80px] h-[36] rounded-md ${
                        selectedContainer?.containerid ===
                        container?.containerid
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
              length: itemsPerPage - containers.length,
            }).map((_, index) => (
              <tr key={`empty-row-${index}`} className="">
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

        <div className="flex justify-between items-center mt-4 ">
          <div className="flex space-x-4">
          <button
            onClick={() => {
              setIsEditing(false);
              openModal();
            }}
            className="bg-blue-900 ml-6 text-white px-4 py-2 rounded-md"
          >
            + Add Container
          </button>
          <ContainerExcelUpload onUpload={fetchContainers} />
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
      <DetailPanel_Container container={selectedContainer} onUpdateQtt={handleUpdateQtt} />

      {isModalOpen && (
        <ModalContainerForm
          isOpen={isModalOpen}
          onClose={closeModal}
          onSave={handleSaveContainer}
          containerData={selectedContainer}
        />
      )}
    </div>
  );
};

export default ContainerPage;

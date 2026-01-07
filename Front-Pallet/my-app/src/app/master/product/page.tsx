"use client";

import React, { useState, useEffect, useCallback } from "react";
import ModalProductForm from "../../../components/Popup-product";
import DetailPanel from "../../../components/Detailproduct";
import ProductExcelUpload from "@/components/Excel/productexcel";

type ProductResponse = {
  items: Product[];
  total_count: number;
};

const ProductPage: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product>();
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 10;
  const [totalPages, setTotalPages] = useState<number>(1);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL; 

  const fetchProducts = useCallback(
    async (page: number = currentPage) => {
      const skip = (page - 1) * itemsPerPage;

      try {
        const response = await fetch(
          `${apiUrl}/products/?skip=${skip}&limit=${itemsPerPage}`
        );
        const data: ProductResponse = await response.json();

        if (data.items) {
          setProducts(data.items);
          setTotalPages(Math.ceil(data.total_count / itemsPerPage));
        } else {
          setProducts([]);
        }
      } catch (error) {
        console.error("Error fetching products:", error);
      }
    },
    [apiUrl, currentPage]
  );

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const openModal = () => setIsModalOpen(true);

  const closeModal = () => {
    setIsModalOpen(false);
    setIsEditing(false);
    setSelectedProduct(undefined);
  };

  const handleSaveProduct = async (productData: Product) => {
    try {
      const url = productData.productid
        ? `${apiUrl}/products/${productData.productid}`
        : `${apiUrl}/products/`;

      const method = productData.productid ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(productData),
      });

      if (response.ok) {
        fetchProducts(currentPage);
        closeModal();
      } else {
        console.error(
          productData.productid
            ? "Failed to update product."
            : "Failed to create product."
        );
      }
    } catch (error) {
      console.error(
        productData.productid
          ? "Error updating product."
          : "Error saving product.",
        error
      );
    }
  };

  const handleEdit = (product: Product) => {
    setSelectedProduct(product); // ตั้งค่า selectedProduct ก่อน
    setIsEditing(true);
    openModal(); // เปิด Modal
  };

  const handleDelete = async () => {
    if (selectedProduct) {
      try {
        const response = await fetch(
          `${apiUrl}/products/${selectedProduct.productid}`,
          {
            method: "DELETE",
          }
        );

        if (!response.ok) {
          console.error("Failed to delete product.");
          return;
        }

        fetchProducts(currentPage);
        setSelectedProduct(undefined);
      } catch (error) {
        console.error("Error deleting product:", error);
      }
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      fetchProducts(nextPage);
    }
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      const prevPage = currentPage - 1;
      setCurrentPage(prevPage);
      fetchProducts(prevPage);
    }
  };

  const handleUpdateqtt = async (productid: string, newqtt: number) => {
    try {
      const response = await fetch(
        `${apiUrl}/products/${productid}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ qtt: newqtt }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to update qtt");
      }

      const updatedProduct = await response.json();

      setProducts((prevProducts) =>
        prevProducts.map((p) =>
          p.productid === updatedProduct.productid ? updatedProduct : p
        )
      );

      if (selectedProduct?.productid === updatedProduct.productid) {
        setSelectedProduct(updatedProduct);
      }

      console.log("qtt updated successfully:", updatedProduct);
    } catch (error) {
      console.error("Error updating qtt:", error);
    }
  };

  return (
    <div className="flex h-full space-x-4 ">
      <div className="w-[1056px] h-screen min-h-[950px] mb-4 bg-[#e2e8f0]">
        <h2 className="ml-12 text-xl font-extrabold mb-10 mt-4">
          Product List
        </h2>
        <table className="ml-6 mr-6 w-[1004.81px] h-[711.84px] border-collapse border-spacing-0 border bg-white border-gray-300 rounded-lg overflow-hidden shadow-md">
          <thead>
            <tr className="bg-[#c1d9ff] ">
              <th className="px-4 py-4 text-center font-bold"></th>
              <th className="px-4 py-4 font-bold">No.</th>
              <th className="px-4 py-4 font-bold">Product Code</th>
              <th className="px-4 py-4 font-bold">Product Name</th>
              <th className="px-4 py-4 font-bold">Product Color</th>
              <th className="px-4 py-4 text-center font-bold"></th>
            </tr>
          </thead>
          <tbody>
            {products.map((product, index) => (
              <tr
                key={product.productid}
                className=" border-b border-[#d6d6d6] hover:bg-gray-50"
              >
                <td className="px-4 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={selectedProduct?.productid === product.productid}
                    onChange={() => setSelectedProduct(product)}
                  />
                </td>
                <td className="px-4 py-2 text-center">
                  {(currentPage - 1) * itemsPerPage + index + 1}
                </td>
                <td className="px-4 py-2 text-center">
                  {product.productcode || "-"}
                </td>
                <td className="px-4 text-center py-2">
                  {product.productname || "-"}
                </td>
                <td className="px-4 py-2">
                  <div
                    className="w-6 h-6 mx-auto rounded-md"
                    style={{ backgroundColor: product.color || "#ffffff" }}
                  ></div>
                </td>
                <td className="px-4 py-2 text-center">
                  <div className="flex justify-center space-x-2">
                    <button
                      onClick={() => {
                        handleEdit(product);
                      }}
                      disabled={
                        selectedProduct?.productid !== product.productid
                      }
                      className={`px-3 py-1 w-[80px] rounded-md ${
                        selectedProduct?.productid === product?.productid
                          ? "bg-blue-500 text-white hover:bg-blue-600"
                          : "bg-gray-300 text-gray-500 cursor-not-allowed"
                      }`}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => {
                        setSelectedProduct(product);
                        handleDelete();
                      }}
                      disabled={
                        selectedProduct?.productid !== product?.productid
                      }
                      className={`px-3 py-1 w-[80px] h-[36] rounded-md ${
                        selectedProduct?.productid === product?.productid
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
            {Array.from({ length: itemsPerPage - products.length }).map(
              (_, index) => (
                <tr key={`empty-row-${index}`} className="">
                  <td className="px-4 py-3 text-center">&nbsp;</td>
                  <td className="px-4 py-3 text-center">&nbsp;</td>
                  <td className="px-4 py-3">&nbsp;</td>
                  <td className="px-4 py-3">&nbsp;</td>
                  <td className="px-4 py-3">&nbsp;</td>
                  <td className="px-4 py-3">&nbsp;</td>
                </tr>
              )
            )}
          </tbody>
        </table>

        <div className="flex justify-between items-center mt-4  ">
          <div className="flex space-x-4">
          <button
            onClick={() => {
              setIsEditing(false);
              openModal();
            }}
            className="bg-blue-900 ml-6 text-white px-4 py-2 rounded-md"
          >
            + Add Product
          </button>
          <ProductExcelUpload onUpload={fetchProducts} />
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
      <DetailPanel product={selectedProduct} onUpdateqtt={handleUpdateqtt} />

      {isModalOpen && (
        <ModalProductForm
          isOpen={isModalOpen}
          onClose={closeModal}
          onSave={handleSaveProduct}
          fetchProducts={fetchProducts}
          productData={isEditing ? selectedProduct : undefined}
        />
      )}
    </div>
  );
};

export default ProductPage;

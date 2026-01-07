// src/components/Sidebar.tsx
"use client";
import Link from "next/link";
import React, { useState } from "react";
import { usePathname } from "next/navigation";
import Image from "next/image";
const Sidebar = () => {
  // State สำหรับควบคุมการแสดงผลของเมนูย่อย
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const currentPath = usePathname();

  // ฟังก์ชันสำหรับสลับการแสดงผลเมนูย่อย
  const toggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };
  const handleLogout = () => {
    // ใส่ logic สำหรับ log out ที่นี่ เช่น clear token, redirect ไปหน้า login
    console.log("User logged out");
    window.location.href = "/login"; // เปลี่ยนเส้นทางไปที่หน้าล็อกอิน
  };
  return (
    <div className="flex flex-col absolute top-260 left-0 items-start bg-[#e2e8f0] w-[331px] min-h-screen h-full  mt-2 ml-0">
      <nav className=" flex flex-col  h-full gap-2 ">
        {/* Dropdown for Master Data */}

        <div className="relative">
          <a
            onClick={toggleDropdown}
            className={`w-[331px] py-3 pl-28  text-left  font-bold hover:bg-blue-600 flex items-center justify-between 
    ${isDropdownOpen ? "bg-[#0369A1] text-white pl-28 " : "bg-[#0ea5e9] text-black pl-28 "}`}
            role="button"
          >
            Master Data
            <Image
              src={
                isDropdownOpen
                  ? "/icon/dropdown.svg"
                  : "/icon/dropup.svg"
              }
              alt="Toggle Icon"
              width={20} // กำหนดขนาดตามต้องการ
              height={20}

            />{" "}
          </a>

          {isDropdownOpen && (
            <div className="flex flex-col   bg-[#e2e8f0] text-black gap-1 py-1 font-bold ">
              <Link href="/master/product" legacyBehavior>
                <a
                  className={`block py-3 px-6 border border-[#c8c0c0] hover:bg-[#9da1a3] ${
                    currentPath === "/master/product"
                      ? "bg-[#d8dfe2] pl-28 "
                      : "text-black bg-white border-r-8 border-r-[#004798] pl-28 "
                  }`}
                >
                  Product
                </a>
              </Link>
              <Link href="/master/pallet" legacyBehavior>
                <a
                  className={`block py-3 px-6 border border-[#c8c0c0] hover:bg-[#9da1a3] ${
                    currentPath === "/master/pallet"
                      ? "bg-[#d8dfe2] pl-28 "
                      : "text-black bg-white border-r-8 border-r-[#004798] pl-28 "
                  }`}
                >
                  Pallet
                </a>
              </Link>
              <Link href="/master/container" legacyBehavior>
                <a
                  className={`block py-3 px-6 border border-[#c8c0c0] hover:bg-[#9da1a3] ${
                    currentPath === "/master/container"
                      ? "bg-[#d8dfe2] pl-28 "
                      : "text-black bg-white border-r-8 border-r-[#004798] pl-28 "
                  }`}
                >
                  Container
                </a>
              </Link>
            </div>
          )}
        </div>
        <Link href="/order" legacyBehavior>
          <a
            className={`w-[331px] py-3 pl-28  font-bold hover:bg-blue-600 
      ${
        currentPath === "/order"
          ? "bg-[#0369A1] text-white pl-28 "
          : "bg-[#0ea5e9] text-black"
      }`}
          >
            ORDER
          </a>
        </Link>

        <Link href="/simulate" legacyBehavior>
          <a
            className={`w-[331px]  py-3 pl-28   font-bold hover:bg-blue-600 ${
              currentPath === "/simulate"
                ? "bg-[#0369A1] text-white"
                : "bg-[#0ea5e9] text-black"
            }`}
          >
            SIMULATE
          </a>
        </Link>

        <Link href="/Report" legacyBehavior>
          <a
            className={`w-[331px]  py-3 pl-28     text-black font-bold hover:bg-blue-600 ${
              currentPath === "/Report"
                ? "bg-[#0369A1] text-white pl-28 "
                : "bg-[#0ea5e9] text-black"
            }`}
          >
            REPORT
          </a>
        </Link>
        <div className="mt-auto w-full">
          <button
            onClick={handleLogout}
            className="w-[331px] py-3 pl-28  space-x-4 bg-[#64748b]  text-white font-bold hover:bg-gray-700 flex items-center"
          >
            Log Out
            <span className="ml-3">
            <Image
              src={
                "/icon/log-out.svg"
              }
              alt="Icon"
              width={20} // กำหนดขนาดตามต้องการ
              height={20}

            />       
            </span>   
          </button>
        </div>
      </nav>
    </div>
  );
};

export default Sidebar;

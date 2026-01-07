// import Link from "next/link";
import Image from "next/image";
import { Nunito } from "next/font/google";

const nunito = Nunito({ subsets: ["latin"], weight: ["400", "600", "700"] });

const Navbar = () => {
  return (
    <nav className={`h-[131px]  custom-navbar ${nunito.className}`}>
      <div className="bg-[#f8fafc]">
        <div className="flex items-center mb-5">
          <Image
            src="/icon/takumi-logo.svg"
            alt="Logo"
            width={80}
            height={80}
            className="object-contain h-[66px] w-[56px]"
          />
          <div className="ml-0">
            <h1 className={` font-bold text-[32px]  text-black`}>TAKUMI</h1>
            <p className="text-black font-bold text-[10px] ">
              (AI Detection and Analyzer)
            </p>
          </div>
          <div className="ml-10 mt-5 h-[85px]  bg-black w-[1px]"></div>
          <Image
            src="/icon/takumi-logo.svg"
            alt="Logo"
            width={80}
            height={80}
            className="object-contain h-[56px] w-[66px]"
          />
          <div className="ml-0">
            <h1 className="font-bold text-[32px] text-black">Pallet Optimization</h1>
          </div>
        </div>
        <div className=" h-[11px]  bg-[#38bdf8] w-full"></div>
      </div>
    </nav>
  );
};

export default Navbar;

// import type { Metadata } from "next";
// import localFont from "next/font/local";
import "./globals.css";
import Sidebar from "@/components/sidebar";
import Navbar from "@/components/navbar";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="relative">
      <Navbar />
      <link
          href="https://fonts.googleapis.com/icon?family=Material+Icons"
          rel="stylesheet"
        />
        <div className="flex">
          <div className="relative z-10 ">

          <Sidebar />
          </div>
          <main className="flex-1 ml-[331px] p-[8px]">{children}</main>
        </div>
      </body>
    </html>
  );
}

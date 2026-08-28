import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import { Sidebar } from "@/components/ui/Sidebar";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
});

export const metadata: Metadata = {
  title: "HOSE Quant Portfolio & Screening Platform",
  description: "Human-in-the-loop value/quality screening and portfolio tracking for HOSE equities.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={manrope.variable}>
      <body className="font-sans">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

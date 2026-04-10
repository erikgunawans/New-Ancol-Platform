import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ancol MoM Compliance System",
  description: "Agentic AI MoM Compliance System — PT Pembangunan Jaya Ancol Tbk",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="antialiased bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}

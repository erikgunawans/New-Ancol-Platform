import type { Metadata, Viewport } from "next";
import { ServiceWorkerRegister } from "@/components/shared/sw-register";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ancol MoM Compliance System",
  description: "Agentic AI MoM Compliance System — PT Pembangunan Jaya Ancol Tbk",
  manifest: "/manifest.json",
  icons: {
    apple: "/icons/icon-192.svg",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "PJAA Compliance",
  },
};

export const viewport: Viewport = {
  themeColor: "#1a237e",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="antialiased bg-gray-50 text-gray-900">
        {children}
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppShell } from "@/components/layout/AppShell";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "Retail Intelligence Suite",
  description: "Omnichannel Retail AI Agent Platform -- enterprise command center.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoExport Admin",
  description: "AutoExport — office admin (progress tree backend only)",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

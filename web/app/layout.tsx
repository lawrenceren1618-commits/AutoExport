import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OFCE Admin · office-cp-ofce",
  description: "Order Freight Customs Export — office deployment",
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

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HR Scout",
  description: "Daily MLB Home Run Prediction Engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      style={{ backgroundColor: "#060a0c", minHeight: "100%" }}
    >
      <body className="flex flex-col" style={{ backgroundColor: "#060a0c", minHeight: "100dvh" }}>{children}</body>
    </html>
  );
}

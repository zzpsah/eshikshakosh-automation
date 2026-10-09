import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "eShikshaKosh Report Downloader",
  description: "Private, read-only school student report generation workspace.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

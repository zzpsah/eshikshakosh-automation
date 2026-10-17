import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "School Data Desk | e-ShikshaKosh workflows",
  description: "A clear guide to the authorised school student and teacher report workflows.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

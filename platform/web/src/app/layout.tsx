import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { UiPreferenceProvider } from "@/components/ui-preference-bootstrap";
import "./globals.css";

/**
 * Geist is the Paper Light typeface. Loaded through next/font so it is
 * self-hosted — the app has to work with no internet connection.
 */
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "RevAI — Local AI code review",
  description:
    "Hybrid code review that runs on your machine. Deterministic analysis first, AI only where it adds judgement.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="system"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col"><UiPreferenceProvider>{children}</UiPreferenceProvider></body>
    </html>
  );
}

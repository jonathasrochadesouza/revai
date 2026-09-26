import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ConnectionProvider } from "@/components/connection-provider";
import { ToastProvider } from "@/components/toast-provider";
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
      <body className="min-h-full flex flex-col">
        <UiPreferenceProvider>
          {/* ToastProvider wraps the app so every client component can push,
              and sits inside the locale provider because it translates.
              ConnectionProvider wraps both: it is the one component that
              survives navigation, which is what keeps a single probe, the
              debounce and a dismissal alive across route changes. */}
          <ConnectionProvider>
            <ToastProvider>{children}</ToastProvider>
          </ConnectionProvider>
        </UiPreferenceProvider>
      </body>
    </html>
  );
}

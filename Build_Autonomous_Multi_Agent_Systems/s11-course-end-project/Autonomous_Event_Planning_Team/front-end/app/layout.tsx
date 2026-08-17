import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, Space_Grotesk } from "next/font/google";
import Link from "next/link";
import { OrchestrationMark } from "../components/icons";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space-grotesk" });

export const metadata: Metadata = {
  title: "Autonomous Event Planning",
  description: "Multi-agent event planning system",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="min-h-screen font-sans text-ink-800 antialiased">
        <header className="sticky top-0 z-20 border-b border-ink-100/70 bg-paper/80 backdrop-blur">
          <div className="mx-auto flex max-w-screen-2xl items-center justify-between px-6 py-4 sm:px-10">
            <Link href="/" className="group flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-marketing-500 text-white shadow-sm transition-transform group-hover:scale-105">
                <OrchestrationMark className="h-5 w-5" />
              </span>
              <span className="font-display text-base font-semibold tracking-tight text-ink-800">
                Autonomous Event Planning
              </span>
            </Link>
            <nav className="flex items-center gap-5">
              <Link href="/history" className="text-sm font-medium text-ink-400 transition-colors hover:text-ink-700">
                History
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-screen-2xl px-6 py-10 sm:px-10">{children}</main>
      </body>
    </html>
  );
}

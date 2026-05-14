import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { PRODUCT_NAME, PRODUCT_TAGLINE } from "@/lib/config";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: `${PRODUCT_NAME} — ${PRODUCT_TAGLINE}`,
  description: PRODUCT_TAGLINE,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-neutral-50 text-neutral-900">
        <header className="border-b border-neutral-200 bg-white">
          <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-baseline gap-3">
              <span className="text-xl font-semibold tracking-tight">
                {PRODUCT_NAME}
              </span>
              <span className="hidden sm:inline text-sm text-neutral-500">
                {PRODUCT_TAGLINE}
              </span>
            </Link>
            <nav className="flex items-center gap-2 text-sm">
              <Link
                href="/"
                className="px-3 py-1.5 rounded-md text-neutral-600 hover:bg-neutral-100"
              >
                Gallery
              </Link>
              <Link
                href="/campaigns/new"
                className="px-3 py-1.5 rounded-md text-neutral-600 hover:bg-neutral-100"
              >
                Campaigns
              </Link>
              <Link
                href="/new"
                className="px-3 py-1.5 rounded-md bg-neutral-900 text-white hover:bg-neutral-700"
              >
                + New creative
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-neutral-200 bg-white">
          <div className="mx-auto max-w-7xl px-6 py-3 text-xs text-neutral-500 flex justify-between">
            <span>{PRODUCT_NAME} · agentic retail creative</span>
            <span className="font-mono">v0.2.0</span>
          </div>
        </footer>
      </body>
    </html>
  );
}

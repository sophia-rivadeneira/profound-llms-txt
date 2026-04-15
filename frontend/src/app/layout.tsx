import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Profound llms.txt Generator",
  description: "Generate and monitor llms.txt files for any website.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} dark h-full antialiased`} >
      <body className="min-h-full flex flex-col items-center">
        <div className="w-full max-w-5xl min-h-screen flex flex-col border-x border-white/15">
          <Providers>{children}</Providers>
        </div>
      </body>
    </html>
  );
}

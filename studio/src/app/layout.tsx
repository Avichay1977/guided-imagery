import type { Metadata } from "next";
import { Heebo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import "@xyflow/react/dist/style.css";

const heebo = Heebo({
  variable: "--font-console",
  subsets: ["hebrew", "latin"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-console-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "האולפן — מכשירי AI",
  description:
    "קונסולה לבניית מכשירי AI: פקדים, חוקים, רמת אוטונומיה ושרשרת עיבוד גלויה.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="he"
      dir="rtl"
      className={`${heebo.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Where Is My Space? — Spatial Intelligence",
  description:
    "Discover available campus spaces with privacy-conscious occupancy intelligence.",
  applicationName: "Where Is My Space?",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "WIMS Capture",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  themeColor: "#080b10",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

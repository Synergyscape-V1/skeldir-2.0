import type { Metadata } from "next";
import { DM_Sans, Playfair_Display } from "next/font/google";
import "./globals.css";
import { NavigationWrapper } from "@/components/layout/NavigationWrapper";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const playfairDisplay = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://skeldir.com"),
  title: "Skeldir - See exactly where your ad budget is wasted",
  description:
    "Skeldir shows you the gap between what ad platforms claim and what actually hits your bank account-so you can move budget with confidence, not guesswork.",
  icons: {
    icon: [
      { url: "/favicon.ico?v=20260310", type: "image/x-icon" },
      { url: "/favicon-32x32.png?v=20260310", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png?v=20260310", sizes: "16x16", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png?v=20260310", sizes: "180x180", type: "image/png" }],
    shortcut: [{ url: "/favicon.ico?v=20260310" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link
          rel="preload"
          as="image"
          href="/assets/images/hero/hero-800w.jpg"
          imageSrcSet="/assets/images/hero/hero-400w.jpg 400w, /assets/images/hero/hero-800w.jpg 800w, /assets/images/hero/hero-1200w.jpg 1200w"
          imageSizes="(max-width: 767px) 100vw, (max-width: 1023px) 80vw, 1200px"
          fetchPriority="high"
        />
        {/* Preload solution articulation image - early fetch avoids waterfall */}
        <link
          rel="preload"
          as="image"
          type="image/png"
          href="/assets/images/solution-articulation/solution-articulation-full.png"
        />
      </head>
      <body className={`${dmSans.variable} ${playfairDisplay.variable} font-sans antialiased`}>
        <NavigationWrapper />
        {children}
      </body>
    </html>
  );
}

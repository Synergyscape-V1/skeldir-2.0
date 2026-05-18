import type { Metadata } from "next";
import { DM_Sans, IBM_Plex_Sans_Condensed, Playfair_Display } from "next/font/google";
import "./globals.css";
import { NavigationWrapper } from "@/components/layout/NavigationWrapper";
import { SITE_DESCRIPTION, SITE_DOCUMENT_TITLE } from "@/lib/siteMetadata";

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

/** Hero headline / typewriter — condensed institutional sans, separate from body (DM Sans) */
const heroDisplay = IBM_Plex_Sans_Condensed({
  variable: "--font-hero-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
});

const FAVICON_VERSION = "20260430a";

export const metadata: Metadata = {
  metadataBase: new URL("https://skeldir.com"),
  title: SITE_DOCUMENT_TITLE,
  description: SITE_DESCRIPTION,
  openGraph: {
    title: SITE_DOCUMENT_TITLE,
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_DOCUMENT_TITLE,
    description: SITE_DESCRIPTION,
  },
  icons: {
    icon: [
      { url: `/icon.png?v=${FAVICON_VERSION}`, type: "image/png", sizes: "512x512" },
    ],
    apple: [{ url: `/apple-icon.png?v=${FAVICON_VERSION}`, sizes: "180x180", type: "image/png" }],
  },
  manifest: `/manifest.webmanifest?v=${FAVICON_VERSION}`,
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
        {/* Solution overview: match asset to viewport so mobile does not pull the wide desktop PNG */}
        <link
          rel="preload"
          as="image"
          type="image/png"
          href="/assets/images/solution-articulation/solution-articulation-full.png"
          media="(min-width: 768px)"
        />
        <link
          rel="preload"
          as="image"
          type="image/png"
          href="/assets/images/solution-articulation/solution-mobile-stage-1-sources.png"
          media="(max-width: 767px)"
          fetchPriority="high"
        />
      </head>
      <body
        className={`${dmSans.variable} ${playfairDisplay.variable} ${heroDisplay.variable} font-sans antialiased`}
      >
        <NavigationWrapper />
        {children}
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { DM_Sans, Playfair_Display } from "next/font/google";
import "./globals.css";

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
  title: "Skeldir - See exactly where your ad budget is wasted",
  description: "Skeldir shows you the gap between what ad platforms claim and what actually hits your bank account—so you can move budget with confidence, not guesswork.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />      </head>
      <body className={`${dmSans.variable} ${playfairDisplay.variable} font-sans antialiased`}>
                <style dangerouslySetInnerHTML={{__html: `body{opacity:0}`}} />
        {children}
                <script dangerouslySetInnerHTML={{__html: `!function(){document.body.style.opacity='1'}()`}} />
      </body>
    </html>
  );
}

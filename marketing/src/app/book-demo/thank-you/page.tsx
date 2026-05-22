"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Footer } from "@/components/layout/Footer";
import { CheckCircle2 } from "lucide-react";

export default function BookDemoThankYouPage() {
  const router = useRouter();

  useEffect(() => {
    const t = setTimeout(() => router.replace("/"), 5000);
    return () => clearTimeout(t);
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <main className="flex-grow pt-8 flex items-center justify-center px-4">
        <div
          style={{
            maxWidth: "440px",
            textAlign: "center",
            padding: "48px 24px",
          }}
        >
          <div
            style={{
              width: "72px",
              height: "72px",
              backgroundColor: "rgba(34, 197, 94, 0.1)",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 24px",
            }}
          >
            <CheckCircle2 size={36} color="#22C55E" />
          </div>
          <h1
            style={{
              fontSize: "24px",
              fontWeight: 700,
              color: "#0F172A",
              marginBottom: "12px",
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            You&apos;re all set
          </h1>
          <p
            style={{
              fontSize: "16px",
              color: "#64748B",
              lineHeight: 1.6,
              marginBottom: "32px",
              fontFamily: "Inter, sans-serif",
            }}
          >
            You will receive a confirmation email shortly.
          </p>
          <Link
            href="/"
            style={{
              display: "inline-block",
              width: "100%",
              maxWidth: "280px",
              height: "52px",
              lineHeight: "52px",
              backgroundColor: "#2563EB",
              color: "#FFFFFF",
              fontSize: "16px",
              fontWeight: 600,
              fontFamily: "Inter, sans-serif",
              border: "none",
              borderRadius: "10px",
              cursor: "pointer",
              textDecoration: "none",
              textAlign: "center",
            }}
          >
            Return to home
          </Link>
          <p
            style={{
              fontSize: "13px",
              color: "#94A3B8",
              marginTop: "24px",
              fontFamily: "Inter, sans-serif",
            }}
          >
            Redirecting to home in 5 seconds…
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}

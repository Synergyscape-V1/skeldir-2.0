"use client";

import Image from 'next/image';

const logos = [
  { name: "Callaway", src: "/images/Callaway_1_transparent.png", height: "2.5rem" },
  { name: "Fresh Clean Threads", src: "/images/FreshCleanThreads_transparent.png", height: "6.75rem" },
  { name: "NordicTrack", src: "/images/Nordictrack_transparent.png", height: "5.2rem" },
  { name: "Pacsun", src: "/images/Pacsun_transparent.png", height: "2.25rem" },
];

export function StaticPartnerLogos() {
  return (
    <div className="mt-8 w-full">
      {/* Trusted by text */}
      <div
        style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          fontWeight: 400,
          lineHeight: 1.4,
          color: 'rgb(20, 20, 20)',
          textAlign: 'center',
          letterSpacing: '0.02em',
          maxWidth: '700px',
          margin: '16px auto -1.9px',
        }}
      >
        Trusted by agencies and brands managing $50M+ in annual ad spend
      </div>

      {/* Static logo grid */}
      <div
        className="partner-logos-grid"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1.25rem',
          flexWrap: 'nowrap',
          width: '100%',
          overflow: 'visible',
          marginTop: '0px',
        }}
      >
        {logos.map((logo) => (
          <Image
            key={logo.name}
            src={logo.src}
            alt={logo.name}
            width={0}
            height={0}
            sizes="(max-width: 768px) 100px, 150px"
            style={{
              height: logo.height,
              width: 'auto',
              objectFit: 'contain',
              filter: 'grayscale(70%) brightness(0.7)',
              opacity: 1,
              flexShrink: 0,
            }}
            className="hover:opacity-100 hover:grayscale-0 transition-all duration-300"
          />
        ))}
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        @media (max-width: 767px) {
          .partner-logos-grid {
            flex-wrap: wrap !important;
            gap: 0.75rem !important;
            padding: 0 8px !important;
            justify-content: center !important;
          }

          .partner-logos-grid img {
            max-height: 40px !important;
            height: auto !important;
            width: auto !important;
          }
        }

        @media (max-width: 375px) {
          .partner-logos-grid {
            gap: 0.5rem !important;
          }

          .partner-logos-grid img {
            max-height: 35px !important;
          }
        }
      `}} />
    </div>
  );
}

"use client";

const logos = [
  { name: "Callaway", srcWebP: "/images/Callaway_1_transparent.webp", srcFallback: "/images/Callaway_1_transparent.png", height: "3.125rem" },
  { name: "Fresh Clean Threads", srcWebP: "/images/FreshCleanThreads_transparent.webp", srcFallback: "/images/FreshCleanThreads_transparent.png", height: "7.9820559rem" },
  { name: "NordicTrack", srcWebP: "/images/Nordictrack_transparent.webp", srcFallback: "/images/Nordictrack_transparent.png", height: "7.6750597rem" },
  { name: "bareMinerals", srcWebP: "/images/Baremin_transparent.webp", srcFallback: "/images/Baremin_transparent.png", height: "6.334965rem" },
  { name: "TUMI", srcWebP: "/images/TUMI_transparent.webp", srcFallback: "/images/TUMI_transparent.png", height: "2.5rem" },
  { name: "Pacsun", srcWebP: "/images/Pacsun_transparent.webp", srcFallback: "/images/Pacsun_transparent.png", height: "2.625rem" },
];

export function PartnerLogos() {
  // Duplicate logos for seamless infinite scroll
  const duplicatedLogos = [...logos, ...logos];

  return (
    <div
      className="partner-logos-container"
      style={{
        marginTop: "3rem",
        width: "100%",
        overflow: "hidden",
        position: "relative",
        background: "transparent",
        border: "none",
        outline: "none",
      }}
    >
      {/* CSS for keyframe animation */}
      <style>
        {`
          @keyframes scroll-logos {
            0% {
              transform: translateX(0);
            }
            100% {
              transform: translateX(-50%);
            }
          }
          .logo-carousel-track {
            display: flex;
            align-items: center;
            gap: 4rem;
            animation: scroll-logos 30s linear infinite;
            width: max-content;
            background: transparent;
            border: none;
            outline: none;
            box-shadow: none;
          }
          .logo-carousel-track img {
            background: transparent !important;
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
          }

          @media (max-width: 767px) {
            .partner-logos-container {
              margin-top: 0 !important;
              padding: 0 16px !important;
            }

            .logo-carousel-track {
              gap: 1.5rem !important;
            }

            .logo-carousel-track img {
              max-height: 50px !important;
              height: auto !important;
              width: auto !important;
            }

            /* Scale Callaway, Pacsun, and TUMI logos down by 1.7x (make them 1/1.7 ≈ 0.588x of original size) */
            .logo-carousel-track img.callaway-logo,
            .logo-carousel-track img.pacsun-logo,
            .logo-carousel-track img.tumi-logo {
              transform: scale(0.588) !important;
            }

            /* Scale Fresh Clean Threads logo up by 0.3x (make it 1.3x of original size) */
            .logo-carousel-track img.fresh-clean-threads-logo {
              transform: scale(1.3) !important;
            }
          }
        `}
      </style>

      {/* Carousel track */}
      <div className="logo-carousel-track">
        {duplicatedLogos.map((logo, index) => (
          <picture key={`${logo.name}-${index}`}>
            <source srcSet={logo.srcWebP} type="image/webp" />
            <img
              src={logo.srcFallback}
              alt={logo.name}
              className={
                logo.name === "TUMI"
                  ? "tumi-logo"
                  : logo.name === "Fresh Clean Threads"
                  ? "fresh-clean-threads-logo"
                  : logo.name === "Callaway"
                  ? "callaway-logo"
                  : logo.name === "Pacsun"
                  ? "pacsun-logo"
                  : ""
              }
              loading="lazy"
              decoding="async"
              style={{
                height: logo.height,
                width: "auto",
                objectFit: "contain",
                filter: "grayscale(100%)",
                opacity: 0.7,
                flexShrink: 0,
                background: "transparent",
                border: "none",
                outline: "none",
                boxShadow: "none",
              }}
            />
          </picture>
        ))}
      </div>
    </div>
  );
}

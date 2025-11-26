import backgroundImage from "@assets/5594016_1758830475467.jpg";

interface GeometricBackgroundProps {
  className?: string;
}

export default function GeometricBackground({ className = "" }: GeometricBackgroundProps) {
  return (
    <>
      <div 
        className={`fixed inset-0 overflow-hidden pointer-events-none ${className}`}
        aria-hidden="true"
        data-testid="geometric-background"
      >
        {/* Background image */}
        <div 
          className="absolute inset-0 bg-cover bg-center bg-no-repeat"
          style={{ backgroundImage: `url(${backgroundImage})` }}
        />
        
        {/* Optional dark overlay for better text readability */}
        <div className="absolute inset-0 bg-black/20 dark:bg-black/40" />
        
        {/* Animated geometric shapes */}
        <div className="absolute inset-0">
          {/* Large floating circles */}
          <div className="geometric-shape geometric-circle-1" />
          <div className="geometric-shape geometric-circle-2" />
          <div className="geometric-shape geometric-circle-3" />
          
          {/* Triangular elements */}
          <div className="geometric-shape geometric-triangle-1" />
          <div className="geometric-shape geometric-triangle-2" />
          
          {/* Hexagonal shapes */}
          <div className="geometric-shape geometric-hexagon-1" />
          <div className="geometric-shape geometric-hexagon-2" />
          
          {/* Additional subtle elements */}
          <div className="geometric-shape geometric-circle-4" />
          <div className="geometric-shape geometric-triangle-3" />
        </div>
      </div>

      {/* Global CSS for geometric background */}
      <style dangerouslySetInnerHTML={{
        __html: `
          @media (prefers-reduced-motion: no-preference) {
            .geometric-shape {
              position: absolute;
              background: rgba(255, 255, 255, 0.01);
              border-radius: 50%;
              will-change: transform, opacity;
            }

            /* Large floating circles */
            .geometric-circle-1 {
              width: 300px;
              height: 300px;
              top: -10%;
              left: -5%;
              animation: geo-float-1 45s ease-in-out infinite;
              opacity: 0.01;
            }

            .geometric-circle-2 {
              width: 200px;
              height: 200px;
              top: 60%;
              right: -10%;
              animation: geo-float-2 35s ease-in-out infinite reverse;
              opacity: 0.015;
            }

            .geometric-circle-3 {
              width: 150px;
              height: 150px;
              top: 30%;
              left: 70%;
              animation: geo-float-3 40s ease-in-out infinite;
              opacity: 0.01;
            }

            .geometric-circle-4 {
              width: 100px;
              height: 100px;
              top: 80%;
              left: 20%;
              animation: geo-float-1 30s ease-in-out infinite reverse;
              opacity: 0.012;
            }

            /* Triangular shapes using clip-path */
            .geometric-triangle-1 {
              width: 180px;
              height: 180px;
              top: 15%;
              right: 25%;
              clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
              border-radius: 0;
              animation: geo-rotate-float-1 50s linear infinite;
              opacity: 0.008;
            }

            .geometric-triangle-2 {
              width: 120px;
              height: 120px;
              top: 70%;
              left: 60%;
              clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
              border-radius: 0;
              animation: geo-rotate-float-2 60s linear infinite reverse;
              opacity: 0.008;
            }

            .geometric-triangle-3 {
              width: 90px;
              height: 90px;
              top: 45%;
              left: 5%;
              clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
              border-radius: 0;
              animation: geo-float-2 25s ease-in-out infinite;
              opacity: 0.01;
            }

            /* Hexagonal shapes */
            .geometric-hexagon-1 {
              width: 140px;
              height: 140px;
              top: 50%;
              right: 5%;
              clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
              border-radius: 0;
              animation: geo-rotate-float-1 55s linear infinite;
              opacity: 0.01;
            }

            .geometric-hexagon-2 {
              width: 80px;
              height: 80px;
              top: 10%;
              left: 50%;
              clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
              border-radius: 0;
              animation: geo-rotate-float-2 40s linear infinite reverse;
              opacity: 0.012;
            }

            /* GPU-accelerated keyframe animations */
            @keyframes geo-float-1 {
              0%, 100% { 
                transform: translate3d(0, 0, 0) scale(1); 
                opacity: 0.04;
              }
              25% { 
                transform: translate3d(20px, -30px, 0) scale(1.05); 
                opacity: 0.06;
              }
              50% { 
                transform: translate3d(-15px, -20px, 0) scale(0.95); 
                opacity: 0.03;
              }
              75% { 
                transform: translate3d(25px, 10px, 0) scale(1.02); 
                opacity: 0.05;
              }
            }

            @keyframes geo-float-2 {
              0%, 100% { 
                transform: translate3d(0, 0, 0) scale(1); 
                opacity: 0.05;
              }
              30% { 
                transform: translate3d(-25px, 20px, 0) scale(1.08); 
                opacity: 0.07;
              }
              60% { 
                transform: translate3d(10px, -25px, 0) scale(0.92); 
                opacity: 0.04;
              }
              90% { 
                transform: translate3d(-10px, 15px, 0) scale(1.03); 
                opacity: 0.06;
              }
            }

            @keyframes geo-float-3 {
              0%, 100% { 
                transform: translate3d(0, 0, 0) scale(1); 
                opacity: 0.03;
              }
              20% { 
                transform: translate3d(15px, -15px, 0) scale(1.1); 
                opacity: 0.05;
              }
              40% { 
                transform: translate3d(-20px, 25px, 0) scale(0.9); 
                opacity: 0.07;
              }
              60% { 
                transform: translate3d(30px, -10px, 0) scale(1.05); 
                opacity: 0.04;
              }
              80% { 
                transform: translate3d(-5px, 20px, 0) scale(0.95); 
                opacity: 0.06;
              }
            }

            @keyframes geo-rotate-float-1 {
              0% { 
                transform: translate3d(0, 0, 0) rotate(0deg) scale(1); 
                opacity: 0.04;
              }
              25% { 
                transform: translate3d(15px, -20px, 0) rotate(90deg) scale(1.02); 
                opacity: 0.06;
              }
              50% { 
                transform: translate3d(-10px, 15px, 0) rotate(180deg) scale(0.98); 
                opacity: 0.05;
              }
              75% { 
                transform: translate3d(20px, -5px, 0) rotate(270deg) scale(1.01); 
                opacity: 0.03;
              }
              100% { 
                transform: translate3d(0, 0, 0) rotate(360deg) scale(1); 
                opacity: 0.04;
              }
            }

            @keyframes geo-rotate-float-2 {
              0% { 
                transform: translate3d(0, 0, 0) rotate(0deg) scale(1); 
                opacity: 0.05;
              }
              33% { 
                transform: translate3d(-18px, 12px, 0) rotate(120deg) scale(1.04); 
                opacity: 0.07;
              }
              66% { 
                transform: translate3d(12px, -18px, 0) rotate(240deg) scale(0.96); 
                opacity: 0.04;
              }
              100% { 
                transform: translate3d(0, 0, 0) rotate(360deg) scale(1); 
                opacity: 0.05;
              }
            }
          }

          /* Respect reduced motion preferences */
          @media (prefers-reduced-motion: reduce) {
            .geometric-shape {
              animation: none !important;
              transform: none !important;
              position: absolute;
              background: rgba(255, 255, 255, 0.02);
            }

            .geometric-circle-1 {
              width: 300px;
              height: 300px;
              top: -10%;
              left: -5%;
              border-radius: 50%;
              opacity: 0.02;
            }

            .geometric-circle-2 {
              width: 200px;
              height: 200px;
              top: 60%;
              right: -10%;
              border-radius: 50%;
              opacity: 0.03;
            }

            .geometric-circle-3 {
              width: 150px;
              height: 150px;
              top: 30%;
              left: 70%;
              border-radius: 50%;
              opacity: 0.02;
            }

            .geometric-circle-4 {
              width: 100px;
              height: 100px;
              top: 80%;
              left: 20%;
              border-radius: 50%;
              opacity: 0.025;
            }

            .geometric-triangle-1,
            .geometric-triangle-2,
            .geometric-triangle-3 {
              opacity: 0.02;
            }

            .geometric-hexagon-1,
            .geometric-hexagon-2 {
              opacity: 0.025;
            }
          }

          /* Dark mode adjustments */
          .dark .geometric-shape {
            background: rgba(245, 245, 245, 0.04);
          }
        `
      }} />
    </>
  );
}
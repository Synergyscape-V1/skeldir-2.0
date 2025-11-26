import { useState, useEffect, useRef } from 'react';

interface ProcessedLogoProps {
  src: string;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
  onError?: () => void;
  'data-testid'?: string;
  onClick?: () => void;
}

interface CachedImage {
  dataUrl: string;
  timestamp: number;
}

// Cache for processed images
const imageCache = new Map<string, CachedImage>();

export function ProcessedLogo({ src, alt, className, style, onError, 'data-testid': testId, onClick }: ProcessedLogoProps) {
  const [processedSrc, setProcessedSrc] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const processImage = async () => {
      try {
        // Check cache first
        const cached = imageCache.get(src);
        if (cached) {
          setProcessedSrc(cached.dataUrl);
          return;
        }

        setIsProcessing(true);
        
        // Create image element
        const img = new Image();
        img.crossOrigin = 'anonymous';
        
        await new Promise<void>((resolve, reject) => {
          img.onload = () => resolve();
          img.onerror = () => reject(new Error('Image failed to load'));
          img.src = src;
        });

        // Create canvas and get context
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          throw new Error('Failed to get canvas context');
        }

        canvas.width = img.width;
        canvas.height = img.height;
        
        // Draw the original image
        ctx.drawImage(img, 0, 0);
        
        // Get image data for processing
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        
        // Sample border pixels to detect background colors
        const borderSamples: number[][] = [];
        const sampleBorder = (x: number, y: number) => {
          if (x >= 0 && x < canvas.width && y >= 0 && y < canvas.height) {
            const i = (y * canvas.width + x) * 4;
            borderSamples.push([data[i], data[i + 1], data[i + 2]]);
          }
        };
        
        // Sample top and bottom edges
        for (let x = 0; x < canvas.width; x += 4) {
          sampleBorder(x, 0); // Top edge
          sampleBorder(x, canvas.height - 1); // Bottom edge
        }
        
        // Sample left and right edges
        for (let y = 0; y < canvas.height; y += 4) {
          sampleBorder(0, y); // Left edge
          sampleBorder(canvas.width - 1, y); // Right edge
        }
        
        // Detect dominant background colors (usually 2-3 colors in checker pattern)
        const colorFreq = new Map<string, number>();
        borderSamples.forEach(([r, g, b]) => {
          const key = `${r},${g},${b}`;
          colorFreq.set(key, (colorFreq.get(key) || 0) + 1);
        });
        
        // Get the most frequent colors (background colors)
        const sortedColors = Array.from(colorFreq.entries())
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3) // Take top 3 colors
          .map(([colorStr]) => colorStr.split(',').map(Number));
        
        // Process each pixel
        for (let i = 0; i < data.length; i += 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          
          // Check if this pixel matches any background color
          let isBackground = false;
          for (const [bgR, bgG, bgB] of sortedColors) {
            // Use color distance threshold (Euclidean distance in RGB space)
            const distance = Math.sqrt(
              Math.pow(r - bgR, 2) + 
              Math.pow(g - bgG, 2) + 
              Math.pow(b - bgB, 2)
            );
            
            if (distance < 30) { // Threshold for background detection
              isBackground = true;
              break;
            }
          }
          
          if (isBackground) {
            // Make background pixels fully transparent
            data[i + 3] = 0;
          } else {
            // For edge smoothing, reduce alpha for pixels close to background colors
            let minDistance = Infinity;
            for (const [bgR, bgG, bgB] of sortedColors) {
              const distance = Math.sqrt(
                Math.pow(r - bgR, 2) + 
                Math.pow(g - bgG, 2) + 
                Math.pow(b - bgB, 2)
              );
              minDistance = Math.min(minDistance, distance);
            }
            
            // Smooth transition for anti-aliasing
            if (minDistance < 60) {
              const alpha = Math.min(255, (minDistance / 60) * 255);
              data[i + 3] = Math.min(data[i + 3], alpha);
            }
          }
        }
        
        // Put the processed image data back
        ctx.putImageData(imageData, 0, 0);
        
        // Convert to data URL
        const dataUrl = canvas.toDataURL('image/png');
        
        // Cache the result
        imageCache.set(src, { dataUrl, timestamp: Date.now() });
        
        setProcessedSrc(dataUrl);
      } catch (err) {
        console.error('Failed to process logo:', err);
        setError(true);
        onError?.();
      } finally {
        setIsProcessing(false);
      }
    };

    processImage();
  }, [src, onError]);

  // If processing failed or is still in progress, show original image
  if (error || !processedSrc) {
    return (
      <img
        src={src}
        alt={alt}
        className={className}
        style={style}
        onError={() => {
          setError(true);
          onError?.();
        }}
        data-testid={testId}
        onClick={onClick}
      />
    );
  }

  // Show processed image with transparent background
  return (
    <img
      src={processedSrc}
      alt={alt}
      className={className}
      style={style}
      data-testid={testId}
      onClick={onClick}
    />
  );
}
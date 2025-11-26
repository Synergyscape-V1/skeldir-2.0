import { useEffect, useState, useRef } from 'react';

const cubicBezier = (p1x: number, p1y: number, p2x: number, p2y: number) => {
  const cx = 3 * p1x;
  const bx = 3 * (p2x - p1x) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * p1y;
  const by = 3 * (p2y - p1y) - cy;
  const ay = 1 - cy - by;
  
  const sampleCurveX = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sampleCurveY = (t: number) => ((ay * t + by) * t + cy) * t;
  const solveCurveX = (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const x2 = sampleCurveX(t) - x;
      if (Math.abs(x2) < 0.001) return t;
      const d2 = (3 * ax * t + 2 * bx) * t + cx;
      if (Math.abs(d2) < 0.000001) break;
      t -= x2 / d2;
    }
    return t;
  };
  
  return (x: number) => sampleCurveY(solveCurveX(x));
};

export const useAnimatedValue = (target: number, duration: number = 600): number => {
  const [current, setCurrent] = useState(0);
  const rafRef = useRef<number>();
  const startValueRef = useRef(0);
  
  useEffect(() => {
    const startTime = Date.now();
    startValueRef.current = current;
    const diff = target - startValueRef.current;
    const easing = cubicBezier(0.4, 0, 0.2, 1);
    
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easing(progress);
      setCurrent(startValueRef.current + diff * easedProgress);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);
  
  return current;
};

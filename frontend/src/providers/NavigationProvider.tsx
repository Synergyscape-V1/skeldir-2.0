import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation } from 'wouter';
import "@/assets/brand/colors.css";

interface BreadcrumbItem { path: string; label: string; isActive: boolean; }

interface NavigationContextValue {
  currentPath: string; breadcrumbs: BreadcrumbItem[]; isActiveRoute: (path: string) => boolean;
  mobileDrawerOpen: boolean; setMobileDrawerOpen: (open: boolean) => void;
  getRouteClassName: (path: string) => string; navigateWithTransition: (path: string) => void;
  getAriaCurrent: (path: string) => "page" | undefined;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);
const ROUTE_LABELS: Record<string, string> = { '': 'Home', 'dashboard': 'Dashboard', 'analytics': 'Analytics', 'settings': 'Settings' };

const generateRouteClasses = (isActive: boolean) => {
  const base = 'transition-all duration-75 will-change-transform backdrop-blur-sm border border-opacity-30';
  return isActive 
    ? `${base} bg-[hsl(var(--brand-tufts)/0.2)] border-[hsl(var(--brand-tufts)/0.4)] text-[hsl(var(--brand-cool-black))] shadow-[0_0_12px_hsl(var(--brand-tufts)/0.3)]`
    : `${base} bg-[hsl(var(--brand-alice)/0.1)] border-[hsl(var(--brand-jordy)/0.2)] text-[hsl(var(--brand-cool-black)/0.8)] hover:bg-[hsl(var(--brand-jordy)/0.15)] hover:border-[hsl(var(--brand-jordy)/0.35)] hover:shadow-[0_0_8px_hsl(var(--brand-jordy)/0.2)]`;
};

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const [location, navigate] = useLocation();
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const breadcrumbs = useMemo((): BreadcrumbItem[] => {
    const segments = location.split('/').filter(Boolean);
    const crumbs: BreadcrumbItem[] = [{ path: '/', label: ROUTE_LABELS[''] || 'Home', isActive: location === '/' }];
    let currentPath = '';
    segments.forEach((segment, index) => {
      currentPath += `/${segment}`;
      const isLast = index === segments.length - 1;
      crumbs.push({ path: currentPath, label: ROUTE_LABELS[segment] || segment.charAt(0).toUpperCase() + segment.slice(1), isActive: isLast && currentPath === location });
    });
    return crumbs;
  }, [location]);

  const isActiveRoute = useCallback((path: string): boolean => location === path || (path !== '/' && location.startsWith(path)), [location]);

  const getRouteClassName = useCallback((path: string): string => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const baseClass = generateRouteClasses(isActiveRoute(path));
    return reducedMotion ? baseClass.replace('duration-75', 'duration-0') : baseClass;
  }, [isActiveRoute]);

  const navigateWithTransition = useCallback((path: string) => {
    if (isTransitioning || location === path) return;
    setIsTransitioning(true);
    requestAnimationFrame(() => { navigate(path); setTimeout(() => setIsTransitioning(false), 50); });
  }, [location, navigate, isTransitioning]);

  const getAriaCurrent = useCallback((path: string): "page" | undefined => isActiveRoute(path) ? "page" : undefined, [isActiveRoute]);

  useEffect(() => {
    let startX = 0, isDragging = false;
    const handleTouchStart = (e: TouchEvent) => { startX = e.touches[0].clientX; isDragging = true; };
    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging) return;
      const diffX = e.touches[0].clientX - startX;
      if (mobileDrawerOpen && diffX < -100) { setMobileDrawerOpen(false); isDragging = false; }
      else if (!mobileDrawerOpen && startX < 50 && diffX > 100) { setMobileDrawerOpen(true); isDragging = false; }
    };
    const handleTouchEnd = () => { isDragging = false; };
    document.addEventListener('touchstart', handleTouchStart, { passive: true });
    document.addEventListener('touchmove', handleTouchMove, { passive: true });
    document.addEventListener('touchend', handleTouchEnd, { passive: true });
    return () => {
      document.removeEventListener('touchstart', handleTouchStart);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [mobileDrawerOpen]);

  const contextValue = useMemo(() => ({
    currentPath: location, breadcrumbs, isActiveRoute, mobileDrawerOpen, setMobileDrawerOpen,
    getRouteClassName, navigateWithTransition, getAriaCurrent
  }), [location, breadcrumbs, isActiveRoute, mobileDrawerOpen, getRouteClassName, navigateWithTransition, getAriaCurrent]);

  return <NavigationContext.Provider value={contextValue}>{children}</NavigationContext.Provider>;
}

export function useNavigation() {
  const context = useContext(NavigationContext);
  if (!context) throw new Error('useNavigation must be used within NavigationProvider');
  return context;
}
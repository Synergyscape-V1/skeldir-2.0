"use client";

import { Navigation } from "./Navigation";
import { usePathname } from "next/navigation";

export function NavigationWrapper() {
  const pathname = usePathname();
  
  // Hide navigation on login and signup pages
  const hideNavRoutes = ['/Login', '/login', '/signup', '/Signup'];
  if (pathname && hideNavRoutes.some(route => pathname === route || pathname.startsWith(`${route}/`))) {
    return null;
  }
  
  return <Navigation />;
}

import type { ReactNode } from "react";
import Link from "next/link";
import { NAV_TEXT_LINK_CLASS } from "@/components/layout/navLinkPhysics";

type NavTextLinkProps = {
  href: string;
  children: ReactNode;
  onClick?: () => void;
};

export function NavTextLink({ href, children, onClick }: NavTextLinkProps) {
  return (
    <Link href={href} className={NAV_TEXT_LINK_CLASS} onClick={onClick}>
      {children}
    </Link>
  );
}

import type { Metadata } from "next";
import { JsonLd } from "@/components/schema/JsonLd";
import { absoluteUrl } from "@/lib/siteCrawl";
import { webPageJsonLd } from "@/lib/schema/entity";
import { PRODUCT_PAGE_LEAD_DESCRIPTION, softwareApplicationJsonLd } from "@/lib/schema/pageSchemas";

export const metadata: Metadata = {
  title: "Product | Skeldir",
  description: PRODUCT_PAGE_LEAD_DESCRIPTION,
  alternates: {
    canonical: absoluteUrl("/product"),
  },
};

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLd
        data={[
          softwareApplicationJsonLd(),
          webPageJsonLd("/product", {
            name: "Product | Skeldir",
            description: PRODUCT_PAGE_LEAD_DESCRIPTION,
          }),
        ]}
      />
      {children}
    </>
  );
}

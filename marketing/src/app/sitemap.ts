import type { MetadataRoute } from "next";

const BASE_URL = "https://skeldir.com";
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = [
    "",
    "/product",
    "/pricing",
    "/agencies",
    "/resources",
    "/book-demo",
    "/signup",
    "/Login",
  ];

  return routes.map((route) => ({
    url: `${BASE_URL}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "weekly" : "monthly",
    priority: route === "" ? 1.0 : 0.7,
  }));
}

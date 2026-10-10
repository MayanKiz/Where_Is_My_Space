import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/capture",
    name: "Where Is My Space? Capture",
    short_name: "WIMS Capture",
    description: "Add a phone camera, screen recording, video file, or authorized IP camera to WIMS.",
    start_url: "/capture",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#080b10",
    theme_color: "#080b10",
    categories: ["utilities", "education", "productivity"],
    icons: [
      { src: "/wims-icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
    ],
  };
}

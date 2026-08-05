import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Requerido por docker/frontend.Dockerfile (gera .next/standalone, um
  // servidor Node autocontido usado na imagem final do Kubernetes).
  output: "standalone",
};

export default nextConfig;

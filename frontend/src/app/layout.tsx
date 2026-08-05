import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SDD Blog CMS",
  description: "CMS de blog com assistente de IA generativa (validação de Spec-Driven Development).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}

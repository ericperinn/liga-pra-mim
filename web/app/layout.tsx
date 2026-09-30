import type { Metadata } from "next";
import { Familjen_Grotesk, Inclusive_Sans } from "next/font/google";
import "./globals.css";

const display = Familjen_Grotesk({ subsets: ["latin"], variable: "--font-display" });
const body = Inclusive_Sans({ subsets: ["latin"], weight: ["400"], style: ["normal", "italic"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "Liga pra Mim",
  description:
    "Uma linha de ajuda por telefone, com inteligência artificial, que orienta famílias de baixa renda sobre seus direitos sociais no Brasil.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}

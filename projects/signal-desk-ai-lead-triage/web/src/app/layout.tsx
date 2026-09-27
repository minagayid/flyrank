import type { Metadata } from "next";
import { DM_Sans, IBM_Plex_Mono, Geist } from "next/font/google";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

const interfaceFont = DM_Sans({ variable: "--font-dm-sans", subsets: ["latin"] });
const dataFont = IBM_Plex_Mono({ variable: "--font-ibm-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: { default: "Signal Desk · Lead review", template: "%s · Signal Desk" },
  description: "An evidence-led lead triage workspace for independent creative studios.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={cn(interfaceFont.variable, dataFont.variable, "font-sans", geist.variable)}>
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}

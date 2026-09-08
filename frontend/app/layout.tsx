import "./globals.css";
import Nav from "./components/Nav";
import type { Metadata } from "next";

const SITE_URL = "https://monza-predictor.vercel.app";
const DESCRIPTION = "Monte Carlo win-probability model for every round of the season";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "F1 Race Predictor",
    // Applies to a *child* route segment (about/, track-record/,
    // race/[slug]/) that sets metadata.title as a plain string — Next
    // slots it into "%s" here. It does NOT apply to "/" itself: the root
    // page shares this exact segment with the layout that defines the
    // template, and Next only templates a segment's children, not the
    // segment doing the defining — see page.tsx, which writes its own
    // full string instead for that reason.
    template: "%s — F1 Race Predictor",
  },
  description: DESCRIPTION,
  openGraph: {
    title: "F1 Race Predictor",
    description: DESCRIPTION,
    url: SITE_URL,
    siteName: "F1 Race Predictor",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "F1 Race Predictor" }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "F1 Race Predictor",
    description: DESCRIPTION,
    images: ["/og-image.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}

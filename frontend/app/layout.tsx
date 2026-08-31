import "./globals.css";

export const metadata = {
  title: "Monza GP Predictor",
  description: "Monte Carlo win-probability model for the Italian Grand Prix",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

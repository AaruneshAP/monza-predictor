import "./globals.css";
import Nav from "./components/Nav";

export const metadata = {
  title: "F1 Race Predictor",
  description: "Monte Carlo win-probability model for every round of the season",
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

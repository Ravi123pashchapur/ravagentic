import type { Metadata } from "next";
import React from "react";
import { generatedTheme } from "@/lib/theme/generatedTheme";

export const metadata: Metadata = {
  title: "ravgentic frontend",
  description: "Themed, route-connected UI (mock backend).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: "Inter, Arial, sans-serif",
          backgroundColor: generatedTheme.colors.background,
          color: generatedTheme.colors.text,
          minHeight: "100vh",
        }}
      >
        {children}
      </body>
    </html>
  );
}

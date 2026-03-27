export type GeneratedTheme = {
  name: string;
  colors: {
    background: string;
    surface: string;
    text: string;
    primary: string;
    accent: string;
    border: string;
  };
  radius: number;
};

export const generatedTheme: GeneratedTheme = {
  name: "dashboard-flame",
  colors: {
    background: "#111827",
    surface: "rgba(255, 255, 255, 0.06)",
    text: "#f9fafb",
    primary: "#111827",
    accent: "#6366f1",
    border: "rgba(255, 255, 255, 0.14)",
  },
  radius: 12,
};

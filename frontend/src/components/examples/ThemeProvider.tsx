import { ThemeProvider } from '../ThemeProvider';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTheme } from '../ThemeProvider';

function ThemeToggleDemo() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="min-h-screen bg-background p-8">
      <Card className="max-w-md mx-auto">
        <CardHeader>
          <CardTitle>Theme Provider Demo</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            Current theme: <strong>{theme}</strong>
          </p>
          <div className="flex gap-2">
            <Button
              variant={theme === "light" ? "default" : "outline"}
              onClick={() => setTheme("light")}
              data-testid="button-light-theme"
            >
              Light
            </Button>
            <Button
              variant={theme === "dark" ? "default" : "outline"}
              onClick={() => setTheme("dark")}
              data-testid="button-dark-theme"
            >
              Dark
            </Button>
            <Button
              variant={theme === "system" ? "default" : "outline"}
              onClick={() => setTheme("system")}
              data-testid="button-system-theme"
            >
              System
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ThemeProviderExample() {
  return (
    <ThemeProvider>
      <ThemeToggleDemo />
    </ThemeProvider>
  );
}
import LoginInterface from '../LoginInterface';
import { ThemeProvider } from '../ThemeProvider';

export default function LoginInterfaceExample() {
  return (
    <ThemeProvider>
      <LoginInterface />
    </ThemeProvider>
  );
}
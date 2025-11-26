import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Eye, EyeOff, AlertCircle, CheckCircle, Loader2 } from "lucide-react";
import { useLogin } from "@/hooks/useAuth";
import { useLocation } from "wouter";
import skeldir_logo from "@assets/Skeldir Logo (no background)_1759004645592.png";

export default function LoginForm() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [emailValidation, setEmailValidation] = useState({
    isValid: true, isValidating: false, message: "", hasBeenValidated: false
  });
  const { login, isLoading, error, clearError } = useLogin();
  const [, navigate] = useLocation();

  const validateEmail = useCallback(async (emailToValidate: string): Promise<boolean> => {
    if (!emailToValidate.trim()) {
      setEmailValidation({ isValid: false, isValidating: false, message: "Email is required", hasBeenValidated: true });
      return false;
    }
    setEmailValidation(prev => ({ ...prev, isValidating: true }));
    try {
      const response = await fetch('/api/validate/email', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: emailToValidate }) });
      const result = await response.json();
      setEmailValidation({ isValid: result.isValid, isValidating: false, message: result.message, hasBeenValidated: true });
      return result.isValid;
    } catch (error) {
      setEmailValidation({ isValid: false, isValidating: false, message: "Unable to verify email", hasBeenValidated: true });
      return false;
    }
  }, []);

  const handleEmailBlur = useCallback(() => validateEmail(email), [email, validateEmail]);
  const handleLogin = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;
    clearError();
    const startTime = Date.now();
    try {
      const loginResult = await login(email, password, rememberMe);
      const elapsed = Date.now() - startTime;
      const delay = Math.max(0, 450 - elapsed); // Minimum delay for security, max 450ms
      if (delay > 0) await new Promise(resolve => setTimeout(resolve, delay));
      if (loginResult.success) navigate("/dashboard"); // Immediate redirect within 500ms total
    } catch (err) {
      const elapsed = Date.now() - startTime;
      if (elapsed < 450) await new Promise(resolve => setTimeout(resolve, 450 - elapsed));
    }
  }, [email, password, rememberMe, login, isLoading, clearError, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-2xl" style={{ background: "rgba(255, 255, 255, 0.2)", backdropFilter: "blur(10px)", border: "1px solid rgba(255, 255, 255, 0.3)" }}>
        <CardHeader className="text-center pb-6">
          <img src={skeldir_logo} alt="Skeldir" className="h-16 w-auto mx-auto mb-4" data-testid="img-skeldir-logo" />
          <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">Welcome Back</h1>
          <p className="text-gray-600 dark:text-gray-300">Sign in to your account</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <div className="relative">
                <Input type="email" placeholder="Email address" value={email} 
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setEmailValidation(prev => ({...prev, hasBeenValidated: false, message: ""}));
                  }} 
                  onBlur={handleEmailBlur} disabled={isLoading} aria-invalid={emailValidation.hasBeenValidated && !emailValidation.isValid}
                  aria-describedby="email-validation" data-testid="input-email" required
                  className={`pr-10 bg-white/30 backdrop-blur-sm border ${emailValidation.hasBeenValidated
                    ? emailValidation.isValid ? 'border-green-400/60' : 'border-red-400/60' : 'border-white/40'}`}
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  {emailValidation.isValidating && <Loader2 className="h-4 w-4 animate-spin text-white/60" />}
                  {emailValidation.hasBeenValidated && !emailValidation.isValidating && (
                    emailValidation.isValid ? 
                      <CheckCircle className="h-4 w-4 text-green-400" data-testid="icon-email-valid" /> :
                      <AlertCircle className="h-4 w-4 text-red-400" data-testid="icon-email-invalid" />)}
                </div>
              </div>
              {emailValidation.hasBeenValidated && emailValidation.message && (
                <p id="email-validation" className={`text-xs ${emailValidation.isValid ? 'text-green-400' : 'text-red-400'}`} 
                   data-testid="text-email-validation">{emailValidation.message}</p>)}
            </div>

            <div className="relative">
              <Input type={showPassword ? "text" : "password"} placeholder="Password" value={password}
                onChange={(e) => setPassword(e.target.value)} disabled={isLoading}
                className="pr-10 bg-white/30 backdrop-blur-sm border border-white/40"
                data-testid="input-password" autoComplete="current-password" required />
              <Button type="button" variant="ghost" size="icon"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 hover-elevate"
                onClick={() => setShowPassword(!showPassword)} data-testid="button-password-toggle"
                aria-label={showPassword ? "Hide password" : "Show password"}>
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="remember-me" checked={rememberMe} disabled={isLoading}
                onCheckedChange={(checked) => setRememberMe(!!checked)} data-testid="checkbox-remember-me" />
              <label htmlFor="remember-me" className="text-sm text-gray-700 dark:text-gray-300 cursor-pointer">Remember me</label>
            </div>
            {error && <p className="text-red-400 text-sm text-center" data-testid="text-login-error" role="alert">{error}</p>}
            <Button type="submit" className="w-full" data-testid="button-submit"
              disabled={isLoading || !email || !password || (emailValidation.hasBeenValidated && !emailValidation.isValid)}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign In
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
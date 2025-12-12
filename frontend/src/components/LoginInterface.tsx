import { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Eye, EyeOff, AlertCircle, CheckCircle, Loader2, Shield, ShieldCheck, ShieldAlert } from "lucide-react";
import { useLogin } from "@/hooks/useAuth";
import { useLocation } from "wouter";
import type { PasswordStrength } from "@shared/schema";
import skelditLogo from "@assets/Skeldir Logo (no background)_1759004645592.png";
import Skeldir_Logo_V3 from "@assets/Skeldir Logo V3.png";

import Skeldir_Logo_V4 from "@assets/Skeldir Logo V4.png";

import Skeldir_Logo_V5 from "@assets/Skeldir Logo V5.png";

import Skeldir_Logo_V6 from "@assets/Skeldir Logo V6.png";

import _2573a716_13f7_4ceb_a8d3_b100edc9d516 from "@assets/2573a716-13f7-4ceb-a8d3-b100edc9d516.png";

import Final_Skeldir_Logo from "@assets/Final Skeldir Logo.png";

import Final_Skeldir_Logo__Black_wording_ from "@assets/Final Skeldir Logo (Black wording).png";

interface EmailValidationState {
  isValid: boolean;
  isValidating: boolean;
  message: string;
  hasBeenValidated: boolean;
}

interface PasswordStrengthState extends PasswordStrength {
  hasBeenEvaluated: boolean;
}

export default function LoginInterface() {
  // Form state
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [logoError, setLogoError] = useState(false);
  
  // Email validation state
  const [emailValidation, setEmailValidation] = useState<EmailValidationState>({
    isValid: true,
    isValidating: false,
    message: "",
    hasBeenValidated: false,
  });

  // Password strength state
  const [passwordStrength, setPasswordStrength] = useState<PasswordStrengthState>({
    score: 0,
    feedback: {
      suggestions: [],
      warning: undefined,
    },
    requirements: {
      minLength: false,
      hasUppercase: false,
      hasLowercase: false,
      hasNumbers: false,
      hasSpecialChars: false,
    },
    hasBeenEvaluated: false,
  });

  // Hooks
  const { login, isLoading, error, clearError } = useLogin();
  const [, navigate] = useLocation();

  // Local email validation using regex (B0.2 contract-compliant - no server dependency)
  const validateEmail = useCallback((emailToValidate: string): boolean => {
    if (!emailToValidate.trim()) {
      setEmailValidation({
        isValid: false,
        isValidating: false,
        message: "Email is required",
        hasBeenValidated: true,
      });
      return false;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const isValid = emailRegex.test(emailToValidate);
    
    setEmailValidation({
      isValid,
      isValidating: false,
      message: isValid ? "Valid email format" : "Please enter a valid email address",
      hasBeenValidated: true,
    });
    return isValid;
  }, []);

  // Password strength evaluation function
  const evaluatePasswordStrength = useCallback((passwordToEvaluate: string): PasswordStrengthState => {
    if (!passwordToEvaluate) {
      return {
        score: 0,
        feedback: {
          suggestions: ['Enter a password'],
          warning: undefined,
        },
        requirements: {
          minLength: false,
          hasUppercase: false,
          hasLowercase: false,
          hasNumbers: false,
          hasSpecialChars: false,
        },
        hasBeenEvaluated: false,
      };
    }

    const requirements = {
      minLength: passwordToEvaluate.length >= 8,
      hasUppercase: /[A-Z]/.test(passwordToEvaluate),
      hasLowercase: /[a-z]/.test(passwordToEvaluate),
      hasNumbers: /\d/.test(passwordToEvaluate),
      hasSpecialChars: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(passwordToEvaluate),
    };

    const metRequirements = Object.values(requirements).filter(Boolean).length;
    let score = 0;
    const suggestions: string[] = [];
    let warning: string | undefined;

    // Calculate score based on requirements met
    if (metRequirements >= 4 && requirements.minLength) {
      score = 4; // Very strong
    } else if (metRequirements >= 3 && requirements.minLength) {
      score = 3; // Strong
    } else if (metRequirements >= 2 && requirements.minLength) {
      score = 2; // Fair
    } else if (passwordToEvaluate.length >= 6) {
      score = 1; // Weak
    } else {
      score = 0; // Very weak
    }

    // Generate suggestions
    if (!requirements.minLength) {
      suggestions.push('Use at least 8 characters');
    }
    if (!requirements.hasUppercase) {
      suggestions.push('Add uppercase letters');
    }
    if (!requirements.hasLowercase) {
      suggestions.push('Add lowercase letters');
    }
    if (!requirements.hasNumbers) {
      suggestions.push('Add numbers');
    }
    if (!requirements.hasSpecialChars) {
      suggestions.push('Add special characters (!@#$%^&*)');
    }

    // Set warning for very weak passwords
    if (score <= 1 && passwordToEvaluate.length > 0) {
      warning = 'This password is too weak';
    }

    return {
      score,
      feedback: { suggestions, warning },
      requirements,
      hasBeenEvaluated: true,
    };
  }, []);

  // Handle password change with strength evaluation
  const handlePasswordChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newPassword = e.target.value;
    setPassword(newPassword);
    
    // Evaluate password strength in real-time
    const strength = evaluatePasswordStrength(newPassword);
    setPasswordStrength(strength);
  }, [evaluatePasswordStrength]);

  // Handle email blur event for validation
  const handleEmailBlur = useCallback(() => {
    validateEmail(email);
  }, [email, validateEmail]);

  // Handle form submission
  const handleLogin = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    // Validate email before submission if not already validated
    if (!emailValidation.hasBeenValidated || !emailValidation.isValid) {
      const isEmailValid = validateEmail(email);
      
      // Only proceed if email validation passed
      if (!isEmailValid) {
        return;
      }
    }

    try {
      const result = await login(email, password, rememberMe);
      if (result && result.success) {
        // Redirect to dashboard on successful login
        navigate('/dashboard');
      }
    } catch (err) {
      // Error is already handled by useLogin hook and will display in UI
      console.error('Login failed:', err);
    }
  }, [email, password, rememberMe, login, navigate, emailValidation, validateEmail, clearError]);

  // Block copy/paste/cut in password field as requested
  const handlePasswordPaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
  }, []);
  
  const handlePasswordCopy = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
  }, []);
  
  const handlePasswordCut = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
  }, []);

  // Clear validation when email changes
  useEffect(() => {
    if (emailValidation.hasBeenValidated) {
      setEmailValidation(prev => ({ ...prev, hasBeenValidated: false, message: "" }));
    }
  }, [email]);

  // Clear auth error when form changes
  useEffect(() => {
    if (error) {
      clearError();
    }
  }, [email, password, clearError]);


  return (
    <div className="min-h-screen flex flex-col md:flex-row md:items-center md:justify-center p-4 relative">
      {/* Skeldir Logo - top left on desktop, in-flow on mobile */}
      <div className="md:fixed md:z-20 md:block flex justify-center mb-8 md:mb-0 pt-8 md:pt-0" 
        style={{ 
          top: '4px', 
          left: '4px' 
        }}
      >
        {!logoError ? (
          <div className="relative inline-block cursor-pointer hover:opacity-80 transition-opacity duration-200"
               onClick={() => window.location.href = '/'}>
            <img 
              src={Final_Skeldir_Logo__Black_wording_}
              alt="Skeldir Logo"
              className="block w-[90px] md:w-[99px] h-auto"
              onError={() => setLogoError(true)}
              data-testid="logo-skeldir"
            />
          </div>
        ) : (
          <div 
            className="flex items-center justify-center h-8 w-auto min-w-[90px] px-3 bg-white/90 backdrop-blur-md border border-white/40 rounded cursor-pointer hover:opacity-80 transition-all duration-200"
            onClick={() => window.location.href = '/'}
            data-testid="logo-skeldir-fallback"
          >
            <span className="text-gray-800 font-semibold text-sm tracking-wide">Skeldir</span>
          </div>
        )}
      </div>
      {/* Bottom right tagline - hidden on mobile, visible on desktop */}
      <div 
        className="fixed z-10 hidden md:block" 
        style={{ 
          bottom: '32px', 
          right: '32px',
          maxWidth: '320px'
        }}
      >
        <div className="text-black text-3xl md:text-4xl leading-tight text-right">
          <div className="font-light text-[28px]">One Platform to</div>
          <div className="font-bold text-[27px]">Track, Trust,</div>
          <div className="font-bold text-[27px]">& Optimize</div>
          <div className="font-bold text-[27px]">Marketing dollars.</div>
        </div>
      </div>
      {/* Main login card with glass effect */}
      <Card className="w-full max-w-md bg-white/20 backdrop-blur-lg border border-white/30 shadow-xl">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold text-gray-800">Log in or Sign up</CardTitle>
          <CardDescription className="text-gray-600">
            Sign in to your account to continue
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            {/* Email field with real-time validation */}
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 sr-only">
                Email Address
              </label>
              <div className="relative">
                <Input
                  id="email"
                  type="email"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={handleEmailBlur}
                  disabled={isLoading}
                  aria-invalid={emailValidation.hasBeenValidated && !emailValidation.isValid}
                  aria-describedby={emailValidation.hasBeenValidated ? "email-validation" : undefined}
                  className={`bg-white/30 backdrop-blur-sm border focus:border-white/60 pr-10 ${
                    emailValidation.hasBeenValidated
                      ? emailValidation.isValid
                        ? 'border-green-400/60 focus:border-green-400/80'
                        : 'border-red-400/60 focus:border-red-400/80'
                      : 'border-white/40'
                  }`}
                  data-testid="input-email"
                  required
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2" role="status">
                  {emailValidation.isValidating ? (
                    <Loader2 className="h-4 w-4 animate-spin text-white/60" aria-hidden="true" />
                  ) : emailValidation.hasBeenValidated ? (
                    emailValidation.isValid ? (
                      <CheckCircle className="h-4 w-4 text-green-400" data-testid="icon-email-valid" aria-hidden="true" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-400" data-testid="icon-email-invalid" aria-hidden="true" />
                    )
                  ) : null}
                </div>
              </div>
              {emailValidation.hasBeenValidated && emailValidation.message && (
                <p 
                  id="email-validation"
                  className={`text-xs ${emailValidation.isValid ? 'text-green-400' : 'text-red-400'}`} 
                  data-testid="text-email-validation"
                  aria-live="polite"
                >
                  {emailValidation.message}
                </p>
              )}
            </div>
            
            {/* Password field with show/hide toggle and copy/paste protection */}
            <div className="space-y-2 relative">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 sr-only">
                Password
              </label>
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Password"
                value={password}
                onChange={handlePasswordChange}
                onPaste={handlePasswordPaste}
                onCopy={handlePasswordCopy}
                onCut={handlePasswordCut}
                disabled={isLoading}
                className="bg-white/30 backdrop-blur-sm border border-white/40 focus:border-white/60 pr-10"
                data-testid="input-password"
                required
              />
              
            </div>

            {/* Password strength indicator */}
            {passwordStrength.hasBeenEvaluated && password.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-600">
                    Password Strength
                  </span>
                  <div className="flex items-center space-x-1">
                    {passwordStrength.score >= 3 ? (
                      <ShieldCheck className="h-3 w-3 text-green-400" aria-hidden="true" />
                    ) : passwordStrength.score >= 2 ? (
                      <Shield className="h-3 w-3 text-yellow-400" aria-hidden="true" />
                    ) : (
                      <ShieldAlert className="h-3 w-3 text-red-400" aria-hidden="true" />
                    )}
                    <span className={`text-xs font-medium ${
                      passwordStrength.score >= 3 ? 'text-green-400' :
                      passwordStrength.score >= 2 ? 'text-yellow-400' : 'text-red-400'
                    }`} data-testid="text-password-strength">
                      {passwordStrength.score === 4 ? 'Very Strong' :
                       passwordStrength.score === 3 ? 'Strong' :
                       passwordStrength.score === 2 ? 'Fair' :
                       passwordStrength.score === 1 ? 'Weak' : 'Very Weak'}
                    </span>
                  </div>
                </div>
                
                {/* Strength meter */}
                <div className="w-full bg-white/20 rounded-full h-1.5 backdrop-blur-sm">
                  <div 
                    className={`h-full rounded-full transition-all duration-300 ${
                      passwordStrength.score >= 3 ? 'bg-green-400' :
                      passwordStrength.score >= 2 ? 'bg-yellow-400' : 'bg-red-400'
                    }`}
                    style={{ width: `${(passwordStrength.score / 4) * 100}%` }}
                    data-testid="meter-password-strength"
                  />
                </div>

                {/* Requirements checklist */}
                <div className="grid grid-cols-2 gap-1 text-xs">
                  <div className={`flex items-center space-x-1 ${
                    passwordStrength.requirements.minLength ? 'text-green-400' : 'text-gray-400'
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${
                      passwordStrength.requirements.minLength ? 'bg-green-400' : 'bg-gray-400'
                    }`} aria-hidden="true" />
                    <span>8+ chars</span>
                  </div>
                  <div className={`flex items-center space-x-1 ${
                    passwordStrength.requirements.hasUppercase ? 'text-green-400' : 'text-gray-400'
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${
                      passwordStrength.requirements.hasUppercase ? 'bg-green-400' : 'bg-gray-400'
                    }`} aria-hidden="true" />
                    <span>Uppercase</span>
                  </div>
                  <div className={`flex items-center space-x-1 ${
                    passwordStrength.requirements.hasLowercase ? 'text-green-400' : 'text-gray-400'
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${
                      passwordStrength.requirements.hasLowercase ? 'bg-green-400' : 'bg-gray-400'
                    }`} aria-hidden="true" />
                    <span>Lowercase</span>
                  </div>
                  <div className={`flex items-center space-x-1 ${
                    passwordStrength.requirements.hasNumbers ? 'text-green-400' : 'text-gray-400'
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${
                      passwordStrength.requirements.hasNumbers ? 'bg-green-400' : 'bg-gray-400'
                    }`} aria-hidden="true" />
                    <span>Numbers</span>
                  </div>
                  <div className={`flex items-center space-x-1 ${
                    passwordStrength.requirements.hasSpecialChars ? 'text-green-400' : 'text-gray-400'
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${
                      passwordStrength.requirements.hasSpecialChars ? 'bg-green-400' : 'bg-gray-400'
                    }`} aria-hidden="true" />
                    <span>Special (!@#$)</span>
                  </div>
                </div>

                {/* Warning message */}
                {passwordStrength.feedback.warning && (
                  <p className="text-xs text-red-400" data-testid="text-password-warning" aria-live="polite">
                    {passwordStrength.feedback.warning}
                  </p>
                )}
              </div>
            )}

            {/* Remember me checkbox */}
            <div className="flex items-center space-x-2">
              <Checkbox
                id="remember-me"
                checked={rememberMe}
                onCheckedChange={(checked) => setRememberMe(checked === true)}
                disabled={isLoading}
                className="bg-white/30 backdrop-blur-sm border border-white/40"
                data-testid="checkbox-remember-me"
              />
              <label
                htmlFor="remember-me"
                className="text-sm text-gray-600 cursor-pointer"
              >
                Remember me for 30 days
              </label>
            </div>

            {/* Error message display */}
            {error && (
              <div className="bg-red-500/20 backdrop-blur-sm border border-red-400/40 rounded-md p-3" data-testid="error-message" role="alert" aria-live="assertive">
                <div className="flex items-center space-x-2">
                  <AlertCircle className="h-4 w-4 text-red-400" aria-hidden="true" />
                  <p className="text-sm text-red-300">{error}</p>
                </div>
              </div>
            )}

            {/* Submit button with loading state */}
            <Button
              type="submit"
              disabled={isLoading || (emailValidation.hasBeenValidated && !emailValidation.isValid)}
              className="w-full bg-primary/80 backdrop-blur-sm hover:bg-primary/90 text-primary-foreground disabled:opacity-50"
              data-testid="button-login"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>

          <div className="mt-6 space-y-4">
            <div className="flex justify-center text-sm">
              <span className="px-3 bg-white/20 backdrop-blur-sm text-gray-600 rounded-full">
                Or continue with
              </span>
            </div>

            <Button
              variant="outline"
              className="w-full bg-white/20 backdrop-blur-sm border border-white/30 hover-elevate"
              data-testid="button-google-auth"
              onClick={() => {
                // Navigate to Google OAuth flow
                window.location.href = '/api/auth/google';
              }}
            >
              <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </Button>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Don't have an account?{" "}
              <button
                className="text-primary hover:underline font-medium"
                onClick={() => console.log("Sign up clicked")}
                data-testid="link-signup"
              >
                Sign up
              </button>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
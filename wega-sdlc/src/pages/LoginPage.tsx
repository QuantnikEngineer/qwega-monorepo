import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '../components/ui/form';
import { Input } from '../components/ui/input';
import {
  AuthBackdrop,
  AUTH_GLASS_BUTTON_CLASS,
  AUTH_GLASS_CARD_CLASS,
  AUTH_GLASS_ERROR_CLASS,
  AUTH_GLASS_INPUT_CLASS,
} from '../components/AuthBackdrop';
import { useAuth } from '../auth/AuthContext';
import { validateEmail } from '../auth/validators';
import { ActivationForm } from '../admin/components/ActivationForm';

interface LoginFormValues {
  email: string;
  password: string;
}

interface LocationState {
  from?: { pathname: string };
}

export function LoginPage() {
  const { login, isAuthenticated, isLoading, user: authUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const activationToken = searchParams.get('token');
  const emailRef = useRef<HTMLInputElement | null>(null);
  const passwordRef = useRef<HTMLInputElement | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const form = useForm<LoginFormValues>({
    defaultValues: { email: '', password: '' },
  });

  const stateFrom = (location.state as LocationState | undefined)?.from?.pathname;
  // Under the auth wall, anonymous users hit LoginPage at the URL they wanted.
  // Prefer location.state.from when set (legacy /login redirect path), else use the
  // current pathname (skip if it's /login itself to avoid a redirect loop).
  const intendedPath = stateFrom ?? (location.pathname !== '/login' ? location.pathname : undefined);

  /** Determine the best landing page based on role & agents. */
  const getDefaultRoute = (user: { capabilities: string[]; allowedAgents?: string[] }): string => {
    // PM lands on dashboard (their home base); they can navigate to /execute from there
    if (user.capabilities.includes('team:manage_users')) return '/dashboard';
    // Anyone with agents goes to execute
    if ((user.allowedAgents?.length ?? 0) > 0) return '/execute';
    return '/';
  };

  const firstErrorField = useMemo(() => {
    if (form.formState.errors.email) return 'email';
    if (form.formState.errors.password) return 'password';
    return null;
  }, [form.formState.errors.email, form.formState.errors.password]);

  useEffect(() => {
    if (firstErrorField === 'email') emailRef.current?.focus();
    if (firstErrorField === 'password') passwordRef.current?.focus();
  }, [firstErrorField]);

  const onSubmit = form.handleSubmit(async (values) => {
    const emailValidationError = validateEmail(values.email);
    if (emailValidationError) {
      form.setError('email', { type: 'validate', message: emailValidationError });
      return;
    }

    setIsSubmitting(true);
    setLoginError(null);
    try {
      const result = await login(values.email.trim(), values.password);
      // Role-based redirect: prefer role-appropriate route; only honour the
      // intended deep-link path if it matches where this user would naturally
      // go (avoids the bug where User A's /execute leaks into PM User B's login).
      const roleDefault = getDefaultRoute(result.user);
      const destination = (intendedPath && intendedPath === roleDefault) ? intendedPath : roleDefault;
      navigate(destination, { replace: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid email or password. Please try again.';
      setLoginError(message || 'Invalid email or password. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  });

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    const destination = getDefaultRoute(authUser ?? { capabilities: [], allowedAgents: [] });
    return <Navigate to={destination} replace />;
  }

  // Activation mode: ?token= param detected — show ActivationForm instead of login (D-32)
  if (activationToken) {
    return (
      <AuthBackdrop>
        <ActivationForm token={activationToken} />
      </AuthBackdrop>
    );
  }

  return (
    <AuthBackdrop>
      <Card className={AUTH_GLASS_CARD_CLASS}>
        <CardHeader className="px-8 pt-8 lg:px-10 lg:pt-10">
          <CardTitle className="text-2xl font-medium text-white">Sign in to WEGA</CardTitle>
          <CardDescription className="text-sm text-white/65">
            Enter your Wipro email and password
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 px-8 pb-8 lg:px-10 lg:pb-10">
          {loginError && (
            <div className={AUTH_GLASS_ERROR_CLASS} role="alert">
              {loginError}
            </div>
          )}
          <Form {...form}>
            <form className="grid gap-4" onSubmit={onSubmit} noValidate>
              <FormField
                control={form.control}
                name="email"
                rules={{
                  required: 'Email is required',
                  onBlur: () => {
                    const email = form.getValues('email');
                    const emailError = validateEmail(email);
                    if (emailError) {
                      form.setError('email', { type: 'validate', message: emailError });
                    } else {
                      form.clearErrors('email');
                    }
                  },
                }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-normal text-white/80">Email</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        ref={(element) => {
                          field.ref(element);
                          emailRef.current = element;
                        }}
                        type="email"
                        placeholder="you@wipro.com"
                        autoComplete="email"
                        autoFocus
                        disabled={isSubmitting}
                        className={AUTH_GLASS_INPUT_CLASS}
                        onChange={(event) => {
                          field.onChange(event);
                          setLoginError(null);
                        }}
                      />
                    </FormControl>
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                rules={{ required: 'Password is required' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-normal text-white/80">Password</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        ref={(element) => {
                          field.ref(element);
                          passwordRef.current = element;
                        }}
                        type="password"
                        placeholder="Enter your password"
                        autoComplete="current-password"
                        disabled={isSubmitting}
                        className={AUTH_GLASS_INPUT_CLASS}
                        onChange={(event) => {
                          field.onChange(event);
                          setLoginError(null);
                        }}
                      />
                    </FormControl>
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />

              <div className="pt-2">
                <Button
                  type="submit"
                  className={AUTH_GLASS_BUTTON_CLASS}
                  disabled={isSubmitting}
                  aria-busy={isSubmitting}
                >
                  {isSubmitting ? 'Signing in…' : 'Sign in'}
                </Button>
              </div>

              <p className="text-center text-sm text-white/60">
                Don&apos;t have an account?{' '}
                <Link to="/register" className="text-[#3b82f6] hover:text-[#60a5fa] underline-offset-2 hover:underline">
                  Register
                </Link>
              </p>
            </form>
          </Form>
        </CardContent>
      </Card>
    </AuthBackdrop>
  );
}

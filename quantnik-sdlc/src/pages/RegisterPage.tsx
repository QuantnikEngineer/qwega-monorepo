import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
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
import { validateEmail, validatePassword, isPasswordValid } from '../auth/validators';
import { register as registerApi, fetchRegistrationDefaults } from '../services/authApi';
import type { RegistrationDefaults } from '../services/authApi';

interface RegisterFormValues {
  email: string;
  displayName: string;
  password: string;
  confirmPassword: string;
}

type RegistrationMode = 'project' | 'pm' | 'loading';

export function RegisterPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Registration mode state
  const [regMode, setRegMode] = useState<RegistrationMode>('loading');
  const [projectSlug, setProjectSlug] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [defaults, setDefaults] = useState<RegistrationDefaults | null>(null);

  const emailRef = useRef<HTMLInputElement | null>(null);
  const nameRef = useRef<HTMLInputElement | null>(null);
  const passwordRef = useRef<HTMLInputElement | null>(null);

  // Resolve registration mode on mount
  useEffect(() => {
    const urlProject = searchParams.get('project');

    if (urlProject) {
      // URL param takes priority — validate via defaults endpoint
      fetchRegistrationDefaults().then((d) => {
        // If URL param matches the configured default, use its project_name
        if (d.mode === 'project' && d.project_slug === urlProject) {
          setProjectSlug(urlProject);
          setProjectName(d.project_name ?? urlProject);
          setDefaults(d);
          setRegMode('project');
        } else {
          // URL param provided but we trust it — backend will validate
          setProjectSlug(urlProject);
          setProjectName(urlProject);
          setDefaults(d);
          setRegMode('project');
        }
      }).catch(() => {
        setProjectSlug(urlProject);
        setProjectName(urlProject);
        setRegMode('project');
      });
    } else {
      // No URL param — check env-configured defaults
      fetchRegistrationDefaults().then((d) => {
        setDefaults(d);
        if (d.mode === 'project' && d.project_slug) {
          setProjectSlug(d.project_slug);
          setProjectName(d.project_name ?? d.project_slug);
          setRegMode('project');
        } else {
          setRegMode('pm');
        }
      }).catch(() => {
        setRegMode('pm');
      });
    }
  }, [searchParams]);

  const form = useForm<RegisterFormValues>({
    defaultValues: { email: '', displayName: '', password: '', confirmPassword: '' },
  });

  const watchedPassword = form.watch('password');
  const passwordChecks = useMemo(() => validatePassword(watchedPassword || ''), [watchedPassword]);

  const firstErrorField = useMemo(() => {
    const errors = form.formState.errors;
    if (errors.email) return 'email';
    if (errors.displayName) return 'displayName';
    if (errors.password) return 'password';
    if (errors.confirmPassword) return 'confirmPassword';
    return null;
  }, [form.formState.errors]);

  useEffect(() => {
    if (firstErrorField === 'email') emailRef.current?.focus();
    if (firstErrorField === 'displayName') nameRef.current?.focus();
    if (firstErrorField === 'password') passwordRef.current?.focus();
  }, [firstErrorField]);

  const switchToMode = (mode: 'project' | 'pm') => {
    if (mode === 'project' && defaults?.mode === 'project' && defaults.project_slug) {
      setProjectSlug(defaults.project_slug);
      setProjectName(defaults.project_name ?? defaults.project_slug);
    } else if (mode === 'pm') {
      setProjectSlug(null);
      setProjectName(null);
    }
    setRegMode(mode);
    setRegisterError(null);
  };

  const onSubmit = form.handleSubmit(async (values) => {
    // Client-side validations
    const emailError = validateEmail(values.email);
    if (emailError) {
      form.setError('email', { type: 'validate', message: emailError });
      return;
    }

    if (!values.displayName.trim()) {
      form.setError('displayName', { type: 'validate', message: 'Display name is required' });
      return;
    }

    if (!isPasswordValid(values.password)) {
      form.setError('password', { type: 'validate', message: 'Password does not meet all requirements' });
      return;
    }

    if (values.password !== values.confirmPassword) {
      form.setError('confirmPassword', { type: 'validate', message: 'Passwords do not match' });
      return;
    }

    setIsSubmitting(true);
    setRegisterError(null);
    try {
      await registerApi(
        values.email.trim(),
        values.displayName.trim(),
        values.password,
        regMode === 'project' ? projectSlug ?? undefined : undefined,
      );
      setSuccess(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Registration failed. Please try again.';
      setRegisterError(message);
    } finally {
      setIsSubmitting(false);
    }
  });

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (success) {
    return (
      <AuthBackdrop>
        <Card className={AUTH_GLASS_CARD_CLASS}>
          <CardHeader className="px-8 pt-8 lg:px-10 lg:pt-10">
            <CardTitle className="text-2xl font-medium text-white">Registration Submitted</CardTitle>
            <CardDescription className="text-sm text-white/65">
              {regMode === 'project'
                ? 'Your account has been created. You can start using agents right after signing in.'
                : 'If this email is valid, your account has been created.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 px-8 pb-8 lg:px-10 lg:pb-10">
            <p className="text-sm text-white/80">You can now sign in with your credentials.</p>
            <div className="pt-2">
              <Button
                className={AUTH_GLASS_BUTTON_CLASS}
                onClick={() => navigate('/login')}
              >
                Go to Sign In
              </Button>
            </div>
          </CardContent>
        </Card>
      </AuthBackdrop>
    );
  }

  const isProjectMode = regMode === 'project';

  return (
    <AuthBackdrop>
      <Card className={AUTH_GLASS_CARD_CLASS}>
        <CardHeader className="px-8 pt-8 lg:px-10 lg:pt-10">
          <CardTitle className="text-2xl font-medium text-white">Create your account</CardTitle>
          <CardDescription className="text-sm text-white/65">
            Register with your Wipro email to get started
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 px-8 pb-8 lg:px-10 lg:pb-10">
          {/* Registration mode context banner */}
          {regMode !== 'loading' && (
            <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/80">
              {isProjectMode ? (
                <>
                  <p className="font-medium text-white/90">
                    🚀 Joining <span className="text-[#3b82f6]">{projectName}</span>
                  </p>
                  <p className="mt-1 text-xs text-white/60">
                    You'll be able to start using AI agents immediately after registration.
                  </p>
                  {defaults?.mode === 'project' && (
                    <button
                      type="button"
                      className="mt-2 text-xs text-white/50 hover:text-white/80 underline-offset-2 hover:underline transition-colors"
                      onClick={() => switchToMode('pm')}
                    >
                      Want to manage your own project? Register as a Project Manager instead
                    </button>
                  )}
                </>
              ) : (
                <>
                  <p className="font-medium text-white/90">📋 Registering as a Project Manager</p>
                  <p className="mt-1 text-xs text-white/60">
                    As a PM, you'll create your project, invite team members, and configure tools.
                    This is ideal for setting up a new initiative from scratch.
                  </p>
                  {defaults?.mode === 'project' && defaults.project_name && (
                    <button
                      type="button"
                      className="mt-2 text-xs text-white/50 hover:text-white/80 underline-offset-2 hover:underline transition-colors"
                      onClick={() => switchToMode('project')}
                    >
                      Just want to try the platform? Join {defaults.project_name} instead
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {registerError && (
            <div className={AUTH_GLASS_ERROR_CLASS} role="alert">
              {registerError}
            </div>
          )}
          <Form {...form}>
            <form className="grid gap-4" onSubmit={onSubmit} noValidate>
              <FormField
                control={form.control}
                name="email"
                rules={{ required: 'Email is required' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-normal text-white/80">Email</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        ref={(el) => { field.ref(el); emailRef.current = el; }}
                        type="email"
                        placeholder="you@wipro.com"
                        autoComplete="email"
                        autoFocus
                        disabled={isSubmitting}
                        className={AUTH_GLASS_INPUT_CLASS}
                        onChange={(e) => { field.onChange(e); setRegisterError(null); }}
                      />
                    </FormControl>
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="displayName"
                rules={{ required: 'Display name is required' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-normal text-white/80">Display Name</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        ref={(el) => { field.ref(el); nameRef.current = el; }}
                        type="text"
                        placeholder="Your full name"
                        autoComplete="name"
                        disabled={isSubmitting}
                        className={AUTH_GLASS_INPUT_CLASS}
                        onChange={(e) => { field.onChange(e); setRegisterError(null); }}
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
                        ref={(el) => { field.ref(el); passwordRef.current = el; }}
                        type="password"
                        placeholder="Create a strong password"
                        autoComplete="new-password"
                        disabled={isSubmitting}
                        className={AUTH_GLASS_INPUT_CLASS}
                        onChange={(e) => { field.onChange(e); setRegisterError(null); }}
                      />
                    </FormControl>
                    <FormMessage className="text-destructive" />
                    {/* Live password strength checklist */}
                    {watchedPassword && (
                      <ul className="mt-2 space-y-1 text-xs" aria-label="Password requirements">
                        {passwordChecks.map(({ rule, met }) => (
                          <li
                            key={rule.id}
                            className={met ? 'text-emerald-400' : 'text-white/50'}
                          >
                            <span className="mr-1.5">{met ? '✓' : '○'}</span>
                            {rule.label}
                          </li>
                        ))}
                      </ul>
                    )}
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="confirmPassword"
                rules={{ required: 'Please confirm your password' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-normal text-white/80">Confirm Password</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="password"
                        placeholder="Repeat your password"
                        autoComplete="new-password"
                        disabled={isSubmitting}
                        className={AUTH_GLASS_INPUT_CLASS}
                        onChange={(e) => { field.onChange(e); setRegisterError(null); }}
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
                  disabled={isSubmitting || regMode === 'loading'}
                  aria-busy={isSubmitting}
                >
                  {isSubmitting ? 'Creating account…' : 'Create Account'}
                </Button>
              </div>

              <p className="text-center text-sm text-white/60">
                Already have an account?{' '}
                <Link to="/login" className="text-[#3b82f6] hover:text-[#60a5fa] underline-offset-2 hover:underline">
                  Sign in
                </Link>
              </p>
            </form>
          </Form>
        </CardContent>
      </Card>
    </AuthBackdrop>
  );
}

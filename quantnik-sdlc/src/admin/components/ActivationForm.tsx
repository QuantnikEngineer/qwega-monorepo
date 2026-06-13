/**
 * ActivationForm
 *
 * Password-setting form for user account activation.
 * Displayed within LoginPage when ?token= query param is detected (D-12, D-32).
 * Validates password against PASSWORD_RULES and POSTs to /api/auth/activate.
 * On success: toast + redirect to login. On 400: expired/invalid token error.
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { PasswordChecklist } from '../../components/PasswordChecklist';
import { PASSWORD_RULES } from '../../auth/validators';
import { apiFetch } from '../../services/apiClient';
import {
  AUTH_GLASS_BUTTON_CLASS,
  AUTH_GLASS_CARD_CLASS,
  AUTH_GLASS_ERROR_CLASS,
  AUTH_GLASS_INPUT_CLASS,
} from '../../components/AuthBackdrop';

interface ActivationFormProps {
  token: string;
}

interface ActivationFormValues {
  password: string;
  confirmPassword: string;
}

export function ActivationForm({ token }: ActivationFormProps) {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const form = useForm<ActivationFormValues>({
    defaultValues: { password: '', confirmPassword: '' },
  });

  const watchedPassword = form.watch('password');
  const watchedConfirm = form.watch('confirmPassword');

  const allRulesMet = useMemo(
    () => PASSWORD_RULES.every((rule) => rule.test(watchedPassword || '')),
    [watchedPassword],
  );
  const passwordsMatch = watchedPassword === watchedConfirm && (watchedConfirm || '').length > 0;
  const canSubmit = allRulesMet && passwordsMatch && !isSubmitting;

  const onSubmit = form.handleSubmit(async (values) => {
    if (!allRulesMet) {
      form.setError('password', { type: 'validate', message: 'Password does not meet requirements' });
      return;
    }
    if (values.password !== values.confirmPassword) {
      form.setError('confirmPassword', { type: 'validate', message: 'Passwords do not match' });
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const res = await apiFetch('/auth/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password: values.password, confirm_password: values.confirmPassword }),
      });

      if (res.ok) {
        toast.success('Account activated! Please sign in.');
        navigate('/', { replace: true });
        return;
      }

      if (res.status === 400) {
        setErrorMessage(
          'This activation link has expired or is invalid. Contact your administrator for a new link.',
        );
        return;
      }

      const err = await res.json().catch(() => ({ detail: 'Activation failed' }));
      toast.error(err.detail || 'Activation failed');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Activation failed';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  });

  return (
    <Card className={AUTH_GLASS_CARD_CLASS}>
      <CardHeader className="px-8 pt-8 lg:px-10 lg:pt-10">
        <CardTitle className="text-2xl font-medium text-white">Set your password</CardTitle>
        <CardDescription className="text-sm text-white/65">
          Create a password to activate your account
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 px-8 lg:px-10">
        {errorMessage && (
          <div className={AUTH_GLASS_ERROR_CLASS} role="alert">
            {errorMessage}
          </div>
        )}
        <form className="grid gap-4" onSubmit={onSubmit} noValidate>
          <div className="grid gap-2">
            <Label htmlFor="activation-password" className="font-normal text-white/80">
              Password
            </Label>
            <Input
              id="activation-password"
              type="password"
              placeholder="Enter your password"
              autoComplete="new-password"
              autoFocus
              disabled={isSubmitting}
              className={AUTH_GLASS_INPUT_CLASS}
              {...form.register('password', { required: 'Password is required' })}
            />
            {form.formState.errors.password && (
              <p className="text-destructive text-sm">{form.formState.errors.password.message}</p>
            )}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="activation-confirm" className="font-normal text-white/80">
              Confirm password
            </Label>
            <Input
              id="activation-confirm"
              type="password"
              placeholder="Confirm your password"
              autoComplete="new-password"
              disabled={isSubmitting}
              className={AUTH_GLASS_INPUT_CLASS}
              {...form.register('confirmPassword', {
                required: 'Confirm password is required',
                validate: (value) =>
                  value === form.getValues('password') || 'Passwords do not match',
              })}
            />
            {form.formState.errors.confirmPassword && (
              <p className="text-destructive text-sm">
                {form.formState.errors.confirmPassword.message}
              </p>
            )}
          </div>

          <PasswordChecklist password={watchedPassword || ''} />

          <div className="pt-2">
            <Button
              type="submit"
              className={AUTH_GLASS_BUTTON_CLASS}
              disabled={!canSubmit}
              aria-busy={isSubmitting}
            >
              {isSubmitting ? 'Activating…' : 'Activate account'}
            </Button>
          </div>
        </form>
      </CardContent>
      <CardFooter className="justify-center px-8 pb-8 lg:px-10 lg:pb-10">
        <button
          type="button"
          className="text-sm text-white/65 hover:text-white underline-offset-4 hover:underline transition-colors"
          onClick={() => navigate('/', { replace: true })}
        >
          Already have an account? Sign in
        </button>
      </CardFooter>
    </Card>
  );
}

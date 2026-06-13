/**
 * ChangePasswordDialog
 *
 * Modal dialog for changing password. Supports two modes:
 * - Voluntary: user clicks "Change Password" from AdminFAB menu (closeable)
 * - Forced: first-login password change (not dismissible until complete)
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { KeyRound, XIcon } from 'lucide-react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Button } from '../../components/ui/button';
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '../../components/ui/form';
import { Input } from '../../components/ui/input';
import { useAuth } from '../../auth/AuthContext';
import { PasswordChecklist } from '../../components/PasswordChecklist';
import { PASSWORD_RULES } from '../../auth/validators';
import { cn } from '../../components/ui/utils';

interface ChangePasswordDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When true, dialog cannot be dismissed (first-login forced change) */
  forced?: boolean;
}

interface ChangePasswordFormValues {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export function ChangePasswordDialog({ open, onOpenChange, forced }: ChangePasswordDialogProps) {
  const { changePassword } = useAuth();
  const currentPasswordRef = useRef<HTMLInputElement | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const form = useForm<ChangePasswordFormValues>({
    defaultValues: { currentPassword: '', newPassword: '', confirmPassword: '' },
  });

  const watchedNewPassword = form.watch('newPassword');
  const watchedConfirmPassword = form.watch('confirmPassword');
  const watchedCurrentPassword = form.watch('currentPassword');

  const allRulesMet = useMemo(
    () => PASSWORD_RULES.every((rule) => rule.test(watchedNewPassword || '')),
    [watchedNewPassword]
  );
  const passwordsMatch = !!watchedNewPassword && watchedNewPassword === watchedConfirmPassword;
  const isDifferentFromCurrent = !!watchedNewPassword && watchedCurrentPassword !== watchedNewPassword;
  const canSubmit = allRulesMet && passwordsMatch && isDifferentFromCurrent && !isSubmitting;

  // Focus current password field when dialog opens
  useEffect(() => {
    if (open) {
      form.reset();
      setErrorMessage(null);
      // Small delay for dialog animation
      const timer = setTimeout(() => currentPasswordRef.current?.focus(), 150);
      return () => clearTimeout(timer);
    }
  }, [open, form]);

  const onSubmit = form.handleSubmit(async (values) => {
    if (!passwordsMatch) {
      form.setError('confirmPassword', { type: 'validate', message: 'Passwords do not match' });
      return;
    }
    if (!isDifferentFromCurrent) {
      form.setError('newPassword', { type: 'validate', message: 'New password must differ from current password' });
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await changePassword(values.currentPassword, values.newPassword);
      toast.success('Password changed successfully');
      onOpenChange(false);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Password change failed';
      setErrorMessage(msg || 'Password change failed');
    } finally {
      setIsSubmitting(false);
    }
  });

  // Prevent closing in forced mode
  const handleOpenChange = (nextOpen: boolean) => {
    if (forced && !nextOpen) return;
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50',
            forced && 'z-[70]'
          )}
        />
        <DialogPrimitive.Content
          className={cn(
            'bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] translate-x-[-50%] translate-y-[-50%] z-50 grid w-full max-w-[calc(100%-2rem)] gap-4 rounded-lg border p-6 shadow-lg duration-200 sm:max-w-md',
            forced && 'z-[70]'
          )}
          onInteractOutside={(e) => { if (forced) e.preventDefault(); }}
          onEscapeKeyDown={(e) => { if (forced) e.preventDefault(); }}
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="w-5 h-5" />
              Change Password
            </DialogTitle>
            <DialogDescription>
              {forced
                ? 'Your temporary password must be changed before continuing.'
                : 'Enter your current password and set a new secure password.'}
            </DialogDescription>
          </DialogHeader>

          {errorMessage && (
            <div
              className="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
              role="alert"
            >
              {errorMessage}
            </div>
          )}

          <Form {...form}>
            <form className="grid gap-4" onSubmit={onSubmit} noValidate>
              <FormField
                control={form.control}
                name="currentPassword"
                rules={{ required: 'Current password is required' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Current password</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        ref={(el) => { field.ref(el); currentPasswordRef.current = el; }}
                        type="password"
                        placeholder="Enter your current password"
                        autoComplete="current-password"
                        disabled={isSubmitting}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="newPassword"
                rules={{ required: 'New password is required' }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New password</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="password"
                        placeholder="Enter new password"
                        autoComplete="new-password"
                        disabled={isSubmitting}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="confirmPassword"
                rules={{
                  required: 'Confirm password is required',
                  validate: (v) => v === form.getValues('newPassword') || 'Passwords do not match',
                }}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirm password</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="password"
                        placeholder="Confirm new password"
                        autoComplete="new-password"
                        disabled={isSubmitting}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <PasswordChecklist password={watchedNewPassword || ''} />

              <DialogFooter className="pt-2">
                {!forced && (
                  <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                    Cancel
                  </Button>
                )}
                <Button type="submit" disabled={!canSubmit} aria-busy={isSubmitting}>
                  {isSubmitting ? 'Changing…' : 'Change password'}
                </Button>
              </DialogFooter>
            </form>
          </Form>

          {/* Close button — only for voluntary mode */}
          {!forced && (
            <DialogPrimitive.Close className="ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4">
              <XIcon />
              <span className="sr-only">Close</span>
            </DialogPrimitive.Close>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </Dialog>
  );
}

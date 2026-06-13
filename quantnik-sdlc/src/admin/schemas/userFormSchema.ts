/**
 * User Form Schemas
 *
 * Multi-role per user, org-scoped (Phase 2 Wave 2).
 * Users can hold one or more roles simultaneously.
 */

import { z } from 'zod';

export const createUserSchema = z.object({
  email: z
    .string()
    .email('Invalid email')
    .endsWith('@wipro.com', 'Must be a @wipro.com email address'),
  display_name: z.string().min(1, 'Full name is required'),
  role_names: z.array(z.string()).min(1, 'At least one role is required'),
});

export const editUserSchema = z.object({
  display_name: z.string().min(1, 'Full name is required'),
  role_names: z.array(z.string()).min(1, 'At least one role is required'),
  status: z.enum(['active', 'suspended', 'deactivated']).optional(),
});

export type CreateUserFormValues = z.infer<typeof createUserSchema>;
export type EditUserFormValues = z.infer<typeof editUserSchema>;

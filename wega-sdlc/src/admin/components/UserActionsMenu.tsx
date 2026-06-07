import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import { Button } from '../../components/ui/button';
import { MoreHorizontal, Pencil, KeyRound, Link, UserX, UserCheck, Trash2 } from 'lucide-react';
import type { AdminUser } from '../api/adminApi';

interface UserActionsMenuProps {
  user: AdminUser;
  currentUserId: string;
  onEdit: () => void;
  onResetPassword: () => void;
  onCopyActivationLink: () => void;
  onDeactivate: () => void;
  onReactivate: () => void;
  onDelete: () => void;
}

export function UserActionsMenu({
  user,
  currentUserId,
  onEdit,
  onResetPassword,
  onCopyActivationLink,
  onDeactivate,
  onReactivate,
  onDelete,
}: UserActionsMenuProps) {
  const isSelf = user.id === currentUserId;
  const isDeactivated = user.status === 'deactivated';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Actions for ${user.displayName}`}>
          <MoreHorizontal className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={onEdit}>
          <Pencil className="size-4" />
          Edit User
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onResetPassword}>
          <KeyRound className="size-4" />
          Reset Password
        </DropdownMenuItem>
        {user.status === 'pending' && (
          <DropdownMenuItem onClick={onCopyActivationLink}>
            <Link className="size-4" />
            Copy Activation Link
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        {isDeactivated ? (
          <>
            <DropdownMenuItem
              onClick={onReactivate}
              aria-label={`Reactivate user ${user.displayName}`}
            >
              <UserCheck className="size-4" />
              Reactivate User
            </DropdownMenuItem>
            <DropdownMenuItem
              variant="destructive"
              disabled={isSelf}
              onClick={onDelete}
              aria-label={`Purge user ${user.displayName}`}
            >
              <Trash2 className="size-4" />
              Purge Account
            </DropdownMenuItem>
          </>
        ) : (
          <DropdownMenuItem
            variant="destructive"
            disabled={isSelf}
            onClick={onDeactivate}
            aria-label={`Deactivate user ${user.displayName}`}
          >
            <UserX className="size-4" />
            Deactivate User
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

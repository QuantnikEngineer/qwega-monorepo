import { Check, X } from 'lucide-react';
import { PASSWORD_RULES } from '../auth/validators';

interface PasswordChecklistProps {
  password: string;
}

export function PasswordChecklist({ password }: PasswordChecklistProps) {
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      {PASSWORD_RULES.map((rule) => {
        const passed = rule.test(password);
        return (
          <div key={rule.id} className="flex items-center gap-2 text-sm">
            {passed ? (
              <Check size={14} className="text-green-500" />
            ) : (
              <X size={14} className="text-muted-foreground" />
            )}
            <span className={passed ? 'text-foreground' : 'text-muted-foreground'}>{rule.label}</span>
          </div>
        );
      })}
    </div>
  );
}

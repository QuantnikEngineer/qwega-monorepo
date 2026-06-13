/**
 * ActivationLinkCopy
 *
 * Post-creation success state that displays the activation URL
 * with copy-to-clipboard and expiration notice.
 */

import { useState } from 'react';
import { Button } from '../../components/ui/button';
import { CheckCircle, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

interface ActivationLinkCopyProps {
  activationUrl: string;
  onDone: () => void;
}

export function ActivationLinkCopy({ activationUrl, onDone }: ActivationLinkCopyProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(activationUrl);
      setCopied(true);
      toast.success('Activation link copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy link');
    }
  };

  return (
    <div className="flex flex-col items-center text-center space-y-4 py-8 px-4">
      <CheckCircle className="size-12 text-[#3498B3]" />
      <h3 className="text-lg font-semibold">User created successfully</h3>
      <p className="text-sm text-muted-foreground">
        Share this activation link with the user:
      </p>

      <div className="w-full space-y-2">
        <code className="block w-full rounded-md border border-[#3498B3]/30 bg-[#3498B3]/5 p-3 text-xs break-all select-all">
          {activationUrl}
        </code>
        <Button
          type="button"
          variant="outline"
          className="w-full border-[#3498B3]/30 text-[#3498B3] hover:bg-[#3498B3]/10"
          onClick={handleCopy}
          aria-label="Copy activation link"
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? 'Copied!' : 'Copy activation link'}
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Expires in 48 hours
      </p>

      <Button variant="default" className="w-full bg-[#3498B3] hover:bg-[#3498B3]/90 text-white" onClick={onDone}>
        Done
      </Button>
    </div>
  );
}

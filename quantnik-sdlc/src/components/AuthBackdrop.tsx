/**
 * AuthBackdrop — shared full-bleed branded background + logo header for the
 * unauthenticated wall. Renders behind both the LoginPage form and the
 * ActivationForm so the visual language is identical across the two surfaces.
 *
 * Layout:
 *   - Image fills viewport (position: fixed; object-fit: cover) and never causes
 *     a layout shift.
 *   - A left-side scrim/gradient guarantees AA contrast on the form column even
 *     in worst-case lighting on the photo.
 *   - On desktop (>= 1024px) the form column is anchored slightly left-of-center
 *     so the warm peak and cobalt ring on the right of the photo remain visible.
 *   - On tablet/mobile the form centers horizontally with sensible side padding.
 *
 * The component renders the QUANTNIK white-variant logo (`DarkThemeLogo`) above the
 * `children` (the glass card). The page surface is always dark; we don't follow
 * the user's theme preference here.
 */

import type { ReactNode } from 'react';
import DarkThemeLogo from './DarkThemeLogo';
import authBgJpg from '../assets/auth-bg.jpg';

// Shared glass-card chrome reused by both the login and activation surfaces.
// 24px blur, ~140% saturation, low-tint navy fill, hairline inner border, soft
// long-shadow, generous padding, max width ~420px. Co-located with the backdrop
// so neither LoginPage nor ActivationForm has to import from the other (avoids
// a circular module dependency).
export const AUTH_GLASS_CARD_CLASS = [
  'w-full max-w-[420px] gap-5 rounded-2xl border border-white/10',
  'bg-white/[0.06] text-white shadow-[0_24px_64px_-24px_rgba(0,0,0,0.6),0_1px_0_0_rgba(255,255,255,0.06)_inset]',
  'backdrop-blur-xl backdrop-saturate-150',
  'auth-card-in',
].join(' ');

// Glass-styled input shared by both forms.
export const AUTH_GLASS_INPUT_CLASS = [
  'h-10 rounded-md border border-white/15 bg-white/[0.06] text-white',
  'placeholder:text-white/45',
  'focus-visible:border-[#3b82f6] focus-visible:ring-[#3b82f6]/35 focus-visible:ring-[3px]',
  'transition-[color,box-shadow,border-color] duration-150 ease-out',
].join(' ');

// Glass-styled submit button — full width, vibrant cobalt drawn from the photo.
export const AUTH_GLASS_BUTTON_CLASS = [
  'h-11 w-full rounded-md bg-[#2f6df6] text-white font-medium',
  'shadow-[0_8px_24px_-8px_rgba(47,109,246,0.55)]',
  'hover:bg-[#3b82f6] hover:shadow-[0_12px_32px_-10px_rgba(59,130,246,0.65)]',
  'transition-[background-color,box-shadow] duration-200 ease-out',
  'focus-visible:ring-[3px] focus-visible:ring-[#3b82f6]/40 focus-visible:ring-offset-0',
].join(' ');

export const AUTH_GLASS_ERROR_CLASS =
  'rounded-md border border-destructive/40 bg-destructive/15 p-3 text-sm text-white';

interface AuthBackdropProps {
  children: ReactNode;
}

export function AuthBackdrop({ children }: AuthBackdropProps) {
  return (
    <div className="relative isolate min-h-screen w-full overflow-hidden bg-[#0c0a2e] text-white">
      {/* Branded image — full-bleed, no layout shift. */}
      <img
        src={authBgJpg}
        alt=""
        aria-hidden="true"
        width={1920}
        height={1080}
        loading="eager"
        fetchPriority="high"
        decoding="async"
        draggable={false}
        className="pointer-events-none fixed inset-0 -z-20 h-full w-full select-none object-cover object-center"
      />

      {/* Scrim — biased to the left half so the warm peak / cobalt ring on the
          right of the photo stay visible while text contrast is preserved on
          the form column. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            'linear-gradient(100deg, rgba(8,8,28,0.78) 0%, rgba(8,8,28,0.55) 28%, rgba(8,8,28,0.18) 55%, rgba(8,8,28,0.0) 78%)',
        }}
      />

      {/* Form column. Slightly left-of-center on desktop, centered on
          tablet/mobile. */}
      <div className="relative z-10 flex min-h-screen w-full flex-col items-center justify-center px-4 py-10 lg:items-start lg:justify-center lg:pl-[clamp(48px,12vw,200px)] lg:pr-8">
        <div className="flex w-full max-w-[420px] flex-col items-center gap-8 lg:items-start">
          <div className="h-[40px] w-auto" aria-label="QUANTNIK">
            <DarkThemeLogo />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

export default AuthBackdrop;

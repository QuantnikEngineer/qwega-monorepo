import React from 'react';

export function Logo({ size = 32 }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
      <img
        src="/quantnik-logo.png"
        height={size}
        alt="Quantnik"
        style={{ display: 'block', height: size, width: 'auto' }}
      />
      <span
        style={{
          fontWeight: 700,
          letterSpacing: '0.18em',
          fontSize: 18,
          color: 'var(--text)',
        }}
      >
        Quantnik
      </span>
    </div>
  );
}

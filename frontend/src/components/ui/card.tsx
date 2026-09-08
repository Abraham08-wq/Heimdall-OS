// ui/card.tsx — Lightweight Card component stubs
// These are used by SovereignBoardroom as internal UI primitives
import React from 'react';

interface CardProps { children: React.ReactNode; className?: string }
interface CardHeaderProps { children: React.ReactNode; className?: string }
interface CardTitleProps { children: React.ReactNode; className?: string }
interface CardContentProps { children: React.ReactNode; className?: string }

export function Card({ children, className = '' }: CardProps) {
  return (
    <div className={`rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
  return (
    <div className={`px-5 pt-5 pb-2 ${className}`}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '' }: CardTitleProps) {
  return (
    <h3 className={`text-sm font-semibold uppercase tracking-widest text-slate-300 ${className}`}>
      {children}
    </h3>
  );
}

export function CardContent({ children, className = '' }: CardContentProps) {
  return (
    <div className={`px-5 pb-5 ${className}`}>
      {children}
    </div>
  );
}

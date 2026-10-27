import type { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-lg border border-brand-100 bg-white shadow-card ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex min-h-[52px] items-center justify-between gap-3 border-b border-brand-100 px-5 py-3">
      <h3 className="font-sans text-[15px] font-semibold tracking-[-0.01em] text-brand-900">
        {title}
      </h3>
      {action}
    </div>
  );
}

export function CardBody({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>;
}

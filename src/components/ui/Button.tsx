import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Link, type LinkProps } from 'react-router-dom';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors duration-150 active:translate-y-px ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ' +
  'disabled:cursor-not-allowed disabled:opacity-60';

const variants: Record<Variant, string> = {
  primary: 'bg-brand-900 text-white hover:bg-brand-800 shadow-sm',
  secondary:
    'bg-white text-brand-800 border border-brand-200 hover:border-brand-300 hover:bg-brand-50 shadow-sm',
  ghost: 'text-brand-700 hover:bg-brand-100',
  danger: 'bg-red-600 text-white hover:bg-red-700 shadow-sm',
};

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-9 px-4 text-sm',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', className = '', type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  );
});

interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  size?: Size;
}

/** A router link styled as a button. Use instead of nesting a Button in a Link. */
export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}: ButtonLinkProps) {
  return <Link className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props} />;
}

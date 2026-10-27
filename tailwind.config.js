/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"Libre Baskerville"', 'Georgia', 'ui-serif', 'serif'],
      },
      colors: {
        // Deep legal navy — primary brand
        brand: {
          50: '#f3f5f8',
          100: '#e3e8ef',
          200: '#c9d2de',
          300: '#a3b1c4',
          400: '#7a8ba3',
          500: '#5a6c86',
          600: '#43546d',
          700: '#2f3e55',
          800: '#1f2b3f',
          900: '#121a2b',
        },
        // The page canvas: a hair warmer than white so cards read as paper.
        canvas: '#f6f7f9',
        accent: {
          // Muted gold — used sparingly
          500: '#b08d57',
          600: '#9a7745',
        },
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(18 26 43 / 0.05)',
        raised: '0 4px 12px -2px rgb(18 26 43 / 0.10), 0 2px 4px -2px rgb(18 26 43 / 0.06)',
      },
    },
  },
  plugins: [],
};

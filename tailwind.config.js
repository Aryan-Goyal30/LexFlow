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
          50: '#f0f4f8',
          100: '#d9e2ec',
          200: '#bcccdc',
          300: '#9fb3c8',
          400: '#829ab1',
          500: '#627d98',
          600: '#486581',
          700: '#334e68',
          800: '#243b53',
          900: '#102a43',
        },
        accent: {
          // Muted gold — used sparingly
          500: '#b08d57',
          600: '#9a7745',
        },
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(16 42 67 / 0.08), 0 1px 2px -1px rgb(16 42 67 / 0.06)',
      },
    },
  },
  plugins: [],
};

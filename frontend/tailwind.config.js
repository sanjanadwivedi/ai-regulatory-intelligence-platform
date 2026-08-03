/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          300: '#60a5fa',
          400: '#3b82f6',
          500: '#0066fe',
          600: '#0052cc',
          700: '#003eb3',
          900: '#001a4d',
        },
        slate: {
          850: '#1e293b',
          950: '#0f172a',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Outfit', 'sans-serif'],
      }
    },
  },
  plugins: [],
}

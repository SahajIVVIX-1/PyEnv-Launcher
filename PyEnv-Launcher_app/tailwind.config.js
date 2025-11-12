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
        'dark-background': '#121212',
        'dark-primary': '#1e1e1e',
        'dark-secondary': '#2a2a2a',
        'dark-border': '#424242',
        'dark-text': '#ffffff',
        'dark-text-header': '#e0e0e0',
        'dark-text-secondary': '#b0b0b0',
        'dark-accent': '#61affe',
        'dark-accent-hover': '#7dc0ff',
        'dark-success': '#66bb6a',
        'dark-error': '#ef5350',
        'dark-dirty': '#ffa726',

        'light-background': '#f8f9fa',
        'light-primary': '#ffffff',
        'light-secondary': '#f0f2f5',
        'light-border': '#e0e2e6',
        'light-text': '#343a40',
        'light-text-header': '#007bff',
        'light-text-secondary': '#6c757d',
        'light-accent': '#007bff',
        'light-accent-hover': '#0069d9',
        'light-success': '#28a745',
        'light-error': '#dc3545',
        'light-dirty': '#ffc107',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['Consolas', 'Menlo', 'monospace'],
      },
      transitionProperty: {
        'height': 'height',
      }
    },
  },
  plugins: [],
}
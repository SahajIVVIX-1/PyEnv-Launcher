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
        // New Dark Theme Palette (desaturated blues/greys)
        'dark-bg': '#111827', // Almost black, deep blue
        'dark-primary': '#1F2937', // Card backgrounds
        'dark-secondary': '#374151', // Inputs, hover states
        'dark-border': '#4B5563', // Borders, dividers
        'dark-text-primary': '#F9FAFB', // Main text
        'dark-text-secondary': '#D1D5DB', // Softer text
        'dark-text-header': '#E5E7EB', // Section headers
        'dark-accent': '#38BDF8', // Bright blue for highlights
        'dark-accent-hover': '#7DD3FC',
        'dark-success': '#4ADE80',
        'dark-error': '#F87171',
        'dark-dirty': '#FBBF24',

        // Refined Light Theme Palette
        'light-bg': '#F9FAFB', // Page background
        'light-primary': '#FFFFFF', // Card backgrounds
        'light-secondary': '#F3F4F6', // Inputs, hover states
        'light-border': '#E5E7EB', // Borders, dividers
        'light-text-primary': '#1F2937', // Main text
        'light-text-secondary': '#6B7280', // Softer text
        'light-text-header': '#111827', // Section headers
        'light-accent': '#0EA5E9', // Vivid blue
        'light-accent-hover': '#38BDF8',
        'light-success': '#22C55E',
        'light-error': '#EF4444',
        'light-dirty': '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['Consolas', 'Menlo', 'monospace'],
      },
      transitionProperty: {
        'height': 'height',
        'max-height': 'max-height',
      },
      backdropBlur: {
        xs: '2px',
      }
    },
  },
  plugins: [],
}

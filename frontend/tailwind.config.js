/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        besg: {
          50: '#E8F5E9',
          100: '#C8E6C9',
          200: '#A5D6A7',
          300: '#6DB77C',
          400: '#43A257',
          500: '#2E9844',
          600: '#29893D',
          700: '#1B5E20',
          800: '#145218',
          900: '#0D3B11',
        },
        teal: {
          400: '#26C6DA',
          500: '#0bafd0',
          600: '#0897B4',
        },
        surface: {
          DEFAULT: '#FFFFFF',
          secondary: '#F8FAF9',
          tertiary: '#F1F5F2',
          border: '#E2E8E4',
          'border-light': '#EDF0ED',
        },
        txt: {
          primary: '#0A0B0D',
          secondary: '#374151',
          muted: '#6B7280',
          faint: '#9CA3AF',
        },
        blocking: { DEFAULT: '#DC2626', light: '#FEF2F2', ring: '#FECACA' },
        warning: { DEFAULT: '#D97706', light: '#FFFBEB', ring: '#FDE68A' },
        info: { DEFAULT: '#4F46E5', light: '#EEF2FF', ring: '#C7D2FE' },
        success: { DEFAULT: '#059669', light: '#ECFDF5', ring: '#A7F3D0' },
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      animation: {
        'slide-in': 'slideIn 0.3s cubic-bezier(0.16,1,0.3,1)',
        'fade-in': 'fadeIn 0.3s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
        'gradient': 'gradientShift 6s ease infinite',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        gradientShift: {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
    },
  },
  plugins: [],
}

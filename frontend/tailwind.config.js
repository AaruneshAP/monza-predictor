/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: "#00D2BE", // teal — swap for whatever fits your design direction
      },
    },
  },
  plugins: [],
};

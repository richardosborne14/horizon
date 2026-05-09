/** @type {import('tailwindcss').Config} */
export default {
	// Scan all Svelte, HTML, TS and JS files for class usage
	content: ['./src/**/*.{html,js,svelte,ts}'],

	// Dark mode disabled per DESIGN_GUIDE.md — these users won't look for it
	darkMode: 'class',

	theme: {
		extend: {
				// ── Font families (mirror design-tokens.css) ──────────────────────────
			// display → Fraunces (page titles, hero numbers — matches sprint-01 mockup)
			//           DM Serif Display kept as local fallback
			// sans    → DM Sans (all body/UI text)
			// mono    → DM Mono (all financial figures)
			fontFamily: {
				display: ["'Fraunces'", "'DM Serif Display'", 'Georgia', 'serif'],
				sans:    ["'DM Sans'", '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
				mono:    ["'DM Mono'", "'SF Mono'", "'Fira Mono'", 'monospace']
			},

			// ── Colours ───────────────────────────────────────────────────────────
			colors: {
				// Primary — ComCoi Purple (main actions, active states)
				primary: {
					50:  '#F3F1FF',
					100: '#E8E4FF',
					200: '#D4CDFF',
					500: '#6C5CE7',
					600: '#5A4BD4',
					700: '#4839B8'
				},
				// Secondary accent — ComCoi Gold (accents, section markers, logo)
				gold: {
					100: '#FFF8E6',
					300: '#FFE082',
					500: '#D4A843',
					700: '#B8860B'
				},
				// Semantic — financial indicators
				profit:  '#27AE60',
				warning: '#F39C12',
				loss:    '#E74C3C',
				// Neutral surfaces — warm, not cold
				surface: {
					DEFAULT: '#FAFAF8',
					card:    '#FFFFFF',
					hover:   '#F8F7F5',
					warm:    '#F5F3EE'
				},
				// Legacy aliases — prefer primary/gold above in new code
				brand: {
					gold:        '#D4A843',
					'gold-light': '#d9be7a',
					'gold-dark':  '#a8892b',
					navy:         '#1E1B2E',
					'navy-light': '#2D2D4E',
					'navy-dark':  '#0D0D1F'
				}
			},

			// ── Border radius ─────────────────────────────────────────────────────
			borderRadius: {
				DEFAULT: '8px',
				lg:      '12px',
				xl:      '16px',
				'2xl':   '22px',  // hero cards
				'3xl':   '28px'
			},

			// ── Box shadows ───────────────────────────────────────────────────────
			boxShadow: {
				card:       '0 1px 4px rgba(0,0,0,0.06), 0 2px 12px rgba(0,0,0,0.04)',
				'card-hover': '0 4px 20px rgba(0,0,0,0.10)',
				coco:       '0 8px 32px rgba(26,26,46,0.2)',
				sidebar:    '2px 0 16px rgba(0,0,0,0.12)'
			}
		}
	},

	plugins: []
};

/**
 * percentLogic.ts — Pure calculation functions for PercentField and SplitBarField.
 *
 * WHY EXTRACTED: Having the business logic in a separate module lets us unit-test
 * it without mounting Svelte components (no jsdom / @testing-library required).
 * The Svelte components import these helpers; the test files import the same module.
 *
 * All functions work in integer percentages (0–100) internally and return either
 * an integer percent or a fraction depending on what the caller needs.
 */

/**
 * Clamp n to [min, max] and snap to the nearest step.
 *
 * @param n     - Raw integer percentage to clamp
 * @param min   - Minimum allowed percentage (default 0)
 * @param max   - Maximum allowed percentage (default 100)
 * @param step  - Snap step in percent (default 1)
 * @returns     - Clamped, stepped integer percentage
 */
export function clampPct(n: number, min = 0, max = 100, step = 1): number {
	// Snap to step first (round to nearest step), then clamp
	const snapped = Math.round(n / step) * step;
	return Math.max(min, Math.min(max, snapped));
}

/**
 * Parse a raw string entered by the user into a clean integer percentage.
 *
 * Handles:
 *   - Integer percent strings: "10" → 10
 *   - Comma-decimal strings: "0,10" → 10
 *   - Dot-decimal fractions: "0.10" → 10  (heuristic: 0 < n < 1 → multiply by 100)
 *   - Invalid/empty strings: returns `fallback`
 *
 * WHY heuristic: hairdressers sometimes paste the raw fraction from a spreadsheet
 * (0.10). Silently converting avoids a frustrating recalculation cycle.
 *
 * @param raw      - User-entered string
 * @param fallback - Value to return when parsing fails
 * @returns        - Integer percentage in [0, 100] range (unclamped)
 */
export function parseUserPercent(raw: string, fallback: number): number {
	const clean = raw.replace(',', '.');
	const n = parseFloat(clean);
	if (isNaN(n)) return fallback;
	// Heuristic: value strictly between 0 and 1 → user pasted a decimal fraction
	if (n > 0 && n < 1) {
		return Math.round(n * 100);
	}
	return Math.round(n);
}

/**
 * Convert a fraction [0,1] to an integer display percentage.
 *
 * @param fraction - Value in [0, 1]
 * @returns        - Integer percentage 0–100
 */
export function fractionToPercent(fraction: number): number {
	return Math.round(fraction * 100);
}

/**
 * Convert an integer display percentage to a fraction [0,1].
 *
 * @param pct - Integer percentage 0–100
 * @returns   - Fraction in [0, 1]
 */
export function percentToFraction(pct: number): number {
	return pct / 100;
}

/**
 * Determine if a value has been customised from its Eric default.
 *
 * Uses a tolerance of 0.001 (0.1%) to handle floating-point imprecision.
 *
 * @param value        - Current fraction value
 * @param defaultValue - Eric's recommended fraction default
 * @returns            - true if the user has changed the value
 */
export function isCustomised(value: number, defaultValue: number): boolean {
	return Math.abs(value - defaultValue) > 0.001;
}

// ── SplitBarField helpers ─────────────────────────────────────────────────────

/**
 * Given a femmes percentage, compute the hommes complement (always = 100 - femmes).
 * Clamps femmes to [0, 100] first.
 *
 * @param femmes - Proposed integer percentage for women
 * @returns      - { femmes, hommes } both clamped and summing to exactly 100
 */
export function splitFromFemmes(femmes: number): { femmes: number; hommes: number } {
	const f = Math.max(0, Math.min(100, Math.round(femmes)));
	return { femmes: f, hommes: 100 - f };
}

/**
 * Given a hommes percentage, compute the femmes complement.
 * Mirrors splitFromFemmes; drives femmes from the hommes side.
 *
 * @param hommes - Proposed integer percentage for men
 * @returns      - { femmes, hommes } both clamped and summing to exactly 100
 */
export function splitFromHommes(hommes: number): { femmes: number; hommes: number } {
	const h = Math.max(0, Math.min(100, Math.round(hommes)));
	return { femmes: 100 - h, hommes: h };
}

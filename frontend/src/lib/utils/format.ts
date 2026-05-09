/**
 * French locale formatting utilities.
 *
 * All monetary values should be formatted via these helpers — never manually.
 * Uses Intl API with 'fr-FR' locale to get:
 *   - Comma as decimal separator
 *   - Space as thousands separator
 *   - Euro symbol with correct placement
 *
 * IMPORTANT: These are display-only. Financial calculations happen on the backend.
 * Never use JavaScript number for financial computation — display only.
 */

const LOCALE = 'fr-FR';

/**
 * Format a number as French currency (euro).
 *
 * @param value - Numeric value to format
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string e.g. "1 234,56 €"
 *
 * @example
 * formatCurrency(1234.56) // "1 234,56 €"
 * formatCurrency(1000)    // "1 000,00 €"
 */
export function formatCurrency(value: number, decimals: number = 2): string {
	return new Intl.NumberFormat(LOCALE, {
		style: 'currency',
		currency: 'EUR',
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals
	}).format(value);
}

/**
 * Format a plain number with French locale (space thousands, comma decimal).
 *
 * @param value - Numeric value to format
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string e.g. "1 234,56"
 *
 * @example
 * formatNumber(1234.56) // "1 234,56"
 * formatNumber(1234.56, 0) // "1 235"
 */
export function formatNumber(value: number, decimals: number = 2): string {
	return new Intl.NumberFormat(LOCALE, {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals
	}).format(value);
}

/**
 * Format a percentage with French locale.
 *
 * @param value - Decimal value (0.15 = 15%)
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted string e.g. "15,0 %"
 *
 * @example
 * formatPercent(0.15)  // "15,0 %"
 * formatPercent(0.203) // "20,3 %"
 */
export function formatPercent(value: number, decimals: number = 1): string {
	return new Intl.NumberFormat(LOCALE, {
		style: 'percent',
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals
	}).format(value);
}

/**
 * Format a date in long French format.
 *
 * @param date - Date object or ISO string
 * @returns Formatted string e.g. "10 avril 2026"
 *
 * @example
 * formatDate('2026-04-10') // "10 avril 2026"
 * formatDate(new Date())   // "10 avril 2026"
 */
export function formatDate(date: Date | string): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	return new Intl.DateTimeFormat(LOCALE, {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	}).format(d);
}

/**
 * Format a date in short French format.
 *
 * @param date - Date object or ISO string
 * @returns Formatted string e.g. "10/04/2026"
 *
 * @example
 * formatDateShort('2026-04-10') // "10/04/2026"
 */
export function formatDateShort(date: Date | string): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	return new Intl.DateTimeFormat(LOCALE, {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	}).format(d);
}

/**
 * Format a month and year in French (for monthly report headings).
 *
 * @param date - Date object or ISO string
 * @returns Formatted string e.g. "Avril 2026"
 *
 * @example
 * formatMonthYear('2026-04-01') // "Avril 2026"
 */
export function formatMonthYear(date: Date | string): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	const formatted = new Intl.DateTimeFormat(LOCALE, {
		month: 'long',
		year: 'numeric'
	}).format(d);
	// Capitalise first letter
	return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

/**
 * Format a number as a compact euro value using k€ / € notation.
 *
 * Used for large values in the projection table and hero cards.
 *
 * @param value - String or number (from API — Decimal serialised as string)
 * @returns Compact formatted string e.g. "42k€" or "1 234 €"
 *
 * @example
 * fmtK(42000)         // "42k€"
 * fmtK("1234.56")     // "1 234 €"
 * fmtK(123456)        // "123k€"
 */
export function fmtK(value: string | number): string {
	const n = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(n)) return '—';
	if (Math.abs(n) >= 1000) {
		const k = n / 1000;
		// If exactly on the thousand, no decimals; otherwise 1 decimal
		const decimals = k % 1 === 0 ? 0 : 1;
		if (k >= 1000) {
			const m = k / 1000;
			return m.toFixed(1) + 'M€';
		}
		return k.toFixed(decimals) + 'k€';
	}
	return n.toFixed(0) + ' €';
}

/**
 * Format a simple euro value with 0 decimals (for compact display).
 *
 * @param value - String or number
 * @returns Formatted string e.g. "1 234 €"
 */
export function fmt(value: string | number): string {
	const n = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(n)) return '—';
	return new Intl.NumberFormat(LOCALE, {
		minimumFractionDigits: 0,
		maximumFractionDigits: 0
	}).format(n) + ' €';
}

/**
 * Format a percentage from a raw rate (e.g. 0.262 → "26,2 %").
 *
 * @param value - String or number (raw decimal rate)
 * @returns Formatted percentage string
 */
export function fmtPct(value: string | number): string {
	const n = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(n)) return '—';
	return (n * 100).toFixed(1) + ' %';
}
/**
 * Fiscal-year helpers (TASK-2.12.12).
 *
 * Mirrors `backend/app/calculations/fiscal.py`. Used by:
 *   • DuplicateMonthModal — to render fiscal-position month grid
 *   • Bilan / Annee headers — to render "Mars 2025 → Février 2026" range
 *   • Wizard "Voir mon année" redirect — to compute the fiscal-ending year
 *     for "today"
 *
 * Conventions:
 *   • A fiscal exercise is identified by its FISCAL-ENDING year.
 *     For fiscal_year_start = 1 (calendar / AE) → ending year == calendar year.
 *     For fiscal_year_start = 3 (Mar–Feb)       → 2026 = Mar 2025 → Feb 2026.
 *   • A fiscal POSITION is the 1-indexed month within the exercise (1 = opening).
 */

const MONTH_NAMES_FR = [
	'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
	'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

export interface FiscalCell {
	/** Position within the exercise (1–12). 1 = opening month. */
	position: number;
	/** Calendar year for this cell (e.g. 2025 or 2026). */
	calendarYear: number;
	/** Calendar month 1–12. */
	calendarMonth: number;
	/** Localised month name in French (e.g. "Mars"). */
	monthName: string;
	/** Pre-formatted "Mars 2025" label for headers / chips. */
	label: string;
}

/**
 * Return all 12 (calendar_year, calendar_month) cells for a fiscal exercise.
 *
 * @param fiscalEndingYear  Fiscal-ending year (e.g. 2026).
 * @param fiscalYearStart   Salon's `fiscal_year_start` (1–12). 1 = calendar.
 *
 * @example
 *   getFiscalWindow(2026, 3)
 *   // → [
 *   //     {position: 1, calendarYear: 2025, calendarMonth: 3, monthName: 'Mars', label: 'Mars 2025'},
 *   //     ...
 *   //     {position: 12, calendarYear: 2026, calendarMonth: 2, monthName: 'Février', label: 'Février 2026'},
 *   //   ]
 */
export function getFiscalWindow(
	fiscalEndingYear: number,
	fiscalYearStart: number,
): FiscalCell[] {
	const start = clampStart(fiscalYearStart);
	const cells: FiscalCell[] = [];
	for (let pos = 1; pos <= 12; pos++) {
		// Position 1 = opening month. If fiscal_year_start=3 and ending year=2026,
		// opening month = March 2025; closing = February 2026.
		const offset = pos - 1; // 0..11 from opening month
		const monthIdxFromStart = (start - 1 + offset) % 12; // 0..11 calendar month index
		const calendarMonth = monthIdxFromStart + 1;
		// Years: opening year = endingYear if start === 1, otherwise endingYear - 1.
		// Then increment when we wrap past December.
		let calendarYear = start === 1 ? fiscalEndingYear : fiscalEndingYear - 1;
		// How many full Decembers have we passed since the opening month?
		// Equivalent to: ((start - 1) + offset) >= 12
		if (start - 1 + offset >= 12) {
			calendarYear += 1;
		}
		const monthName = MONTH_NAMES_FR[monthIdxFromStart];
		cells.push({
			position: pos,
			calendarYear,
			calendarMonth,
			monthName,
			label: `${monthName} ${calendarYear}`,
		});
	}
	return cells;
}

/**
 * Convert a calendar (year, month) to its fiscal-ending year.
 *
 * @param calendarYear   The calendar year of the month.
 * @param calendarMonth  The calendar month 1–12.
 * @param fiscalYearStart  Salon's `fiscal_year_start`.
 *
 * @example
 *   getFiscalYearFor(2025, 4, 3) // → 2026 (April 2025 sits in fiscal-ending 2026)
 *   getFiscalYearFor(2026, 1, 3) // → 2026 (Jan 2026 still in fiscal-ending 2026)
 *   getFiscalYearFor(2026, 3, 3) // → 2027 (March 2026 opens fiscal-ending 2027)
 */
export function getFiscalYearFor(
	calendarYear: number,
	calendarMonth: number,
	fiscalYearStart: number,
): number {
	const start = clampStart(fiscalYearStart);
	if (start === 1) return calendarYear;
	// Months >= start belong to the exercise that ENDS the following calendar year.
	return calendarMonth >= start ? calendarYear + 1 : calendarYear;
}

/**
 * Convert a calendar (year, month) to its fiscal position 1–12.
 *
 * @returns position (1 = opening month of the exercise).
 */
export function calendarToFiscalPosition(
	calendarYear: number,
	calendarMonth: number,
	fiscalYearStart: number,
): number {
	const start = clampStart(fiscalYearStart);
	// Same logic as backend: ((month - start) mod 12) + 1
	return ((calendarMonth - start + 12) % 12) + 1;
}

/**
 * Format a human-readable label for a fiscal exercise window.
 *
 * @example
 *   formatFiscalRange(2026, 1) // → "2026"          (calendar year)
 *   formatFiscalRange(2026, 3) // → "Mars 2025 → Février 2026"
 */
export function formatFiscalRange(
	fiscalEndingYear: number,
	fiscalYearStart: number,
): string {
	const start = clampStart(fiscalYearStart);
	if (start === 1) return String(fiscalEndingYear);
	const window = getFiscalWindow(fiscalEndingYear, start);
	return `${window[0].label} → ${window[11].label}`;
}

/**
 * Compute the fiscal-ending year that contains "today", given the salon's
 * fiscal start. Used by the wizard CTA "Voir mon année" so the redirect
 * lands on the actual current exercise — not the calendar year.
 */
export function getCurrentFiscalEndingYear(
	fiscalYearStart: number,
	today: Date = new Date(),
): number {
	return getFiscalYearFor(
		today.getFullYear(),
		today.getMonth() + 1,
		fiscalYearStart,
	);
}

/** Coerce nullish/out-of-range values to a safe 1 (calendar year). */
function clampStart(fy: number | null | undefined): number {
	if (!fy || fy < 1 || fy > 12) return 1;
	return Math.trunc(fy);
}

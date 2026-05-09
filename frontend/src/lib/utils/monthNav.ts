/**
 * Month navigation helpers — TASK-2.9.8.5 (Swipeable Year Carousel)
 *
 * Centralised so the mois page, year feed, and any future carousel
 * all use the same boundary logic — no duplicated month arithmetic.
 *
 * WHY a dedicated module: month wrapping (Dec→Jan, Jan→Dec) is a
 * classic off-by-one trap. One well-tested implementation is safer.
 */

/**
 * Returns {year, month} for the previous month.
 * Wraps January of any year back to December of the previous year.
 *
 * @param year  - Current year (e.g. 2026)
 * @param month - Current month 1–12
 * @returns The previous month as {year, month}
 */
export function prevMonth(year: number, month: number): { year: number; month: number } {
	if (month === 1) return { year: year - 1, month: 12 };
	return { year, month: month - 1 };
}

/**
 * Returns {year, month} for the next month.
 * Wraps December of any year forward to January of the next year.
 *
 * @param year  - Current year (e.g. 2026)
 * @param month - Current month 1–12
 * @returns The next month as {year, month}
 */
export function nextMonth(year: number, month: number): { year: number; month: number } {
	if (month === 12) return { year: year + 1, month: 1 };
	return { year, month: month + 1 };
}

/**
 * Can the user navigate backward from the given year/month?
 *
 * Blocks navigation before the salon's first fiscal month (or a
 * sensible floor if fiscalYearStart is not available).
 *
 * @param fiscalYearStart - ISO date "YYYY-MM-DD" (or null → defaults to "2024-01-01")
 * @param year  - The page's current year
 * @param month - The page's current month (1–12)
 * @returns true if backward navigation is permitted
 */
export function canGoBack(
	fiscalYearStart: string | null,
	year: number,
	month: number
): boolean {
	const start = fiscalYearStart ?? '2024-01-01';
	// WHY: parse only the year/month portion — avoid timezone shifts from Date().
	const [fy, fm] = start.split('-').map(Number);
	if (year > fy) return true;
	if (year === fy && month > fm) return true;
	return false;
}

/**
 * Can the user navigate forward from the given year/month?
 *
 * Allows navigation up to December of (today_year + 1).
 *
 * WHY this limit (not today's calendar month):
 *   The year bilan page already allows browsing forecast/typical-month data
 *   up to `today.year + 2` (see YearSummaryBanner). Capping the mois detail
 *   page at today's calendar month was inconsistent — users were blocked from
 *   stepping into months they could already select from the list view.
 *   Setting the ceiling at today_year + 1 (i.e. ~12–24 months ahead) matches
 *   the spirit of the year-page policy while preventing unbounded future nav.
 *   If a month has no report the existing "Créer le rapport" CTA handles it.
 *
 * @param year  - The page's current year
 * @param month - The page's current month (1–12)
 * @param today - Reference date (default: new Date()). Injectable for tests.
 * @returns true if forward navigation is permitted
 */
export function canGoForward(
	year: number,
	month: number,
	today: Date = new Date()
): boolean {
	const maxYear = today.getFullYear() + 1;
	// Allow any month up to and including Dec of maxYear.
	// `month` is always 1–12, so `year <= maxYear` is sufficient.
	return year <= maxYear;
}

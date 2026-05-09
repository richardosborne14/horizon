/**
 * Shared TypeScript types for the Communauté Coiffure frontend.
 *
 * These mirror the Pydantic response schemas from the FastAPI backend.
 * Keep in sync with backend/app/schemas/*.py.
 */

// ── Salary (Task 2.3) ──────────────────────────────────────────────────────────

/**
 * Minimal employee info embedded in a salary row response.
 * Avoids a separate API call when rendering the salary grid.
 */
export interface SalaryEmployeeInfo {
	id: string;
	name: string;
	role_type: 'dirigeant' | 'salarie' | 'apprenti';
}

/**
 * A single monthly salary row as returned by GET .../salaries.
 *
 * salaire_brut: Primary input (gross for salarié, net remuneration for TNS dirigeant).
 * cotisations_sociales: Employer social charges (auto-calc unless charges_overridden=True).
 * total_charge: salaire_brut + cotisations_sociales (always backend-computed).
 * salaire_net_approx: Display-only approximate net take-home. null for TNS dirigeant.
 * charges_overridden: True when user manually edited cotisations_sociales.
 */
export interface SalaryRow {
	id: string;
	monthly_report_id: string;
	employee_id: string;
	employee: SalaryEmployeeInfo;
	salaire_brut: string; // Decimal as string from API
	cotisations_sociales: string;
	total_charge: string;
	salaire_net_approx: string | null;
	charges_overridden: boolean;
	days_worked: number | null;
	ca_realise: string | null;
}

/**
 * Aggregated Section A totals for a monthly report's salary section.
 * total_salaires_charges = the key figure fed into the point mort calculation.
 *
 * pct_ca: total as % of CA (benchmarks: MY France 55%, idéal 40%)
 */
export interface SalaryTotals {
	sous_total_salaires_bruts: string;
	total_cotisations_patronales: string;
	total_salaires_charges: string;
	pct_ca: string | null;
}

/**
 * Full salary section response combining rows + Section A totals.
 */
export interface SalaryListResponse {
	salaries: SalaryRow[];
	totals: SalaryTotals;
}

// ── Monthly Full Point Mort (Task 2.7) ────────────────────────────────────────

/**
 * Full point mort (break-even) calculation for a monthly report.
 * Returned by GET /monthly-reports/{id}/full → point_mort key.
 *
 * All values are Decimal strings from the backend.
 * Section A = total_A (masse salariale chargée)
 * Section B = total_B (achats TTC)
 * total_decaissement = total_AB + remboursement_emprunt = point mort
 * cash_flow = CA − point_mort_dirigeant_inclus
 */
export interface MonthlyFullPointMort {
	total_A: string;
	total_B: string;
	total_AB: string;
	tva_payee_achats: string;
	remboursement_emprunt: string;
	total_decaissement: string;
	point_mort_salon_ttc: string;
	salaire_net_dirigeant: string;
	dirigeant_majore: string;
	point_mort_dirigeant_inclus: string;
	tva_encaissee: string;
	tva_a_payer: string;
	cash_flow: string;
	/**
	 * AE-only: URSSAF cotisations calculated on gross CA.
	 * Always "0" for non-AE users. Included in total_decaissement for AE.
	 * Added in TASK-3.X AE UX overhaul.
	 */
	urssaf_cotisations: string;
	/**
	 * AE-only: effective URSSAF rate applied (e.g. "0.212" = 21.2%).
	 * Always "0" for non-AE users.
	 */
	urssaf_rate: string;
	/**
	 * TASK-2.11.17: AE-only effective minimum personal living cost included in total_decaissement.
	 * Resolved: per-month override ?? salon default ?? 0. Always "0" for non-AE.
	 * Informational line item displayed separately in the point mort breakdown.
	 */
	cout_vie_perso: string;
}

/**
 * Full monthly Atlas (pilotage) response from GET /monthly-reports/{id}/full.
 * Combines report + salary grid + complete point mort in one round-trip.
 */
export interface MonthlyFullResponse {
	report: MonthlyReport;
	salary_totals: SalaryTotals;
	salary_rows: SalaryRow[];
	point_mort: MonthlyFullPointMort;
}

// ── Auth / User ────────────────────────────────────────────────────────────────

/**
 * Public user data as returned by GET /api/users/me.
 * Never includes password_hash or session tokens.
 */
export interface User {
	id: string;
	email: string;
	name: string;
	phone: string | null;
	role: 'user' | 'admin';
	onboarding_completed: boolean;
	/** True after completing the Mon Mois Typique wizard. Controls dashboard mode. */
	has_completed_typical_month: boolean;
	preferred_tools: string[];
	created_at: string;
	last_login_at: string | null;
	/** TASK-2.16.2: Grandfathering flag — null for standard users. */
	legacy_pricing_plan: string | null;
	/**
	 * TASK-2.17.10: Bubble migration tracking fields.
	 * Null for native users who registered directly on Atlas.
	 * 'bubble_migration_2026_05' for users imported from the Bubble platform.
	 */
	import_source: string | null;
	/** Cohort classification: 'imported_active_paying' | 'imported_active_unpaid' | 'imported_lapsed' | 'imported_dormant' | null */
	import_status: string | null;
	/**
	 * First-login wizard step.
	 * 'pending' | 'welcome' | 'legal_form' | 'salon_config' | 'team'
	 * | 'services' | 'savings_hook' | 'done' | 'deferred' | null (native users)
	 */
	import_completion_step: string | null;
}

// ── Salon ──────────────────────────────────────────────────────────────────────

/**
 * Full salon record as returned by the salon CRUD API.
 * Mirrors backend/app/schemas/salon.py SalonResponse.
 * Never includes deleted_at — soft-deleted salons are hidden from the API.
 */
export interface Salon {
	id: string;
	user_id: string;
	name: string;
	business_type: string;
	/** TASK-2.14.2: True when business_type is a legacy statut (currently only EIRL, suppressed 15/02/2022). */
	business_type_legacy: boolean;
	siret: string | null;
	address: string | null;
	ville: string | null;
	code_postal: string | null;
	nb_employees: number;
	versement_liberatoire: boolean;
	acre: boolean;
	fiscal_year_start: number;
	created_at: string;
	/** TASK-2.11.1: Direct contact details per salon for ComCoi team and partner referrals. */
	contact_email: string | null;
	contact_phone: string | null;
}

/**
 * Payload for creating a new salon (POST /api/salons).
 */
export interface SalonCreate {
	name: string;
	business_type: string;
	siret?: string | null;
	address?: string | null;
	ville?: string | null;
	code_postal?: string | null;
	nb_employees?: number;
	versement_liberatoire?: boolean;
	acre?: boolean;
	fiscal_year_start?: number;
}

/**
 * Payload for updating a salon (PUT /api/salons/:id).
 * All fields optional — only send what changed.
 */
export interface SalonUpdate {
	name?: string;
	business_type?: string;
	siret?: string | null;
	address?: string | null;
	ville?: string | null;
	code_postal?: string | null;
	nb_employees?: number;
	versement_liberatoire?: boolean;
	acre?: boolean;
	fiscal_year_start?: number;
}

// ── Employee ───────────────────────────────────────────────────────────────────

/**
 * Employee record as returned by GET /api/salons/:id/employees.
 * Mirrors backend/app/schemas/employee.py EmployeeResponse.
 *
 * Role types:
 *   - dirigeant: Salon owner / travailleur indépendant. No cotisations_patronales.
 *     Point mort uses salary_brut × 1.45.
 *   - salarie: Salaried employee with fiche de paie. cotisations_patronales applies.
 *   - apprenti: Apprentice — same as salarié for MVP.
 */
export interface Employee {
	id: string;
	salon_id: string;
	name: string;
	role_type: 'dirigeant' | 'salarie' | 'apprenti';
	/** cdi | cdd | apprentissage | temps_partiel | tns | assimile_salarie | null */
	contract_type: string | null;
	/**
	 * TASK-2.12.5: Apprenti qualification level.
	 * 'cap' = non-productive (0 billable minutes in Mes Prix).
	 * 'bp' | 'bm' = productive (default taux 0.35).
	 * null = not yet set.
	 */
	contract_subtype: 'cap' | 'bp' | 'bm' | null;
	hours_per_week: number;
	weeks_per_year: number;
	salary_brut: number | null;
	cotisations_patronales: number | null;
	taux_occupation: number;
	is_active: boolean;
	created_at: string;
	/** Computed by backend: salary_brut + cotisations_patronales (or just salary_brut for dirigeant). */
	cout_total_mensuel: number | null;
}

/**
 * Payload for creating an employee (POST /api/salons/:id/employees).
 */
export interface EmployeeCreate {
	name: string;
	role_type: string;
	contract_type?: string | null;
	/** TASK-2.12.5: cap | bp | bm | null */
	contract_subtype?: 'cap' | 'bp' | 'bm' | null;
	hours_per_week: number;
	weeks_per_year?: number;
	salary_brut?: number | null;
	cotisations_patronales?: number | null;
	taux_occupation?: number;
}

/**
 * Payload for updating an employee (PUT /api/salons/:id/employees/:eid).
 * All fields optional.
 */
export interface EmployeeUpdate {
	name?: string;
	role_type?: string;
	contract_type?: string | null;
	/** TASK-2.12.5: cap | bp | bm | null */
	contract_subtype?: 'cap' | 'bp' | 'bm' | null;
	hours_per_week?: number;
	weeks_per_year?: number;
	salary_brut?: number | null;
	cotisations_patronales?: number | null;
	taux_occupation?: number;
}

// ── Tool Definitions (from static-data/tools.json) ────────────────────────────

/**
 * A dashboard tool card definition as returned by GET /api/static-data/tools.
 * The icon field is a Lucide icon name (string) — mapped to a component in ToolCard.svelte.
 */
export interface ToolDefinition {
	id: string;
	label: string;
	description: string;
	icon: string;
	route: string;
	bg: string;
	color: string;
	goals: string[];
}

// ── Monthly Reports & Expenses ────────────────────────────────────────────────

/** Expense category from GET /api/static-data/expense-categories. */
export interface ExpenseCategory {
	id: string;
	name: string;
	i18n_key: string;
	percent_ca_repere: string | null;
	percent_ca_ideal: string | null;
	/** Upper alert ceiling — above this triggers red (Task 2.8.7) */
	percent_ca_seuil_alerte: string | null;
	/** Lower floor — below this is also bad (marketing / EBITDA) (Task 2.8.7) */
	percent_ca_min: string | null;
	description: string | null;
	sort_order: number;
	is_system: boolean;
}

/** Single expense entry (nested inside MonthlyReport). */
export interface Expense {
	id: string;
	monthly_report_id: string;
	category_id: string;
	category: ExpenseCategory;
	amount_ttc: string;
	amount_ht: string | null;
	tva_amount: string | null;
	notes: string | null;
}

/** Computed totals returned with every full MonthlyReportResponse. */
export interface MonthlyReportTotals {
	expense_total_ttc: string;
	expense_total_ht: string;
	tva_payee_achats: string;
	tva_encaissee: string;
	tva_a_payer: string;
	cash_flow: string;
}

/** Full monthly report as returned by GET /salons/:id/monthly-reports/:rid. */
export interface MonthlyReport {
	id: string;
	salon_id: string;
	year: number;
	month: number;
	ca_realise_ttc: string;
	subventions: string;
	/** Monthly loan repayment added to decaissements for point mort (Task 2.7). */
	remboursement_emprunt: string;
	/**
	 * TASK-2.11.17: AE-only per-month minimum vital override.
	 * null = no override set (month uses salon-wide default from salon_config).
	 * Non-null = user has customised this specific month.
	 */
	cout_vie_perso_override: string | null;
	/**
	 * TASK-2.12.11: Structured payslip cost per bulletin TTC.
	 * null = not set yet (savings engine uses 2× ComCoi heuristic).
	 * Non-null = user's real provider cost per bulletin per month.
	 */
	payslip_current_cost_per_bulletin_ttc: string | null;
	/**
	 * TASK-2.12.11: Structured monthly comptable fee TTC.
	 * null = not set yet (savings engine regex-scans expenses then uses 2 000 € average).
	 * Non-null = user's real monthly honoraires to their comptable.
	 */
	honoraires_comptables_ttc: string | null;
	is_duplicate: boolean;
	source_month_id: string | null;
	created_at: string;
	expenses: Expense[];
	totals: MonthlyReportTotals;
}

/** Lightweight monthly report for the year-overview list. */
export interface MonthlyReportSummary {
	id: string;
	year: number;
	month: number;
	ca_realise_ttc: string;
	subventions: string;
	expense_count: number;
	expense_total_ttc: string;
	cash_flow: string;
}

// ── Annual Summary (Task 2.8) ──────────────────────────────────────────────────

/** Per-category annual expense total with benchmark comparison. */
export interface AnnualCategoryTotal {
	category_id: string;
	category_name: string;
	i18n_key: string;
	total_ttc: string;
	pct_ca: string | null;
	percent_ca_repere: string | null;
	percent_ca_ideal: string | null;
	/** Upper alert ceiling — above this triggers red (Task 2.8.7) */
	percent_ca_seuil_alerte: string | null;
	/** Lower floor — below this is also bad (marketing / EBITDA) (Task 2.8.7) */
	percent_ca_min: string | null;
}

/** Single month's headline figures within an annual summary. */
export interface AnnualMonthBreakdown {
	/**
	 * Calendar year this month belongs to.
	 * WHY: for non-calendar fiscal years (e.g. fiscal 2026 = Mar 2025…Feb 2026),
	 * months in the opening half belong to year-1. The frontend uses this to build
	 * correct /pilotage/mois/{year}/{month} deep-links. (Bug fix)
	 */
	year: number;
	month: number;
	report_id: string | null;
	ca_realise_ttc: string;
	expense_total_ttc: string;
	total_salaries: string;
	point_mort: string;
	cash_flow: string;
	has_data: boolean;
	/** Task 2.10.8: true if this month's data was manually entered (vs wizard duplication). */
	is_user_modified: boolean;
	/**
	 * TASK-2.11.17: AE-only effective minimum vital included in point_mort.
	 * Resolved from per-month override → salon default → "0".
	 * Always "0" for non-AE users. Used to show a named hint on year cards.
	 */
	cout_vie_perso: string;
}

/**
 * Full annual financial summary as returned by GET /salons/:id/annual-summary/:year.
 * months always has 12 items (Jan–Dec); has_data=false for months without reports.
 */
export interface AnnualSummaryResponse {
	year: number;
	salon_id: string;
	months: AnnualMonthBreakdown[];
	total_ca: string;
	total_expenses: string;
	total_salaries: string;
	total_point_mort: string;
	total_cash_flow: string;
	months_with_data: number;
	category_totals: AnnualCategoryTotal[];
}

/** Result of a duplicate month operation. */
export interface DuplicateMonthResult {
	created: number;
	skipped: number;
	errors: number;
	created_months: number[];
	skipped_months: number[];
}

// ── Business Types (from static-data/business-types.json) ─────────────────────

/**
 * A legal structure type for a salon.
 * Loaded from the backend static-data endpoint and used in dropdowns.
 */
export interface BusinessType {
	id: string;
	label: string;
	label_short: string;
	description: string;
	tva: boolean;
	charges_type: string;
}

// ── Salon Config (Task 2.6) ────────────────────────────────────────────────────

/**
 * Salon configuration record as returned by GET /api/salons/:id/config.
 * Mirrors backend/app/schemas/salon_config.py SalonConfigResponse.
 *
 * Decimal fields (taux_*, percent_*, montant_*, majoration_*) are returned
 * as strings from the API to preserve precision — convert with Number() for
 * display only. Always send back as numbers in PUT.
 *
 * jours_an and heures_an are server-computed read-only fields.
 */
export interface SalonConfig {
	id: string;
	salon_id: string;
	/** Days open per week */
	jours_ouverture_semaine: string | number;
	/** Weeks open per year */
	semaines_ouverture_an: string | number;
	/** Hours open per day */
	heures_ouverture_jour: string | number;
	/** Computed: jours_semaine × semaines_an (read-only) */
	jours_an: string | null;
	/** Computed: jours_an × heures_jour (read-only) */
	heures_an: string | null;
	/** Legal status of the operator — determines social charge method */
	type_exploitant: 'auto_entrepreneur' | 'tns' | 'assimile_salarie';
	/**
	 * WHY: AE URSSAF rate depends on business activity type.
	 * bic_services (coiffure) = 21.2%, bic_vente = 12.3%, bnc_* = 25.6/23.2%.
	 * Null defaults to bic_services in the backend. Task 3.X AE UX overhaul.
	 */
	ae_activity_type: 'bic_services' | 'bic_vente' | 'bnc_non_reglementee' | 'bnc_cipav' | null;
	/** Whether the salon benefits from ACRE */
	has_acre: boolean;
	/** ISO date string when ACRE started (null if not applicable) */
	acre_start_date: string | null;
	/** Total headcount — affects FNAL and formation tax rates */
	effectif_entreprise: number;
	/** Safety/profit markup fraction applied to cost price (default 0.10) */
	majoration_securite_benefice: string | number;
	/** Share of revenue from product sales (default 0.10) */
	taux_produits: string | number;
	/** Fixed costs as fraction of revenue (default 0.25) */
	taux_charges_fixes: string | number;
	/** Fraction of clientele who are female (default 0.70) */
	percent_clients_f: string | number;
	/** Average spend per female visit in € */
	montant_moyen_f: string | number;
	/** Fraction of clientele who are male (default 0.30) */
	percent_clients_h: string | number;
	/** Average spend per male visit in € */
	montant_moyen_h: string | number;
	/** Average annual visits per female client */
	nb_visites_moyen_f: string | number;
	/** Average annual visits per male client */
	nb_visites_moyen_h: string | number;
	/**
	 * Month (1–12) when the fiscal year starts.
	 * Default 1 (January). AE users are always locked to 1.
	 * Task 2.8.5.
	 */
	fiscal_year_start: number;
	/**
	 * Safety cushion as a fraction of point_mort (default 0.05 = 5%).
	 * Used by the YTD cash-flow alert card. Task 2.8.6.
	 */
	marge_securite_pct: string | number;
	/**
	 * Profit target as a fraction of point_mort (default 0.10 = 10%).
	 * Used by the YTD cash-flow alert card. Task 2.8.6.
	 */
	benefice_cible_pct: string | number;
	updated_at: string;
}

/**
 * Lightweight employee summary for the parametrage page employee table.
 * Returns auto-calculated cout_total_mois using the salon's current config.
 * Mirrors backend/app/schemas/salon_config.py EmployeeConfigSummary.
 */
export interface EmployeeConfigSummary {
	id: string;
	name: string;
	role_type: 'dirigeant' | 'salarie' | 'apprenti';
	hours_per_week: number;
	/** Occupation rate (0.0–1.0) — hours_per_week / 35 */
	taux_occupation: number;
	/** Auto-calculated monthly employer cost as Decimal string */
	cout_total_mois: string;
}

// ── Dashboard Summary (Task 2.5.5) ────────────────────────────────────────────

/**
 * KPI snapshot for the most-recently-created MonthlyReport.
 * Computed on-the-fly from MonthlySalary + Expense rows.
 * Mirrors backend/app/schemas/salon.py DashboardLatestMonth.
 */
export interface DashboardLatestMonth {
	year: number;
	month: number;
	ca_ttc: number;
	point_mort: number;
	resultat_net: number;
	marge_nette_pct: number;
	masse_salariale_pct: number;
}

/**
 * One data point in the monthly trend sparkline (last 6 months).
 * Mirrors backend DashboardMonthTrend.
 */
export interface DashboardMonthTrend {
	year: number;
	month: number;
	resultat_net: number;
	ca_ttc: number;
}

/**
 * Full dashboard summary returned by GET /api/salons/{id}/dashboard-summary.
 *
 * Drives the three dashboard states:
 *   State A: has_typical_month = false  → wizard CTA
 *   State B: has_typical_month = true, months_this_year ≤ 1  → KPIs + tracker
 *   State C: months_this_year >= 3  → trend sparkline + CoCo recommendations
 *
 * Mirrors backend DashboardSummaryResponse.
 */
/**
 * YTD cash-flow alert block returned inside DashboardSummaryResponse.
 * Mirrors backend/app/schemas/salon.py CashFlowAlert. Task 2.8.6.
 *
 * alert_level values:
 *   "on_track"         — profit ≥ full target
 *   "safe_no_profit"   — profit ≥ safety cushion
 *   "above_break_even" — profit ≥ 0 (covers costs, no buffer)
 *   "warning"          — profit slightly negative (within 25% of costs)
 *   "critical"         — profit severely negative (> 25% loss)
 *   "no_data"          — no reports yet this fiscal year
 */
export interface CashFlowAlert {
	fiscal_year: number;
	fiscal_start_month: number;
	months_elapsed: number;
	months_with_data: number;
	cash_flow_ytd: number;
	point_mort_ytd: number;
	target_with_securite_ytd: number;
	target_with_benefice_ytd: number;
	delta_vs_securite: number;
	delta_vs_benefice: number;
	alert_level: 'on_track' | 'safe_no_profit' | 'above_break_even' | 'warning' | 'critical' | 'no_data';
	alert_message: string;
}

// ── Feed sub-types (Task 2.8.11) ──────────────────────────────────────────────

/** Greeting data for the mobile feed header. */
export interface DashboardGreeting {
	first_name: string;
	avatar_initials: string;
}

/** Current-month KPIs for the Hero card. */
export interface DashboardCurrentMonth {
	month_number: number;
	month_name: string;
	year: number;
	ca_realise_ttc: number;
	point_mort: number;
	cash_flow: number;
	status: 'positive' | 'negative';
	/** Task 2.10.8: true if the current-month report was manually edited vs wizard duplication. */
	is_user_modified: boolean;
}

/** Proactive CoCo insight for the feed insight card. */
export interface DashboardCocoInsight {
	id: string;
	message: string;
	source_context: string;
}

/** Nudge card data — shown when current month has no report and day >= 5. */
export interface DashboardMonthToEnter {
	visible: boolean;
	month_name: string;
	day_of_month: number;
}

/** Teaser for the most-recently-published blog post. */
export interface DashboardLatestBlogPost {
	title: string;
	thumbnail_url: string | null;
	minutes_to_read: number;
	slug: string;
}

export interface DashboardSummary {
	has_typical_month: boolean;
	has_year: boolean;
	months_this_year: number;
	has_pricing: boolean;
	latest_month: DashboardLatestMonth | null;
	monthly_trend: DashboardMonthTrend[];
	/** YTD cash-flow alert (null if salon has no fiscal config yet). Task 2.8.6. */
	cash_flow_alert: CashFlowAlert | null;
	/** Feed greeting block (Task 2.8.11). */
	greeting: DashboardGreeting | null;
	/** Current-month hero card data (Task 2.8.11). */
	current_month: DashboardCurrentMonth | null;
	/** Proactive CoCo insight (null until Phase 2 implements it). */
	coco_insight: DashboardCocoInsight | null;
	/** Month-to-enter nudge (Task 2.8.11). */
	month_to_enter: DashboardMonthToEnter | null;
	/** Latest published blog post (Task 2.8.11). */
	latest_blog_post: DashboardLatestBlogPost | null;
	/** True if salon has at least one active employee (Task 2.8.11). */
	has_employees?: boolean;
	/** Task 2.10.8: count of months in current year that have is_user_modified=true. */
	months_ytd_user_modified?: number;
	/** Task 2.10.8: YTD data lineage — "real" | "estimation" | "partial" | null. */
	ytd_lineage?: 'real' | 'estimation' | 'partial' | null;
}


// ── Payslip / Dossier / Contrat (Sprint 2.13) ────────────────────────────────

/** Lightweight employee info from GET /submissions. Mirrors EmployeeInfo schema. */
export interface PayslipEmployeeInfo {
	id: string;
	name: string;
	contract_type: string | null;
	role_type: string;
}

/** Full submission row. Mirrors SubmissionOut schema. */
export interface PayslipSubmission {
	id: string;
	salon_id: string;
	employee_id: string;
	period_month: number;
	period_year: number;
	heures_supplementaires: string | null;
	prime_conventionnelle_pct: string | null;
	ca_services_ht: string | null;
	prime_revente_pct: string | null;
	ca_revente_ht: string | null;
	absence_conges_du: string | null;
	absence_conges_au: string | null;
	absence_maladie_du: string | null;
	absence_maladie_au: string | null;
	absence_injustifiee_du: string | null;
	absence_injustifiee_au: string | null;
	commentaire: string | null;
	status: 'draft' | 'paid_pending_email' | 'emailed' | 'pdf_attached' | 'error';
	subject_token: string | null;
	emailed_at: string | null;
	pdf_url: string | null;
	pdf_attached_at: string | null;
	created_at: string;
	updated_at: string;
}

/** Response from GET /api/salons/{id}/payslip/submissions. */
export interface PayslipSubmissionsResponse {
	dossier_status: 'not_started' | 'paid' | 'active' | 'suspended';
	salaried_employees: PayslipEmployeeInfo[];
	submissions: PayslipSubmission[];
	is_ae: boolean;
}

/** Per-unit and total price display. Mirrors DisplayPrice schema. */
export interface PayslipDisplayPrice {
	ht_eur: string;
	ttc_eur: string;
	framing: 'ht_primary' | 'ttc_primary';
}

/** Response from POST /submissions/intent. */
export interface PayslipIntentResponse {
	client_secret: string;
	payment_intent_id: string;
	submission_ids: string[];
	display_price: PayslipDisplayPrice;
	quantity: number;
	total_ttc_eur: string;
}

/** Response from POST /submissions/confirm. */
export interface PayslipConfirmResponse {
	submissions: Array<{ id: string; status: string; emailed_at: string | null }>;
	message: string;
}

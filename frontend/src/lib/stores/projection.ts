/**
 * Reactive projection data store (TASK-4.3).
 *
 * Holds the current projection response (timeline + summary + scale)
 * so all Runway components subscribe to a single source of truth.
 *
 * Scale changes and goal saves trigger a re-fetch that updates this store.
 */
import { writable } from 'svelte/store';

/** Shape of a single year in the timeline (from the API). */
export interface YearProjection {
	year: number;
	age: number;
	gross_annual: string;
	ae_rate: string;
	charges: string;
	cfe: string;
	base_expenses: string;
	kid_expenses: string;
	pet_expenses: string;
	car_expenses: string;
	tech_expenses: string;
	recurring_expenses: string;
	project_expenses: string;
	project_income: string;
	caf_annual: string;
	tax_credits: string;
	status_bonus: string;
	total_income: string;
	total_outgoing: string;
	net_annual: string;
	year_invested: string;
	year_returns: string;
	total_wealth: string;
	passive_monthly: string;
	total_monthly_income: string;
	goal_reached: boolean;
}

export interface Milestone {
	label: string;
	year: number;
	age: number;
}

export interface GoalYear {
	year: number;
	age: number;
}

export interface ProjectionSummary {
	years: number;
	final_wealth: string;
	final_passive_monthly: string;
	total_invested: string;
	total_returns: string;
	goal_year: GoalYear | null;
	milestones: Milestone[];
}

export interface ProjectionData {
	timeline: YearProjection[];
	summary: ProjectionSummary;
	scale: string;
}

/** The writable store holding the current projection (or null if not yet loaded). */
export const projectionStore = writable<ProjectionData | null>(null);

/** Whether a projection fetch is in progress (subtle loading state). */
export const projectionLoading = writable<boolean>(false);
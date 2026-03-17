/**
 * Shared dropdown/autocomplete option constants used across search pages.
 *
 * Note: different pages use different subsets because the SAM.gov opportunity
 * API and USASpending award API support different set-aside code vocabularies.
 */

export interface SelectOption {
  value: string;
  label: string;
}

/**
 * Set-aside options for opportunity search pages (OpportunitySearchPage,
 * TargetOpportunityPage). These use the SAM.gov opportunity set-aside codes.
 */
export const OPPORTUNITY_SET_ASIDE_OPTIONS: SelectOption[] = [
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: '8(A)', label: '8(a)' },
  { value: 'HUBZone', label: 'HUBZone' },
  { value: 'SDVOSB', label: 'SDVOSB' },
  { value: 'SBA', label: 'Total Small Business' },
];

/**
 * Set-aside options for award search (AwardSearchPage).
 * These use the FPDS/USASpending set-aside codes.
 */
export const AWARD_SET_ASIDE_OPTIONS: SelectOption[] = [
  { value: 'SBA', label: 'Small Business' },
  { value: 'SBP', label: 'Small Business Set-Aside' },
  { value: '8A', label: '8(a)' },
  { value: '8AN', label: '8(a) Sole Source' },
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: 'HZC', label: 'HUBZone' },
  { value: 'SDVOSBC', label: 'SDVOSB' },
];

/**
 * Set-aside options for saved searches. Superset that covers both opportunity
 * and award code vocabularies.
 */
export const SAVED_SEARCH_SET_ASIDE_OPTIONS: SelectOption[] = [
  { value: 'SBA', label: 'Small Business' },
  { value: 'SBP', label: 'Small Business Set-Aside' },
  { value: '8A', label: '8(a)' },
  { value: '8AN', label: '8(a) Sole Source' },
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: 'HZC', label: 'HUBZone' },
  { value: 'SDVOSBS', label: 'SDVOSB Sole Source' },
  { value: 'SDVOSBC', label: 'SDVOSB Competitive' },
];

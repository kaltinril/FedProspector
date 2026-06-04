import { useMemo } from 'react';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';

import { useOrgNaics, useAffiliatedSizeEligibilityForCodes } from '@/queries/useOrganization';
import type { AffiliatedSizeEligibilityResultDto } from '@/types/organization';
import { formatCurrency } from '@/utils/formatters';

/**
 * Formats a size-standard figure for display, honoring SBA size_type. Per the C# DTO,
 * for type 'M' BOTH the threshold and combinedRevenue are expressed in USD *millions*
 * (e.g. 41.5 -> $41.5M), so we scale to raw dollars before compact-currency formatting.
 * For type 'E' the value is an employee headcount rendered as an integer count.
 */
function formatSizeValue(
  value: number | null | undefined,
  type: string | null | undefined,
): string {
  if (value == null) return '--';
  if (type === 'M') {
    return formatCurrency(value * 1_000_000, true);
  }
  return value.toLocaleString();
}

/** Threshold label, size-type aware (employees get a unit suffix; receipts are compact currency). */
function formatThreshold(
  threshold: number | null | undefined,
  type: string | null | undefined,
): string {
  if (threshold == null) return '--';
  if (type === 'E') return `${threshold.toLocaleString()} employees`;
  return formatSizeValue(threshold, type);
}

/** The combined enterprise figure that determined the affiliated verdict, by size_type. */
function combinedFigure(r: AffiliatedSizeEligibilityResultDto): string {
  if (r.sizeType === 'E') return formatSizeValue(r.combinedEmployees, 'E');
  if (r.sizeType === 'M') return formatSizeValue(r.combinedRevenue, 'M');
  // Unknown/null type: show whichever figure the API populated, assuming millions for receipts.
  if (r.combinedRevenue != null) return formatSizeValue(r.combinedRevenue, 'M');
  if (r.combinedEmployees != null) return r.combinedEmployees.toLocaleString();
  return '--';
}

/** A NAICS where the org is small alone but other-than-small once affiliates are summed in. */
function isFlip(r: AffiliatedSizeEligibilityResultDto): boolean {
  // Primary signal is the backend's explicit flag; also catch the general case
  // (small standalone, other-than-small combined) in case the flag ever lags the verdicts.
  if (r.flippedToOtherThanSmall) return true;
  return r.standaloneEligible === true && r.affiliatedEligible === false;
}

/** One detail block per flipping NAICS inside the banner. */
function FlipDetail({ result }: { result: AffiliatedSizeEligibilityResultDto }) {
  return (
    <Box sx={{ mt: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 0.5 }}>
        <Typography variant="subtitle2" component="span">
          NAICS {result.naicsCode}
        </Typography>
        <Chip size="small" color="success" variant="outlined" label="Standalone: Small" />
        <Chip size="small" color="error" label="With affiliates: Other than small" />
      </Box>

      <Typography variant="body2" sx={{ mb: 0.25 }}>
        Combined {result.sizeType === 'E' ? 'employees' : 'receipts'}:{' '}
        <strong>{combinedFigure(result)}</strong> vs threshold{' '}
        <strong>{formatThreshold(result.threshold, result.sizeType)}</strong>
      </Typography>

      {result.reason && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
          {result.reason}
        </Typography>
      )}

      {result.includedAffiliates.length > 0 && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
          Driven by:{' '}
          {result.includedAffiliates
            .map((a) => `${a.uei} (${a.relationship})`)
            .join(', ')}
        </Typography>
      )}

      {result.excludedAffiliates.length > 0 && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
          Excluded:{' '}
          {result.excludedAffiliates
            .map((a) => `${a.uei} (${a.reason === 'APPROVED_MPA' ? 'approved MPA' : 'teaming'})`)
            .join(', ')}
        </Typography>
      )}

      {result.missingAffiliateData.length > 0 && (
        <Tooltip title="These affiliates have no revenue/headcount entered, so the combined total is a lower bound. Enter their figures on the Linked Entities tab.">
          <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mt: 0.5 }}>
            Missing data for {result.missingAffiliateData.length} affiliate(s) — combined total is a
            lower bound, so the real position may be worse.
          </Typography>
        </Tooltip>
      )}
    </Box>
  );
}

/**
 * Phase 133 surfacing fix: evaluate the SBA affiliation roll-up across ALL of the org's
 * registered NAICS — not just the >=80%-of-threshold codes the size-standard monitor view
 * returns — and prominently warn about any NAICS where the org is small standalone but flips
 * to "other than small" once affiliates are combined (13 CFR 121.103). An org that is
 * comfortably small alone (e.g. 30% of threshold) produces no monitor card, so without this
 * banner the dangerous flip would go unsurfaced.
 *
 * Renders nothing when the org has no NAICS, while still loading, or when no NAICS flips, so
 * the existing monitor page content stands unchanged in the common case.
 */
export function AffiliationFlipBanner() {
  const { data: orgNaics } = useOrgNaics();

  const naicsCodes = useMemo(
    () => Array.from(new Set((orgNaics ?? []).map((n) => n.naicsCode).filter(Boolean))),
    [orgNaics],
  );

  const eligibilityQueries = useAffiliatedSizeEligibilityForCodes(naicsCodes);

  const flips = useMemo(
    () =>
      eligibilityQueries
        .map((q) => q.data)
        .filter((d): d is AffiliatedSizeEligibilityResultDto => d != null)
        .filter(isFlip),
    [eligibilityQueries],
  );

  // Nothing alarming to show: no NAICS, or none flip (the page content below stands).
  // We intentionally render nothing during loading to avoid a flash of a transient warning.
  if (naicsCodes.length === 0 || flips.length === 0) return null;

  return (
    <Alert severity="warning" sx={{ mb: 3 }}>
      <AlertTitle>
        Affiliation roll-up flips {flips.length} NAICS code{flips.length !== 1 ? 's' : ''} to
        other-than-small
      </AlertTitle>
      <Typography variant="body2" sx={{ mb: 0.5 }}>
        Your organization is <strong>small on its own</strong> for the code
        {flips.length !== 1 ? 's' : ''} below, but once affiliate receipts/employees are combined
        under 13 CFR 121.103 the enterprise is <strong>other than small</strong>. The combined
        enterprise — not your standalone size — determines your eligibility for these set-asides.
      </Typography>
      <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider', mt: 1 }} />}>
        {flips.map((result) => (
          <FlipDetail key={result.naicsCode} result={result} />
        ))}
      </Stack>
    </Alert>
  );
}

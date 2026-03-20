import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

import PWinGauge from '@/components/shared/PWinGauge';
import { QualificationChecklist } from '@/components/shared/QualificationChecklist';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { getPWin, getQualification } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type { OpportunityDetail } from '@/types/api';

const PWIN_FORMULA = [
  { factor: 'Set-Aside Match', weight: '20%', logic: 'Org certs vs. opp set-aside: exact=100, related=50, none=0, unknown=50' },
  { factor: 'NAICS Experience', weight: '20%', logic: 'Past perf + FPDS contracts in NAICS: >=5=100, >=3=75, >=1=50, 0=10' },
  { factor: 'Competition Level', weight: '15%', logic: 'Distinct vendors in NAICS (3yr): 0-3=100, 4-6=70, 7-10=40, 10+=20' },
  { factor: 'Incumbent Advantage', weight: '15%', logic: 'Is org incumbent: yes=100, no incumbent=70, other incumbent=30' },
  { factor: 'Teaming Strength', weight: '10%', logic: 'Partners with NAICS exp: 3+=100, 1-2=60, 0=30' },
  { factor: 'Time to Respond', weight: '10%', logic: 'Days to deadline: 30+=100, 14-30=70, 7-14=40, <7=10, past=0' },
  { factor: 'Contract Value Fit', weight: '10%', logic: 'Est. value vs. org avg: <=2x=100, 2-5x=60, >5x=30, no history=50' },
];

export default function QualificationPWinTab({ opp }: { opp: OpportunityDetail }) {
  const [explainerOpen, setExplainerOpen] = useState(false);
  const {
    data: pwin,
    isLoading: pwinLoading,
    isError: pwinError,
  } = useQuery({
    queryKey: queryKeys.opportunities.pwin(opp.noticeId),
    queryFn: () => getPWin(opp.noticeId),
    staleTime: 5 * 60 * 1000,
  });

  const {
    data: qual,
    isLoading: qualLoading,
    isError: qualError,
  } = useQuery({
    queryKey: queryKeys.opportunities.qualification(opp.noticeId),
    queryFn: () => getQualification(opp.noticeId),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Box>
      {/* pWin Section */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Win Probability (pWin)
        </Typography>
        {pwinLoading ? (
          <LoadingState message="Calculating win probability..." />
        ) : pwinError || !pwin ? (
          <ErrorState
            title="pWin unavailable"
            message="Could not calculate win probability for this opportunity."
          />
        ) : (
          <Box>
            {/* Top section: gauge + factor breakdown */}
            <Box
              sx={{
                display: 'flex',
                flexDirection: { xs: 'column', md: 'row' },
                gap: 4,
                alignItems: { xs: 'center', md: 'flex-start' },
              }}
            >
              {/* Left: Gauge */}
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 200 }}>
                <PWinGauge score={pwin.score} category={pwin.category} size="large" />
              </Box>

              {/* Right: Factor breakdown */}
              <Box sx={{ flex: 1, width: '100%' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  Score Factors
                </Typography>
                {pwin.factors.map((factor) => (
                  <Box key={factor.name} sx={{ mb: 1.5 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2" fontWeight={500}>
                        {factor.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {factor.score} (wt {Math.round(factor.weight * 100)}%)
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={factor.score}
                      sx={{ height: 8, borderRadius: 1 }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {factor.detail}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>

            {/* Suggestions */}
            {pwin.suggestions.length > 0 && (
              <Alert severity="info" sx={{ mt: 3 }}>
                <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                  Suggestions to improve your score
                </Typography>
                <Box component="ul" sx={{ m: 0, pl: 2 }}>
                  {pwin.suggestions.map((suggestion, idx) => (
                    <li key={idx}>
                      <Typography variant="body2">{suggestion}</Typography>
                    </li>
                  ))}
                </Box>
              </Alert>
            )}

            {/* pWin Explainer (Phase 91-C1) */}
            <Box sx={{ mt: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  cursor: 'pointer',
                  '&:hover': { color: 'primary.main' },
                }}
                onClick={() => setExplainerOpen(!explainerOpen)}
              >
                <HelpOutlineIcon fontSize="small" sx={{ mr: 0.5 }} />
                <Typography variant="body2" color="text.secondary">
                  How is this calculated?
                </Typography>
                <IconButton size="small">
                  <ExpandMoreIcon
                    sx={{
                      transform: explainerOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s',
                    }}
                  />
                </IconButton>
              </Box>
              <Collapse in={explainerOpen}>
                <Paper variant="outlined" sx={{ p: 2, mt: 1 }}>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Win probability (pWin) is calculated using 7 weighted factors. Each factor scores 0-100,
                    then is multiplied by its weight. The total (0-100%) indicates estimated chance of winning.
                  </Typography>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Factor</TableCell>
                        <TableCell align="center">Weight</TableCell>
                        <TableCell>Scoring Logic</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {PWIN_FORMULA.map((row) => (
                        <TableRow key={row.factor}>
                          <TableCell>
                            <Typography variant="body2" fontWeight={500}>{row.factor}</Typography>
                          </TableCell>
                          <TableCell align="center">{row.weight}</TableCell>
                          <TableCell>
                            <Typography variant="caption">{row.logic}</Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    Categories: High (70-100), Medium (40-69), Low (15-39), Very Low (0-14).
                    Scores use all linked entity UEIs (SELF + JV Partners + Teaming Partners) for FPDS and subaward queries.
                  </Typography>
                </Paper>
              </Collapse>
            </Box>
          </Box>
        )}
      </Paper>

      {/* Qualification Section */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Qualification Assessment
        </Typography>
        {qualLoading ? (
          <LoadingState message="Running qualification checks..." />
        ) : qualError || !qual ? (
          <ErrorState
            title="Qualification check unavailable"
            message="Could not run qualification checks for this opportunity."
          />
        ) : (
          <QualificationChecklist
            overallStatus={qual.overallStatus}
            passCount={qual.passCount}
            failCount={qual.failCount}
            warningCount={qual.warningCount}
            checks={qual.checks.map((c) => ({
              name: c.name,
              category: c.category,
              status: c.status,
              detail: c.detail,
              sourceUei: c.sourceUei,
            }))}
          />
        )}
      </Paper>
    </Box>
  );
}

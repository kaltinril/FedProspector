import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';

import PWinGauge from '@/components/shared/PWinGauge';
import { QualificationChecklist } from '@/components/shared/QualificationChecklist';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { getPWin, getQualification } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type { OpportunityDetail } from '@/types/api';

export default function QualificationPWinTab({ opp }: { opp: OpportunityDetail }) {
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
                        {factor.score}/{factor.weight}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={factor.weight > 0 ? (factor.score / factor.weight) * 100 : 0}
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
            }))}
          />
        )}
      </Paper>
    </Box>
  );
}

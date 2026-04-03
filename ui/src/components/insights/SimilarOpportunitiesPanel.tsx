import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

import { useSimilarOpportunities } from '@/queries/useInsights';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type { SimilarOpportunityDto } from '@/types/insights';

function scoreColor(score: number): 'success' | 'warning' | 'error' | 'default' {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  if (score >= 40) return 'default';
  return 'error';
}

interface SimilarOpportunitiesPanelProps {
  noticeId: string;
  maxResults?: number;
  defaultExpanded?: boolean;
}

export function SimilarOpportunitiesPanel({
  noticeId,
  maxResults = 10,
  defaultExpanded = false,
}: SimilarOpportunitiesPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const navigate = useNavigate();

  const { data, isLoading, isError } = useSimilarOpportunities(
    noticeId,
    maxResults,
    expanded,
  );

  const count = data?.length ?? 0;

  return (
    <Paper variant="outlined" sx={{ mb: 3 }}>
      {/* Header - always visible */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
          cursor: 'pointer',
          '&:hover': { bgcolor: 'action.hover' },
          borderRadius: expanded ? '4px 4px 0 0' : 1,
        }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <ContentCopyIcon fontSize="small" color="primary" />
          <Typography variant="subtitle2">More Like This</Typography>
          {!isLoading && count > 0 && (
            <Chip label={count} size="small" color="primary" variant="outlined" />
          )}
        </Box>
        <IconButton size="small" aria-label={expanded ? 'Collapse' : 'Expand'}>
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>

      {/* Content */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          {isLoading && (
            <Box>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} height={60} sx={{ mb: 0.5 }} />
              ))}
            </Box>
          )}

          {isError && (
            <Typography variant="body2" color="error">
              Failed to load similar opportunities.
            </Typography>
          )}

          {!isLoading && !isError && count === 0 && (
            <Typography variant="body2" color="text.secondary">
              No similar opportunities found.
            </Typography>
          )}

          {!isLoading && !isError && data && data.length > 0 && (
            <List disablePadding>
              {data.map((item: SimilarOpportunityDto) => (
                <ListItemButton
                  key={item.matchNoticeId}
                  divider
                  onClick={() =>
                    navigate(
                      `/opportunities/${encodeURIComponent(item.matchNoticeId)}`,
                    )
                  }
                  sx={{ px: 1, py: 1 }}
                >
                  <ListItemText
                    primary={item.matchTitle ?? item.matchNoticeId}
                    secondary={
                      <Box
                        component="span"
                        sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}
                      >
                        {item.matchAgency && (
                          <Typography variant="caption" component="span">
                            {item.matchAgency}
                          </Typography>
                        )}
                        {item.matchNaics && (
                          <Chip
                            label={`NAICS ${item.matchNaics}`}
                            size="small"
                            variant="outlined"
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        )}
                        {item.matchSetAside && (
                          <Chip
                            label={item.matchSetAside}
                            size="small"
                            color="secondary"
                            variant="outlined"
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        )}
                        {item.matchValue != null && (
                          <Typography variant="caption" component="span">
                            {formatCurrency(item.matchValue, true)}
                          </Typography>
                        )}
                        {item.matchPostedDate && (
                          <Typography variant="caption" component="span" color="text.disabled">
                            Posted {formatDate(item.matchPostedDate)}
                          </Typography>
                        )}
                      </Box>
                    }
                    primaryTypographyProps={{
                      variant: 'body2',
                      fontWeight: 500,
                      noWrap: true,
                    }}
                    secondaryTypographyProps={{ component: 'div' as const }}
                  />
                  <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0, alignItems: 'center' }}>
                    {item.similarityFactors && (
                      <Tooltip title={item.similarityFactors} placement="left">
                        <Chip
                          label={`${item.similarityScore}%`}
                          size="small"
                          color={scoreColor(item.similarityScore)}
                        />
                      </Tooltip>
                    )}
                    {!item.similarityFactors && (
                      <Chip
                        label={`${item.similarityScore}%`}
                        size="small"
                        color={scoreColor(item.similarityScore)}
                      />
                    )}
                  </Box>
                </ListItemButton>
              ))}
            </List>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Paper from '@mui/material/Paper';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TodayIcon from '@mui/icons-material/Today';
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addMonths,
  subMonths,
  eachDayOfInterval,
  format,
  isSameMonth,
  isToday,
} from 'date-fns';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { usePipelineCalendar } from '@/queries/usePipeline';
import { formatCurrency } from '@/utils/formatters';
import type { PipelineCalendarEventDto } from '@/types/pipeline';

// ---------------------------------------------------------------------------
// Priority colors
// ---------------------------------------------------------------------------

const PRIORITY_CHIP_COLOR: Record<string, 'error' | 'warning' | 'default' | 'info'> = {
  CRITICAL: 'error',
  HIGH: 'error',
  MEDIUM: 'warning',
  LOW: 'default',
};

// ---------------------------------------------------------------------------
// Weekday header
// ---------------------------------------------------------------------------

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// ---------------------------------------------------------------------------
// PipelineCalendarPage
// ---------------------------------------------------------------------------

export default function PipelineCalendarPage() {
  const navigate = useNavigate();
  const [currentMonth, setCurrentMonth] = useState(() => new Date());

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calendarStart = startOfWeek(monthStart);
  const calendarEnd = endOfWeek(monthEnd);

  const startDate = format(calendarStart, 'yyyy-MM-dd');
  const endDate = format(calendarEnd, 'yyyy-MM-dd');

  const { data: events, isLoading, isError, refetch } = usePipelineCalendar(startDate, endDate);

  const days = useMemo(
    () => eachDayOfInterval({ start: calendarStart, end: calendarEnd }),
    [calendarStart, calendarEnd],
  );

  const eventsByDay = useMemo(() => {
    const map = new Map<string, PipelineCalendarEventDto[]>();
    if (!events) return map;
    for (const event of events) {
      if (!event.responseDeadline) continue;
      const key = format(new Date(event.responseDeadline), 'yyyy-MM-dd');
      const existing = map.get(key) ?? [];
      existing.push(event);
      map.set(key, existing);
    }
    return map;
  }, [events]);

  const handlePrev = () => setCurrentMonth((m) => subMonths(m, 1));
  const handleNext = () => setCurrentMonth((m) => addMonths(m, 1));
  const handleToday = () => setCurrentMonth(new Date());

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  // Build weeks (rows of 7)
  const weeks: Date[][] = [];
  for (let i = 0; i < days.length; i += 7) {
    weeks.push(days.slice(i, i + 7));
  }

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader title="Pipeline Calendar" subtitle="Prospects by response deadline" />

      {/* Month navigation */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton onClick={handlePrev} aria-label="Previous month">
              <ChevronLeftIcon />
            </IconButton>
            <Typography variant="h6" sx={{ minWidth: 180, textAlign: 'center' }}>
              {format(currentMonth, 'MMMM yyyy')}
            </Typography>
            <IconButton onClick={handleNext} aria-label="Next month">
              <ChevronRightIcon />
            </IconButton>
          </Box>
          <IconButton onClick={handleToday} aria-label="Go to today">
            <TodayIcon />
          </IconButton>
        </Box>
      </Paper>

      {/* Calendar grid */}
      <Paper sx={{ overflow: 'hidden' }}>
        {/* Weekday header */}
        <Grid container>
          {WEEKDAYS.map((day) => (
            <Grid
              key={day}
              size={{ xs: 12 / 7 }}
              sx={{
                textAlign: 'center',
                py: 1,
                bgcolor: 'action.hover',
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <Typography variant="caption" fontWeight={600}>
                {day}
              </Typography>
            </Grid>
          ))}
        </Grid>

        {/* Day cells */}
        {weeks.map((week, wIdx) => (
          <Grid container key={wIdx}>
            {week.map((day) => {
              const dayKey = format(day, 'yyyy-MM-dd');
              const dayEvents = eventsByDay.get(dayKey) ?? [];
              const inMonth = isSameMonth(day, currentMonth);
              const today = isToday(day);

              return (
                <Grid
                  key={dayKey}
                  size={{ xs: 12 / 7 }}
                  sx={{
                    minHeight: 100,
                    borderBottom: 1,
                    borderRight: 1,
                    borderColor: 'divider',
                    p: 0.5,
                    bgcolor: today ? 'action.selected' : inMonth ? 'background.paper' : 'action.disabledBackground',
                    opacity: inMonth ? 1 : 0.5,
                  }}
                >
                  <Typography
                    variant="caption"
                    fontWeight={today ? 700 : 400}
                    color={today ? 'primary.main' : 'text.secondary'}
                    sx={{ display: 'block', mb: 0.5 }}
                  >
                    {format(day, 'd')}
                  </Typography>

                  {dayEvents.slice(0, 3).map((event) => (
                    <Tooltip
                      key={event.prospectId}
                      title={`${event.opportunityTitle ?? event.noticeId} - ${event.status}${event.estimatedValue ? ` - ${formatCurrency(event.estimatedValue, true)}` : ''}`}
                      arrow
                    >
                      <Chip
                        label={event.opportunityTitle?.substring(0, 20) ?? event.solicitationNumber ?? event.noticeId.substring(0, 12)}
                        size="small"
                        color={PRIORITY_CHIP_COLOR[event.priority?.toUpperCase() ?? ''] ?? 'info'}
                        variant="outlined"
                        onClick={() => navigate(`/prospects/${event.prospectId}`)}
                        sx={{
                          display: 'block',
                          mb: 0.25,
                          maxWidth: '100%',
                          cursor: 'pointer',
                          '& .MuiChip-label': {
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            display: 'block',
                            fontSize: '0.65rem',
                          },
                        }}
                      />
                    </Tooltip>
                  ))}
                  {dayEvents.length > 3 && (
                    <Typography variant="caption" color="text.secondary">
                      +{dayEvents.length - 3} more
                    </Typography>
                  )}
                </Grid>
              );
            })}
          </Grid>
        ))}
      </Paper>
    </Box>
  );
}

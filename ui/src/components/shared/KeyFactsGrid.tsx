import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

interface KeyFact {
  label: string;
  value: React.ReactNode;
  fullWidth?: boolean;
}

interface KeyFactsGridProps {
  facts: KeyFact[];
  columns?: 2 | 3;
}

export function KeyFactsGrid({ facts, columns = 2 }: KeyFactsGridProps) {
  const visibleFacts = facts.filter((fact) => fact.value != null);

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr',
          md: `repeat(${columns}, 1fr)`,
        },
        gap: 2.5,
      }}
    >
      {visibleFacts.map((fact) => (
        <Box
          key={fact.label}
          sx={{
            gridColumn: fact.fullWidth ? { md: `1 / -1` } : undefined,
          }}
        >
          <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
            {fact.label}
          </Typography>
          <Typography variant="body1" color="text.primary">
            {fact.value}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

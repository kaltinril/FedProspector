import Button from '@mui/material/Button';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';

interface BackToSearchProps {
  searchPath: string;
  label?: string;
}

export function BackToSearch({
  searchPath,
  label = 'Back to search',
}: BackToSearchProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(searchPath);
    }
  };

  return (
    <Button
      startIcon={<ArrowBackIcon />}
      onClick={handleClick}
      size="small"
      sx={{ mb: 2 }}
    >
      {label}
    </Button>
  );
}

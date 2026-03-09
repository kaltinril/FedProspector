import type { ReactNode } from 'react';
import Link from '@mui/material/Link';
import type { SxProps, Theme } from '@mui/material/styles';

interface ExternalLinkProps {
  href: string;
  children: ReactNode;
  sx?: SxProps<Theme>;
}

export function ExternalLink({ href, children, sx }: ExternalLinkProps) {
  return (
    <Link href={href} target="_blank" rel="noopener noreferrer" sx={sx}>
      {children}
    </Link>
  );
}

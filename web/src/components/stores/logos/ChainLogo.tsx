import React from 'react';
import { Store as StoreIcon } from 'lucide-react';
import type { ChainType } from '@/types';
import { CountdownLogo } from './CountdownLogo';
import { NewWorldLogo } from './NewWorldLogo';
import { PaknSaveLogo } from './PaknSaveLogo';

interface ChainLogoProps {
  chain: string;
  className?: string;
  color?: string;
}

/**
 * ChainLogo component - Renders the appropriate logo for a given supermarket chain
 */
export const ChainLogo: React.FC<ChainLogoProps> = ({ chain, className, color }) => {
  const logoComponents: Record<ChainType, React.FC<{ className?: string; color?: string }>> = {
    countdown: CountdownLogo,
    new_world: NewWorldLogo,
    paknsave: PaknSaveLogo,
  };

  const LogoComponent = logoComponents[chain as ChainType];

  if (LogoComponent) {
    return <LogoComponent className={className} color={color} />;
  }

  // Fallback to generic store icon for unknown chains
  return <StoreIcon className={className} style={{ color }} />;
};

export default React.memo(ChainLogo);

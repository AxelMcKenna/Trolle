import { Badge } from '@/components/ui/badge';
import type { ChainType } from '@/types';
import everydayRewardsLogo from '@/assets/logos/everyday_rewards.svg';
import nwClubcardLogo from '@/assets/logos/nw_clubcard.svg';
import paknsaveClubcardLogo from '@/assets/logos/paknsave_clubcard.svg';

const programs: Partial<Record<ChainType, { name: string; logo: string }>> = {
  countdown: { name: 'Everyday Rewards', logo: everydayRewardsLogo },
  new_world: { name: 'Clubcard', logo: nwClubcardLogo },
  paknsave: { name: 'Sticky Club', logo: paknsaveClubcardLogo },
};

interface LoyaltyBadgeProps {
  chain: string;
  className?: string;
}

export const LoyaltyBadge = ({ chain, className }: LoyaltyBadgeProps) => {
  const program = programs[chain as ChainType];
  if (!program) {
    return (
      <Badge variant="outline" className={className}>
        Members
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className={`gap-1 rounded-md ${className ?? ''}`}>
      <img src={program.logo} alt={program.name} className="h-3.5 w-3.5" style={{ objectFit: 'contain' }} />
      {program.name}
    </Badge>
  );
};

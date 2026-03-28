/**
 * Centralized constants for supermarket chains
 */

import type { ChainType } from '@/types';

/**
 * Brand colors for each supermarket chain (hex format)
 */
export const chainColors: Record<ChainType, string> = {
  countdown: '#007837',       // Woolworths green
  new_world: '#e11a2c',       // Brand red
  paknsave: '#ffd600',        // Brand yellow
  mad_butcher: '#d42b1e',     // Mad Butcher red
  prestons: '#1a1a1a',        // Preston's black
};

/**
 * Display names for each supermarket chain
 */
export const chainNames: Record<ChainType, string> = {
  countdown: 'Woolworths',
  new_world: 'New World',
  paknsave: "PAK'nSAVE",
  mad_butcher: 'Mad Butcher',
  prestons: "Preston's",
};

/**
 * Tailwind CSS background color classes for each chain
 */
export const chainColorClasses: Record<ChainType, string> = {
  countdown: 'bg-[#007837]',
  new_world: 'bg-[#e11a2c]',
  paknsave: 'bg-[#ffd600]',
  mad_butcher: 'bg-[#d42b1e]',
  prestons: 'bg-[#1a1a1a]',
};

/**
 * Get the color for a given chain, with fallback
 */
export const getChainColor = (chain: string): string => {
  return chainColors[chain as ChainType] || '#6b7280'; // Gray fallback
};

/**
 * Get the display name for a given chain, with fallback
 */
export const getChainName = (chain: string): string => {
  return chainNames[chain as ChainType] || chain;
};

/**
 * Get the Tailwind class for a given chain, with fallback
 */
export const getChainColorClass = (chain: string): string => {
  return chainColorClasses[chain as ChainType] || 'bg-gray-500';
};

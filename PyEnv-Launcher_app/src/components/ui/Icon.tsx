
import React from 'react';
import { ICONS } from '../../constants';

interface IconProps {
  name: keyof typeof ICONS;
  className?: string;
}

export const Icon: React.FC<IconProps> = ({ name, className = 'w-4 h-4' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {ICONS[name]}
    </svg>
  );
};

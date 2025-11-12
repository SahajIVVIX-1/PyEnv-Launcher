
import React, { useEffect, useState } from 'react';
import { Icon } from './ui/Icon';

interface FooterProps {
  status: { message: string; type: 'success' | 'error' | 'info' } | null;
  isProcessing: boolean;
}

export const Footer: React.FC<FooterProps> = ({ status, isProcessing }) => {
  const [displayStatus, setDisplayStatus] = useState(status);

  useEffect(() => {
    if (status) {
      setDisplayStatus(status);
      const timer = setTimeout(() => {
        setDisplayStatus(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [status]);
  
  const statusClasses = {
      success: 'bg-dark-success text-white',
      error: 'bg-dark-error text-white',
      info: 'bg-dark-accent text-white',
  }
  
  const defaultStatus = 'Welcome! Ready for your next command.';

  return (
    <footer className="relative flex items-center justify-between px-4 py-1 text-xs border-t border-light-border dark:border-dark-border text-light-text-secondary dark:text-dark-text-secondary">
      <div className="absolute top-0 left-0 w-full h-0.5">
          {isProcessing && <div className="h-full bg-dark-accent animate-pulse w-1/3"></div>}
      </div>
      <div className="flex items-center gap-2">
        {isProcessing && <span className="text-dark-accent text-lg leading-none animate-ping">●</span>}
        <div className={`px-2 py-0.5 rounded ${displayStatus ? statusClasses[displayStatus.type] : 'bg-transparent'}`}>
            {displayStatus ? displayStatus.message : defaultStatus}
        </div>
      </div>
      <div className="text-xs">
        v1.0.0-web
      </div>
    </footer>
  );
};

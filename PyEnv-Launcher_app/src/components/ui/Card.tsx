import React from "react";

interface CardProps {
  title?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ title, icon, children, className }) => {
  return (
    <div
      className={`flex flex-col p-4 bg-light-primary dark:bg-dark-secondary/20 rounded-lg border border-light-border dark:border-dark-border/30 ${className}`}
    >
      {title && (
        <div className="flex items-center gap-2 mb-3">
          {icon}
          <h3 className="text-sm font-bold tracking-wider uppercase text-light-text-secondary dark:text-dark-text-secondary">
            {title}
          </h3>
        </div>
      )}
      <div className="flex-grow">{children}</div>
    </div>
  );
};

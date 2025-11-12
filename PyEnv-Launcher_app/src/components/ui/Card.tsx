import React, { useState, useEffect } from "react";
import { Icon } from "./Icon";

interface CardProps {
  title?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

export const Card: React.FC<CardProps> = ({
  title,
  icon,
  children,
  className,
  collapsible = false,
  defaultCollapsed = false,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  useEffect(() => {
    // If you want to persist the collapsed state, you could use localStorage here
  }, [isCollapsed]);

  const handleToggle = () => {
    if (collapsible) {
      setIsCollapsed(!isCollapsed);
    }
  };

  return (
    <div
      className={`flex flex-col bg-light-primary dark:bg-dark-primary rounded-lg border border-light-border dark:border-dark-border transition-all duration-300 ${className}`}
    >
      {title && (
        <div
          className={`flex items-center gap-2 p-3 ${
            collapsible ? "cursor-pointer hover:bg-light-secondary/50 dark:hover:bg-dark-secondary/50" : ""
          }`}
          onClick={handleToggle}
        >
          {icon}
          <h3 className="flex-grow text-sm font-bold tracking-wider uppercase text-light-text-header dark:text-dark-text-header">
            {title}
          </h3>
          {collapsible && (
            <Icon
              name="chevronRight"
              className={`w-4 h-4 text-dark-text-secondary transition-transform duration-300 ${
                !isCollapsed ? "rotate-90" : ""
              }`}
            />
          )}
        </div>
      )}
      <div
        className={`overflow-hidden transition-max-height duration-500 ease-in-out ${
          isCollapsed ? "max-h-0" : "max-h-[1000px]"
        }`}
      >
        <div className="p-4 pt-1">{children}</div>
      </div>
    </div>
  );
};

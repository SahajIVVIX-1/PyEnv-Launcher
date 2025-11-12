import React from "react";
import { Icon } from "./Icon";
import { ICONS } from "../../constants";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: keyof typeof ICONS;
  children?: React.ReactNode;
}

const baseClasses =
  "inline-flex items-center justify-center rounded-md font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-light-primary dark:focus:ring-offset-dark-primary disabled:opacity-50 disabled:pointer-events-none transform hover:scale-105 active:scale-95";

const variantClasses: { [key in ButtonVariant]: string } = {
  primary:
    "bg-light-accent text-white hover:bg-light-accent-hover dark:bg-dark-accent dark:hover:bg-dark-accent-hover focus:ring-light-accent dark:focus:ring-dark-accent",
  secondary:
    "bg-light-secondary text-light-text border border-light-border hover:bg-light-border dark:bg-dark-secondary dark:text-dark-text dark:border-dark-border dark:hover:bg-dark-border focus:ring-light-accent dark:focus:ring-dark-accent",
  danger:
    "bg-light-error text-white hover:bg-opacity-90 dark:bg-dark-error dark:hover:bg-opacity-90 focus:ring-light-error dark:focus:ring-dark-error",
  ghost:
    "hover:bg-light-secondary dark:hover:bg-dark-secondary text-light-text-secondary dark:text-dark-text-secondary",
};

const sizeClasses: { [key in ButtonSize]: string } = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

const iconSizeClasses: { [key in ButtonSize]: string } = {
  sm: "w-3.5 h-3.5",
  md: "w-4 h-4",
  lg: "w-5 h-5",
};

export const Button: React.FC<ButtonProps> = ({
  variant = "secondary",
  size = "md",
  icon,
  children,
  className,
  ...props
}) => {
  return (
    <button className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} {...props}>
      {icon && <Icon name={icon} className={`${iconSizeClasses[size]} ${children ? "mr-2" : ""}`} />}
      {children}
    </button>
  );
};

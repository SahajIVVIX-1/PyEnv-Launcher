import React from "react";

interface FooterProps {
  status: { message: string; type: "success" | "error" | "info" } | null;
  isProcessing: boolean;
}

export const Footer: React.FC<FooterProps> = ({ status, isProcessing }) => {
  const statusClasses = {
    success: "bg-dark-success text-white",
    error: "bg-dark-error text-white",
    info: "bg-dark-accent text-white",
  };

  const defaultStatus = "Welcome! Ready for your next command.";

  return (
    <footer className="relative flex items-center justify-between px-4 py-1 text-xs border-t border-light-border dark:border-dark-border text-light-text-secondary dark:text-dark-text-secondary">
      <div className="absolute top-0 left-0 w-full h-0.5">
        {isProcessing && <div className="h-full bg-dark-accent animate-pulse w-1/3 rounded-r-full"></div>}
      </div>
      <div className="flex items-center gap-2 h-5">
        <div
          className={`transition-all duration-300 px-2 py-0.5 rounded ${
            status ? statusClasses[status.type] : "bg-transparent"
          }`}
        >
          {status ? status.message : defaultStatus}
        </div>
      </div>
      <div className="text-xs">v1.1.0-modern</div>
    </footer>
  );
};

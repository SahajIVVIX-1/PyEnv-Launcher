import React from "react";
import { Theme } from "../types";
import { Icon } from "./ui/Icon";
import { Button } from "./ui/Button";

interface HeaderProps {
  theme: Theme;
  toggleTheme: () => void;
}

export const Header: React.FC<HeaderProps> = ({ theme, toggleTheme }) => {
  return (
    <header className="flex items-center justify-between p-3 border-b border-light-border dark:border-dark-border/50">
      <div className="flex items-center gap-3">
        <Icon name="pyenvLauncherLogo" className="w-8 h-8 text-light-accent dark:text-dark-accent" />
        <h1 className="text-lg font-bold text-light-text-header dark:text-dark-text-header">PyEnv Launcher</h1>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => alert("About dialog placeholder.")} icon="info" />
        <Button variant="ghost" size="sm" onClick={() => alert("Settings dialog placeholder.")} icon="cog" />
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          icon={theme === "dark" ? "sun" : "moon"}
        />
      </div>
    </header>
  );
};

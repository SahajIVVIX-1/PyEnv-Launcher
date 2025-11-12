import React from "react";
import { ProjectData, Venv } from "../types";
import { ProjectWorkspace } from "./ProjectWorkspace";
import { VersionControl } from "./VersionControl";
import { EnvironmentManager } from "./EnvironmentManager";
import { BuildToolsManager } from "./BuildToolsManager";

interface LeftPanelProps {
  projectData: ProjectData | null;
  currentPath: string;
  setCurrentPath: (path: string) => void;
  selectedVenv: Venv | null;
  setSelectedVenv: (venv: Venv) => void;
  onCommit: (message: string) => Promise<void>;
  onSuggestCommitMessage: () => Promise<string>;
  withLoading: <T>(action: string, promise: Promise<T>) => Promise<T>;
  refreshData: () => void;
}

export const LeftPanel: React.FC<LeftPanelProps> = (props) => {
  return (
    <div className="w-1/2 flex flex-col gap-4 overflow-y-auto pr-2 -mr-2">
      <ProjectWorkspace
        currentPath={props.currentPath}
        setCurrentPath={props.setCurrentPath}
        withLoading={props.withLoading}
      />
      {props.projectData?.gitStatus && (
        <VersionControl
          gitStatus={props.projectData.gitStatus}
          onCommit={props.onCommit}
          onSuggestCommitMessage={props.onSuggestCommitMessage}
        />
      )}
      <EnvironmentManager
        venvs={props.projectData?.venvs || []}
        selectedVenv={props.selectedVenv}
        setSelectedVenv={props.setSelectedVenv}
        withLoading={props.withLoading}
        refreshData={props.refreshData}
      />
      {props.projectData?.buildTools && (
        <BuildToolsManager buildTools={props.projectData.buildTools} withLoading={props.withLoading} />
      )}
    </div>
  );
};

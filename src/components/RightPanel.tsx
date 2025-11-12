import React from "react";
import { FileItem } from "../types";
import { FileExplorer } from "./FileExplorer";
import { ActivityLog } from "./ActivityLog";

interface RightPanelProps {
  files: FileItem[];
  currentPath: string;
  logs: string[];
  clearLogs: () => void;
  withLoading: <T>(action: string, promise: Promise<T>) => Promise<T>;
  refreshData: () => void;
}

export const RightPanel: React.FC<RightPanelProps> = (props) => {
  return (
    <div className="w-1/2 flex flex-col gap-4 overflow-hidden">
      <div className="flex flex-col flex-grow min-h-0">
        <FileExplorer
          files={props.files}
          currentPath={props.currentPath}
          withLoading={props.withLoading}
          refreshData={props.refreshData}
        />
      </div>
      <div className="flex flex-col flex-grow min-h-0">
        <ActivityLog logs={props.logs} clearLogs={props.clearLogs} />
      </div>
    </div>
  );
};

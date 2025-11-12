import React, { useState } from "react";
import { FileItem } from "../types";
import { Card } from "./ui/Card";
import { Icon } from "./ui/Icon";
import { Button } from "./ui/Button";
import * as localApiService from "../services/localApiService";

interface FileExplorerProps {
  files: FileItem[];
  currentPath: string;
  withLoading: <T>(action: string, promise: Promise<T>) => Promise<T>;
  refreshData: () => void;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({ files, currentPath, withLoading, refreshData }) => {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const handleNewFile = async () => {
    const name = prompt("Enter new file name:", "new_file.py");
    if (name) {
      await withLoading(`Create file: ${name}`, localApiService.createFile(currentPath, name));
      refreshData();
    }
  };

  const handleNewFolder = async () => {
    const name = prompt("Enter new folder name:", "new_folder");
    if (name) {
      await withLoading(`Create folder: ${name}`, localApiService.createFolder(currentPath, name));
      refreshData();
    }
  };

  const getFileIcon = (file: FileItem): React.ReactNode => {
    if (file.type === "directory") return <Icon name="folder" className="w-4 h-4 text-sky-400" />;
    switch (file.suffix) {
      case ".py":
        return <Icon name="python" className="w-4 h-4 text-green-400" />;
      case ".ipynb":
        return <Icon name="notebook" className="w-4 h-4 text-orange-400" />;
      case ".md":
        return <Icon name="file" className="w-4 h-4 text-indigo-400" />;
      case ".txt":
        return <Icon name="file" className="w-4 h-4 text-gray-400" />;
      default:
        return <Icon name="file" className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <Card title="Directory & Files" icon={<Icon name="folder" className="w-4 h-4" />} className="h-full">
      <div className="flex flex-col h-full">
        <div className="flex gap-2 mb-2">
          <Button size="sm" icon="fileMedical" onClick={handleNewFile}>
            New File
          </Button>
          <Button size="sm" icon="folderPlus" onClick={handleNewFolder}>
            New Folder
          </Button>
          <Button size="sm" icon="play" disabled={!selectedFile || !selectedFile.endsWith(".py")}>
            Run Script
          </Button>
          <Button size="sm" icon="trash" variant="danger" disabled={!selectedFile}>
            Delete
          </Button>
        </div>
        <div className="flex-grow border border-light-border dark:border-dark-border rounded-md overflow-y-auto p-1 bg-light-secondary dark:bg-dark-secondary">
          <ul>
            {files.map((file) => (
              <li
                key={file.name}
                onClick={() => setSelectedFile(file.name)}
                className={`flex items-center gap-2 p-1.5 hover:bg-light-border dark:hover:bg-dark-border rounded-md cursor-pointer text-sm transition-colors duration-100
                                    ${selectedFile === file.name ? "bg-light-accent/20 dark:bg-dark-accent/20" : ""}
                                `}
              >
                {getFileIcon(file)}
                <span>{file.name}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
};

import React, { useState, useEffect, useCallback } from "react";
import { Header } from "./components/Header";
import { LeftPanel } from "./components/LeftPanel";
import { RightPanel } from "./components/RightPanel";
import { Footer } from "./components/Footer";
import { Theme, ProjectData, Venv, GitStatus, FileItem, BuildTools } from "./types";
import * as localApiService from "./services/localApiService";
import * as geminiService from "./services/geminiService";

const App: React.FC = () => {
  const [theme, setTheme] = useState<Theme>((localStorage.getItem("theme") as Theme) || "dark");
  const [currentPath, setCurrentPath] = useState<string>("/Users/developer/projects/customer-churn-analysis");
  const [projectData, setProjectData] = useState<ProjectData | null>(null);
  const [selectedVenv, setSelectedVenv] = useState<Venv | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
  const [runningProcesses, setRunningProcesses] = useState<number>(0);

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prevTheme) => (prevTheme === "dark" ? "light" : "dark"));
  };

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prevLogs) => [...prevLogs, `[${timestamp}] ${message}`]);
  }, []);

  const showStatus = useCallback((message: string, type: "success" | "error" | "info") => {
    setStatus({ message, type });
    setTimeout(() => setStatus(null), 5000);
  }, []);

  const withLoading = useCallback(
    async <T,>(action: string, promise: Promise<T>): Promise<T> => {
      addLog(`Starting: ${action}...`);
      setRunningProcesses((p) => p + 1);
      try {
        const result = await promise;
        addLog(`Finished: ${action} successfully.`);
        showStatus(`${action} completed.`, "success");
        return result;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        addLog(`Error: ${action} failed: ${errorMessage}`);
        showStatus(`Error during ${action}: ${errorMessage}`, "error");
        throw error;
      } finally {
        setRunningProcesses((p) => p - 1);
      }
    },
    [addLog, showStatus]
  );

  const fetchProjectData = useCallback(
    async (path: string) => {
      try {
        const data = await withLoading(`Discover resources for ${path}`, localApiService.getProjectData(path));
        setProjectData(data);
        if (data.venvs.length > 0) {
          setSelectedVenv(data.venvs[0]);
        } else {
          setSelectedVenv(null);
        }
      } catch (e) {
        setProjectData(null);
        setSelectedVenv(null);
      } finally {
        setIsLoading(false);
      }
    },
    [withLoading]
  );

  useEffect(() => {
    fetchProjectData(currentPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPath]);

  const handleCommit = async (message: string) => {
    await withLoading("Git Commit", localApiService.runGitCommit(message));
    fetchProjectData(currentPath);
  };

  const suggestCommitMessage = async (): Promise<string> => {
    return await withLoading(
      "Suggest commit message",
      geminiService.suggestCommitMessage(localApiService.getMockDiff())
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-light-background dark:bg-dark-background text-light-text dark:text-dark-text">
        Loading PyEnv Launcher...
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 flex flex-col">
      <div className="bg-light-primary dark:bg-dark-primary/80 dark:backdrop-blur-sm rounded-xl shadow-2xl flex-grow flex flex-col min-w-[1200px] border border-light-border dark:border-dark-border/50">
        <Header theme={theme} toggleTheme={toggleTheme} />
        <main className="flex-grow flex p-4 pt-2 gap-6 overflow-hidden">
          <LeftPanel
            projectData={projectData}
            currentPath={currentPath}
            setCurrentPath={setCurrentPath}
            selectedVenv={selectedVenv}
            setSelectedVenv={setSelectedVenv}
            onCommit={handleCommit}
            onSuggestCommitMessage={suggestCommitMessage}
            withLoading={withLoading}
            refreshData={() => fetchProjectData(currentPath)}
          />
          <RightPanel
            files={projectData?.files || []}
            currentPath={currentPath}
            logs={logs}
            clearLogs={() => setLogs([])}
            withLoading={withLoading}
            refreshData={() => fetchProjectData(currentPath)}
          />
        </main>
        <Footer status={status} isProcessing={runningProcesses > 0} />
      </div>
    </div>
  );
};

export default App;

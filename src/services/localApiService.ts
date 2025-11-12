
import { ProjectData, FileItem, GitStatus, GitFileStatus, Venv, BuildTools, Package } from '../types';

// --- MOCK DATA ---
const mockFiles: FileItem[] = [
  { name: 'data', type: 'directory' },
  { name: 'notebooks', type: 'directory' },
  { name: 'scripts', type: 'directory' },
  { name: '.gitignore', type: 'file' },
  { name: 'main.py', type: 'file', suffix: '.py' },
  { name: 'README.md', type: 'file', suffix: '.md' },
  { name: 'requirements.txt', type: 'file', suffix: '.txt' },
  { name: 'analysis.ipynb', type: 'file', suffix: '.ipynb' },
];

const mockGitStatus: GitStatus = {
  branch: 'feature/new-ui',
  isDirty: true,
  files: [
    { status: GitFileStatus.Modified, path: 'main.py' },
    { status: GitFileStatus.Untracked, path: 'new_feature.py' },
  ],
  log: [
    { hash: 'a1b2c3d', author: 'Dev Team', date: '2 hours ago', message: 'feat: Add initial project structure' },
    { hash: 'e4f5g6h', author: 'Dev Team', date: '1 day ago', message: 'ci: Configure initial CI pipeline' },
    { hash: 'i7j8k9l', author: 'Dev Team', date: '2 days ago', message: 'docs: Create initial README' },
  ],
};

const mockVenvs: Venv[] = [
  { name: '.venv', type: 'venv', path: '/Users/dev/project/.venv', pythonVersion: '3.10.4' },
  { name: 'data-science-env (conda)', type: 'conda', path: '/Users/dev/miniconda3/envs/data-science-env', pythonVersion: '3.9.7' },
];

const mockBuildTools: BuildTools = {
    hasPoetry: true,
    hasPdm: false,
};

const mockPackages: Package[] = [
    { name: 'pandas', version: '1.4.2', latestVersion: '1.5.0' },
    { name: 'numpy', version: '1.22.3' },
    { name: 'scikit-learn', version: '1.1.1', latestVersion: '1.1.2' },
    { name: 'matplotlib', version: '3.5.2' },
    { name: 'requests', version: '2.28.1' },
];

export const getMockDiff = (): string => {
    return `
diff --git a/main.py b/main.py
index e69de29..9c3c1e3 100644
--- a/main.py
+++ b/main.py
@@ -0,0 +1,5 @@
+import pandas as pd
+
+def process_data(df):
+    # New processing logic
+    return df.dropna()
`;
};

// --- MOCK API FUNCTIONS ---

const simulateDelay = (ms: number = 500) => new Promise(res => setTimeout(res, ms));

export const getProjectData = async (path: string): Promise<ProjectData> => {
  await simulateDelay();
  if (path.includes('empty')) {
      return {
          path,
          files: [],
          gitStatus: null,
          venvs: [],
          buildTools: { hasPoetry: false, hasPdm: false }
      }
  }
  return {
    path,
    files: mockFiles,
    gitStatus: mockGitStatus,
    venvs: mockVenvs,
    buildTools: mockBuildTools,
  };
};

export const getVenvPackages = async (venvName: string): Promise<Package[]> => {
    await simulateDelay(800);
    console.log(`Fetching packages for ${venvName}`);
    return mockPackages;
};

export const runGitCommit = async (message: string): Promise<void> => {
    await simulateDelay(1000);
    console.log(`Committing with message: "${message}"`);
    // In a real scenario, you would update the mock data here
    mockGitStatus.isDirty = false;
    mockGitStatus.files = [];
    mockGitStatus.log.unshift({ hash: 'n3wH4sh', author: 'You', date: 'just now', message });
};

export const createNewProject = async(path: string, name: string): Promise<void> => {
    await simulateDelay();
    console.log(`Creating new project "${name}" at ${path}`);
}

export const createFile = async (path: string, name: string): Promise<void> => {
    await simulateDelay(300);
    console.log(`Creating file ${name} in ${path}`);
    mockFiles.push({ name, type: 'file' });
}

export const createFolder = async (path: string, name: string): Promise<void> => {
    await simulateDelay(300);
    console.log(`Creating folder ${name} in ${path}`);
    mockFiles.unshift({ name, type: 'directory' });
}

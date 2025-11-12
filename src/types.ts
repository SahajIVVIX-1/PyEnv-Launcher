
export type Theme = 'dark' | 'light';

export interface FileItem {
  name: string;
  type: 'file' | 'directory';
  suffix?: string;
}

export enum GitFileStatus {
    Modified = 'M',
    Added = 'A',
    Deleted = 'D',
    Untracked = '??'
}

export interface GitStatus {
  branch: string;
  isDirty: boolean;
  files: { status: GitFileStatus; path: string }[];
  log: { hash: string; author: string; date: string; message: string }[];
}

export interface Venv {
  name: string;
  type: 'venv' | 'conda';
  path: string;
  pythonVersion: string;
}

export interface Package {
    name: string;
    version: string;
    latestVersion?: string;
}

export interface BuildTools {
    hasPoetry: boolean;
    hasPdm: boolean;
}

export interface ProjectData {
  path: string;
  files: FileItem[];
  gitStatus: GitStatus | null;
  venvs: Venv[];
  buildTools: BuildTools;
}

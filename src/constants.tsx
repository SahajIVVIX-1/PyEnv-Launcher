import React from 'react';

export const ICONS: { [key: string]: React.ReactNode } = {
  pyenvLauncherLogo: (
    <>
      <path d="M10 18v-5l-3-3 3-3v5h3v-5l3 3-3 3v5z"></path>
      <path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z"></path>
    </>
  ),
  folder: <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />,
  python: <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"><path d="M12 21a9 9 0 1 0-9-9" /><path d="M10 14a2 2 0 1 0-4 0v-4a2 2 0 1 1 4 0" /><path d="M15 14a2 2 0 1 0-4 0v-4a2 2 0 1 1 4 0" /></g>,
  notebook: <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />,
  file: <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />,
  archive: <path d="M21 8v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8" />,
  image: <path d="m21 12-3.37-3.37a2 2 0 0 0-2.83 0L3 21" />,
  arrowUp: <path d="m5 12 7-7 7 7" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" /></>,
  moon: <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />,
  info: <><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></>,
  cog: <path d="M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" />,
  folderOpen: <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />,
  plusCircle: <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></>,
  externalLink: <><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></>,
  history: <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />,
  gitBranch: <><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></>,
  cloudDownload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></>,
  save: <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />,
  terminal: <><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></>,
  plusSquare: <><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></>,
  trash: <><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></>,
  sync: <path d="M21 12a9 9 0 1 1-6.219-8.56" />,
  arrowUpCircle: <><circle cx="12" cy="12" r="10"/><polyline points="12 8 12 16 16 12 8 12 12 8"/></>,
  minusCircle: <><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></>,
  fileImport: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 12 15 15"/></>,
  fileExport: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="12" x2="12" y2="18"/><polyline points="9 15 12 18 15 15"/></>,
  lock: <><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>,
  bookOpen: <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />,
  tools: <path d="M13.2 2.8 10 6.1l-2.9-3-2.3 2.3 3 2.9-6.1 6.1 2.3 2.3 6.1-6.1 2.9 3 2.3-2.3-3-2.9 3.2-3.3" />,
  list: <><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></>,
  route: <path d="m2 8 9.4-4.2c.6-.3 1.2-.3 1.8 0L22 8" />,
  fileMedical: <><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M12 18v-6"/><path d="M9 15h6"/></>,
  folderPlus: <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />,
  play: <polygon points="5 3 19 12 5 21 5 3"/>,
  broom: <path d="m9.9 2.1 7.4 7.4c.8.8.8 2 0 2.8l-1.2 1.2a2 2 0 0 1-2.8 0L5.9 6.1a2 2 0 0 1 0-2.8l1.2-1.2c.8-.8 2-.8 2.8 0z" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  sparkles: <><path d="M12 3-2 15h10v5l12-12h-10z"/><path d="m22 3-2 15h10v5l12-12h-10z"/></>,
};
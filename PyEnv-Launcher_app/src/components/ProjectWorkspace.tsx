
import React, { useState } from 'react';
import { Card } from './ui/Card';
import { Icon } from './ui/Icon';
import { Button } from './ui/Button';
import * as localApiService from '../services/localApiService';


interface ProjectWorkspaceProps {
    currentPath: string;
    setCurrentPath: (path: string) => void;
    withLoading: <T,>(action: string, promise: Promise<T>) => Promise<T>;
}

export const ProjectWorkspace: React.FC<ProjectWorkspaceProps> = ({ currentPath, setCurrentPath, withLoading }) => {
    const [pathInput, setPathInput] = useState(currentPath);

    const handlePathChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setPathInput(e.target.value);
    };

    const handlePathSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setCurrentPath(pathInput);
    };
    
    const handleNewProject = async () => {
        const name = prompt("Enter new project name:", "new-analysis-project");
        if(name) {
            await withLoading(`Create new project: ${name}`, localApiService.createNewProject(currentPath, name));
            setCurrentPath(`${currentPath}/${name}`);
        }
    };

    return (
        <Card title="Project Workspace" icon={<Icon name="folderOpen" className="w-4 h-4 text-light-text-header dark:text-dark-text-header" />}>
            <div className="flex flex-col gap-2">
                <form onSubmit={handlePathSubmit} className="flex gap-2">
                    <input 
                        type="text"
                        value={pathInput}
                        onChange={handlePathChange}
                        className="flex-grow bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md px-3 py-1.5 text-sm w-full"
                        placeholder="Enter project path..."
                    />
                     <Button type="button" size="sm" icon="history" aria-label="Recent Paths" />
                </form>
                <div className="flex gap-2">
                    <Button onClick={() => setCurrentPath('/Users/developer/projects/sample-project')} size="sm" icon="folderOpen">Select Directory</Button>
                    <Button onClick={handleNewProject} size="sm" icon="plusCircle">New Project</Button>
                    <Button onClick={() => alert('Opening in explorer...')} size="sm" icon="externalLink">Open in Explorer</Button>
                </div>
            </div>
        </Card>
    );
};

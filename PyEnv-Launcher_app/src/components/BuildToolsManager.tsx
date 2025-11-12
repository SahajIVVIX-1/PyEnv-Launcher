
import React from 'react';
import { BuildTools } from '../types';
import { Card } from './ui/Card';
import { Icon } from './ui/Icon';
import { Button } from './ui/Button';

interface BuildToolsManagerProps {
    buildTools: BuildTools;
    withLoading: <T,>(action: string, promise: Promise<T>) => Promise<T>;
}

export const BuildToolsManager: React.FC<BuildToolsManagerProps> = ({ buildTools, withLoading }) => {
    if (!buildTools.hasPdm && !buildTools.hasPoetry) {
        return null;
    }

    return (
        <Card title="Build & Global Tools" icon={<Icon name="tools" className="w-4 h-4 text-light-text-header dark:text-dark-text-header" />}>
            <div className="flex flex-col gap-2">
                 <p className="text-xs text-light-text-secondary dark:text-dark-text-secondary">Project-specific build tools detected:</p>
                <div className="flex gap-2">
                    {buildTools.hasPoetry && (
                        <Button size="sm" onClick={() => withLoading('Poetry Install', new Promise(res => setTimeout(res, 2000)))}>
                            Poetry Install
                        </Button>
                    )}
                    {buildTools.hasPdm && (
                         <Button size="sm" onClick={() => withLoading('PDM Sync', new Promise(res => setTimeout(res, 2000)))}>
                            PDM Sync
                        </Button>
                    )}
                </div>
            </div>
        </Card>
    );
};

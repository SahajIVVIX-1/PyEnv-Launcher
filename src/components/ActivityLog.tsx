
import React, { useRef, useEffect } from 'react';
import { Card } from './ui/Card';
import { Icon } from './ui/Icon';
import { Button } from './ui/Button';

interface ActivityLogProps {
    logs: string[];
    clearLogs: () => void;
}

export const ActivityLog: React.FC<ActivityLogProps> = ({ logs, clearLogs }) => {
    const logContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <Card title="Activity & Logs" icon={<Icon name="list" className="w-4 h-4 text-light-text-header dark:text-dark-text-header" />} className="h-full">
             <div className="flex flex-col h-full">
                <div className="flex justify-end mb-2">
                    <Button size="sm" icon="broom" onClick={clearLogs}>Clear Log</Button>
                </div>
                <div ref={logContainerRef} className="flex-grow bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md p-2 font-mono text-xs overflow-y-auto">
                    {logs.map((log, index) => (
                        <div key={index} className="whitespace-pre-wrap">{log}</div>
                    ))}
                </div>
             </div>
        </Card>
    );
};

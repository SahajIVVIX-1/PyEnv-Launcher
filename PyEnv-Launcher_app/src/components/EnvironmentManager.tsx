
import React, { useState, useEffect } from 'react';
import { Venv, Package } from '../types';
import { Card } from './ui/Card';
import { Icon } from './ui/Icon';
import { Button } from './ui/Button';
import * as localApiService from '../services/localApiService';

interface EnvironmentManagerProps {
    venvs: Venv[];
    selectedVenv: Venv | null;
    setSelectedVenv: (venv: Venv) => void;
    withLoading: <T,>(action: string, promise: Promise<T>) => Promise<T>;
    refreshData: () => void;
}

const PackageTable: React.FC<{ venv: Venv, withLoading: EnvironmentManagerProps['withLoading'], refreshData: () => void }> = ({ venv, withLoading, refreshData }) => {
    const [packages, setPackages] = useState<Package[]>([]);
    const [selectedPackage, setSelectedPackage] = useState<string | null>(null);

    useEffect(() => {
        if(venv) {
            withLoading(`Fetch packages for ${venv.name}`, localApiService.getVenvPackages(venv.name))
                .then(setPackages);
        }
    }, [venv, withLoading]);

    return (
        <div className="space-y-2">
            <div className="flex gap-2">
                <Button size="sm" icon="sync">Check Updates</Button>
                <Button size="sm" icon="arrowUpCircle" disabled={!selectedPackage}>Upgrade Selected</Button>
                <Button size="sm" icon="minusCircle" variant="danger" disabled={!selectedPackage}>Uninstall Selected</Button>
            </div>
            <div className="border border-light-border dark:border-dark-border rounded-md max-h-48 overflow-y-auto text-sm">
                <table className="w-full text-left">
                    <thead className="sticky top-0 bg-light-secondary dark:bg-dark-secondary">
                        <tr>
                            <th className="p-2 font-semibold">Package</th>
                            <th className="p-2 font-semibold">Version</th>
                            <th className="p-2 font-semibold">Latest</th>
                        </tr>
                    </thead>
                    <tbody>
                        {packages.map(p => (
                            <tr 
                                key={p.name}
                                onClick={() => setSelectedPackage(p.name)}
                                className={`cursor-pointer hover:bg-light-border dark:hover:bg-dark-border ${selectedPackage === p.name ? 'bg-light-accent/20 dark:bg-dark-accent/20' : ''}`}
                            >
                                <td className="p-2">{p.name}</td>
                                <td className="p-2">{p.version}</td>
                                <td className={`p-2 ${p.latestVersion ? 'text-dark-dirty' : ''}`}>{p.latestVersion || 'N/A'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export const EnvironmentManager: React.FC<EnvironmentManagerProps> = ({ venvs, selectedVenv, setSelectedVenv, withLoading, refreshData }) => {
    return (
        <Card title="Python Environments" icon={<Icon name="terminal" className="w-4 h-4 text-light-text-header dark:text-dark-text-header" />}>
            <div className="space-y-4">
                {/* Create New Environment */}
                <div className="space-y-2">
                    <div className="flex gap-2">
                        <input type="text" placeholder="Enter new env name (e.g. .venv)" className="flex-grow bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md px-3 py-1.5 text-sm w-full" />
                        <Button variant="primary" size="sm" icon="plusSquare">Create</Button>
                    </div>
                </div>

                {/* Manage Existing Environment */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <label htmlFor="venv-select" className="text-sm font-semibold">Active Environment:</label>
                        <select 
                            id="venv-select"
                            value={selectedVenv?.name || ''}
                            onChange={(e) => {
                                const venv = venvs.find(v => v.name === e.target.value);
                                if (venv) setSelectedVenv(venv);
                            }}
                            className="flex-grow bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md px-3 py-1.5 text-sm"
                        >
                            {venvs.map(v => <option key={v.name} value={v.name}>{v.name}</option>)}
                        </select>
                         <Button variant="ghost" size="sm" icon="trash" aria-label="Delete Environment" />
                    </div>
                    {selectedVenv && (
                        <div className="text-xs text-light-text-secondary dark:text-dark-text-secondary bg-light-secondary dark:bg-dark-secondary p-2 rounded-md">
                            Python Version: {selectedVenv.pythonVersion}
                        </div>
                    )}
                </div>

                {selectedVenv && <PackageTable venv={selectedVenv} withLoading={withLoading} refreshData={refreshData}/>}
                
                <div className="grid grid-cols-2 gap-2">
                    <Button size="sm" icon="fileImport" disabled={!selectedVenv}>Install from File</Button>
                    <Button size="sm" icon="fileExport" disabled={!selectedVenv}>Export to JSON</Button>
                    <Button size="sm" icon="lock" disabled={!selectedVenv}>Freeze to TXT</Button>
                    <Button size="sm" icon="terminal" disabled={!selectedVenv}>Activate Terminal</Button>
                    <Button size="sm" icon="bookOpen" variant="primary" className="col-span-2" disabled={!selectedVenv}>Launch Jupyter</Button>
                </div>

            </div>
        </Card>
    );
};

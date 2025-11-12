
import React, { useState } from 'react';
import { GitStatus } from '../types';
import { Card } from './ui/Card';
import { Icon } from './ui/Icon';
import { Button } from './ui/Button';

interface CommitModalProps {
    isOpen: boolean;
    onClose: () => void;
    onCommit: (message: string) => void;
    onSuggest: () => Promise<string>;
}

const CommitModal: React.FC<CommitModalProps> = ({ isOpen, onClose, onCommit, onSuggest }) => {
    const [message, setMessage] = useState('');
    const [isSuggesting, setIsSuggesting] = useState(false);

    if (!isOpen) return null;

    const handleSuggest = async () => {
        setIsSuggesting(true);
        try {
            const suggestion = await onSuggest();
            setMessage(suggestion);
        } catch (e) {
            // Error is handled by the parent's withLoading wrapper
        } finally {
            setIsSuggesting(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (message.trim()) {
            onCommit(message.trim());
            setMessage('');
            onClose();
        }
    };
    
    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-light-primary dark:bg-dark-primary p-6 rounded-lg shadow-xl w-full max-w-lg">
                <h2 className="text-lg font-bold mb-4 text-light-text-header dark:text-dark-text-header">Git Commit</h2>
                <form onSubmit={handleSubmit}>
                    <textarea 
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="A brief summary of the changes..."
                        className="w-full h-32 bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md p-2 mb-4 text-sm"
                    />
                    <div className="flex justify-between items-center">
                        <Button type="button" onClick={handleSuggest} icon="sparkles" size="sm" disabled={isSuggesting}>
                            {isSuggesting ? 'Suggesting...' : 'Suggest with AI'}
                        </Button>
                        <div className="flex gap-2">
                            <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
                            <Button type="submit" variant="primary">Commit</Button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
};

interface VersionControlProps {
    gitStatus: GitStatus;
    onCommit: (message: string) => Promise<void>;
    onSuggestCommitMessage: () => Promise<string>;
}

export const VersionControl: React.FC<VersionControlProps> = ({ gitStatus, onCommit, onSuggestCommitMessage }) => {
    const [isCommitModalOpen, setCommitModalOpen] = useState(false);

    return (
        <Card title="Version Control" icon={<Icon name="gitBranch" className="w-4 h-4 text-light-text-header dark:text-dark-text-header" />}>
            <div className="space-y-3">
                <div className="bg-light-secondary dark:bg-dark-secondary p-2 rounded-md text-sm">
                    <p>
                        Branch: <span className="font-semibold">{gitStatus.branch}</span>
                        {gitStatus.isDirty ? 
                            <span className="text-dark-dirty ml-2">(dirty)</span> : 
                            <span className="text-dark-success ml-2">(clean)</span>
                        }
                    </p>
                </div>
                <div className="text-xs font-mono bg-light-secondary dark:bg-dark-secondary p-2 rounded-md max-h-24 overflow-y-auto">
                    <p className="font-sans font-bold text-xs mb-1">Recent Commits:</p>
                    {gitStatus.log.map(l => (
                        <div key={l.hash} className="truncate">
                            <span className="text-light-accent dark:text-dark-accent">{l.hash.substring(0, 7)}</span>
                            <span className="text-light-text-secondary dark:text-dark-text-secondary mx-1">-</span>
                            <span>{l.message}</span>
                            <span className="text-light-text-secondary dark:text-dark-text-secondary ml-2">({l.date})</span>
                        </div>
                    ))}
                </div>
                <div className="flex justify-end gap-2">
                    <Button size="sm" icon="cloudDownload">Pull</Button>
                    <Button size="sm" icon="save" onClick={() => setCommitModalOpen(true)} disabled={!gitStatus.isDirty}>Commit</Button>
                </div>
            </div>
            <CommitModal 
                isOpen={isCommitModalOpen} 
                onClose={() => setCommitModalOpen(false)} 
                onCommit={onCommit}
                onSuggest={onSuggestCommitMessage}
            />
        </Card>
    );
};

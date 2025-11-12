import React, { useState, useEffect } from "react";
import { Venv, Package } from "../types";
import { Card } from "./ui/Card";
import { Icon } from "./ui/Icon";
import { Button } from "./ui/Button";
import * as localApiService from "../services/localApiService";

interface EnvironmentManagerProps {
  venvs: Venv[];
  selectedVenv: Venv | null;
  setSelectedVenv: (venv: Venv) => void;
  withLoading: <T>(action: string, promise: Promise<T>) => Promise<T>;
  refreshData: () => void;
}

const PackageTable: React.FC<{
  venv: Venv;
  withLoading: EnvironmentManagerProps["withLoading"];
  refreshData: () => void;
}> = ({ venv, withLoading, refreshData }) => {
  const [packages, setPackages] = useState<Package[]>([]);
  const [selectedPackage, setSelectedPackage] = useState<string | null>(null);

  useEffect(() => {
    if (venv) {
      withLoading(`Fetch packages for ${venv.name}`, localApiService.getVenvPackages(venv.name)).then(setPackages);
    }
  }, [venv, withLoading]);

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Button size="sm" icon="sync">
          Check Updates
        </Button>
        <Button size="sm" icon="arrowUpCircle" disabled={!selectedPackage}>
          Upgrade
        </Button>
        <Button size="sm" icon="minusCircle" variant="danger" disabled={!selectedPackage}>
          Uninstall
        </Button>
      </div>
      <div className="border border-light-border dark:border-dark-border rounded-md max-h-48 overflow-y-auto text-sm">
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-light-secondary dark:bg-dark-secondary/70 backdrop-blur-sm">
            <tr>
              <th className="p-2 font-semibold text-xs uppercase tracking-wider">Package</th>
              <th className="p-2 font-semibold text-xs uppercase tracking-wider">Version</th>
              <th className="p-2 font-semibold text-xs uppercase tracking-wider">Latest</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-light-border dark:divide-dark-border">
            {packages.map((p) => (
              <tr
                key={p.name}
                onClick={() => setSelectedPackage(p.name)}
                className={`cursor-pointer hover:bg-light-secondary dark:hover:bg-dark-secondary ${
                  selectedPackage === p.name ? "bg-light-accent/10 dark:bg-dark-accent/10" : ""
                }`}
              >
                <td
                  className={`p-2 font-medium ${
                    selectedPackage === p.name ? "text-light-accent dark:text-dark-accent" : ""
                  }`}
                >
                  {p.name}
                </td>
                <td className="p-2 text-light-text-secondary dark:text-dark-text-secondary">{p.version}</td>
                <td
                  className={`p-2 font-semibold ${
                    p.latestVersion ? "text-dark-dirty" : "text-light-text-secondary dark:text-dark-text-secondary"
                  }`}
                >
                  {p.latestVersion || "N/A"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const EnvironmentManager: React.FC<EnvironmentManagerProps> = ({
  venvs,
  selectedVenv,
  setSelectedVenv,
  withLoading,
  refreshData,
}) => {
  return (
    <Card
      title="Python Environments"
      icon={<Icon name="terminal" className="w-4 h-4 text-light-text-header dark:text-dark-text-header" />}
      collapsible={true}
      defaultCollapsed={true}
    >
      <div className="space-y-4">
        {/* Create New Environment */}
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Enter new env name (e.g. .venv)"
              className="flex-grow bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md px-3 py-1.5 text-sm w-full focus:ring-2 focus:ring-light-accent dark:focus:ring-dark-accent focus:outline-none transition"
            />
            <Button variant="primary" size="sm" icon="plusSquare">
              Create
            </Button>
          </div>
        </div>

        {/* Manage Existing Environment */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <label
              htmlFor="venv-select"
              className="text-sm font-semibold text-light-text-secondary dark:text-dark-text-secondary"
            >
              Active Environment:
            </label>
            <select
              id="venv-select"
              value={selectedVenv?.name || ""}
              onChange={(e) => {
                const venv = venvs.find((v) => v.name === e.target.value);
                if (venv) setSelectedVenv(venv);
              }}
              className="flex-grow bg-light-secondary dark:bg-dark-secondary border border-light-border dark:border-dark-border rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-light-accent dark:focus:ring-dark-accent focus:outline-none transition"
            >
              {venvs.map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name}
                </option>
              ))}
            </select>
            <Button variant="ghost" size="sm" icon="trash" aria-label="Delete Environment" />
          </div>
          {selectedVenv && (
            <div className="text-xs text-light-text-secondary dark:text-dark-text-secondary bg-light-secondary dark:bg-dark-secondary p-2 rounded-md">
              Python Version:{" "}
              <span className="font-semibold text-light-text-primary dark:text-dark-text-primary">
                {selectedVenv.pythonVersion}
              </span>
            </div>
          )}
        </div>

        {selectedVenv && <PackageTable venv={selectedVenv} withLoading={withLoading} refreshData={refreshData} />}

        <div className="grid grid-cols-2 gap-2">
          <Button size="sm" icon="fileImport" disabled={!selectedVenv}>
            Install from File
          </Button>
          <Button size="sm" icon="fileExport" disabled={!selectedVenv}>
            Export to JSON
          </Button>
          <Button size="sm" icon="lock" disabled={!selectedVenv}>
            Freeze to TXT
          </Button>
          <Button size="sm" icon="terminal" disabled={!selectedVenv}>
            Activate Terminal
          </Button>
          <Button size="sm" icon="bookOpen" variant="primary" className="col-span-2" disabled={!selectedVenv}>
            Launch Jupyter
          </Button>
        </div>
      </div>
    </Card>
  );
};


'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { GitBranch, PlayCircle, CheckCircle, AlertCircle, Download } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface CicdBuilderProps {
  onClose: () => void;
  onSave: () => void;
}

interface Repository {
  id: string;
  name: string;
  owner: string;
}

interface PipelineStep {
  name: string;
  uses?: string;
  run?: string;
  with?: Record<string, any>;
}

interface PipelineJob {
  name: string;
  runsOn: string;
  steps: PipelineStep[];
}

interface CicdConfig {
  name: string;
  description: string;
  repositoryId: string;
  combinedMode: boolean;
  ci: {
    triggers: string[];
    jobs: PipelineJob[];
  };
  cd: {
    environments: string[];
    deploymentJobs: Record<string, PipelineJob>;
  };
}

export function CicdBuilder({ onClose, onSave }: CicdBuilderProps) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [config, setConfig] = useState<CicdConfig>({
    name: '',
    description: '',
    repositoryId: '',
    combinedMode: false,
    ci: {
      triggers: ['push', 'pull_request'],
      jobs: [{
        name: 'test',
        runsOn: 'ubuntu-latest',
        steps: [
          { name: 'Checkout code', uses: 'actions/checkout@v3' },
          { name: 'Setup Node.js', uses: 'actions/setup-node@v3', with: { 'node-version': '18' } },
          { name: 'Install dependencies', run: 'npm ci' },
          { name: 'Run tests', run: 'npm test' }
        ]
      }]
    },
    cd: {
      environments: ['staging', 'production'],
      deploymentJobs: {
        staging: {
          name: 'deploy-staging',
          runsOn: 'ubuntu-latest',
          steps: [
            { name: 'Checkout code', uses: 'actions/checkout@v3' },
            { name: 'Deploy to staging', run: 'npm run deploy:staging' }
          ]
        }
      }
    }
  });

  useEffect(() => {
    fetchRepositories();
  }, []);

  const fetchRepositories = async () => {
    try {
      const response = await fetch('/api/repositories');
      if (response.ok) {
        const data = await response.json();
        setRepositories(data);
      }
    } catch (error) {
      console.error('Error fetching repositories:', error);
    }
  };

  const addJob = (section: 'ci' | 'cd') => {
    if (section === 'ci') {
      setConfig(prev => ({
        ...prev,
        ci: {
          ...prev.ci,
          jobs: [...prev.ci.jobs, {
            name: '',
            runsOn: 'ubuntu-latest',
            steps: [{ name: 'Checkout code', uses: 'actions/checkout@v3' }]
          }]
        }
      }));
    }
  };

  const updateJob = (section: 'ci' | 'cd', jobIndex: number, field: keyof PipelineJob, value: any) => {
    if (section === 'ci') {
      const newJobs = [...config.ci.jobs];
      newJobs[jobIndex] = { ...newJobs[jobIndex], [field]: value };
      setConfig(prev => ({
        ...prev,
        ci: { ...prev.ci, jobs: newJobs }
      }));
    }
  };

  const addStep = (section: 'ci' | 'cd', jobIndex: number) => {
    if (section === 'ci') {
      const newJobs = [...config.ci.jobs];
      newJobs[jobIndex].steps.push({ name: '', run: '' });
      setConfig(prev => ({
        ...prev,
        ci: { ...prev.ci, jobs: newJobs }
      }));
    }
  };

  const updateStep = (section: 'ci' | 'cd', jobIndex: number, stepIndex: number, field: keyof PipelineStep, value: any) => {
    if (section === 'ci') {
      const newJobs = [...config.ci.jobs];
      newJobs[jobIndex].steps[stepIndex] = { ...newJobs[jobIndex].steps[stepIndex], [field]: value };
      setConfig(prev => ({
        ...prev,
        ci: { ...prev.ci, jobs: newJobs }
      }));
    }
  };

  const generateYaml = () => {
    if (config.combinedMode) {
      return `name: ${config.name}

on:
  ${config.ci.triggers.map(trigger => `${trigger}:`).join('\n  ')}

jobs:
${config.ci.jobs.map(job => `
  ${job.name}:
    runs-on: ${job.runsOn}
    steps:
${job.steps.map(step => `
      - name: ${step.name}
        ${step.uses ? `uses: ${step.uses}` : `run: ${step.run || ''}`}
        ${step.with ? `with:\n${Object.entries(step.with).map(([key, value]) => `          ${key}: ${value}`).join('\n')}` : ''}
`).join('')}
`).join('')}

  deploy-staging:
    needs: [${config.ci.jobs.map(job => job.name).join(', ')}]
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: echo "Deploying to staging"

  deploy-production:
    needs: [${config.ci.jobs.map(job => job.name).join(', ')}]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: echo "Deploying to production"
`;
    } else {
      return {
        ci: `name: CI Pipeline

on:
  ${config.ci.triggers.map(trigger => `${trigger}:`).join('\n  ')}

jobs:
${config.ci.jobs.map(job => `
  ${job.name}:
    runs-on: ${job.runsOn}
    steps:
${job.steps.map(step => `
      - name: ${step.name}
        ${step.uses ? `uses: ${step.uses}` : `run: ${step.run || ''}`}
        ${step.with ? `with:\n${Object.entries(step.with).map(([key, value]) => `          ${key}: ${value}`).join('\n')}` : ''}
`).join('')}
`).join('')}`,
        cd: `name: CD Pipeline

on:
  workflow_run:
    workflows: ["CI Pipeline"]
    types: [completed]
    branches: [main, develop]

jobs:
  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: echo "Deploying to staging"

  deploy-production:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: echo "Deploying to production"
`
      };
    }
  };

  const handleSave = async () => {
    try {
      const response = await fetch('/api/pipelines', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: config.name,
          type: config.combinedMode ? 'COMBINED' : 'CI_CD',
          description: config.description,
          repositoryId: config.repositoryId || null,
          config: {
            combinedMode: config.combinedMode,
            ci: config.ci,
            cd: config.cd,
            generatedYaml: generateYaml()
          }
        }),
      });

      if (response.ok) {
        onSave();
        onClose();
      }
    } catch (error) {
      console.error('Error creating CI/CD pipeline:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Basic Info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="name">Pipeline Name</Label>
          <Input
            id="name"
            value={config.name}
            onChange={(e) => setConfig({ ...config, name: e.target.value })}
            placeholder="Full Stack CI/CD Pipeline"
          />
        </div>
        <div>
          <Label htmlFor="repository">Repository</Label>
          <Select value={config.repositoryId} onValueChange={(value) => setConfig({ ...config, repositoryId: value })}>
            <SelectTrigger>
              <SelectValue placeholder="Select repository" />
            </SelectTrigger>
            <SelectContent>
              {repositories.map((repo) => (
                <SelectItem key={repo.id} value={repo.id}>
                  {repo.owner}/{repo.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Input
          id="description"
          value={config.description}
          onChange={(e) => setConfig({ ...config, description: e.target.value })}
          placeholder="Complete CI/CD pipeline for full stack applications"
        />
      </div>

      {/* Combined Mode Toggle */}
      <div className="flex items-center space-x-2">
        <Switch
          id="combined"
          checked={config.combinedMode}
          onCheckedChange={(checked) => setConfig({ ...config, combinedMode: checked })}
        />
        <Label htmlFor="combined">
          Combined CI/CD Pipeline (single .yml file)
        </Label>
      </div>

      <Tabs defaultValue="ci" className="space-y-4">
        <TabsList>
          <TabsTrigger value="ci">Continuous Integration</TabsTrigger>
          <TabsTrigger value="cd">Continuous Deployment</TabsTrigger>
          <TabsTrigger value="preview">Preview YAML</TabsTrigger>
        </TabsList>

        <TabsContent value="ci">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PlayCircle className="h-5 w-5 text-blue-500" />
                CI Configuration
              </CardTitle>
              <CardDescription>Configure your continuous integration pipeline</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Triggers */}
              <div>
                <Label>Triggers</Label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {['push', 'pull_request', 'schedule', 'workflow_dispatch'].map((trigger) => (
                    <Badge
                      key={trigger}
                      variant={config.ci.triggers.includes(trigger) ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        const newTriggers = config.ci.triggers.includes(trigger)
                          ? config.ci.triggers.filter(t => t !== trigger)
                          : [...config.ci.triggers, trigger];
                        setConfig(prev => ({ ...prev, ci: { ...prev.ci, triggers: newTriggers } }));
                      }}
                    >
                      {trigger}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Jobs */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Jobs</Label>
                  <Button variant="outline" size="sm" onClick={() => addJob('ci')}>
                    Add Job
                  </Button>
                </div>

                {config.ci.jobs.map((job, jobIndex) => (
                  <Card key={jobIndex}>
                    <CardHeader>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Job Name</Label>
                          <Input
                            value={job.name}
                            onChange={(e) => updateJob('ci', jobIndex, 'name', e.target.value)}
                            placeholder="test"
                          />
                        </div>
                        <div>
                          <Label>Runs On</Label>
                          <Select value={job.runsOn} onValueChange={(value) => updateJob('ci', jobIndex, 'runsOn', value)}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ubuntu-latest">ubuntu-latest</SelectItem>
                              <SelectItem value="windows-latest">windows-latest</SelectItem>
                              <SelectItem value="macos-latest">macos-latest</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label>Steps</Label>
                          <Button variant="outline" size="sm" onClick={() => addStep('ci', jobIndex)}>
                            Add Step
                          </Button>
                        </div>
                        {job.steps.map((step, stepIndex) => (
                          <div key={stepIndex} className="grid grid-cols-3 gap-2 p-2 border rounded">
                            <Input
                              value={step.name}
                              onChange={(e) => updateStep('ci', jobIndex, stepIndex, 'name', e.target.value)}
                              placeholder="Step name"
                            />
                            <Input
                              value={step.uses || ''}
                              onChange={(e) => updateStep('ci', jobIndex, stepIndex, 'uses', e.target.value)}
                              placeholder="uses: action@version"
                            />
                            <Input
                              value={step.run || ''}
                              onChange={(e) => updateStep('ci', jobIndex, stepIndex, 'run', e.target.value)}
                              placeholder="run: command"
                            />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cd">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                CD Configuration
              </CardTitle>
              <CardDescription>Configure your continuous deployment pipeline</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">CD Configuration</h3>
                <p className="text-muted-foreground mb-4">
                  Deployment configuration will be based on your environments
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {config.cd.environments.map((env) => (
                    <Badge key={env} variant="outline">{env}</Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="preview">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download className="h-5 w-5 text-purple-500" />
                Generated YAML
              </CardTitle>
              <CardDescription>Preview of your pipeline configuration</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-muted p-4 rounded-lg">
                <pre className="text-sm whitespace-pre-wrap overflow-x-auto">
                  {(() => {
                    const yaml = generateYaml();
                    if (typeof yaml === 'string') {
                      return yaml;
                    } else {
                      return `# CI Pipeline (.github/workflows/ci.yml)\n${yaml.ci}\n\n# CD Pipeline (.github/workflows/cd.yml)\n${yaml.cd}`;
                    }
                  })()}
                </pre>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="flex justify-end space-x-2">
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSave}>
          <GitBranch className="h-4 w-4 mr-2" />
          Create CI/CD Pipeline
        </Button>
      </div>
    </div>
  );
}

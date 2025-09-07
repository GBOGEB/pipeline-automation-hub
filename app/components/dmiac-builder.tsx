
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BarChart3, Target, Ruler, Search, TrendingUp, Shield } from 'lucide-react';

interface DmiacBuilderProps {
  onClose: () => void;
  onSave: () => void;
}

interface DmiacPhase {
  objectives: string[];
  tools: string[];
  deliverables: string[];
  description: string;
}

interface DmiacWorkflow {
  name: string;
  description: string;
  repositoryId?: string;
  Define: DmiacPhase;
  Measure: DmiacPhase;
  Analyze: DmiacPhase;
  Improve: DmiacPhase;
  Control: DmiacPhase;
}

export function DmiacBuilder({ onClose, onSave }: DmiacBuilderProps) {
  const [workflow, setWorkflow] = useState<DmiacWorkflow>({
    name: '',
    description: '',
    Define: {
      objectives: [''],
      tools: [''],
      deliverables: [''],
      description: ''
    },
    Measure: {
      objectives: [''],
      tools: [''],
      deliverables: [''],
      description: ''
    },
    Analyze: {
      objectives: [''],
      tools: [''],
      deliverables: [''],
      description: ''
    },
    Improve: {
      objectives: [''],
      tools: [''],
      deliverables: [''],
      description: ''
    },
    Control: {
      objectives: [''],
      tools: [''],
      deliverables: [''],
      description: ''
    }
  });

  const phases = [
    {
      key: 'Define',
      title: 'Define',
      icon: Target,
      color: 'text-blue-500',
      description: 'Define the problem, project goals, and customer requirements'
    },
    {
      key: 'Measure',
      title: 'Measure',
      icon: Ruler,
      color: 'text-green-500',
      description: 'Collect data and establish baseline performance'
    },
    {
      key: 'Analyze',
      title: 'Analyze',
      icon: Search,
      color: 'text-orange-500',
      description: 'Identify root causes and validate with data'
    },
    {
      key: 'Improve',
      title: 'Improve',
      icon: TrendingUp,
      color: 'text-purple-500',
      description: 'Implement solutions and validate improvements'
    },
    {
      key: 'Control',
      title: 'Control',
      icon: Shield,
      color: 'text-red-500',
      description: 'Monitor and sustain the improvements'
    }
  ];

  const updatePhase = (phaseKey: keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>, field: keyof DmiacPhase, value: any) => {
    setWorkflow(prev => ({
      ...prev,
      [phaseKey]: {
        ...prev[phaseKey],
        [field]: value
      }
    }));
  };

  const addArrayItem = (phaseKey: keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>, field: 'objectives' | 'tools' | 'deliverables') => {
    const phase = workflow[phaseKey];
    updatePhase(phaseKey, field, [...phase[field], '']);
  };

  const updateArrayItem = (phaseKey: keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>, field: 'objectives' | 'tools' | 'deliverables', index: number, value: string) => {
    const phase = workflow[phaseKey];
    const newArray = [...phase[field]];
    newArray[index] = value;
    updatePhase(phaseKey, field, newArray);
  };

  const generateAsciiVisualization = () => {
    return `
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ DEFINE  │───▶│ MEASURE │───▶│ ANALYZE │───▶│ IMPROVE │───▶│ CONTROL │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
         │              │              │              │              │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Goals &  │    │Collect  │    │Root     │    │Implement│    │Monitor  │
    │Problems │    │Baseline │    │Cause    │    │Solutions│    │& Sustain│
    │         │    │Data     │    │Analysis │    │         │    │         │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
    `;
  };

  const generateMarkdownExport = () => {
    return `# DMIAC Workflow: ${workflow.name}

## Overview
${workflow.description}

${phases.map(phase => `
## Phase ${phases.indexOf(phase) + 1}: ${phase.title}
${phase.description}

${workflow[phase.key as keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>].description}

### Objectives
${workflow[phase.key as keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>].objectives.filter(obj => obj.trim()).map(obj => `- ${obj}`).join('\n')}

### Tools & Techniques
${workflow[phase.key as keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>].tools.filter(tool => tool.trim()).map(tool => `- ${tool}`).join('\n')}

### Deliverables
${workflow[phase.key as keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>].deliverables.filter(del => del.trim()).map(del => `- ${del}`).join('\n')}
`).join('\n')}
    `;
  };

  const handleSave = async () => {
    try {
      const response = await fetch('/api/pipelines', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: workflow.name,
          type: 'DMIAC',
          description: workflow.description,
          config: {
            phases: {
              Define: workflow.Define,
              Measure: workflow.Measure,
              Analyze: workflow.Analyze,
              Improve: workflow.Improve,
              Control: workflow.Control
            }
          },
          asciiVisualization: generateAsciiVisualization(),
          markdownExport: generateMarkdownExport()
        }),
      });

      if (response.ok) {
        onSave();
        onClose();
      }
    } catch (error) {
      console.error('Error creating DMIAC workflow:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Basic Info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="name">Workflow Name</Label>
          <Input
            id="name"
            value={workflow.name}
            onChange={(e) => setWorkflow({ ...workflow, name: e.target.value })}
            placeholder="Quality Improvement DMIAC"
          />
        </div>
        <div>
          <Label htmlFor="description">Description</Label>
          <Input
            id="description"
            value={workflow.description}
            onChange={(e) => setWorkflow({ ...workflow, description: e.target.value })}
            placeholder="Brief description of the workflow"
          />
        </div>
      </div>

      {/* DMIAC Phases */}
      <div className="space-y-4">
        {phases.map((phase) => {
          const phaseData = workflow[phase.key as keyof Omit<DmiacWorkflow, 'name' | 'description' | 'repositoryId'>];
          
          return (
            <Card key={phase.key}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <phase.icon className={`h-5 w-5 ${phase.color}`} />
                  {phase.title}
                  <Badge variant="outline">{phases.indexOf(phase) + 1}/5</Badge>
                </CardTitle>
                <CardDescription>{phase.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>Phase Description</Label>
                  <Textarea
                    value={phaseData.description}
                    onChange={(e) => updatePhase(phase.key as any, 'description', e.target.value)}
                    placeholder="Describe what happens in this phase"
                    rows={2}
                  />
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label>Objectives</Label>
                    {phaseData.objectives.map((obj, index) => (
                      <Input
                        key={index}
                        value={obj}
                        onChange={(e) => updateArrayItem(phase.key as any, 'objectives', index, e.target.value)}
                        placeholder="Enter objective"
                        className="mt-1"
                      />
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => addArrayItem(phase.key as any, 'objectives')}
                      className="mt-2 w-full"
                    >
                      Add Objective
                    </Button>
                  </div>
                  
                  <div>
                    <Label>Tools & Techniques</Label>
                    {phaseData.tools.map((tool, index) => (
                      <Input
                        key={index}
                        value={tool}
                        onChange={(e) => updateArrayItem(phase.key as any, 'tools', index, e.target.value)}
                        placeholder="Enter tool/technique"
                        className="mt-1"
                      />
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => addArrayItem(phase.key as any, 'tools')}
                      className="mt-2 w-full"
                    >
                      Add Tool
                    </Button>
                  </div>
                  
                  <div>
                    <Label>Deliverables</Label>
                    {phaseData.deliverables.map((deliverable, index) => (
                      <Input
                        key={index}
                        value={deliverable}
                        onChange={(e) => updateArrayItem(phase.key as any, 'deliverables', index, e.target.value)}
                        placeholder="Enter deliverable"
                        className="mt-1"
                      />
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => addArrayItem(phase.key as any, 'deliverables')}
                      className="mt-2 w-full"
                    >
                      Add Deliverable
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Actions */}
      <div className="flex justify-end space-x-2">
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSave}>
          <BarChart3 className="h-4 w-4 mr-2" />
          Create DMIAC Workflow
        </Button>
      </div>
    </div>
  );
}


'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Wrench, Clock, CheckSquare, Star } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface RefactorTemplatesProps {
  onClose: () => void;
  onSave: () => void;
}

interface RefactorTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  template: {
    steps: string[];
    estimatedHours?: number;
    dependencies?: string[];
    checklist?: string[];
  };
  isBuiltIn: boolean;
  usageCount: number;
}

export function RefactorTemplates({ onClose, onSave }: RefactorTemplatesProps) {
  const [templates, setTemplates] = useState<RefactorTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<RefactorTemplate | null>(null);
  const [customTemplate, setCustomTemplate] = useState({
    name: '',
    description: '',
    category: '',
    steps: [''],
    estimatedHours: 8,
    dependencies: [''],
    checklist: ['']
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await fetch('/api/refactor-templates');
      if (response.ok) {
        const data = await response.json();
        setTemplates(data);
      }
    } catch (error) {
      console.error('Error fetching templates:', error);
    } finally {
      setLoading(false);
    }
  };

  const addArrayItem = (field: 'steps' | 'dependencies' | 'checklist') => {
    setCustomTemplate(prev => ({
      ...prev,
      [field]: [...prev[field], '']
    }));
  };

  const updateArrayItem = (field: 'steps' | 'dependencies' | 'checklist', index: number, value: string) => {
    setCustomTemplate(prev => ({
      ...prev,
      [field]: prev[field].map((item, i) => i === index ? value : item)
    }));
  };

  const applyTemplate = (template: RefactorTemplate) => {
    setSelectedTemplate(template);
    setCustomTemplate({
      name: `${template.name} - Custom`,
      description: template.description,
      category: template.category,
      steps: [...template.template.steps, ''],
      estimatedHours: template.template.estimatedHours || 8,
      dependencies: template.template.dependencies ? [...template.template.dependencies, ''] : [''],
      checklist: template.template.checklist ? [...template.template.checklist, ''] : ['']
    });
  };

  const handleSaveTemplate = async () => {
    try {
      const response = await fetch('/api/pipelines', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: customTemplate.name,
          type: 'REFACTOR',
          description: customTemplate.description,
          config: {
            category: customTemplate.category,
            steps: customTemplate.steps.filter(step => step.trim()),
            estimatedHours: customTemplate.estimatedHours,
            dependencies: customTemplate.dependencies.filter(dep => dep.trim()),
            checklist: customTemplate.checklist.filter(item => item.trim())
          },
          isTemplate: true
        }),
      });

      if (response.ok) {
        onSave();
        onClose();
      }
    } catch (error) {
      console.error('Error creating refactor pipeline:', error);
    }
  };

  if (loading) {
    return <div>Loading templates...</div>;
  }

  return (
    <div className="space-y-6">
      <Tabs defaultValue="browse" className="space-y-4">
        <TabsList>
          <TabsTrigger value="browse">Browse Templates</TabsTrigger>
          <TabsTrigger value="create">Create Custom</TabsTrigger>
        </TabsList>

        <TabsContent value="browse">
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold mb-2">Built-in Refactor Templates</h3>
              <p className="text-muted-foreground">
                Choose from pre-built refactoring templates or customize them for your needs
              </p>
            </div>

            <div className="grid gap-4">
              {templates.map((template) => (
                <Card key={template.id} className="cursor-pointer hover:shadow-md transition-shadow">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Wrench className="h-5 w-5 text-orange-500" />
                        <CardTitle className="text-base">{template.name}</CardTitle>
                        {template.isBuiltIn && (
                          <Badge variant="secondary">
                            <Star className="h-3 w-3 mr-1" />
                            Built-in
                          </Badge>
                        )}
                      </div>
                      <Badge variant="outline">{template.category}</Badge>
                    </div>
                    <CardDescription>{template.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <div className="flex items-center space-x-4">
                        <span className="flex items-center">
                          <Clock className="h-3 w-3 mr-1" />
                          {template.template.estimatedHours || 'N/A'}h estimated
                        </span>
                        <span className="flex items-center">
                          <CheckSquare className="h-3 w-3 mr-1" />
                          {template.template.steps.length} steps
                        </span>
                        <span>Used {template.usageCount} times</span>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => applyTemplate(template)}
                      >
                        Use Template
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="create">
          <div className="space-y-4">
            {selectedTemplate && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-700">
                  <strong>Template Applied:</strong> {selectedTemplate.name}
                  <br />
                  You can now customize this template below.
                </p>
              </div>
            )}

            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="templateName">Template Name</Label>
                <Input
                  id="templateName"
                  value={customTemplate.name}
                  onChange={(e) => setCustomTemplate({ ...customTemplate, name: e.target.value })}
                  placeholder="Custom Refactor Template"
                />
              </div>
              <div>
                <Label htmlFor="category">Category</Label>
                <Select value={customTemplate.category} onValueChange={(value) => setCustomTemplate({ ...customTemplate, category: value })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Architecture">Architecture</SelectItem>
                    <SelectItem value="Performance">Performance</SelectItem>
                    <SelectItem value="Modernization">Modernization</SelectItem>
                    <SelectItem value="Security">Security</SelectItem>
                    <SelectItem value="Testing">Testing</SelectItem>
                    <SelectItem value="Database">Database</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="templateDescription">Description</Label>
              <Textarea
                id="templateDescription"
                value={customTemplate.description}
                onChange={(e) => setCustomTemplate({ ...customTemplate, description: e.target.value })}
                placeholder="Describe what this refactor template does"
                rows={2}
              />
            </div>

            <div>
              <Label htmlFor="estimatedHours">Estimated Hours</Label>
              <Input
                id="estimatedHours"
                type="number"
                value={customTemplate.estimatedHours}
                onChange={(e) => setCustomTemplate({ ...customTemplate, estimatedHours: parseInt(e.target.value) || 0 })}
                className="w-32"
              />
            </div>

            {/* Steps */}
            <div>
              <Label>Refactoring Steps</Label>
              <div className="space-y-2 mt-2">
                {customTemplate.steps.map((step, index) => (
                  <Input
                    key={index}
                    value={step}
                    onChange={(e) => updateArrayItem('steps', index, e.target.value)}
                    placeholder={`Step ${index + 1}: Describe the action to take`}
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => addArrayItem('steps')}
                  className="w-full"
                >
                  Add Step
                </Button>
              </div>
            </div>

            {/* Dependencies */}
            <div>
              <Label>Dependencies</Label>
              <div className="space-y-2 mt-2">
                {customTemplate.dependencies.map((dep, index) => (
                  <Input
                    key={index}
                    value={dep}
                    onChange={(e) => updateArrayItem('dependencies', index, e.target.value)}
                    placeholder="Tool, library, or framework required"
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => addArrayItem('dependencies')}
                  className="w-full"
                >
                  Add Dependency
                </Button>
              </div>
            </div>

            {/* Checklist */}
            <div>
              <Label>Success Checklist</Label>
              <div className="space-y-2 mt-2">
                {customTemplate.checklist.map((item, index) => (
                  <Input
                    key={index}
                    value={item}
                    onChange={(e) => updateArrayItem('checklist', index, e.target.value)}
                    placeholder="Success criteria or deliverable"
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => addArrayItem('checklist')}
                  className="w-full"
                >
                  Add Checklist Item
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="flex justify-end space-x-2">
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSaveTemplate}>
          <Wrench className="h-4 w-4 mr-2" />
          Save Refactor Pipeline
        </Button>
      </div>
    </div>
  );
}

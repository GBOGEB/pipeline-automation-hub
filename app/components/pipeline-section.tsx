
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Plus, 
  Workflow, 
  GitBranch, 
  Settings, 
  Play, 
  FileText,
  BarChart3,
  Wrench,
  Eye,
  Download
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DmiacBuilder } from '@/components/dmiac-builder';
import { CicdBuilder } from '@/components/cicd-builder';
import { RefactorTemplates } from '@/components/refactor-templates';

interface Pipeline {
  id: string;
  name: string;
  type: 'CI_CD' | 'DMIAC' | 'REFACTOR' | 'COMBINED';
  description?: string;
  isActive: boolean;
  createdAt: string;
  repository?: {
    name: string;
    owner: string;
  };
  _count?: {
    executions: number;
  };
}

export function PipelineSection() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);

  useEffect(() => {
    fetchPipelines();
  }, []);

  const fetchPipelines = async () => {
    try {
      const response = await fetch('/api/pipelines');
      if (response.ok) {
        const data = await response.json();
        setPipelines(data);
      }
    } catch (error) {
      console.error('Error fetching pipelines:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPipelineTypeIcon = (type: string) => {
    switch (type) {
      case 'CI_CD':
        return <GitBranch className="h-4 w-4" />;
      case 'DMIAC':
        return <BarChart3 className="h-4 w-4" />;
      case 'REFACTOR':
        return <Wrench className="h-4 w-4" />;
      case 'COMBINED':
        return <Workflow className="h-4 w-4" />;
      default:
        return <Workflow className="h-4 w-4" />;
    }
  };

  const getPipelineTypeColor = (type: string) => {
    switch (type) {
      case 'CI_CD':
        return 'text-blue-500';
      case 'DMIAC':
        return 'text-green-500';
      case 'REFACTOR':
        return 'text-orange-500';
      case 'COMBINED':
        return 'text-purple-500';
      default:
        return 'text-gray-500';
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <div className="h-5 w-48 bg-muted rounded animate-pulse" />
              <div className="h-4 w-32 bg-muted rounded animate-pulse" />
            </CardHeader>
            <CardContent>
              <div className="h-4 w-full bg-muted rounded animate-pulse" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Pipeline Management</h2>
          <p className="text-muted-foreground">
            Create and manage DMIAC workflows, CI/CD pipelines, and refactor templates
          </p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700">
              <Plus className="h-4 w-4 mr-2" />
              Create Pipeline
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create New Pipeline</DialogTitle>
              <DialogDescription>
                Choose the type of pipeline you want to create
              </DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="dmiac" className="mt-4">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="dmiac">DMIAC Workflow</TabsTrigger>
                <TabsTrigger value="cicd">CI/CD Pipeline</TabsTrigger>
                <TabsTrigger value="refactor">Refactor Template</TabsTrigger>
              </TabsList>
              <TabsContent value="dmiac">
                <DmiacBuilder onClose={() => setIsCreateDialogOpen(false)} onSave={fetchPipelines} />
              </TabsContent>
              <TabsContent value="cicd">
                <CicdBuilder onClose={() => setIsCreateDialogOpen(false)} onSave={fetchPipelines} />
              </TabsContent>
              <TabsContent value="refactor">
                <RefactorTemplates onClose={() => setIsCreateDialogOpen(false)} onSave={fetchPipelines} />
              </TabsContent>
            </Tabs>
          </DialogContent>
        </Dialog>
      </div>

      {/* Pipeline List */}
      <div className="space-y-4">
        {pipelines.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Workflow className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Pipelines Created</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first pipeline to start automating your workflows
              </p>
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Pipeline
              </Button>
            </CardContent>
          </Card>
        ) : (
          pipelines.map((pipeline, index) => (
            <motion.div
              key={pipeline.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className={`${getPipelineTypeColor(pipeline.type)}`}>
                        {getPipelineTypeIcon(pipeline.type)}
                      </div>
                      <div>
                        <CardTitle className="text-lg">{pipeline.name}</CardTitle>
                        <CardDescription>
                          {pipeline.description}
                          {pipeline.repository && (
                            <>
                              {' • '}
                              {pipeline.repository.owner}/{pipeline.repository.name}
                            </>
                          )}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant="outline">
                        {pipeline.type.replace('_', '/')}
                      </Badge>
                      <Badge variant={pipeline.isActive ? "default" : "secondary"}>
                        {pipeline.isActive ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                      <span>{pipeline._count?.executions || 0} executions</span>
                      <span>•</span>
                      <span>Created {new Date(pipeline.createdAt).toLocaleDateString()}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      {pipeline.type === 'DMIAC' && (
                        <>
                          <Button variant="outline" size="sm">
                            <Eye className="h-4 w-4 mr-1" />
                            View ASCII
                          </Button>
                          <Button variant="outline" size="sm">
                            <Download className="h-4 w-4 mr-1" />
                            Export MD
                          </Button>
                        </>
                      )}
                      <Button variant="outline" size="sm">
                        <Settings className="h-4 w-4" />
                      </Button>
                      <Button size="sm" className="bg-green-600 hover:bg-green-700">
                        <Play className="h-4 w-4 mr-1" />
                        Execute
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}

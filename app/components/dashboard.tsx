
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  GitBranch, 
  Workflow, 
  Settings, 
  Activity, 
  TestTube, 
  Bot, 
  BarChart3,
  Zap,
  FileText,
  Play,
  Clock
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { RepositorySection } from '@/components/repository-section';
import { PipelineSection } from '@/components/pipeline-section';
import { AgentMonitoringSection } from '@/components/agent-monitoring-section';
import { ExecutionDashboard } from '@/components/execution-dashboard';

interface DashboardStats {
  repositories: number;
  pipelines: number;
  activeExecutions: number;
  agents: number;
  successRate: number;
}

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    repositories: 0,
    pipelines: 0,
    activeExecutions: 0,
    agents: 0,
    successRate: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      const response = await fetch('/api/dashboard/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      title: 'Repositories',
      value: stats.repositories,
      icon: GitBranch,
      color: 'text-blue-500',
      change: '+2 this week'
    },
    {
      title: 'Active Pipelines',
      value: stats.pipelines,
      icon: Workflow,
      color: 'text-green-500',
      change: '+5 this month'
    },
    {
      title: 'Running Executions',
      value: stats.activeExecutions,
      icon: Play,
      color: 'text-orange-500',
      change: 'Live updates'
    },
    {
      title: 'Deployed Agents',
      value: stats.agents,
      icon: Bot,
      color: 'text-purple-500',
      change: '100% uptime'
    }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pipeline Automation Hub</h1>
          <p className="text-muted-foreground">
            Orchestrate your CI/CD, DMIAC workflows, and agent monitoring from one central location
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant="outline" className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            System Active
          </Badge>
          <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
            <Zap className="h-4 w-4 mr-2" />
            Quick Start
          </Button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat, index) => (
          <motion.div
            key={stat.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {stat.title}
                </CardTitle>
                <stat.icon className={`h-4 w-4 ${stat.color}`} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading ? '...' : stat.value.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stat.change}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Success Rate Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-green-500" />
              Pipeline Success Rate
            </CardTitle>
            <CardDescription>
              Overall success rate across all pipeline executions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Success Rate</span>
                <span className="text-sm font-medium">
                  {loading ? '...' : `${stats.successRate}%`}
                </span>
              </div>
              <Progress value={stats.successRate} className="w-full" />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Main Content Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="grid w-full lg:grid-cols-6">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="repositories">Repositories</TabsTrigger>
            <TabsTrigger value="pipelines">Pipelines</TabsTrigger>
            <TabsTrigger value="executions">Executions</TabsTrigger>
            <TabsTrigger value="agents">Agents</TabsTrigger>
            <TabsTrigger value="testing">Testing</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-blue-500" />
                    Recent Activity
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>DMIAC Quality Pipeline</span>
                      <Badge variant="secondary">Running</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span>CI/CD Full Stack</span>
                      <Badge variant="outline" className="text-green-600">Success</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span>Refactor Template Applied</span>
                      <Badge variant="secondary">Completed</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-orange-500" />
                    Upcoming Tasks
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="text-sm">
                      <div className="font-medium">Deploy to Production</div>
                      <div className="text-muted-foreground">Scheduled in 2 hours</div>
                    </div>
                    <div className="text-sm">
                      <div className="font-medium">Weekly DMIAC Review</div>
                      <div className="text-muted-foreground">Tomorrow at 9 AM</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TestTube className="h-5 w-5 text-purple-500" />
                    Testing Status
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>Unit Tests</span>
                      <Badge variant="outline" className="text-green-600">Passing</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span>Integration Tests</span>
                      <Badge variant="outline" className="text-green-600">Passing</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span>E2E Tests</span>
                      <Badge variant="secondary">Running</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="repositories">
            <RepositorySection />
          </TabsContent>

          <TabsContent value="pipelines">
            <PipelineSection />
          </TabsContent>

          <TabsContent value="executions">
            <ExecutionDashboard />
          </TabsContent>

          <TabsContent value="agents">
            <AgentMonitoringSection />
          </TabsContent>

          <TabsContent value="testing">
            <Card>
              <CardHeader>
                <CardTitle>Pipeline Testing Interface</CardTitle>
                <CardDescription>
                  Test and provide feedback on your DMIAC and CI/CD pipelines
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <TestTube className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Testing Interface</h3>
                  <p className="text-muted-foreground mb-4">
                    Interactive testing tools coming soon
                  </p>
                  <Button>
                    Start Pipeline Test
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </motion.div>
    </div>
  );
}

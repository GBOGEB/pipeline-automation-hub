
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
  Clock,
  Github,
  User,
  Database,
  ExternalLink,
  Rocket,
  Shield,
  Link,
  Info
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
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Pipeline Automation Hub</h1>
            <p className="text-muted-foreground">
              Orchestrate your CI/CD, DMIAC workflows, and agent monitoring from one central location
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="flex items-center gap-1 bg-yellow-50 border-yellow-200">
              <Info className="h-3 w-3 text-yellow-600" />
              Demo Mode
            </Badge>
            <Badge variant="outline" className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              System Active
            </Badge>
            <Button 
              size="sm" 
              className="bg-blue-600 hover:bg-blue-700"
              onClick={() => {
                if (window.confirm('Deploy to production environment?')) {
                  alert('Deployment initiated! Check the Executions tab for progress.');
                }
              }}
            >
              <Rocket className="h-4 w-4 mr-2" />
              Deploy Live
            </Button>
          </div>
        </div>

        {/* External Services Section */}
        <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <ExternalLink className="h-5 w-5 text-blue-600" />
              External Service Integrations
            </CardTitle>
            <CardDescription>
              Connect your external services and launch integrated workflows
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white h-auto py-3 px-4 flex flex-col items-center gap-2"
                onClick={() => window.open('https://github.com', '_blank')}
              >
                <Github className="h-5 w-5" />
                <span className="text-xs">GitHub</span>
              </Button>
              
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white h-auto py-3 px-4 flex flex-col items-center gap-2"
                onClick={() => window.open('/api/user/profile', '_blank')}
              >
                <User className="h-5 w-5" />
                <span className="text-xs">Local User</span>
              </Button>
              
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white h-auto py-3 px-4 flex flex-col items-center gap-2"
                onClick={() => window.open('https://gitlab.com', '_blank')}
              >
                <GitBranch className="h-5 w-5" />
                <span className="text-xs">GitLab</span>
              </Button>
              
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white h-auto py-3 px-4 flex flex-col items-center gap-2"
                onClick={() => window.open('/api/database/admin', '_blank')}
              >
                <Database className="h-5 w-5" />
                <span className="text-xs">Database</span>
              </Button>
              
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white h-auto py-3 px-4 flex flex-col items-center gap-2"
                onClick={() => window.open('https://bitbucket.org', '_blank')}
              >
                <Link className="h-5 w-5" />
                <span className="text-xs">Bitbucket</span>
              </Button>
              
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white h-auto py-3 px-4 flex flex-col items-center gap-2"
                onClick={() => window.open('/api/security/vault', '_blank')}
              >
                <Shield className="h-5 w-5" />
                <span className="text-xs">Vault</span>
              </Button>
            </div>
          </CardContent>
        </Card>
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
                  <Badge variant="outline" className="ml-2 text-xs text-orange-600 border-orange-200">
                    Demo
                  </Badge>
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
            <TabsTrigger 
              value="overview"
              onClick={() => console.log('Overview tab clicked')}
            >
              Overview
            </TabsTrigger>
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
                    <Badge variant="outline" className="text-xs text-orange-600 border-orange-200">
                      Demo Data
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <div className="font-medium">DMIAC Quality Pipeline</div>
                        <div className="text-xs text-muted-foreground">GitHub • repo/quality-control</div>
                      </div>
                      <Badge variant="secondary" className="bg-yellow-100 text-yellow-700">Running</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <div className="font-medium">CI/CD Full Stack</div>
                        <div className="text-xs text-muted-foreground">GitHub • repo/web-app</div>
                      </div>
                      <Badge variant="outline" className="text-green-600 border-green-200">Success</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <div className="font-medium">Refactor Template Applied</div>
                        <div className="text-xs text-muted-foreground">Local • code-improvement</div>
                      </div>
                      <Badge variant="secondary" className="bg-blue-100 text-blue-700">Completed</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-orange-500" />
                    Upcoming Tasks
                    <Badge variant="outline" className="text-xs text-orange-600 border-orange-200">
                      Demo Data
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="text-sm">
                      <div className="font-medium">Deploy to Production</div>
                      <div className="text-muted-foreground flex items-center gap-2">
                        <Clock className="h-3 w-3" />
                        Scheduled in 2 hours
                      </div>
                    </div>
                    <div className="text-sm">
                      <div className="font-medium">Weekly DMIAC Review</div>
                      <div className="text-muted-foreground flex items-center gap-2">
                        <Clock className="h-3 w-3" />
                        Tomorrow at 9 AM
                      </div>
                    </div>
                    <div className="text-sm">
                      <div className="font-medium">Agent Health Check</div>
                      <div className="text-muted-foreground flex items-center gap-2">
                        <Clock className="h-3 w-3" />
                        Every 30 minutes
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TestTube className="h-5 w-5 text-purple-500" />
                    Testing Status
                    <Badge variant="outline" className="text-xs text-orange-600 border-orange-200">
                      Demo Data
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <div className="font-medium">Unit Tests</div>
                        <div className="text-xs text-muted-foreground">847 tests • 2.3s</div>
                      </div>
                      <Badge variant="outline" className="text-green-600 border-green-200">Passing</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <div className="font-medium">Integration Tests</div>
                        <div className="text-xs text-muted-foreground">156 tests • 45s</div>
                      </div>
                      <Badge variant="outline" className="text-green-600 border-green-200">Passing</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <div className="font-medium">E2E Tests</div>
                        <div className="text-xs text-muted-foreground">23 tests • running...</div>
                      </div>
                      <Badge variant="secondary" className="bg-yellow-100 text-yellow-700">Running</Badge>
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

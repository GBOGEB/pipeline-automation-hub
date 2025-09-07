
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Bot, 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Clock,
  Settings,
  RefreshCw,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface Agent {
  id: string;
  name: string;
  type: string;
  status: 'ACTIVE' | 'INACTIVE' | 'ERROR' | 'DEPLOYING';
  endpoint?: string;
  version?: string;
  deployedAt?: string;
  lastSeen?: string;
  config?: any;
}

interface AgentMetrics {
  id: string;
  agentId: string;
  timestamp: string;
  status: string;
  cpuUsage?: number;
  memoryUsage?: number;
  errorCount: number;
  errors?: any;
  metrics?: any;
}

export function AgentMonitoringSection() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [metrics, setMetrics] = useState<Record<string, AgentMetrics[]>>({});
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  useEffect(() => {
    fetchAgents();
    fetchMetrics();
    
    // Set up polling for real-time updates
    const interval = setInterval(() => {
      fetchMetrics();
    }, 30000); // Update every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const fetchAgents = async () => {
    try {
      const response = await fetch('/api/agents');
      if (response.ok) {
        const data = await response.json();
        setAgents(data);
        if (data.length > 0 && !selectedAgent) {
          setSelectedAgent(data[0].id);
        }
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await fetch('/api/agent-monitoring');
      if (response.ok) {
        const data = await response.json();
        // Group metrics by agent ID
        const groupedMetrics = data.reduce((acc: Record<string, AgentMetrics[]>, metric: AgentMetrics) => {
          if (!acc[metric.agentId]) {
            acc[metric.agentId] = [];
          }
          acc[metric.agentId].push(metric);
          return acc;
        }, {});
        setMetrics(groupedMetrics);
      }
    } catch (error) {
      console.error('Error fetching agent metrics:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'INACTIVE':
        return <XCircle className="h-4 w-4 text-gray-500" />;
      case 'ERROR':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'DEPLOYING':
        return <Clock className="h-4 w-4 text-orange-500" />;
      default:
        return <XCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'text-green-600 bg-green-50';
      case 'INACTIVE':
        return 'text-gray-600 bg-gray-50';
      case 'ERROR':
        return 'text-red-600 bg-red-50';
      case 'DEPLOYING':
        return 'text-orange-600 bg-orange-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const selectedAgentData = agents.find(agent => agent.id === selectedAgent);
  const selectedAgentMetrics = metrics[selectedAgent || ''] || [];
  const latestMetrics = selectedAgentMetrics?.[0];

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
          <h2 className="text-2xl font-bold tracking-tight">Agent Monitoring</h2>
          <p className="text-muted-foreground">
            Monitor deployed agents and track post-deployment performance
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" onClick={fetchMetrics}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Badge variant="outline" className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            Live Monitoring
          </Badge>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Agents</CardTitle>
            <Bot className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{agents.length}</div>
            <p className="text-xs text-muted-foreground">Deployed agents</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {agents.filter(agent => agent.status === 'ACTIVE').length}
            </div>
            <p className="text-xs text-muted-foreground">Running normally</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Errors</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {agents.filter(agent => agent.status === 'ERROR').length}
            </div>
            <p className="text-xs text-muted-foreground">Need attention</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Uptime</CardTitle>
            <TrendingUp className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">99.2%</div>
            <p className="text-xs text-muted-foreground">Last 24 hours</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="details">Agent Details</TabsTrigger>
          <TabsTrigger value="errors">Error Reports</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="space-y-4">
            {agents.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <Bot className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Agents Deployed</h3>
                  <p className="text-muted-foreground text-center mb-4">
                    Deploy your first agent to start monitoring post-deployment activities
                  </p>
                  <Button>Deploy Agent</Button>
                </CardContent>
              </Card>
            ) : (
              agents.map((agent, index) => (
                <motion.div
                  key={agent.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <Bot className="h-5 w-5 text-blue-500" />
                          <div>
                            <CardTitle className="text-lg">{agent.name}</CardTitle>
                            <CardDescription>
                              {agent.type} • Version {agent.version}
                              {agent.deployedAt && (
                                <>
                                  {' • Deployed '}
                                  {new Date(agent.deployedAt).toLocaleDateString()}
                                </>
                              )}
                            </CardDescription>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge className={getStatusColor(agent.status)}>
                            {getStatusIcon(agent.status)}
                            <span className="ml-1">{agent.status}</span>
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        {/* Performance Metrics */}
                        {metrics[agent.id]?.[0] && (
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <div className="flex justify-between text-sm mb-1">
                                <span>CPU Usage</span>
                                <span>{metrics[agent.id][0].cpuUsage || 0}%</span>
                              </div>
                              <Progress value={metrics[agent.id][0].cpuUsage || 0} className="h-2" />
                            </div>
                            <div>
                              <div className="flex justify-between text-sm mb-1">
                                <span>Memory Usage</span>
                                <span>{metrics[agent.id][0].memoryUsage || 0}%</span>
                              </div>
                              <Progress value={metrics[agent.id][0].memoryUsage || 0} className="h-2" />
                            </div>
                          </div>
                        )}

                        <div className="flex items-center justify-between text-sm text-muted-foreground">
                          <span>
                            Last seen: {agent.lastSeen 
                              ? new Date(agent.lastSeen).toLocaleString() 
                              : 'Never'
                            }
                          </span>
                          <div className="flex items-center space-x-2">
                            <span>
                              Errors: {metrics[agent.id]?.[0]?.errorCount || 0}
                            </span>
                            <Button variant="outline" size="sm" onClick={() => setSelectedAgent(agent.id)}>
                              <Settings className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="details">
          {selectedAgentData ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-blue-500" />
                  {selectedAgentData.name} Details
                </CardTitle>
                <CardDescription>
                  Detailed monitoring and configuration for this agent
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Agent Info */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium">Type</Label>
                    <p className="text-sm text-muted-foreground">{selectedAgentData.type}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Version</Label>
                    <p className="text-sm text-muted-foreground">{selectedAgentData.version}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Endpoint</Label>
                    <p className="text-sm text-muted-foreground">{selectedAgentData.endpoint || 'N/A'}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Status</Label>
                    <Badge className={getStatusColor(selectedAgentData.status)}>
                      {getStatusIcon(selectedAgentData.status)}
                      <span className="ml-1">{selectedAgentData.status}</span>
                    </Badge>
                  </div>
                </div>

                {/* Recent Metrics */}
                {latestMetrics && (
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium">Current Metrics</h4>
                    <div className="grid grid-cols-3 gap-4">
                      <Card>
                        <CardContent className="pt-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold">{latestMetrics.cpuUsage || 0}%</div>
                            <p className="text-xs text-muted-foreground">CPU Usage</p>
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold">{latestMetrics.memoryUsage || 0}%</div>
                            <p className="text-xs text-muted-foreground">Memory Usage</p>
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold text-red-600">{latestMetrics.errorCount}</div>
                            <p className="text-xs text-muted-foreground">Error Count</p>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="flex items-center justify-center py-12">
                <div className="text-center">
                  <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Select an Agent</h3>
                  <p className="text-muted-foreground">
                    Choose an agent from the overview to view detailed metrics
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="errors">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                Error Reports
              </CardTitle>
              <CardDescription>
                Recent errors and issues from deployed agents
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Critical Errors</h3>
                <p className="text-muted-foreground mb-4">
                  All agents are functioning normally. Error reports will appear here when issues occur.
                </p>
                <Badge variant="outline" className="text-green-600">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  System Healthy
                </Badge>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Label({ className, children }: { className?: string; children: React.ReactNode }) {
  return <label className={className}>{children}</label>;
}


'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, GitBranch, Settings, ExternalLink, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

interface Repository {
  id: string;
  name: string;
  owner: string;
  url: string;
  branch: string;
  isActive: boolean;
  createdAt: string;
  _count?: {
    pipelines: number;
  };
}

export function RepositorySection() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newRepo, setNewRepo] = useState({
    name: '',
    owner: '',
    url: '',
    branch: 'main',
    token: '',
    isActive: true
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
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRepository = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/repositories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newRepo),
      });
      
      if (response.ok) {
        await fetchRepositories();
        setIsDialogOpen(false);
        setNewRepo({
          name: '',
          owner: '',
          url: '',
          branch: 'main',
          token: '',
          isActive: true
        });
      }
    } catch (error) {
      console.error('Error creating repository:', error);
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
          <h2 className="text-2xl font-bold tracking-tight">Repository Management</h2>
          <p className="text-muted-foreground">
            Connect and manage your GitHub repositories
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700">
              <Plus className="h-4 w-4 mr-2" />
              Add Repository
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Add GitHub Repository</DialogTitle>
              <DialogDescription>
                Connect a new repository to enable pipeline automation
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateRepository} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="owner">Repository Owner</Label>
                  <Input
                    id="owner"
                    value={newRepo.owner}
                    onChange={(e) => setNewRepo({ ...newRepo, owner: e.target.value })}
                    placeholder="username or org"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="name">Repository Name</Label>
                  <Input
                    id="name"
                    value={newRepo.name}
                    onChange={(e) => setNewRepo({ ...newRepo, name: e.target.value })}
                    placeholder="repository-name"
                    required
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="url">Repository URL</Label>
                <Input
                  id="url"
                  value={newRepo.url}
                  onChange={(e) => setNewRepo({ ...newRepo, url: e.target.value })}
                  placeholder="https://github.com/username/repo"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="branch">Default Branch</Label>
                  <Input
                    id="branch"
                    value={newRepo.branch}
                    onChange={(e) => setNewRepo({ ...newRepo, branch: e.target.value })}
                    placeholder="main"
                  />
                </div>
                <div className="flex items-center space-x-2 pt-6">
                  <Switch
                    id="active"
                    checked={newRepo.isActive}
                    onCheckedChange={(checked) => setNewRepo({ ...newRepo, isActive: checked })}
                  />
                  <Label htmlFor="active">Active</Label>
                </div>
              </div>
              <div>
                <Label htmlFor="token">Access Token (Optional)</Label>
                <Input
                  id="token"
                  type="password"
                  value={newRepo.token}
                  onChange={(e) => setNewRepo({ ...newRepo, token: e.target.value })}
                  placeholder="ghp_xxxxxxxxxxxx"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">Add Repository</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Repository List */}
      <div className="space-y-4">
        {repositories.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <GitBranch className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Repositories Connected</h3>
              <p className="text-muted-foreground text-center mb-4">
                Connect your first GitHub repository to start automating your pipelines
              </p>
              <Button onClick={() => setIsDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Repository
              </Button>
            </CardContent>
          </Card>
        ) : (
          repositories.map((repo, index) => (
            <motion.div
              key={repo.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <GitBranch className="h-5 w-5 text-blue-500" />
                      <CardTitle className="text-lg">
                        {repo.owner}/{repo.name}
                      </CardTitle>
                      <Badge variant={repo.isActive ? "default" : "secondary"}>
                        {repo.isActive ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button variant="outline" size="sm">
                        <Settings className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" asChild>
                        <a href={repo.url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                    </div>
                  </div>
                  <CardDescription>
                    Default branch: {repo.branch} • Connected on{' '}
                    {new Date(repo.createdAt).toLocaleDateString()}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                      <span>{repo._count?.pipelines || 0} pipelines</span>
                      <span>•</span>
                      <span className="flex items-center">
                        <RefreshCw className="h-3 w-3 mr-1" />
                        Last sync: 2 hours ago
                      </span>
                    </div>
                    <Button variant="outline" size="sm">
                      Sync Repository
                    </Button>
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

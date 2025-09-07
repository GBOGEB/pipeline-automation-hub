
import { PrismaClient, PipelineType, ExecutionStatus, TriggerType, AgentStatus, FeedbackCategory } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Starting database seeding...');

  // Clear existing data (optional - remove for production)
  await prisma.pipelineFeedback.deleteMany();
  await prisma.pipelineExecution.deleteMany();
  await prisma.agentMonitoring.deleteMany();
  await prisma.agent.deleteMany();
  await prisma.pipeline.deleteMany();
  await prisma.repository.deleteMany();
  await prisma.refactorTemplate.deleteMany();

  // Create Refactor Templates
  const refactorTemplates = await prisma.refactorTemplate.createMany({
    data: [
      {
        name: 'Clean Architecture Refactor',
        description: 'Refactor codebase to follow clean architecture principles',
        category: 'Architecture',
        isBuiltIn: true,
        template: {
          steps: [
            'Identify domain entities and business logic',
            'Create domain layer with entities and use cases',
            'Implement repository pattern for data access',
            'Separate presentation layer from business logic',
            'Add dependency injection container',
            'Update tests to match new architecture'
          ],
          estimatedHours: 40,
          dependencies: ['typescript', 'jest'],
          checklist: [
            'Domain models defined',
            'Use cases implemented',
            'Repository interfaces created',
            'Controllers refactored',
            'Tests updated'
          ]
        }
      },
      {
        name: 'Performance Optimization',
        description: 'Optimize application performance and reduce bottlenecks',
        category: 'Performance',
        isBuiltIn: true,
        template: {
          steps: [
            'Profile application performance',
            'Identify performance bottlenecks',
            'Optimize database queries',
            'Implement caching strategies',
            'Optimize frontend assets',
            'Add performance monitoring'
          ],
          estimatedHours: 24,
          tools: ['lighthouse', 'webpack-bundle-analyzer', 'redis'],
          checklist: [
            'Performance baseline established',
            'Critical path optimized',
            'Caching implemented',
            'Bundle size reduced',
            'Monitoring in place'
          ]
        }
      },
      {
        name: 'Legacy Code Modernization',
        description: 'Update legacy code to modern standards and frameworks',
        category: 'Modernization',
        isBuiltIn: true,
        template: {
          steps: [
            'Audit existing codebase',
            'Create migration plan',
            'Update dependencies',
            'Refactor deprecated patterns',
            'Add modern testing framework',
            'Update documentation'
          ],
          estimatedHours: 60,
          technologies: ['typescript', 'react', 'node.js'],
          checklist: [
            'Legacy code audited',
            'Dependencies updated',
            'Code patterns modernized',
            'Tests migrated',
            'Documentation updated'
          ]
        }
      }
    ]
  });

  // Create Sample Repositories
  const sampleRepo = await prisma.repository.create({
    data: {
      name: 'pipeline-demo-app',
      owner: 'demo-org',
      url: 'https://github.com/demo-org/pipeline-demo-app',
      branch: 'main',
      isActive: true
    }
  });

  // Create Sample Pipelines
  const dmiapPipeline = await prisma.pipeline.create({
    data: {
      name: 'Quality Improvement DMIAC',
      type: PipelineType.DMIAC,
      description: 'A DMIAC workflow for improving code quality metrics',
      repositoryId: sampleRepo.id,
      config: {
        phases: {
          Define: {
            objectives: ['Reduce bug count by 50%', 'Improve test coverage to 90%'],
            stakeholders: ['Development Team', 'QA Team', 'Product Owner'],
            timeline: '2 weeks'
          },
          Measure: {
            metrics: ['Bug count', 'Test coverage', 'Code complexity'],
            tools: ['SonarQube', 'Jest', 'ESLint'],
            baseline: 'Current: 45 bugs, 65% coverage'
          },
          Analyze: {
            rootCauses: ['Insufficient testing', 'Complex code structure'],
            techniques: ['Fishbone diagram', 'Statistical analysis'],
            hypotheses: ['Better testing reduces bugs', 'Simpler code has fewer bugs']
          },
          Improve: {
            solutions: ['Implement TDD', 'Refactor complex functions', 'Add automated testing'],
            pilot: 'Start with user authentication module',
            validation: 'A/B testing on selected modules'
          },
          Control: {
            monitoring: ['Daily bug reports', 'Weekly coverage reports'],
            documentation: ['Updated testing guidelines', 'Code review checklist'],
            sustainment: 'Monthly review meetings'
          }
        }
      },
      asciiVisualization: `
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ DEFINE  │───▶│ MEASURE │───▶│ ANALYZE │───▶│ IMPROVE │───▶│ CONTROL │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
         │              │              │              │              │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Goals &  │    │Collect  │    │Root     │    │Implement│    │Monitor  │
    │Problems │    │Baseline │    │Cause    │    │Solutions│    │& Sustain│
    │         │    │Data     │    │Analysis │    │         │    │         │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
      `,
      markdownExport: `# DMIAC Workflow: Quality Improvement

## Overview
This DMIAC workflow focuses on improving code quality metrics through systematic process improvement.

## Phase 1: Define
- **Objectives**: Reduce bug count by 50%, Improve test coverage to 90%
- **Stakeholders**: Development Team, QA Team, Product Owner
- **Timeline**: 2 weeks

## Phase 2: Measure
- **Metrics**: Bug count, Test coverage, Code complexity
- **Tools**: SonarQube, Jest, ESLint
- **Baseline**: Current: 45 bugs, 65% coverage

## Phase 3: Analyze
- **Root Causes**: Insufficient testing, Complex code structure
- **Techniques**: Fishbone diagram, Statistical analysis
- **Hypotheses**: Better testing reduces bugs, Simpler code has fewer bugs

## Phase 4: Improve
- **Solutions**: Implement TDD, Refactor complex functions, Add automated testing
- **Pilot**: Start with user authentication module
- **Validation**: A/B testing on selected modules

## Phase 5: Control
- **Monitoring**: Daily bug reports, Weekly coverage reports
- **Documentation**: Updated testing guidelines, Code review checklist
- **Sustainment**: Monthly review meetings
      `
    }
  });

  const cicdPipeline = await prisma.pipeline.create({
    data: {
      name: 'Full Stack CI/CD Pipeline',
      type: PipelineType.CI_CD,
      description: 'Complete CI/CD pipeline for full stack applications',
      repositoryId: sampleRepo.id,
      config: {
        ci: {
          triggers: ['push', 'pull_request'],
          jobs: {
            test: {
              steps: ['checkout', 'setup-node', 'install-dependencies', 'run-tests', 'coverage-report']
            },
            lint: {
              steps: ['checkout', 'setup-node', 'install-dependencies', 'run-lint']
            },
            build: {
              steps: ['checkout', 'setup-node', 'install-dependencies', 'build-app', 'build-docker-image']
            }
          }
        },
        cd: {
          environments: ['staging', 'production'],
          deployment: {
            staging: {
              trigger: 'merge-to-develop',
              steps: ['deploy-to-staging', 'run-e2e-tests', 'notify-team']
            },
            production: {
              trigger: 'merge-to-main',
              steps: ['deploy-to-production', 'health-check', 'rollback-on-failure']
            }
          }
        }
      }
    }
  });

  // Create Sample Agents
  const prodMonitor = await prisma.agent.create({
    data: {
      name: 'Production Monitor',
      type: 'monitoring',
      status: AgentStatus.ACTIVE,
      endpoint: 'https://api.example.com/monitor',
      version: '1.2.0',
      deployedAt: new Date(),
      lastSeen: new Date(),
      config: {
        interval: 60,
        metrics: ['cpu', 'memory', 'errors'],
        alertThreshold: 80
      }
    }
  });

  const errorReporter = await prisma.agent.create({
    data: {
      name: 'Error Reporter',
      type: 'error-tracking',
      status: AgentStatus.ACTIVE,
      endpoint: 'https://api.example.com/errors',
      version: '1.1.0',
      deployedAt: new Date(),
      lastSeen: new Date(),
      config: {
        errorTypes: ['runtime', 'network', 'validation'],
        reportLevel: 'error'
      }
    }
  });

  const loadBalancer = await prisma.agent.create({
    data: {
      name: 'Load Balancer Monitor',
      type: 'network',
      status: AgentStatus.INACTIVE,
      endpoint: 'https://lb.example.com/monitor',
      version: '2.0.0',
      deployedAt: new Date(Date.now() - 86400000), // 1 day ago
      lastSeen: new Date(Date.now() - 3600000), // 1 hour ago
      config: {
        checkInterval: 30,
        healthEndpoints: ['/health', '/status']
      }
    }
  });

  // Create Agent Monitoring Data
  const agentIds = [prodMonitor.id, errorReporter.id, loadBalancer.id];
  const monitoringData: {
    agentId: string;
    timestamp: Date;
    status: string;
    cpuUsage: number;
    memoryUsage: number;
    errorCount: number;
    metrics: any;
  }[] = [];

  // Generate monitoring data for the last 24 hours
  for (let i = 0; i < 48; i++) {
    const timestamp = new Date(Date.now() - (i * 30 * 60 * 1000)); // Every 30 minutes
    
    agentIds.forEach(agentId => {
      monitoringData.push({
        agentId,
        timestamp,
        status: 'healthy',
        cpuUsage: Math.random() * 100,
        memoryUsage: Math.random() * 100,
        errorCount: Math.floor(Math.random() * 5),
        metrics: {
          requestCount: Math.floor(Math.random() * 1000),
          responseTime: Math.random() * 500,
          uptime: Math.random() * 100
        }
      });
    });
  }

  await prisma.agentMonitoring.createMany({
    data: monitoringData
  });

  // Create Sample Pipeline Executions
  const execution1 = await prisma.pipelineExecution.create({
    data: {
      pipelineId: cicdPipeline.id,
      status: ExecutionStatus.SUCCESS,
      triggerType: TriggerType.MANUAL,
      completedAt: new Date(),
      logs: 'Pipeline executed successfully. All tests passed. Deployment completed.',
      output: {
        tests: { passed: 45, failed: 0, coverage: '92%' },
        build: { status: 'success', artifacts: ['app.zip', 'docker-image:latest'] },
        deployment: { environment: 'staging', url: 'https://staging.example.com' }
      }
    }
  });

  const execution2 = await prisma.pipelineExecution.create({
    data: {
      pipelineId: dmiapPipeline.id,
      status: ExecutionStatus.RUNNING,
      triggerType: TriggerType.MANUAL,
      logs: 'Currently in Analyze phase. Root cause analysis in progress.',
      output: {
        currentPhase: 'Analyze',
        progress: '60%',
        findings: ['Testing gaps identified', 'Code complexity hotspots found']
      }
    }
  });

  // Create Sample Feedback
  await prisma.pipelineFeedback.createMany({
    data: [
      {
        pipelineId: cicdPipeline.id,
        userId: 'developer1',
        rating: 5,
        comment: 'Pipeline works great! Fast execution and clear feedback.',
        category: FeedbackCategory.USABILITY
      },
      {
        pipelineId: dmiapPipeline.id,
        userId: 'developer2',
        rating: 4,
        comment: 'DMIAC workflow is helpful, but could use more automation in the Measure phase.',
        category: FeedbackCategory.FEATURE_REQUEST
      }
    ]
  });

  console.log('✅ Database seeding completed successfully!');
  console.log(`Created ${refactorTemplates.count} refactor templates`);
  console.log('Created sample repository, pipelines, agents, executions, and feedback');
  console.log(`Created 3 agents with ${monitoringData.length} monitoring data points`);
}

main()
  .catch((e) => {
    console.error('❌ Error during seeding:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });

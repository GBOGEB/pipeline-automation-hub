
import { NextResponse } from 'next/server';
import { PrismaClient, ExecutionStatus } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const [repositories, pipelines, activeExecutions, agents, allExecutions] = await Promise.all([
      prisma.repository.count({ where: { isActive: true } }),
      prisma.pipeline.count({ where: { isActive: true } }),
      prisma.pipelineExecution.count({ where: { status: ExecutionStatus.RUNNING } }),
      prisma.agent.count(),
      prisma.pipelineExecution.findMany({
        select: { status: true },
        where: {
          completedAt: {
            not: null
          }
        }
      })
    ]);

    // Calculate success rate
    const completedExecutions = allExecutions.length;
    const successfulExecutions = allExecutions.filter(
      execution => execution.status === ExecutionStatus.SUCCESS
    ).length;
    const successRate = completedExecutions > 0 
      ? Math.round((successfulExecutions / completedExecutions) * 100)
      : 0;

    return NextResponse.json({
      repositories,
      pipelines,
      activeExecutions,
      agents,
      successRate
    });
  } catch (error) {
    console.error('Error fetching dashboard stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch dashboard stats' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

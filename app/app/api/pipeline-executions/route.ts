
import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient, ExecutionStatus, TriggerType } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const executions = await prisma.pipelineExecution.findMany({
      include: {
        pipeline: {
          select: {
            id: true,
            name: true,
            type: true
          }
        }
      },
      orderBy: {
        startedAt: 'desc'
      },
      take: 50 // Limit to last 50 executions
    });

    return NextResponse.json(executions);
  } catch (error) {
    console.error('Error fetching pipeline executions:', error);
    return NextResponse.json(
      { error: 'Failed to fetch pipeline executions' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { pipelineId, triggerType, logs, output } = body;

    // Basic validation
    if (!pipelineId || !triggerType) {
      return NextResponse.json(
        { error: 'Pipeline ID and trigger type are required' },
        { status: 400 }
      );
    }

    // Validate trigger type
    const validTriggerTypes: TriggerType[] = ['MANUAL', 'WEBHOOK', 'SCHEDULED', 'AUTO'];
    if (!validTriggerTypes.includes(triggerType)) {
      return NextResponse.json(
        { error: 'Invalid trigger type' },
        { status: 400 }
      );
    }

    // Check if pipeline exists
    const pipeline = await prisma.pipeline.findUnique({
      where: { id: pipelineId }
    });

    if (!pipeline) {
      return NextResponse.json(
        { error: 'Pipeline not found' },
        { status: 404 }
      );
    }

    // Create execution record
    const execution = await prisma.pipelineExecution.create({
      data: {
        pipelineId,
        status: ExecutionStatus.QUEUED,
        triggerType,
        logs: logs || 'Pipeline execution queued...',
        output: output || {}
      },
      include: {
        pipeline: {
          select: {
            id: true,
            name: true,
            type: true
          }
        }
      }
    });

    // Simulate pipeline execution (in a real scenario, this would trigger actual execution)
    setTimeout(async () => {
      try {
        // Update to running
        await prisma.pipelineExecution.update({
          where: { id: execution.id },
          data: {
            status: ExecutionStatus.RUNNING,
            logs: 'Pipeline execution started...\nProcessing steps...'
          }
        });

        // Simulate execution time
        setTimeout(async () => {
          try {
            // Randomly succeed or fail for demo purposes
            const success = Math.random() > 0.2; // 80% success rate
            
            await prisma.pipelineExecution.update({
              where: { id: execution.id },
              data: {
                status: success ? ExecutionStatus.SUCCESS : ExecutionStatus.FAILED,
                completedAt: new Date(),
                logs: success 
                  ? 'Pipeline execution completed successfully!\nAll steps completed.'
                  : 'Pipeline execution failed!\nError in step 3: Build failed.',
                errorMsg: success ? null : 'Build process failed with exit code 1',
                output: success 
                  ? { 
                      result: 'success', 
                      steps: ['checkout', 'build', 'test', 'deploy'],
                      duration: '3m 45s'
                    }
                  : { 
                      result: 'failed', 
                      failedStep: 'build',
                      error: 'Build process failed'
                    }
              }
            });
          } catch (error) {
            console.error('Error updating execution:', error);
          }
        }, 15000); // Complete after 15 seconds

      } catch (error) {
        console.error('Error updating execution to running:', error);
      }
    }, 2000); // Start running after 2 seconds

    return NextResponse.json(execution, { status: 201 });
  } catch (error: any) {
    console.error('Error creating pipeline execution:', error);
    
    return NextResponse.json(
      { error: 'Failed to create pipeline execution' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

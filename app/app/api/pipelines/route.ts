
import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient, PipelineType } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const pipelines = await prisma.pipeline.findMany({
      include: {
        repository: {
          select: { name: true, owner: true }
        },
        _count: {
          select: { executions: true }
        }
      },
      orderBy: {
        createdAt: 'desc'
      }
    });

    return NextResponse.json(pipelines);
  } catch (error) {
    console.error('Error fetching pipelines:', error);
    return NextResponse.json(
      { error: 'Failed to fetch pipelines' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { 
      name, 
      type, 
      description, 
      config, 
      asciiVisualization, 
      markdownExport, 
      repositoryId,
      isTemplate 
    } = body;

    // Basic validation
    if (!name || !type) {
      return NextResponse.json(
        { error: 'Name and type are required' },
        { status: 400 }
      );
    }

    // Validate pipeline type
    const validTypes: PipelineType[] = ['CI_CD', 'DMIAC', 'REFACTOR', 'COMBINED'];
    if (!validTypes.includes(type)) {
      return NextResponse.json(
        { error: 'Invalid pipeline type' },
        { status: 400 }
      );
    }

    const pipeline = await prisma.pipeline.create({
      data: {
        name,
        type,
        description: description || null,
        config: config || {},
        asciiVisualization: asciiVisualization || null,
        markdownExport: markdownExport || null,
        repositoryId: repositoryId || null,
        isTemplate: isTemplate || false
      },
      include: {
        repository: {
          select: { name: true, owner: true }
        }
      }
    });

    return NextResponse.json(pipeline, { status: 201 });
  } catch (error: any) {
    console.error('Error creating pipeline:', error);
    
    return NextResponse.json(
      { error: 'Failed to create pipeline' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}


import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const repositories = await prisma.repository.findMany({
      include: {
        _count: {
          select: { pipelines: true }
        }
      },
      orderBy: {
        createdAt: 'desc'
      }
    });

    return NextResponse.json(repositories);
  } catch (error) {
    console.error('Error fetching repositories:', error);
    return NextResponse.json(
      { error: 'Failed to fetch repositories' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, owner, url, branch, token, isActive } = body;

    // Basic validation
    if (!name || !owner || !url) {
      return NextResponse.json(
        { error: 'Name, owner, and URL are required' },
        { status: 400 }
      );
    }

    const repository = await prisma.repository.create({
      data: {
        name,
        owner,
        url,
        branch: branch || 'main',
        token: token || null,
        isActive: isActive !== undefined ? isActive : true
      }
    });

    return NextResponse.json(repository, { status: 201 });
  } catch (error: any) {
    console.error('Error creating repository:', error);
    
    // Handle unique constraint violation
    if (error.code === 'P2002') {
      return NextResponse.json(
        { error: 'Repository with this owner and name already exists' },
        { status: 409 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to create repository' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

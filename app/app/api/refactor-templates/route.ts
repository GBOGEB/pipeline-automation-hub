
import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const templates = await prisma.refactorTemplate.findMany({
      orderBy: [
        { isBuiltIn: 'desc' },
        { usageCount: 'desc' },
        { createdAt: 'desc' }
      ]
    });

    return NextResponse.json(templates);
  } catch (error) {
    console.error('Error fetching refactor templates:', error);
    return NextResponse.json(
      { error: 'Failed to fetch refactor templates' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

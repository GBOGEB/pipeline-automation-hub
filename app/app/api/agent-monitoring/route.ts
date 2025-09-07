
import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const monitoring = await prisma.agentMonitoring.findMany({
      include: {
        agent: {
          select: {
            name: true,
            type: true
          }
        }
      },
      orderBy: {
        timestamp: 'desc'
      },
      take: 100 // Limit to last 100 records
    });

    return NextResponse.json(monitoring);
  } catch (error) {
    console.error('Error fetching agent monitoring data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch agent monitoring data' },
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}

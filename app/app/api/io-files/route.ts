
import { NextRequest, NextResponse } from 'next/server';

export async function GET() {
  const ioData = {
    stats: {
      inputFiles: 247,
      outputFiles: 189,
      processed: 156,
      inProgress: 12
    },
    directories: {
      inputs: {
        path: '/TEST_CAMPAIGN_REPO/inputs',
        totalFiles: 156,
        subdirectories: {
          master_documents: { count: 42, type: '.docx' },
          baseline_docs: { count: 38, type: '.pdf' },
          metadata: { count: 76, type: '.json' },
          configs: { count: 24, type: '.yaml' }
        }
      },
      outputs: {
        path: '/TEST_CAMPAIGN_REPO/outputs',
        totalFiles: 189,
        subdirectories: {
          digital_twins: { count: 42, type: '.md' },
          diff_reports: { count: 38, type: '.html' },
          analytics: { count: 45, type: '.json' },
          archived: { count: 64, type: '.zip' }
        }
      }
    },
    recentActivity: [
      {
        id: 'activity-001',
        type: 'upload',
        file: 'Master_Document_v2.4.docx',
        path: '/inputs/master_documents/',
        status: 'processing',
        timestamp: '2 min ago'
      },
      {
        id: 'activity-002',
        type: 'generate',
        file: 'Digital_Twin_v2.4.md',
        path: '/outputs/digital_twins/',
        status: 'complete',
        timestamp: '1 min ago'
      },
      {
        id: 'activity-003',
        type: 'create',
        file: 'Diff_Report_2024_09_07.html',
        path: '/outputs/diff_reports/',
        status: 'complete',
        timestamp: '3 min ago'
      }
    ]
  };
  
  return NextResponse.json(ioData);
}

export async function POST(request: NextRequest) {
  try {
    const { action, file, path, metadata } = await request.json();
    
    // Simulate file operations
    const operations = {
      'upload': {
        id: `upload-${Date.now()}`,
        status: 'initiated',
        message: `File ${file} uploaded to ${path}`,
        timestamp: new Date().toISOString()
      },
      'process': {
        id: `process-${Date.now()}`,
        status: 'processing',
        message: `Processing ${file} for digital twin generation`,
        timestamp: new Date().toISOString()
      },
      'archive': {
        id: `archive-${Date.now()}`,
        status: 'archived',
        message: `File ${file} archived successfully`,
        timestamp: new Date().toISOString()
      }
    };
    
    return NextResponse.json(operations[action as keyof typeof operations] || { error: 'Unknown operation' });
  } catch (error) {
    return NextResponse.json(
      { error: 'File operation failed' },
      { status: 500 }
    );
  }
}

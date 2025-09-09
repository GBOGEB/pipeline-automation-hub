
import { NextRequest, NextResponse } from 'next/server';

export async function GET() {
  const agentsData = {
    agents: [
      {
        id: 'ppt-parser',
        name: 'PPT_Parser_Agent',
        type: 'DOCUMENT_PROCESSOR',
        status: 'active',
        capabilities: ['pptx_parsing', 'slide_extraction', 'text_extraction', 'image_extraction'],
        currentTasks: 5,
        maxTasks: 10,
        processed: 145,
        errors: 2,
        successRate: 98.6,
        lastActivity: new Date(Date.now() - 2 * 60 * 1000).toISOString(), // 2 minutes ago
        performance: {
          avgProcessingTime: '2.3s',
          throughput: '12 files/min',
          cpuUsage: 45,
          memoryUsage: 67
        }
      },
      {
        id: 'pdf-extraction',
        name: 'PDF_Extraction_Agent',
        type: 'DOCUMENT_PROCESSOR',
        status: 'active',
        capabilities: ['pdf_parsing', 'text_extraction', 'table_extraction', 'image_extraction'],
        currentTasks: 3,
        maxTasks: 8,
        processed: 89,
        errors: 1,
        successRate: 98.9,
        lastActivity: new Date(Date.now() - 1 * 60 * 1000).toISOString(), // 1 minute ago
        performance: {
          avgProcessingTime: '1.8s',
          throughput: '15 files/min',
          cpuUsage: 38,
          memoryUsage: 52
        }
      },
      {
        id: 'metadata-extraction',
        name: 'Metadata_Extraction_Agent',
        type: 'ANALYZER',
        status: 'processing',
        capabilities: ['metadata_extraction', 'python_scripting', 'vba_scripting', 'property_analysis'],
        currentTasks: 7,
        maxTasks: 12,
        processed: 234,
        errors: 3,
        successRate: 98.7,
        lastActivity: new Date(Date.now() - 30 * 1000).toISOString(), // 30 seconds ago
        performance: {
          avgProcessingTime: '4.1s',
          throughput: '8 files/min',
          cpuUsage: 62,
          memoryUsage: 78
        }
      },
      {
        id: 'cross-reference',
        name: 'Cross_Reference_Agent',
        type: 'INDEXER',
        status: 'indexing',
        capabilities: ['reference_extraction', 'sck_cen_parsing', 'global_indexing', 'link_building'],
        currentTasks: 12,
        maxTasks: 15,
        processed: 456,
        errors: 5,
        successRate: 98.9,
        lastActivity: new Date(Date.now() - 45 * 1000).toISOString(), // 45 seconds ago
        performance: {
          avgProcessingTime: '1.2s',
          throughput: '25 refs/min',
          cpuUsage: 55,
          memoryUsage: 43
        }
      },
      {
        id: 'visual-artifact',
        name: 'Visual_Artifact_Agent',
        type: 'VISUAL_PROCESSOR',
        status: 'scanning',
        capabilities: ['image_analysis', 'diagram_extraction', 'table_recognition', 'chart_parsing'],
        currentTasks: 8,
        maxTasks: 10,
        processed: 178,
        errors: 4,
        successRate: 97.8,
        lastActivity: new Date(Date.now() - 1.5 * 60 * 1000).toISOString(), // 1.5 minutes ago
        performance: {
          avgProcessingTime: '6.7s',
          throughput: '6 items/min',
          cpuUsage: 72,
          memoryUsage: 85
        }
      },
      {
        id: 'markdown-generator',
        name: 'Markdown_Generator_Agent',
        type: 'TRANSFORMER',
        status: 'generating',
        capabilities: ['markdown_generation', 'digital_twin_creation', 'recursive_building', 'keb_frontend'],
        currentTasks: 4,
        maxTasks: 8,
        processed: 67,
        errors: 2,
        successRate: 97.0,
        lastActivity: new Date(Date.now() - 3 * 60 * 1000).toISOString(), // 3 minutes ago
        performance: {
          avgProcessingTime: '8.4s',
          throughput: '4 twins/min',
          cpuUsage: 58,
          memoryUsage: 74
        }
      }
    ],
    systemMetrics: {
      totalAgents: 6,
      activeAgents: 6,
      totalTasksRunning: 39,
      maxConcurrentTasks: 73,
      systemLoad: 56.8,
      overallSuccessRate: 98.3,
      totalProcessed: 1169,
      totalErrors: 17
    },
    taskQueues: {
      ppt_processing: {
        queued: 15,
        processing: 5,
        completed: 145,
        failed: 2
      },
      pdf_conversion: {
        queued: 8,
        processing: 3,
        completed: 89,
        failed: 1
      },
      metadata_extraction: {
        queued: 23,
        processing: 7,
        completed: 234,
        failed: 3
      },
      cross_referencing: {
        queued: 45,
        processing: 12,
        completed: 456,
        failed: 5
      },
      visual_processing: {
        queued: 18,
        processing: 8,
        completed: 178,
        failed: 4
      },
      markdown_generation: {
        queued: 12,
        processing: 4,
        completed: 67,
        failed: 2
      }
    }
  };

  return NextResponse.json(agentsData);
}

export async function POST(request: NextRequest) {
  try {
    const { action, agentId, taskType, filename, options } = await request.json();
    
    const operations = {
      'assign_task': {
        id: `task-${Date.now()}`,
        agentId: agentId,
        taskType: taskType,
        filename: filename,
        status: 'assigned',
        priority: options?.priority || 'MEDIUM',
        estimatedDuration: `${Math.floor(Math.random() * 10) + 2}s`,
        timestamp: new Date().toISOString()
      },
      'pause_agent': {
        id: `pause-${Date.now()}`,
        agentId: agentId,
        status: 'paused',
        timestamp: new Date().toISOString(),
        message: `Agent ${agentId} paused successfully`
      },
      'resume_agent': {
        id: `resume-${Date.now()}`,
        agentId: agentId,
        status: 'active',
        timestamp: new Date().toISOString(),
        message: `Agent ${agentId} resumed successfully`
      },
      'get_agent_log': {
        agentId: agentId,
        logs: [
          {
            timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
            level: 'INFO',
            message: 'Processing task completed successfully',
            taskId: 'task-12345'
          },
          {
            timestamp: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
            level: 'WARN',
            message: 'High memory usage detected',
            details: '85% memory utilization'
          },
          {
            timestamp: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
            level: 'INFO',
            message: 'New task assigned',
            taskId: 'task-12344'
          }
        ]
      },
      'bulk_process': {
        id: `bulk-${Date.now()}`,
        status: 'initiated',
        fileCount: options?.files?.length || 0,
        estimatedTime: `${Math.floor((options?.files?.length || 0) * 3)}s`,
        timestamp: new Date().toISOString()
      }
    };
    
    return NextResponse.json(operations[action as keyof typeof operations] || { error: 'Unknown operation' });
  } catch (error) {
    return NextResponse.json(
      { error: 'Task agent operation failed' },
      { status: 500 }
    );
  }
}

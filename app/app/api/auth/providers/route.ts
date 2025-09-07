
import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    providers: {
      credentials: {
        name: "Pipeline Auth",
        type: "credentials"
      }
    }
  });
}

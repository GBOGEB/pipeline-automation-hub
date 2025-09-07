
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Basic validation
    if (!body.email || !body.password) {
      return NextResponse.json(
        { error: 'Email and password are required' },
        { status: 400 }
      );
    }

    // For demo purposes, accept any valid email/password
    if (body.email.includes('@') && body.password.length >= 6) {
      return NextResponse.json({
        user: {
          id: '1',
          email: body.email,
          name: body.name || 'Pipeline User'
        },
        message: 'User created successfully'
      });
    }

    return NextResponse.json(
      { error: 'Invalid email or password too short (min 6 characters)' },
      { status: 400 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

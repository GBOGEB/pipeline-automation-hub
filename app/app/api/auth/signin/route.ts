
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
    if (body.email.includes('@') && body.password.length >= 3) {
      return NextResponse.json({
        user: {
          id: '1',
          email: body.email,
          name: 'Pipeline User'
        },
        token: 'demo-jwt-token',
        message: 'Login successful'
      });
    }

    return NextResponse.json(
      { error: 'Invalid credentials' },
      { status: 401 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

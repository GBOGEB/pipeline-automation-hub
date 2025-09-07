
import { NextResponse } from 'next/server';
import { randomBytes } from 'crypto';

export async function GET() {
  try {
    const csrfToken = randomBytes(32).toString('hex');
    
    const response = NextResponse.json({
      csrfToken: csrfToken
    });
    
    // Set CSRF token in cookie
    response.cookies.set('csrf-token', csrfToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 3600 // 1 hour
    });
    
    return response;
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to generate CSRF token' },
      { status: 500 }
    );
  }
}

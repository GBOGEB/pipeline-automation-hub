
import { NextRequest, NextResponse } from 'next/server';

// Mock NextAuth.js handler for demo purposes
export async function GET(request: NextRequest, { params }: { params: { nextauth: string[] } }) {
  const [...nextauth] = params.nextauth || [];
  
  if (nextauth.includes('session')) {
    return NextResponse.json({
      user: null,
      expires: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
    });
  }
  
  if (nextauth.includes('providers')) {
    return NextResponse.json({
      credentials: {
        id: "credentials",
        name: "Pipeline Auth",
        type: "credentials"
      }
    });
  }
  
  if (nextauth.includes('csrf')) {
    return NextResponse.json({
      csrfToken: 'demo-csrf-token'
    });
  }
  
  if (nextauth.includes('signin')) {
    return NextResponse.redirect('/');
  }
  
  if (nextauth.includes('signout')) {
    return NextResponse.redirect('/');
  }
  
  return NextResponse.json({ message: 'Auth endpoint' });
}

export async function POST(request: NextRequest, { params }: { params: { nextauth: string[] } }) {
  const [...nextauth] = params.nextauth || [];
  
  if (nextauth.includes('signin')) {
    const body = await request.json().catch(() => ({}));
    
    // Always redirect to home for demo
    return NextResponse.redirect(new URL('/', request.url), 302);
  }
  
  if (nextauth.includes('signout')) {
    return NextResponse.redirect(new URL('/', request.url), 302);
  }
  
  if (nextauth.includes('callback')) {
    return NextResponse.redirect(new URL('/', request.url), 302);
  }
  
  return NextResponse.json({ message: 'Auth POST endpoint' });
}

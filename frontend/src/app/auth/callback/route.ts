import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')

  if (!code) {
    const url = new URL('/login', request.url)
    url.searchParams.set('error', 'true')
    return NextResponse.redirect(url)
  }

  const supabase = await createClient()
  const { error } = await supabase.auth.exchangeCodeForSession(code)

  if (error) {
    const url = new URL('/login', request.url)
    url.searchParams.set('error', 'true')
    return NextResponse.redirect(url)
  }

  return NextResponse.redirect(new URL('/', request.url))
}

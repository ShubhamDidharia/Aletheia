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

  // Only ever follow a same-site relative path — never an absolute URL from
  // the query string, which would be an open redirect.
  const next = searchParams.get('next') ?? '/dashboard'
  const safeNext = next.startsWith('/') && !next.startsWith('//') ? next : '/dashboard'

  return NextResponse.redirect(new URL(safeNext, request.url))
}

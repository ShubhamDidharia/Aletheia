import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

const PROTECTED_PREFIXES = ['/dashboard']
/** Exact paths that also need auth ('/' would match everything as a prefix). */
const PROTECTED_EXACT = ['/']

/**
 * Refreshes the Supabase auth cookie on every request and redirects
 * unauthenticated visitors away from protected routes.
 */
export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request })

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  // Without Supabase configured there is nothing to enforce — don't lock
  // the developer out of their own app.
  if (!url || !anonKey) return response

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
        response = NextResponse.next({ request })
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options)
        )
      },
    },
  })

  const {
    data: { user },
  } = await supabase.auth.getUser()

  const { pathname } = request.nextUrl
  const isProtected =
    PROTECTED_EXACT.includes(pathname) || PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))

  // No "redirectTo" round-trip: Next normalises proxy redirects to a bare
  // path and drops the query string, and both protected routes land on
  // /dashboard anyway. Sending a param that gets stripped would just be
  // decoration.
  if (!user && isProtected) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  if (user && pathname === '/login') {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|auth/callback|.*\\.(?:svg|png|jpg|webp)$).*)'],
}

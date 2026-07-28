'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Telescope, AlertTriangle, Loader2 } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'

const GoogleIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden>
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
)

const FEATURES = [
  'Breaks your goal into targeted searches',
  'Pauses to ask when sources genuinely conflict',
  'Deletes any claim it cannot cite',
]

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh bg-plane" />}>
      <Login />
    </Suspense>
  )
}

function Login() {
  const searchParams = useSearchParams()
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(searchParams.get('error') === 'true')

  const signIn = async () => {
    setPending(true)
    setFailed(false)
    const { error } = await createClient().auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
    if (error) {
      setFailed(true)
      setPending(false)
    }
  }

  return (
    <main className="min-h-dvh grid place-items-center bg-plane px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center text-center">
          <span className="w-12 h-12 rounded-2xl bg-brand/15 grid place-items-center text-brand mb-5">
            <Telescope className="w-6 h-6" />
          </span>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">Aletheia</h1>
          <p className="mt-2 text-sm text-ink-3">Strategic Intelligence Agent</p>
        </div>

        <ul className="my-8 space-y-2.5">
          {FEATURES.map((feature) => (
            <li key={feature} className="flex items-start gap-2.5 text-sm text-ink-2">
              <span className="mt-1.5 w-1 h-1 rounded-full bg-brand shrink-0" />
              {feature}
            </li>
          ))}
        </ul>

        {failed && (
          <div
            role="alert"
            className="mb-4 flex items-start gap-2 rounded-lg border border-critical/30 bg-critical/10 px-3 py-2.5"
          >
            <AlertTriangle className="w-4 h-4 text-critical shrink-0 mt-0.5" />
            <p className="text-xs text-ink leading-relaxed">
              Sign-in didn’t complete. Please try again.
            </p>
          </div>
        )}

        <button
          onClick={signIn}
          disabled={pending}
          className="w-full flex items-center justify-center gap-2.5 h-11 rounded-xl bg-white hover:bg-white/90 disabled:opacity-70 text-[#1a1a19] text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-plane"
        >
          {pending ? <Loader2 className="w-4 h-4 animate-spin" /> : <GoogleIcon />}
          {pending ? 'Redirecting…' : 'Continue with Google'}
        </button>

        <p className="mt-6 text-center text-[11px] text-ink-3 leading-relaxed">
          Your research sessions are private to your account.
        </p>
      </div>
    </main>
  )
}

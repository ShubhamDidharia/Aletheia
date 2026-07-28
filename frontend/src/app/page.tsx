import { redirect } from 'next/navigation'

/**
 * There is one workspace. The old landing page duplicated the dashboard's
 * composer and carried two panels ("Missions", "Source Library") that never
 * filled in — both now live in the dashboard for real.
 */
export default function Home() {
  redirect('/dashboard')
}

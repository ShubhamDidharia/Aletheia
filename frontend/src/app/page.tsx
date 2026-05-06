'use client'

import { useRouter } from 'next/navigation'
import { Search, Library, Shield, LogOut } from "lucide-react";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";

export default function Home() {
  const router = useRouter()
  const supabase = createClient()

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <main className="flex h-screen overflow-hidden relative">
      <button
        onClick={handleSignOut}
        className="absolute top-4 right-4 flex items-center gap-2 px-3 py-2 text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 rounded-lg transition-colors z-10"
      >
        <LogOut className="w-4 h-4" />
        Sign out
      </button>

      {/* Dark Sidebar */}
      <aside className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col">
        <div className="p-6 flex items-center gap-2">
          <Shield className="w-6 h-6 text-blue-500" />
          <h1 className="text-xl font-bold tracking-tight">Aletheia</h1>
        </div>
        <div className="flex-1 px-4 py-2">
          <div className="text-sm text-zinc-500 font-medium mb-4 uppercase tracking-wider">
            Missions
          </div>
          <div className="flex flex-col items-center justify-center h-40 text-center px-4 border-2 border-dashed border-zinc-800 rounded-lg">
            <p className="text-sm text-zinc-500 italic">No missions yet</p>
          </div>
        </div>
        <div className="p-4 border-t border-zinc-800 text-xs text-zinc-500">
          v1.0.0-alpha
        </div>
      </aside>

      {/* Main Center Area */}
      <section className="flex-1 flex flex-col relative bg-zinc-900/50">
        <div className="flex-1 flex flex-col items-center justify-center px-4 max-w-3xl mx-auto w-full">
          <h2 className="text-4xl font-semibold mb-8 text-center bg-gradient-to-b from-white to-zinc-400 bg-clip-text text-transparent">
            What do you want to investigate?
          </h2>
          
          <div className="w-full relative group">
            <div className="absolute inset-0 bg-blue-500/10 blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity" />
            <div className="relative flex items-center">
              <Search className="absolute left-4 w-5 h-5 text-zinc-500" />
              <Input 
                className="w-full h-14 pl-12 pr-4 bg-zinc-900 border-zinc-800 focus:border-blue-500/50 focus:ring-blue-500/20 text-lg rounded-2xl transition-all"
                placeholder="Enter a research topic or URL..."
              />
            </div>
          </div>
          
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {["Market Analysis", "Cyber Threat Intel", "Competitor Research"].map((tag) => (
              <button 
                key={tag}
                className="px-3 py-1.5 rounded-full bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-400 transition-colors border border-zinc-700/50"
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 text-center text-xs text-zinc-600">
          Aletheia uses advanced AI agents to synthesize intelligence from across the web.
        </div>
      </section>

      {/* Right Panel */}
      <aside className="w-72 bg-zinc-950/50 border-l border-zinc-800 flex flex-col">
        <div className="p-6 flex items-center gap-2 border-b border-zinc-800">
          <Library className="w-5 h-5 text-zinc-400" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
            Source Library
          </h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-8 text-center">
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto">
              <Library className="w-6 h-6 text-zinc-700" />
            </div>
            <p className="text-sm text-zinc-600">
              Your research sources and citations will appear here.
            </p>
          </div>
        </div>
      </aside>
    </main>
  );
}

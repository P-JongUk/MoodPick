import { createClient } from "@supabase/supabase-js"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

let supabaseSingleton: ReturnType<typeof createClient> | null = null

export function getSupabaseClient() {
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Missing Supabase environment variables. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local.",
    )
  }

  if (!supabaseSingleton) {
    supabaseSingleton = createClient(supabaseUrl, supabaseAnonKey)
  }

  return supabaseSingleton
}

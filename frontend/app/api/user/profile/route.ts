import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL
const supabaseServiceRole = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!supabaseUrl || !supabaseServiceRole) {
  // We intentionally don't throw at import time in production builds,
  // but handlers will return errors if env is missing.
}

function getAdminClient() {
  if (!supabaseUrl || !supabaseServiceRole) {
    throw new Error('Missing Supabase server environment variables (SUPABASE_SERVICE_ROLE_KEY/SUPABASE_URL)')
  }
  return createClient(supabaseUrl, supabaseServiceRole)
}

export async function PUT(request: Request) {
  try {
    const body = await request.json()
    const { user_id, display_name, gender, birth_year } = body as {
      user_id: string
      display_name?: string
      gender?: string | null
      birth_year?: number | null
    }

    if (!user_id || !display_name) {
      return NextResponse.json({ error: 'user_id and display_name are required' }, { status: 400 })
    }

    const supabase = getAdminClient()

    const payload: Record<string, unknown> = {
      user_id,
      display_name,
      updated_at: new Date().toISOString(),
    }
    if (gender !== undefined) payload.gender = gender
    if (birth_year !== undefined) payload.birth_year = birth_year

    const { error } = await supabase.from('user_profiles').upsert(payload, { onConflict: 'user_id' })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Optionally update auth metadata display_name
    try {
      await supabase.auth.admin.updateUserById(user_id, {
        user_metadata: {
          display_name,
          ...(gender !== undefined ? { gender } : {}),
          ...(birth_year !== undefined ? { birth_year } : {}),
        },
      })
    } catch (e) {
      // ignore; not fatal
    }

    return NextResponse.json({ status: 'ok' })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}

export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const userId = url.searchParams.get('user_id')
    if (!userId) return NextResponse.json({ error: 'user_id required' }, { status: 400 })

    const supabase = getAdminClient()
    const { data, error } = await supabase.from('user_profiles').select('*').eq('user_id', userId).maybeSingle()
    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json(data || null)
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}

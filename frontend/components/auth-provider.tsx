'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { getSupabaseClient } from '@/lib/supabaseClient'

type AuthProviderProps = {
  children: React.ReactNode
}

type AuthProviderValue = {
  user: User | null
  session: Session | null
  isLoggedIn: boolean
  isAuthLoading: boolean
  authErrorMessage: string | null
  setAuthErrorMessage: (message: string | null) => void
  signInWithPassword: (email: string, password: string) => Promise<void>
  signInWithOAuth: (provider: 'google' | 'kakao') => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthProviderValue | null>(null)

export function AuthProvider({ children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [isAuthLoading, setIsAuthLoading] = useState(true)
  const [authErrorMessage, setAuthErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    const supabase = getSupabaseClient()

    const initializeSession = async () => {
      const { data, error } = await supabase.auth.getSession()

      if (!isMounted) {
        return
      }

      if (error) {
        setAuthErrorMessage(error.message)
      }

      setSession(data.session ?? null)
      setUser(data.session?.user ?? null)
      setIsAuthLoading(false)
    }

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!isMounted) {
        return
      }

      setSession(nextSession)
      setUser(nextSession?.user ?? null)
      setIsAuthLoading(false)
    })

    void initializeSession()

    return () => {
      isMounted = false
      authListener.subscription.unsubscribe()
    }
  }, [])

  const signInWithPassword = async (email: string, password: string) => {
    const supabase = getSupabaseClient()
    setIsAuthLoading(true)
    setAuthErrorMessage(null)

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (error) {
      setAuthErrorMessage(error.message)
      setIsAuthLoading(false)
      throw error
    }

    setIsAuthLoading(false)
  }

  const signInWithOAuth = async (provider: 'google' | 'kakao') => {
    const supabase = getSupabaseClient()
    setIsAuthLoading(true)
    setAuthErrorMessage(null)

    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: typeof window !== 'undefined' ? window.location.origin : undefined,
      },
    })

    if (error) {
      setAuthErrorMessage(error.message)
      setIsAuthLoading(false)
      throw error
    }
  }

  const signOut = async () => {
    const supabase = getSupabaseClient()

    try {
      await supabase.auth.signOut()
    } finally {
      setSession(null)
      setUser(null)
      setAuthErrorMessage(null)
      setIsAuthLoading(false)
    }
  }

  const value: AuthProviderValue = {
    user,
    session,
    isLoggedIn: Boolean(user),
    isAuthLoading,
    authErrorMessage,
    setAuthErrorMessage,
    signInWithPassword,
    signInWithOAuth,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('AuthProvider 안에서 useAuth를 사용해야 합니다.')
  }

  return context
}
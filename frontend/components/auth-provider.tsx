'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import type { AuthChangeEvent, Session, User } from '@supabase/supabase-js'
import { getSupabaseClient } from '@/lib/supabaseClient'
import { upsertUserProfile } from '@/lib/api'

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
  signUpWithPassword: (
    email: string,
    password: string,
    displayName: string,
    gender?: string | null,
    birthYear?: number | null
  ) => Promise<void>
  signInWithPassword: (email: string, password: string) => Promise<void>
  signInWithOAuth: (provider: 'google' | 'kakao') => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthProviderValue | null>(null)

export function AuthProvider({ children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [isAuthLoading, setIsAuthLoading] = useState(false)
  const [authErrorMessage, setAuthErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    let authTimeout: ReturnType<typeof setTimeout> | null = null
    let authListener: { subscription: { unsubscribe: () => void } } | null = null

    setIsAuthLoading(true)

    const initializeSession = async () => {
      try {
        const supabase = getSupabaseClient()
        const { data, error } = await supabase.auth.getSession()

        if (!isMounted) {
          return
        }

        if (error) {
          setAuthErrorMessage(error.message)
        }

        setSession(data.session ?? null)
        setUser(data.session?.user ?? null)

        const { data: listener } = supabase.auth.onAuthStateChange(
          (_event: AuthChangeEvent, nextSession: Session | null) => {
            if (!isMounted) {
              return
            }

            setSession(nextSession)
            setUser(nextSession?.user ?? null)
            setIsAuthLoading(false)
          },
        )

        authListener = listener
      } catch (error) {
        if (!isMounted) {
          return
        }

        const message = error instanceof Error ? error.message : '인증 초기화 중 오류가 발생했습니다.'
        setAuthErrorMessage(message)
        setSession(null)
        setUser(null)
      } finally {
        if (isMounted) {
          setIsAuthLoading(false)
        }
      }
    }

    authTimeout = setTimeout(() => {
      if (!isMounted) {
        return
      }

      setIsAuthLoading(false)
    }, 7000)

    void initializeSession()

    return () => {
      isMounted = false

      if (authTimeout) {
        clearTimeout(authTimeout)
      }

      if (authListener) {
        authListener.subscription.unsubscribe()
      }
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

  const signUpWithPassword = async (
    email: string,
    password: string,
    displayName: string,
    gender?: string | null,
    birthYear?: number | null
  ) => {
    const supabase = getSupabaseClient()
    setIsAuthLoading(true)
    setAuthErrorMessage(null)

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          display_name: displayName,
          gender: gender ?? null,
          birth_year: birthYear ?? null,
          onboarding_completed: false,
          onboarding_profile: null,
        },
      },
    })

    if (error) {
      setAuthErrorMessage(error.message)
      setIsAuthLoading(false)
      throw error
    }

    if (data.user?.id) {
      try {
        await upsertUserProfile(data.user.id, displayName, gender ?? null, birthYear ?? null)
      } catch {
        // Profile sync failure should not block signup.
      }
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
    signUpWithPassword,
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

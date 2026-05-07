#!/usr/bin/env node

import fs from "node:fs"
import path from "node:path"
import { createClient } from "@supabase/supabase-js"

const rootDir = path.resolve(process.cwd())
const envPath = path.join(rootDir, ".env.local")

function loadEnvFile(filePath) {
  const raw = fs.readFileSync(filePath, "utf8")
  const result = {}

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) {
      continue
    }

    const idx = trimmed.indexOf("=")
    if (idx <= 0) {
      continue
    }

    const key = trimmed.slice(0, idx).trim()
    const value = trimmed.slice(idx + 1).trim()
    result[key] = value
  }

  return result
}

async function requestJson(url, init = {}) {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  })

  const text = await response.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }

  return {
    ok: response.ok,
    status: response.status,
    body,
  }
}

function assertResult(step, condition, details) {
  if (!condition) {
    throw new Error(`[${step}] failed: ${details}`)
  }
  console.log(`[PASS] ${step}`)
}

async function main() {
  const env = loadEnvFile(envPath)
  const supabaseUrl = env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  const backendBase = env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"

  assertResult("env check", Boolean(supabaseUrl && supabaseAnonKey), "Missing Supabase env vars")

  const supabase = createClient(supabaseUrl, supabaseAnonKey)

  const testEmail = `moodpick-e2e-${Date.now()}@example.com`
  const testPassword = "Test1234!"

  const signUpResult = await supabase.auth.signUp({
    email: testEmail,
    password: testPassword,
  })

  if (signUpResult.error) {
    throw new Error(`[signup] ${signUpResult.error.message}`)
  }

  const userId = signUpResult.data.user?.id
  assertResult("signup", Boolean(userId), "No user id returned from signup")

  const sessionStart = await requestJson(`${backendBase}/session/start`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, context: "e2e rehearsal" }),
  })
  assertResult("session/start", sessionStart.ok && sessionStart.body?.id, JSON.stringify(sessionStart.body))

  const sessionId = sessionStart.body.id

  const preSurvey = await requestJson(`${backendBase}/survey/submit`, {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      phase: "pre",
      question_key: "mood_general",
      emoji_value: "low",
    }),
  })
  assertResult("survey/submit pre", preSurvey.ok, JSON.stringify(preSurvey.body))

  const counseling = await requestJson(`${backendBase}/counseling/message`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, message: "I feel stressed today." }),
  })
  assertResult("counseling/message", counseling.ok, JSON.stringify(counseling.body))

  const feedback = await requestJson(`${backendBase}/content/feedback`, {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      session_id: sessionId,
      content_id: "e2e-content-1",
      feedback: "like",
    }),
  })
  assertResult("content/feedback", feedback.ok, JSON.stringify(feedback.body))

  const watched = await requestJson(`${backendBase}/content/watched`, {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      session_id: sessionId,
      content_id: "e2e-content-1",
      content_title: "E2E Demo Content",
    }),
  })
  assertResult("content/watched", watched.ok, JSON.stringify(watched.body))

  const postSurvey = await requestJson(`${backendBase}/survey/submit`, {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      phase: "post",
      question_key: "mood_general",
      emoji_value: "good",
    }),
  })
  assertResult("survey/submit post", postSurvey.ok, JSON.stringify(postSurvey.body))

  const delta = await requestJson(`${backendBase}/survey/delta/${sessionId}`)
  assertResult("survey/delta", delta.ok && delta.body?.delta, JSON.stringify(delta.body))

  const sessionEnd = await requestJson(`${backendBase}/session/end`, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  })
  assertResult("session/end", sessionEnd.ok, JSON.stringify(sessionEnd.body))

  const stats = await requestJson(`${backendBase}/user/stats/${userId}`)
  assertResult("user/stats", stats.ok, JSON.stringify(stats.body))

  console.log("\nE2E rehearsal completed successfully.")
  console.log(`User: ${testEmail}`)
  console.log(`Session: ${sessionId}`)
}

main().catch((error) => {
  console.error("E2E rehearsal failed:", error.message)
  process.exit(1)
})

#!/usr/bin/env node

/**
 * Non-AI smoke check for MoodPick.
 * Verifies frontend and backend availability plus key non-AI endpoints.
 */

const backendBase = process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000"
const frontendBase = process.env.FRONTEND_BASE_URL || "http://127.0.0.1:3000"

const checks = [
  {
    name: "Backend health",
    url: `${backendBase}/health`,
    method: "GET",
    validate: (status, body) => status === 200 && body.includes('"status":"ok"'),
  },
  {
    name: "Backend survey questions",
    url: `${backendBase}/survey/questions`,
    method: "GET",
    validate: (status, body) => status === 200 && body.includes("mood_general"),
  },
  {
    name: "Backend survey history (dummy user)",
    url: `${backendBase}/survey/history/00000000-0000-0000-0000-000000000000`,
    method: "GET",
    validate: (status, body) => status === 200 && body.includes('"status":"success"'),
  },
  {
    name: "Frontend home",
    url: `${frontendBase}/`,
    method: "GET",
    validate: (status, body) => status === 200 && body.toLowerCase().includes("<html"),
  },
]

async function runCheck(check) {
  try {
    const response = await fetch(check.url, { method: check.method })
    const body = await response.text()
    const ok = check.validate(response.status, body)
    return {
      name: check.name,
      ok,
      status: response.status,
      details: ok ? "OK" : `Unexpected response: ${body.slice(0, 180)}`,
    }
  } catch (error) {
    return {
      name: check.name,
      ok: false,
      status: "ERR",
      details: error instanceof Error ? error.message : String(error),
    }
  }
}

async function main() {
  console.log("Running non-AI smoke checks...")
  console.log(`Backend: ${backendBase}`)
  console.log(`Frontend: ${frontendBase}`)
  console.log("")

  const results = []
  for (const check of checks) {
    const result = await runCheck(check)
    results.push(result)
    console.log(`[${result.ok ? "PASS" : "FAIL"}] ${result.name} (${result.status})`)
    if (!result.ok) {
      console.log(`  -> ${result.details}`)
    }
  }

  const failed = results.filter((r) => !r.ok)
  console.log("")
  if (failed.length === 0) {
    console.log("All smoke checks passed.")
    process.exit(0)
  }

  console.log(`${failed.length} check(s) failed.`)
  process.exit(1)
}

main().catch((error) => {
  console.error("Smoke check crashed:", error)
  process.exit(1)
})

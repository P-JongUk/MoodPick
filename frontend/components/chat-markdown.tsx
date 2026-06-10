"use client"

import { memo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { Components } from "react-markdown"

/** LLM 출력 보정: `**…**`가 strong으로 파싱되도록(별표는 DOM에 남지 않음). */
function normalizeChatMarkdown(source: string): string {
  let s = source.replace(/\uFF0A/g, "*")
  // AI가 ```markdown```으로 감싼 응답을 일반 markdown으로 변환
  s = s.replace(/```(?:markdown|md)\s*\n([\s\S]*?)\n```/gi, "$1")
  s = s.replace(/\*\*([ \t\f\v]+)(?=[^\s*`])/g, "**")
  // `**시작하세요.**깊게`, `**"곡명"**이나`처럼 굵게 끝이 구두점·따옴표 등이고 `**` 뒤에 글자/숫자가 붙으면 CommonMark가 강조로 인식하지 않음 → thin space(U+2009).
  s = s.replace(/(\p{P}\*\*)(?=[\p{L}\p{N}])/gu, "$1\u2009")
  return s
}

const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="my-2 ml-4 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 ml-4 list-decimal space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => (
    <h1 className="mb-1 mt-3 text-base font-semibold first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1 mt-3 text-sm font-semibold first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-2 text-sm font-semibold first:mt-0">{children}</h3>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      className="font-medium text-primary underline underline-offset-2"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-bold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  del: ({ children }) => <del className="text-muted-foreground line-through">{children}</del>,
  code: ({ className, children }) => {
    const isBlock = Boolean(className?.includes("language-"))
    if (isBlock) {
      return <code className={className}>{children}</code>
    }
    return (
      <code className="rounded bg-background/90 px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
    )
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-background/90 p-3 text-xs">{children}</pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-primary/40 pl-3 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-3 border-border" />,
  table: ({ children }) => (
    <div className="my-2 w-full overflow-x-auto">
      <table className="w-full border-collapse border border-border text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-muted/60">{children}</thead>,
  th: ({ children }) => (
    <th className="border border-border px-2 py-1 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => <td className="border border-border px-2 py-1">{children}</td>,
}

export const ChatMarkdown = memo(function ChatMarkdown({ source }: { source: string }) {
  return (
    <div className="break-words text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {normalizeChatMarkdown(source)}
      </ReactMarkdown>
    </div>
  )
})

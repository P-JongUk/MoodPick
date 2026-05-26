/**
 * content_id / media_url 규칙으로 외부 재생(YouTube·팟캐스트) 여부를 판별합니다.
 *
 * - YouTube: `youtube:VIDEO_ID`, `yt:VIDEO_ID`, 또는 11자 video id 단독
 * - Podcast: `podcast:episode:<EPISODE_KEY>`
 * - media_url에 youtube.com/watch?v= / youtu.be/ 포함 시 추출
 */

export type PlaybackKind = "youtube" | "podcast" | "none"

export interface ContentPlaybackInput {
  content_id: string
  media_provider?: "youtube" | "podcast" | null
  media_url?: string | null
}

export interface ResolvedPlayback {
  kind: PlaybackKind
  youtubeVideoId?: string
  podcastAudioUrl?: string
}

function extractYoutubeFromUrl(url: string): string | undefined {
  const v = url.match(/(?:[?&]v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
  return v?.[1]
}

function extractYoutubeVideoId(contentId: string, mediaUrl?: string | null): string | undefined {
  const trimmed = contentId.trim()
  const prefixed = trimmed.replace(/^(youtube|yt):/i, "").trim()
  if (/^[a-zA-Z0-9_-]{11}$/.test(prefixed)) {
    return prefixed
  }
  if (mediaUrl) {
    return extractYoutubeFromUrl(mediaUrl)
  }
  return undefined
}

export function resolvePlayback(input: ContentPlaybackInput): ResolvedPlayback {
  const { content_id, media_provider, media_url } = input

  if (content_id?.toLowerCase().startsWith("podcast:") && media_url) {
    return { kind: "podcast", podcastAudioUrl: media_url }
  }

  if (media_provider === "youtube" || content_id.toLowerCase().includes("youtube:") || content_id.toLowerCase().startsWith("yt:")) {
    const id = extractYoutubeVideoId(content_id, media_url)
    if (id) return { kind: "youtube", youtubeVideoId: id }
  }

  const yt = extractYoutubeVideoId(content_id, media_url)
  if (yt) return { kind: "youtube", youtubeVideoId: yt }

  return { kind: "none" }
}

export function youtubeThumbnailUrl(
  videoId: string,
  size: "default" | "mqdefault" | "hqdefault" = "mqdefault"
): string {
  return `https://img.youtube.com/vi/${videoId}/${size}.jpg`
}

export function youtubeEmbedUrl(
  videoId: string,
  opts?: { autoplay?: boolean }
): string {
  let q = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?rel=0&enablejsapi=1`
  if (opts?.autoplay) {
    // mute=1: 많은 브라우저가 사용자 제스처 없이는 음소거 자동재생만 허용 — 플레이어에서 음소거 해제 가능
    q += "&autoplay=1&mute=1"
  }
  return q
}

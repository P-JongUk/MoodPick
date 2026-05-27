/** YouTube iframe API postMessage (enablejsapi=1 필요) */

export type YoutubeEmbedCommand =
  | "mute"
  | "unMute"
  | "setVolume"
  | "playVideo"
  | "pauseVideo"

export function postYoutubeEmbedCommand(
  iframe: HTMLIFrameElement | null | undefined,
  func: YoutubeEmbedCommand,
  args: number[] = []
): void {
  const win = iframe?.contentWindow
  if (!win) return
  win.postMessage(JSON.stringify({ event: "command", func, args }), "*")
}

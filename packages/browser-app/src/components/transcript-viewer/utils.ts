import type { SegmentCompact } from '../../types'

// ── Speaker colours ───────────────────────────────────────────────────────────

const SPEAKER_HEX: Record<string, string> = {
  SPEAKER_00: '#e5737f',
  SPEAKER_01: '#73b8e5',
  SPEAKER_02: '#73e5a0',
  SPEAKER_03: '#e5c873',
}
const PALETTE = ['#e5737f', '#73b8e5', '#73e5a0', '#e5c873']

export function speakerHex(speaker: string, order: string[]): string {
  if (SPEAKER_HEX[speaker]) return SPEAKER_HEX[speaker]
  const idx = order.indexOf(speaker)
  if (idx >= 0) return PALETTE[idx % PALETTE.length]
  return '#888'
}

// ── Utilities ─────────────────────────────────────────────────────────────────

export function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export interface ConversationTurn {
  speaker: string
  start: number
  segments: SegmentCompact[]
}

export function groupIntoTurns(segments: SegmentCompact[]): ConversationTurn[] {
  const turns: ConversationTurn[] = []
  for (const seg of segments) {
    const last = turns[turns.length - 1]
    if (last && last.speaker === seg.speaker) {
      last.segments.push(seg)
    } else {
      turns.push({ speaker: seg.speaker, start: seg.start, segments: [seg] })
    }
  }
  return turns
}

// ── Edit stats ────────────────────────────────────────────────────────────────

export interface EditStats {
  speakerChanges: number
  textChanges: number
  splitChanges: number
}

export function computeEditStats(editSegs: SegmentCompact[], origSegs: SegmentCompact[]): EditStats {
  const origMap = new Map(origSegs.map(s => [s.id, s]))
  let speakerChanges = 0
  let textChanges = 0
  let splitChanges = 0
  for (const seg of editSegs) {
    const orig = origMap.get(seg.id)
    if (!orig) {
      splitChanges++
    } else {
      if (orig.speaker !== seg.speaker) speakerChanges++
      if (orig.text !== seg.text) textChanges++
    }
  }
  return { speakerChanges, textChanges, splitChanges }
}

import type { IneligibilityReason, RiskLevel } from '../types/trip'

export type RiskOrUnavailable = RiskLevel | 'UNAVAILABLE'

export const RISK_ORDER: RiskLevel[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL']

/** Risk colors are only used for risk. Route identity uses neutral line styles and letters. */
export const RISK_STYLE: Record<RiskOrUnavailable, { label: string; color: string; badge: string }> = {
  LOW: { label: 'Low', color: '#16a34a', badge: 'bg-green-100 text-green-800' },
  MODERATE: { label: 'Moderate', color: '#ca8a04', badge: 'bg-yellow-100 text-yellow-800' },
  HIGH: { label: 'High', color: '#ea580c', badge: 'bg-orange-100 text-orange-800' },
  SEVERE: { label: 'Severe', color: '#dc2626', badge: 'bg-red-100 text-red-800' },
  NO_TRAVEL: { label: 'No Travel', color: '#7e22ce', badge: 'bg-purple-100 text-purple-800' },
  UNAVAILABLE: { label: 'Unavailable', color: '#94a3b8', badge: 'bg-slate-100 text-slate-700' },
}

export function riskRank(level: RiskLevel): number {
  return RISK_ORDER.indexOf(level)
}

/** Same rule as the backend: a stretch takes the worse endpoint risk; any missing end is unavailable. */
export function segmentRisk(start: RiskLevel | null, end: RiskLevel | null): RiskOrUnavailable {
  if (start === null || end === null) return 'UNAVAILABLE'
  return riskRank(start) >= riskRank(end) ? start : end
}

export const INELIGIBLE_LABEL: Record<IneligibilityReason, string> = {
  no_travel: 'Has No Travel conditions',
  incomplete_forecast: 'Forecast incomplete',
}

// Form layout and the questions that are not in the scored list (kept apart from questions.ts,
// which a Python test parses line by line).
import type { FieldAnswers } from './api';

// Grouping of the scored questions into the collapsible boxes on the form.
export const questionGroups: { title: string; hint: string; ids: (keyof FieldAnswers)[] }[] = [
  { title: 'Flow and seasons', hint: 'How much water, and how it changes', ids: ['flow_vs_past', 'lean_flow_lpm', 'monsoon_flow_lpm', 'low_flow_months', 'dry_months', 'seasonality', 'water_quality'] },
  { title: 'People', hint: 'Who depends on the spring', ids: ['households', 'users_vs_past'] },
  { title: 'Surroundings', hint: 'What is around the outlet and uphill', ids: ['pollution_30m', 'disturbance_uphill', 'disaster_prone'] },
  { title: 'Care', hint: 'Protection and recharge work done so far', ids: ['protection', 'existing_interventions', 'recharge_works'] },
];

// Not scored: written down for the report and used by the springshed map.
export type TextQuestion = { key: string; label: string; placeholder: string };
export const textQuestions: TextQuestion[] = [
  { key: 'spring_type', label: 'Spring type (if known)', placeholder: 'e.g. fracture, contact, depression' },
  { key: 'rock_at_outlet', label: 'Rock at the outlet', placeholder: 'e.g. quartzite, slate, phyllite' },
];

export type DipQuestion = { key: 'dip_direction_deg' | 'dip_angle_deg'; label: string; unit: string; min: number; max: number; help: string };
export const dipQuestions: DipQuestion[] = [
  { key: 'dip_direction_deg', label: 'Direction the rock layers tilt down towards', unit: '° from north', min: 0, max: 360, help: '0 = north, 90 = east, 180 = south, 270 = west. Measured with a compass-clinometer.' },
  { key: 'dip_angle_deg', label: 'How steeply the rock layers tilt', unit: '°', min: 0, max: 90, help: '0 = flat, 90 = standing upright.' },
];

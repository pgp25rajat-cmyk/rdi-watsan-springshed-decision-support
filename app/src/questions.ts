// Module A field questions. Ids and allowed values must match OPTIONAL in scripts/module_a_vulnerability.py.
export type Question =
  | { id: string; label: string; kind: 'choice'; options: [value: string, label: string][] }
  | { id: string; label: string; kind: 'number'; unit: string; integer?: boolean; help?: string }
  | { id: string; label: string; kind: 'multi'; options: [value: string, label: string][] }; // stored as 'a,b,c'

export const vulnerabilityQuestions: Question[] = [
  { id: 'flow_vs_past', label: 'Flow now vs 10-20 years ago', kind: 'choice', options: [
    ['more', 'More'], ['same', 'Same'], ['a_bit_less', 'A bit less'], ['much_less', 'Much less'], ['dries_at_times', 'Dries up at times']] },
  { id: 'lean_flow_lpm', label: 'Lean-season flow (May-June); 0 if it dries', kind: 'number', unit: 'L/min' },
  { id: 'monsoon_flow_lpm', label: 'Monsoon flow', kind: 'number', unit: 'L/min' },
  { id: 'low_flow_months', label: 'Months a year with low or no flow', kind: 'number', unit: 'months', integer: true },
  { id: 'dry_months', label: 'Of those, months with no flow at all', kind: 'number', unit: 'months', integer: true, help: 'Even one dry month counts strongly. 0 if it never dries.' },
  { id: 'households', label: 'Households using the spring', kind: 'number', unit: 'households', integer: true },
  { id: 'users_vs_past', label: 'Users now vs 10-20 years ago', kind: 'choice', options: [
    ['fewer', 'Fewer'], ['same', 'Same'], ['more', 'More'], ['much_more', 'Much more']] },
  { id: 'water_quality', label: 'Water quality', kind: 'choice', options: [
    ['no_issue', 'No issue'], ['muddy_after_rain', 'Muddy after rain'], ['contamination', 'Contamination']] },
  { id: 'pollution_30m', label: 'Pollution sources within 30 m of the outlet', kind: 'choice', options: [
    ['none', 'None'], ['one', 'One'], ['two_or_more', 'Two or more'], ['latrine', 'A latrine']] },
  { id: 'disturbance_uphill', label: 'Roads, fire, grazing or landslides uphill', kind: 'choice', options: [
    ['little', 'Little'], ['some', 'Some'], ['major', 'Major']] },
  { id: 'disaster_prone', label: 'Is the area prone to landslides, cloudbursts or flash floods?', kind: 'choice', options: [
    ['no', 'No'], ['minor', 'Minor events'], ['major', 'Major events in the last 10 years']] },
  { id: 'protection', label: 'Outlet protected and an active user committee', kind: 'choice', options: [
    ['both', 'Both'], ['one', 'One of them'], ['neither', 'Neither']] },
  { id: 'existing_interventions', label: 'Recharge works already at the spring or uphill (tick all)', kind: 'multi', options: [
    ['check_dams', 'Check dams'], ['trenches', 'Contour trenches'], ['pits', 'Recharge pits'], ['ponds', 'Ponds (chal-khal)'],
    ['plantation', 'Plantation'], ['di_handpumps', 'DI handpumps'], ['other', 'Other'], ['none', 'None']] },
  { id: 'recharge_works', label: 'Condition of those recharge works', kind: 'choice', options: [
    ['maintained', 'Maintained'], ['neglected', 'Neglected'], ['none', 'None']] },
  { id: 'seasonality', label: 'Seasonality', kind: 'choice', options: [
    ['perennial', 'Perennial'], ['seasonal_perennial', 'Seasonal-perennial'], ['seasonal', 'Seasonal'],
    ['highly_seasonal', 'Highly seasonal'], ['ephemeral', 'Ephemeral']] },
];

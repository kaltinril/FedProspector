export const SET_ASIDE_CODES: Record<string, string> = {
  SBA: 'Total Small Business',
  SBP: 'Partial Small Business',
  WOSB: 'Women-Owned Small Business',
  EDWOSB: 'Economically Disadvantaged WOSB',
  '8A': '8(a)',
  '8AN': '8(a) Sole Source',
  HZC: 'HUBZone',
  HZS: 'HUBZone Sole Source',
  SDVOSBC: 'Service-Disabled Veteran-Owned',
  SDVOSBS: 'SDVOSB Sole Source',
  VSA: 'Veteran-Owned Small Business',
  VSB: 'VOSB Sole Source',
};

export const PROSPECT_STAGES = [
  'Lead',
  'Qualifying',
  'Pursuing',
  'Proposal',
  'Submitted',
  'Won',
  'Lost',
  'No-Bid',
] as const;

export const PROPOSAL_STATUSES = [
  'Draft',
  'In Review',
  'Submitted',
  'Awarded',
  'Not Awarded',
] as const;

export const ENTITY_STRUCTURES = [
  'LLC',
  'Corp',
  'S-Corp',
  'Sole Prop',
  'Partnership',
  'JV',
] as const;

export const CERTIFICATION_TYPES = [
  'WOSB',
  'EDWOSB',
  '8(a)',
  'SDVOSB',
  'HUBZone',
  'Small Business',
  'Veteran-Owned',
] as const;

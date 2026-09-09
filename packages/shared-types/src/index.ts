export interface PestRecord {
  id: string;
  region: string;
  pestName: string;
  riskLevel: 'Low' | 'Moderate' | 'High';
  temperature: number;
  humidity: number;
  rainfall: number;
  recordedAt: string;
}
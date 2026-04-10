export interface Script {
  id: number;
  shopId: number;
  title: string;
  content: string;
  productIds: number[];
  personaId: number | null;
  durationTarget: number | null;
  tone: string | null;
  wordCount: number | null;
  estimatedDurationSeconds: number | null;
  ctaCount: number | null;
  version: number;
  createdAt: string;
  updatedAt: string;
}

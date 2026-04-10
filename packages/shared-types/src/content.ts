export interface Product {
  id: number;
  shopId: number;
  name: string;
  description: string | null;
  price: number | null;
  currency: string;
  highlights: string[];
  images: Array<{ url: string; alt?: string }>;
  externalUrl: string | null;
  category: string | null;
  isActive: boolean;
  embeddingUpdatedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProductFaq {
  id: number;
  productId: number;
  question: string;
  answer: string;
  source: "manual" | "ai_generated" | "learned";
  orderIndex: number;
}

export interface Persona {
  id: number;
  shopId: number;
  name: string;
  description: string | null;
  tone: string | null;
  quirks: string[];
  samplePhrases: string[];
  isDefault: boolean;
  isPreset: boolean;
}

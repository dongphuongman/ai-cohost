export interface Shop {
  id: number;
  uuid: string;
  name: string;
  slug: string;
  industry: string | null;
  teamSize: string | null;
  plan: string;
  planStatus: string;
  trialEndsAt: string | null;
  timezone: string;
  createdAt: string;
}

export interface User {
  id: number;
  uuid: string;
  email: string;
  emailVerified: boolean;
  fullName: string | null;
  avatarUrl: string | null;
  phone: string | null;
  twoFaEnabled: boolean;
  lastLoginAt: string | null;
  createdAt: string;
}

export interface ShopMember {
  id: number;
  shopId: number;
  userId: number;
  role: "owner" | "admin" | "member";
  status: string;
  joinedAt: string | null;
}

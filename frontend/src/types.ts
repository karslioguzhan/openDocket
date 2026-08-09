export interface User {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  theme: string;
}

export interface Counterparty {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  created_at: string;
}

export interface CategoryMeta {
  key: string;
  group: string;
}

export interface Tag {
  id: string;
  name: string;
}

export interface ContractFile {
  id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Share {
  id: string;
  user_id: string;
  email: string;
  display_name: string | null;
  role: string;
}

export type ContractStatus = "draft" | "active" | "expired" | "terminated";

export interface Contract {
  id: string;
  title: string;
  status: ContractStatus;
  role: "owner" | "viewer";
  owner_id: string;
  versicherungsnummer: string | null;
  counterparty: Counterparty | null;
  category: string | null;
  tags: string[];
  effective_date: string | null;
  expiry_date: string | null;
  notice_days: number | null;
  notes: string | null;
  value: string | null;
  currency: string | null;
  files: ContractFile[];
  shares: Share[];
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface Dashboard {
  expiring_soon: Contract[];
  status_counts: Record<string, number>;
  category_counts: { key: string; count: number }[];
}

export interface ContractPayload {
  title: string;
  status: ContractStatus;
  counterparty_id?: string | null;
  counterparty_name?: string | null;
  versicherungsnummer?: string | null;
  category?: string | null;
  tags?: string[];
  effective_date?: string | null;
  expiry_date?: string | null;
  notice_days?: number | null;
  notes?: string | null;
  value?: string | null;
  currency?: string | null;
}

export interface ExtractedFile {
  original_name: string;
  mime_type: string;
  size_bytes: number;
}

export interface ExtractionResult {
  title: string | null;
  counterparty_name: string | null;
  versicherungsnummer: string | null;
  category: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  notice_days: number | null;
  value: string | null;
  currency: string | null;
  files: ExtractedFile[];
}

export interface LLMConfig {
  provider: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  vision?: boolean;
}

export interface LLMTestResult {
  ok: boolean;
  error: string | null;
  response: string | null;
}

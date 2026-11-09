export type Companion = 'Saad' | 'Mohamed';
export interface Source {
  id: number; chunk_id: string; file: string; reference: string; date: string;
  page: number; pages?: number[]; section: string | null; type: string;
  version: string; status: string; kind: 'paragraph' | 'table'; excerpt: string;
  score: number; distance?: number;
}
export interface AskResponse { answer: string; found: boolean; sources: Source[]; invalid_citations: number[]; latency_ms: number; }
export interface SearchResponse { results: Source[]; latency_ms: number; }
export interface SchoolDocument { file: string; reference: string; type: string; date: string; version: string; status: string; chunks_count: number; }
export interface RequestBody { question: string; top_k: number; filters: { type: string | null }; }
export interface Exchange { id: string; question: string; companion: Companion; answer?: AskResponse; error?: string; }

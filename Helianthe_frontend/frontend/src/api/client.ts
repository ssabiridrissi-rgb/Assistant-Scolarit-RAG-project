import type { AskResponse, RequestBody, SchoolDocument, SearchResponse } from '../types';

// Une seule adresse pour toutes les routes ; aucune clé de LLM dans le navigateur.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const messages: Record<number, string> = {
  422: 'La saisie est invalide ou trop longue. Vérifie la question et les paramètres.',
  502: 'Le modèle de réponse ne répond pas correctement. Vérifie Ollama côté serveur, puis réessaie.',
  503: 'Le service documentaire est indisponible. Vérifie le backend et son index.',
  404: 'Cette ressource est introuvable. Vérifie que le module PDF est installé.',
};
async function request<T>(path: string, init: RequestInit = {}, timeout = 30000): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  init.signal?.addEventListener('abort', abort, { once: true });
  if (init.signal?.aborted) controller.abort();
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
    if (!response.ok) throw new Error(messages[response.status] || `Le serveur a retourné l’erreur ${response.status}.`);
    return await response.json() as T;
  } catch (error) {
    if (timedOut) throw new Error('Le délai d’attente est dépassé. Le modèle local peut être lent : réessaie ou vérifie le serveur.');
    if (init.signal?.aborted) throw new DOMException('Requête annulée', 'AbortError');
    if (error instanceof TypeError) throw new Error('Connexion impossible. Vérifie FastAPI, l’URL de l’API et la configuration CORS.');
    throw error;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', abort);
  }
}
const post = (body: RequestBody, signal?: AbortSignal): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
export const api = {
  health: () => request<{ status: string; indexed_chunks: number }>('/api/health'),
  documents: () => request<{ documents: SchoolDocument[] }>('/api/documents'),
  files: () => request<{ files: string[] }>('/api/files'),
  ask: (body: RequestBody, signal?: AbortSignal) => request<AskResponse>('/api/ask', post(body, signal), 240000),
  search: (body: RequestBody, signal?: AbortSignal) => request<SearchResponse>('/api/search', post(body, signal), 90000),
};
export function pdfUrl(file: string, page = 1, download = false) {
  return `${API_BASE}/api/files/${encodeURIComponent(file)}?download=${download}${download ? '' : `#page=${Math.max(1, page)}`}`;
}
export function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'Une erreur inattendue est survenue.'; }

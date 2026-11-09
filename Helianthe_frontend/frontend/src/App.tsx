import { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowRight, ArrowUp, BookOpen, Check, CheckCircle2, ChevronRight, Copy, Download, ExternalLink, FileText, GraduationCap, Info, Lightbulb, MessageCircle, Plus, RefreshCw, Search, Settings2, Sparkles, Sun, X } from 'lucide-react';
import { api, errorMessage, pdfUrl } from './api/client';
import type { Companion, Exchange, SchoolDocument, SearchResponse, Source } from './types';
import Avatar from './components/Avatar';
import CitedAnswer from './components/CitedAnswer';
import SourceDialog from './components/SourceDialog';

type View = 'home' | 'chat' | 'documents' | 'search';
const topics = [
  { title: 'Stages & PFE', detail: 'Conventions, délais et parcours', icon: '01', question: 'Quand faut-il déposer la convention de stage ?', color: 'mint' },
  { title: 'Partir à l’étranger', detail: 'Mobilité et destinations', icon: '02', question: 'Combien de places de semestre d’études à l’étranger sont ouvertes au total ?', color: 'lavender' },
  { title: 'Vie étudiante', detail: 'Clubs, projets et initiatives', icon: '03', question: 'Que doit faire un groupe d’étudiants pour créer un club et obtenir une subvention ?', color: 'peach' },
];
function title(file: string) { return file.replace(/^\d+_/, '').replace(/\.pdf$/i, '').replaceAll('_', ' '); }
function PdfActions({ file, available }: { file: string; available: boolean }) {
  return available ? <div className="document-actions"><a href={pdfUrl(file)} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Ouvrir</a><a href={pdfUrl(file, 1, true)}><Download size={16} /> Télécharger</a></div> : <p className="micro">PDF indisponible · vérifie le module PDF du serveur.</p>;
}

export default function App() {
  const [view, setView] = useState<View>('home');
  const [companion, setCompanion] = useState<Companion>('Saad');
  const [question, setQuestion] = useState('');
  const [topK, setTopK] = useState(5);
  const [filter, setFilter] = useState('');
  const [settings, setSettings] = useState(false);
  const [motion, setMotion] = useState(true);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState<SchoolDocument[]>([]);
  const [docQuery, setDocQuery] = useState('');
  const [docFilter, setDocFilter] = useState('');
  const [docError, setDocError] = useState('');
  const [docLoading, setDocLoading] = useState(true);
  const [files, setFiles] = useState<string[]>([]);
  const [fileError, setFileError] = useState(false);
  const [health, setHealth] = useState<'loading' | 'ok' | 'offline'>('loading');
  const [indexed, setIndexed] = useState(0);
  const [source, setSource] = useState<Source | null>(null);
  const [searchText, setSearchText] = useState('');
  const [searchData, setSearchData] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [toast, setToast] = useState('');
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const types = [...new Set(documents.map(d => d.type))].sort();

  async function refresh() {
    setHealth('loading'); setDocLoading(true); setDocError('');
    await Promise.allSettled([
      api.health().then(data => { setIndexed(data.indexed_chunks); setHealth('ok'); }).catch(() => setHealth('offline')),
      api.documents().then(data => setDocuments(data.documents)).catch(e => { setDocuments([]); setDocError(errorMessage(e)); }).finally(() => setDocLoading(false)),
      api.files().then(data => { setFiles(data.files); setFileError(false); }).catch(() => { setFiles([]); setFileError(true); }),
    ]);
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') { event.preventDefault(); setView(exchanges.length ? 'chat' : 'home'); setTimeout(() => questionRef.current?.focus(), 0); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [exchanges.length]);
  useEffect(() => { if (view === 'chat') endRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' }); }, [exchanges, busy, view]);
  useEffect(() => { if (toast) { const timer = setTimeout(() => setToast(''), 3500); return () => clearTimeout(timer); } }, [toast]);
  useEffect(() => () => activeRequest.current?.abort(), []);

  function choose(name: Companion) { setCompanion(name); setView('chat'); setTimeout(() => questionRef.current?.focus(), 0); }
  function newChat() {
    activeRequest.current?.abort(); activeRequest.current = null;
    setBusy(false); setExchanges([]); setQuestion(''); setSource(null); setView('home');
  }
  async function send(text = question) {
    if (!text.trim() || busy) return;
    const id = crypto.randomUUID();
    const controller = new AbortController();
    activeRequest.current = controller;
    setView('chat'); setQuestion(''); setBusy(true);
    setExchanges(current => [...current, { id, question: text.trim(), companion }]);
    try {
      const answer = await api.ask({ question: text.trim(), top_k: topK, filters: { type: filter || null } }, controller.signal);
      if (!controller.signal.aborted) setExchanges(current => current.map(item => item.id === id ? { ...item, answer } : item));
    } catch (error) {
      if (!controller.signal.aborted) setExchanges(current => current.map(item => item.id === id ? { ...item, error: errorMessage(error) } : item));
    } finally {
      if (activeRequest.current === controller) { setBusy(false); activeRequest.current = null; }
    }
  }
  async function runSearch() {
    if (!searchText.trim() || searchBusy) return;
    setSearchBusy(true); setSearchError(''); setSearchData(null);
    try { setSearchData(await api.search({ question: searchText.trim(), top_k: topK, filters: { type: filter || null } })); }
    catch (error) { setSearchError(errorMessage(error)); }
    finally { setSearchBusy(false); }
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setToast('Réponse copiée.'); }
    catch { setToast('Copie indisponible. Sélectionne le texte pour le copier.'); }
  }
  const params = <div className="settings-panel"><label>Passages recherchés <select value={topK} onChange={e => setTopK(Number(e.target.value))}>{Array.from({ length: 10 }, (_, i) => <option key={i + 1}>{i + 1}</option>)}</select></label><label>Type de document <select value={filter} onChange={e => setFilter(e.target.value)}><option value="">Tous les types</option>{types.map(type => <option key={type}>{type}</option>)}</select></label><p className="micro">Ces réglages s’appliquent aux prochaines recherches. Les textes modificatifs liés peuvent compléter les passages.</p></div>;
  const composer = <form className="composer" onSubmit={e => { e.preventDefault(); void send(); }}>
    <label className="sr-only" htmlFor="question">Ta question sur la scolarité</label>
    <textarea ref={questionRef} id="question" value={question} onChange={e => setQuestion(e.target.value)} rows={2} maxLength={3000} placeholder="Pose ta question, on t’accompagne…" onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
    <div className="composer-bottom"><button className={`settings-button ${settings ? 'selected' : ''}`} type="button" aria-expanded={settings} onClick={() => setSettings(!settings)}><Settings2 size={16} /> Paramètres</button><span className="shortcut">Entrée pour envoyer</span><button type="submit" className="send-button" disabled={busy || !question.trim()} aria-label="Envoyer la question"><ArrowUp size={21} /></button></div>
    {settings && params}
  </form>;

  return <div className={`app ${motion ? '' : 'no-motion'}`}>
    <aside className="sidebar">
      <button className="brand" onClick={() => setView('home')} aria-label="Hélianthe, accueil"><span className="brand-symbol"><Sun size={25} /></span><span>hélianthe<span className="brand-sub">L’ÉCOLE, EN PLUS SIMPLE.</span></span></button>
      <button className="new-chat" onClick={newChat} disabled={busy} title={busy ? 'Attends la fin de la réponse.' : undefined}><Plus size={18} /> Nouvelle discussion</button>
      <span className="nav-label">TON ESPACE</span>
      <nav aria-label="Navigation principale">
        <button className={view === 'home' || view === 'chat' ? 'active' : ''} onClick={() => setView(exchanges.length ? 'chat' : 'home')}><MessageCircle size={19} /> Conversation <ChevronRight size={15} /></button>
        <button className={view === 'documents' ? 'active' : ''} onClick={() => setView('documents')}><BookOpen size={19} /> Documents {documents.length > 0 && <span className="count">{documents.length}</span>}</button>
        <button className={view === 'search' ? 'active' : ''} onClick={() => setView('search')}><Search size={19} /> Recherche avancée</button>
      </nav>
      <div className="sidebar-note"><div className="note-icon"><Lightbulb size={22} /></div><h3>Une question.<br />Des sources à l’appui.</h3><p>Explore les documents de l’École, à ton rythme.</p><button onClick={() => setView('documents')}>Voir les documents <ArrowRight size={15} /></button></div>
      <div className="sidebar-bottom"><button className="motion-toggle" aria-pressed={motion} onClick={() => setMotion(!motion)}><Sparkles size={16} /> Effets visuels <span>{motion ? 'Activés' : 'Désactivés'}</span></button><div className="school"><span className="school-logo"><GraduationCap size={20} /></span><div>École Hélianthe<small>Établissement fictif · EIH</small></div></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><span className="breadcrumb">Ton campus <ChevronRight size={14} /><strong>{view === 'documents' ? 'Documents' : view === 'search' ? 'Recherche avancée' : 'Assistant scolarité'}</strong></span><button className={`connection ${health}`} onClick={() => void refresh()} title="Actualiser la connexion"><span className="status-dot" />{health === 'ok' ? 'Base disponible' : health === 'loading' ? 'Connexion…' : 'Base indisponible'}<RefreshCw size={13} /></button></header>
      <main>
        {view === 'home' && <div className="home">
          <section className="hero">
            <div className="hero-copy"><div className="eyebrow"><span className="tiny-star">✦</span> TON DUO POUR Y VOIR CLAIR</div><h1>Vos études.<br /><span>En clair.</span></h1><p className="hero-intro">Bonjour ! Nous sommes <strong>Saad et Mohamed.</strong><br />On va t’accompagner dans tes démarches à l’École.</p><p className="hero-sub">Des réponses issues des documents. <br />Les sources à portée de clic.</p><button className="hero-link" onClick={() => questionRef.current?.focus()}>Qu’est-ce qu’on éclaire aujourd’hui ? <ArrowDown size={17} /></button></div>
            <div className="duo-stage"><div className="duo-orbit" /><div className="hello-bubble">Un petit doute ? <span>On est là.</span><Sparkles size={17} /></div><img className="duo-image" src="/images/compagnons.png" alt="Saad avec ses lunettes et Mohamed avec son écharpe te souhaitent la bienvenue." /><div className="companion-labels"><button onClick={() => choose('Saad')}><span className="cyan-dot" /><span><strong>Saad</strong><small>Discuter avec moi</small></span><ArrowUp size={17} /></button><button onClick={() => choose('Mohamed')}><span className="purple-dot" /><span><strong>Mohamed</strong><small>Discuter avec moi</small></span><ArrowUp size={17} /></button></div></div>
          </section>
          <section className="home-question" aria-label="Poser une question">{composer}<p className="composer-note"><BookOpen size={13} /> Les documents de l’EIH sont notre seule source. Chaque question est indépendante.</p></section>
          <section className="topics"><div className="section-heading"><h2>Un point de départ ?</h2><span>À toi de choisir.</span></div><div className="topic-grid">{topics.map(topic => <button key={topic.title} className={`topic ${topic.color}`} onClick={() => { setQuestion(topic.question); questionRef.current?.focus(); }}><span className="topic-number">{topic.icon}</span><ArrowRight size={19} /><h3>{topic.title}</h3><p>{topic.detail}</p></button>)}</div></section>
          <footer className="home-footer"><span><CheckCircle2 size={14} /> Des sources consultables</span><span><FileText size={14} /> Les PDF à télécharger</span><span><Sparkles size={14} /> Deux compagnons, une même base</span></footer>
        </div>}

        {view === 'chat' && <div className="chat-layout"><section className="chat-main"><div className="chat-heading"><div><span className="eyebrow">ON T’ÉCOUTE</span><h1>Un peu plus clair, ensemble.</h1></div><label className="companion-select">Avec <select value={companion} onChange={e => setCompanion(e.target.value as Companion)} disabled={busy}><option>Saad</option><option>Mohamed</option></select></label></div>
          <div className="conversation" aria-label="Historique de cette session">
            {!exchanges.length && <div className="chat-empty"><Avatar name={companion} /><h2>Bonjour, moi c’est {companion}.</h2><p>Pose-moi ta question. Je m’appuie sur les documents de l’École, et tu peux consulter les sources.</p><button className="suggestion" onClick={() => { setQuestion(topics[0].question); questionRef.current?.focus(); }}>{topics[0].question} <ArrowRight size={16} /></button></div>}
            {exchanges.map(item => <article className="exchange" key={item.id}><div className="user-message"><span>TOI</span><p>{item.question}</p><button className="text-button" disabled={busy} onClick={() => { setQuestion(item.question); questionRef.current?.focus(); }}>Modifier la question</button></div>
              {(item.answer || item.error) && <div className="assistant-message"><div className="message-identity"><Avatar name={item.companion} small /><strong>{item.companion}</strong><span>Assistant scolarité</span></div>
                {item.error ? <div role="alert" className="error-box"><Info size={19} /><div><strong>La réponse n’a pas pu arriver.</strong><p>{item.error}</p><button className="text-button" disabled={busy} onClick={() => void send(item.question)}>Réessayer</button></div></div> : item.answer && <>
                  <div className={item.answer.found ? 'answer-card' : 'answer-card refusal'}>{!item.answer.found && <span className="refusal-label"><Info size={16} /> Information non trouvée</span>}<CitedAnswer answer={item.answer.answer} sources={item.answer.sources} onSource={setSource} /></div>
                  {item.answer.sources.length > 0 && <div className="source-chips">{item.answer.sources.map(s => <button key={s.id} onClick={() => setSource(s)}><FileText size={14} /><strong>[{s.id}]</strong> {title(s.file)} <span>p. {s.page}</span></button>)}</div>}
                  <div className="answer-footer"><button onClick={() => void copy(item.answer!.answer)}><Copy size={14} /> Copier</button><span>{(item.answer.latency_ms / 1000).toFixed(1)} s</span></div>
                </>}
              </div>}
            </article>)}
            {busy && <div className="thinking" role="status"><span className="lamp glowing"><Lightbulb size={22} /></span><span>{companion} prépare la réponse…<small>Le modèle local peut prendre un moment.</small></span><span className="thinking-dots">•••</span></div>}
            <div ref={endRef} />
          </div><div className="chat-compose">{composer}<p className="composer-note">Historique conservé pendant cette session. Chaque question est traitée indépendamment.</p></div>
        </section><aside className={`hologram-panel ${companion.toLowerCase()} ${busy ? 'working' : ''}`}><span className="eyebrow">TON COMPAGNON</span><div className="holo-person"><Avatar name={companion} /><div className="holo-scan" /><div className="holo-base" /></div><h2>{companion}</h2><p>On éclaire ta question,<br />une source à la fois.</p><span className={`lamp ${busy ? 'glowing' : exchanges.some(e => e.answer) ? 'answered' : ''}`}><Lightbulb size={23} /></span><span className="holo-status">{busy ? 'Préparation en cours' : 'À ton écoute'}</span><div className="holo-tip"><FileText size={17} /><p>Un clic sur <strong>[1]</strong> ouvre le passage utilisé et son PDF.</p></div></aside></div>}

        {view === 'documents' && <section className="page documents-page"><span className="eyebrow">LA BIBLIOTHÈQUE DE L’ÉCOLE</span><h1>Les réponses commencent ici.</h1><p className="page-intro">Consulte les textes, retrouve une référence et garde une copie du document.</p><div className="page-toolbar"><label className="search-field"><Search size={19} /><input aria-label="Rechercher un document" value={docQuery} onChange={e => setDocQuery(e.target.value)} placeholder="Titre, référence, mot-clé…" /></label><select aria-label="Filtrer les documents par type" value={docFilter} onChange={e => setDocFilter(e.target.value)}><option value="">Tous les types</option>{types.map(type => <option key={type}>{type}</option>)}</select><button className="icon-button" aria-label="Actualiser les documents" onClick={() => void refresh()}><RefreshCw size={18} /></button></div>
          {fileError && <p className="notice">L’accès aux PDF n’est pas actif. Installe le module fourni, puis actualise cette page.</p>}
          {docLoading ? <p role="status">Chargement des documents…</p> : docError ? <div role="alert" className="error-box">{docError}</div> : <><div className="section-heading"><p>{documents.length} documents indexés</p><span>{indexed} fragments dans la base</span></div><div className="document-grid">{documents.filter(d => (!docFilter || d.type === docFilter) && `${d.file} ${d.reference} ${d.type}`.toLowerCase().includes(docQuery.toLowerCase())).map((d, i) => <article className="document-card" key={d.file}><div className="doc-top"><span className={`doc-icon tone-${i % 3}`}><FileText size={24} /></span><span className="pdf-badge">PDF</span></div><span className="doc-type">{d.type}</span><h2>{title(d.file)}</h2><p className="doc-reference">{d.reference}</p><div className="tags"><span>{d.date}</span><span>v{d.version}</span></div><p className="doc-status">{d.status}</p><PdfActions file={d.file} available={files.includes(d.file)} /><details><summary>Informations d’indexation</summary><p>{d.chunks_count} fragments</p></details></article>)}</div>{documents.filter(d => (!docFilter || d.type === docFilter) && `${d.file} ${d.reference} ${d.type}`.toLowerCase().includes(docQuery.toLowerCase())).length === 0 && <div className="empty-state">Aucun document ne correspond à cette recherche.</div>}</>}
        </section>}

        {view === 'search' && <section className="page search-page"><span className="eyebrow">SOUS LE CAPOT</span><h1>Explorer les passages.</h1><p className="page-intro">Observe la recherche documentaire, sans appeler le modèle de réponse.</p><form className="debug-form" onSubmit={e => { e.preventDefault(); void runSearch(); }}><label htmlFor="search-query">Question à rechercher</label><div className="debug-input"><input id="search-query" value={searchText} onChange={e => setSearchText(e.target.value)} placeholder="Quand faut-il déposer la convention de stage ?" /><button className="primary-button" disabled={searchBusy || !searchText.trim()}><Search size={17} /> {searchBusy ? 'Recherche…' : 'Rechercher'}</button></div>{params}</form><div className="notice"><Info size={17} /><span>Le score exprime une proximité, pas la fiabilité d’une réponse. Le backend utilise <code>score = 1 − distance / 2</code> avec une distance cosinus.</span></div>
          {searchError && <div className="error-box" role="alert">{searchError}</div>}
          {searchBusy && <p role="status">Recherche des passages…</p>}
          {searchData && <><div className="section-heading"><h2>{searchData.results.length} passages retrouvés</h2><span>{Math.round(searchData.latency_ms)} ms</span></div>{searchData.results.length === 0 && <p>Aucun passage pour ces paramètres.</p>}{searchData.results.map((s, index) => <article className="result-card" key={s.chunk_id}><div className="result-top"><span className="rank">{index + 1}</span><div><h3>{title(s.file)}</h3><p>{s.reference} · page {s.page}</p></div><span className="score">Proximité <strong>{s.score.toFixed(3)}</strong></span></div><p className="result-section">{s.section}</p><blockquote>{s.excerpt}</blockquote><div className="result-bottom"><button className="text-button" onClick={() => setSource(s)}>Consulter la source <ArrowRight size={15} /></button><span>{s.distance === undefined ? '' : `Distance cosinus : ${s.distance.toFixed(3)}`}</span></div></article>)}</>}
        </section>}
      </main>
    </div>
    <SourceDialog source={source} available={Boolean(source && files.includes(source.file))} close={() => setSource(null)} />
    {toast && <div className="toast" role="status"><Check size={17} />{toast}<button onClick={() => setToast('')} aria-label="Fermer la notification"><X size={16} /></button></div>}
  </div>;
}

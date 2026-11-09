import type { Source } from '../types';
// Le texte reste du texte React : pas d'injection HTML produite par le modèle.
export default function CitedAnswer({ answer, sources, onSource }: { answer: string; sources: Source[]; onSource: (source: Source) => void }) {
  return <div className="answer-text">{answer.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    // Les identifiants peuvent être 1, 4, 8 : ne jamais utiliser sources[n - 1].
    const source = match ? sources.find(item => item.id === Number(match[1])) : undefined;
    return source ? <button className="citation" key={index} onClick={() => onSource(source)} aria-label={`Source ${source.id}, ${source.reference}, page ${source.page}`}>{part}</button> : <span key={index}>{part}</span>;
  })}</div>;
}

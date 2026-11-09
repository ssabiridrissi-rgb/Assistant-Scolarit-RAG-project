import { useEffect, useRef, useState } from 'react';
import { Download, ExternalLink, FileText, X } from 'lucide-react';
import { pdfUrl } from '../api/client';
import type { Source } from '../types';
export default function SourceDialog({ source, available, close }: { source: Source | null; available: boolean; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [preview, setPreview] = useState(false);
  useEffect(() => {
    setPreview(false);
    if (source && !ref.current?.open) ref.current?.showModal();
    if (!source && ref.current?.open) ref.current.close();
  }, [source]);
  return <dialog ref={ref} className="source-dialog" onCancel={close} onClose={close} aria-labelledby="source-title" onClick={e => { if (e.target === e.currentTarget) close(); }}>
    {source && <section className="source-content">
      <header><span className="eyebrow"><FileText size={16} /> DOCUMENT SOURCE</span><button className="icon-button" onClick={close} aria-label="Fermer la source"><X /></button></header>
      <h2 id="source-title">La réponse, dans son contexte.</h2>
      <p className="source-file">{source.file}</p>
      <div className="tags"><span>Page {source.pages?.join(', ') || source.page}</span><span>{source.date}</span><span>Version {source.version}</span></div>
      <h3>{source.section || 'Extrait du document'}</h3>
      <blockquote>{source.excerpt}</blockquote>
      <dl><dt>Référence</dt><dd>{source.reference}</dd><dt>Type</dt><dd>{source.type}</dd><dt>Statut</dt><dd>{source.status}</dd></dl>
      <details><summary>Détails techniques de la recherche</summary><p>Score de proximité : {source.score.toFixed(3)}. Ce score ne mesure pas la fiabilité de la réponse.</p>{source.distance !== undefined && <p>Distance cosinus : {source.distance.toFixed(3)}</p>}</details>
      {available ? <><div className="source-actions"><a className="primary-button" target="_blank" rel="noreferrer" href={pdfUrl(source.file, source.page)}><ExternalLink size={17} /> Ouvrir le PDF · p. {source.page}</a><a className="secondary-button" href={pdfUrl(source.file, 1, true)}><Download size={17} /> Télécharger</a></div><button className="text-button" onClick={() => setPreview(!preview)}>{preview ? 'Masquer' : 'Afficher'} le PDF ici</button>{preview && <iframe title={`PDF ${source.reference}, page ${source.page}`} src={pdfUrl(source.file, source.page)} className="pdf-frame" />}<p className="micro">L’ouverture à la page dépend du lecteur PDF de ton navigateur.</p></> : <p className="notice">Le PDF n’est pas accessible pour le moment. L’extrait reste disponible. Le module PDF du backend doit être actif.</p>}
    </section>}
  </dialog>;
}

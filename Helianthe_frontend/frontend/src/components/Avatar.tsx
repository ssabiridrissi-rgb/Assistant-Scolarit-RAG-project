import type { Companion } from '../types';
export default function Avatar({ name, small = false }: { name: Companion; small?: boolean }) {
  return <span className={`avatar ${name.toLowerCase()} ${small ? 'small' : ''}`}><img src="/images/compagnons.png" alt={`Caricature de ${name}${name === 'Saad' ? ', avec lunettes' : ', avec écharpe'}`} /></span>;
}

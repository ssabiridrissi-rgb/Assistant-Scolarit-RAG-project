# Hélianthe — Saad & Mohamed

Frontend React/TypeScript pour le backend Assistant Scolarité existant.
Le dossier `frontend` contient tout le code de l'interface. Le dossier
`backend_addon` contient uniquement le module de consultation des PDF et ses tests.
Ce pack ne remplace ni votre corpus, ni votre prompt, ni vos fonctions de découpage.

## 1. Installer dans Cursor

1. Décompresser cette archive dans un dossier temporaire.
2. Dans votre projet `assistant-scolarite`, renommer le frontend Vite de départ
   en `frontend-ancien` si vous souhaitez le garder.
3. Copier le dossier `frontend` de ce pack à la racine de `assistant-scolarite`.
   Il doit être à côté de `src`, `data`, `tests` et `pyproject.toml`.
4. Dans Cursor : Terminal → Nouveau terminal. Depuis la racine du projet :

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

L'interface s'ouvre sur http://127.0.0.1:5173.
`npm ci` installe les versions exactes du fichier `package-lock.json` livré.
Le port est fixé à 5173 pour correspondre aux origines CORS déjà présentes
dans votre `api.py`. Si ce port est occupé, arrêter l'ancien serveur Vite
avec Ctrl+C dans son terminal, puis relancer.

L'adresse dans `frontend/.env` est :

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Redémarrer Vite après une modification de `.env`.
Ne jamais mettre de clé de fournisseur LLM dans une variable `VITE_`.
L'adresse d'API, elle, est publique et ne contient pas de secret.

## 2. Activer l'ouverture et le téléchargement des PDF

1. Copier `backend_addon/pdf_routes.py` dans `src/assistant_scolarite/pdf_routes.py`.
2. Ajouter ces deux lignes **tout à la fin** de `src/assistant_scolarite/api.py` :

```python
from pdf_routes import router as pdf_router
app.include_router(pdf_router)
```

Les imports simples correspondent à votre lancement actuel avec `--app-dir`.
Si vous transformez ensuite le backend en package importable, adaptez tous
ses imports ensemble ; ce pack conserve votre organisation actuelle.

3. Garder les sept PDF originaux dans `data/corpus/`, avec leurs noms actuels.
4. Depuis la racine, lancer ou redémarrer le backend dans un autre terminal :

```powershell
uv run python -m uvicorn api:app --app-dir src/assistant_scolarite --reload
```

5. Vérifier http://127.0.0.1:8000/api/files : la liste doit contenir les sept PDF.
6. Dans l'interface, cliquer sur le statut de connexion ou sur Actualiser
   dans Documents. Les boutons PDF deviennent disponibles.

Routes ajoutées :

| Route | Comportement |
|---|---|
| GET /api/files | Liste uniquement les PDF du corpus présents et autorisés |
| GET /api/files/{filename} | Ouvre le PDF original dans le navigateur |
| GET /api/files/{filename}?download=true | Télécharge le PDF original |

Un fichier inconnu, absent ou extérieur au corpus donne 404.
Le catalogue donne 503 si le dossier corpus n'existe pas.
Un paramètre `download` invalide donne 422.
Le module ne modifie aucun octet des documents. La liste fermée des fichiers
sert uniquement à autoriser leur accès ; aucune règle scolaire n'y est codée.

## 3. Utiliser l'application

- Accueil : vos deux caricatures, choix du compagnon, exemples modifiables.
- Conversation : le compagnon choisi apparaît avec un effet holographique.
  La lampe s'allume pendant l'attente et reste lumineuse après une réponse.
  Ce sont des images animées par CSS, pas des personnages 3D interactifs ni une voix.
- Les deux compagnons appellent le même système RAG : leur sélection ne change
  ni les textes scolaires, ni le prompt.
- Entrée envoie la question ; Maj+Entrée ajoute une ligne. Ctrl+K cible la saisie.
- L'historique reste en mémoire pendant la session et disparaît au rechargement.
  Il n'est pas envoyé au LLM : chaque question doit être autonome.
- Paramètres : top_k de 1 à 10 et filtre par type. Les textes modificatifs
  ajoutés par votre backend peuvent dépasser ce nombre de passages.
- [1], [4]… : un clic ouvre le passage exact retourné, puis le PDF à sa page.
  L'association se fait par `source.id` dans la réponse concernée, pas par position.
- Documents : liste réelle retournée par `/api/documents`, recherche, filtre,
  métadonnées, consultation et téléchargement. Si l'index est indisponible,
  la liste n'est pas remplacée par un faux catalogue.
- Recherche avancée : `/api/search` seulement, extraits et scores techniques.

### Pourquoi cacher le score dans le chat ?

La proximité cosinus ne mesure pas la vérité. Le score du backend
`1 - distance / 2` est montré en recherche avancée, avec la distance.
Le panneau des sources privilégie référence, date, page et extrait. Pour respecter
l'énoncé, il propose aussi « Détails techniques de la recherche », replié par défaut,
avec le score et une explication. Aucun pourcentage de confiance n'est affiché.

### Les états gérés

- Réponse documentaire : citations cliquables et sources.
- Refus : `found=false`, carte crème, texte du backend conservé exactement.
- 422 : question ou paramètres invalides.
- 502 : modèle indisponible ou réponse invalide.
- 503 : recherche/base indisponible.
- Erreur réseau/CORS : explication et possibilité de réessayer.
- Délai dépassé : message distinct ; attente maximum 240 s pour `/api/ask`.
- Envoi désactivé pendant une requête pour éviter les doublons.
- Réglage d'effets visuels sur ordinateur et respect du réglage système
  « réduire les animations » sur tous les écrans.

Le badge « Base disponible » concerne uniquement `/api/health`. Il ne prétend
pas vérifier la disponibilité d'Ollama.

## 4. Où modifier le code ?

| Fichier | Rôle |
|---|---|
| frontend/src/App.tsx | Écrans, état de session, interactions |
| frontend/src/styles.css | Palette, disposition, mobile, animations |
| frontend/src/types.ts | Contrat TypeScript des requêtes/réponses |
| frontend/src/api/client.ts | Tous les appels HTTP et erreurs |
| frontend/src/components/Avatar.tsx | Affichage d'un personnage |
| frontend/src/components/CitedAnswer.tsx | Association citation/source |
| frontend/src/components/SourceDialog.tsx | Panneau, ouverture et téléchargement PDF |
| frontend/public/images/compagnons.png | Vos caricatures sur fond transparent |
| backend_addon/pdf_routes.py | Routes PDF à copier dans le backend |

## 5. Vérifier chez vous

```powershell
# Dans frontend
npm run build
```

Copier `backend_addon/test_pdf_routes.py` dans votre dossier `tests/`, puis :

```powershell
# À la racine de assistant-scolarite
uv run python -m pytest -q
```

Les tests PDF vérifient : catalogue limité, lecture inchangée, téléchargement,
refus des fichiers non autorisés, fichier absent, dossier absent, paramètre invalide,
et lien symbolique extérieur. Le dernier peut être ignoré sur Windows si les droits
de création de liens symboliques ne sont pas disponibles.
Ces tests complètent ceux du découpage. Ils ne remplacent PAS le test de refus
hors corpus avant appel au LLM demandé dans l'énoncé.

Vérifications manuelles :
1. `/api/health` et `/api/documents` fonctionnent.
2. `/api/files` liste les sept fichiers et un téléchargement ouvre un PDF intact.
3. Question sur la convention : le backend doit répondre « 15 jours calendaires ».
4. Cliquer sur une citation, lire l'extrait, ouvrir le PDF à la page indiquée.
5. Tester un refus, une panne du modèle et la recherche sans LLM.
6. Réduire la fenêtre à 390 px, puis naviguer au clavier (Tab, Entrée, Échap).

## 6. Limites à connaître

- Le refus à tort observé précédemment sur la convention n'est pas corrigé ici.
  Une belle interface ne résout pas une erreur de génération. Le code affiche
  les résultats réels ; aucune réponse simulée ne remplace le backend.
- L'ouverture d'un PDF à une page via `#page=N` dépend du lecteur du navigateur.
  Le panneau affiche toujours le numéro de page et l'extrait. Pas de surlignage
  de coordonnées dans le PDF : le backend ne fournit pas ces coordonnées.
- Une citation existante ne prouve pas à elle seule la fidélité de l'affirmation.
- La bibliothèque actuelle reflète la collection active. Votre backend revient
  à sa collection structurelle par défaut après redémarrage.
- Ce pack est conçu pour la démonstration locale, sans comptes utilisateurs,
  authentification, mémoire longue, publication ni hébergement configuré.
- Pour un hébergement futur, une adresse 127.0.0.1 désigne la machine du visiteur :
  configurer une API HTTPS accessible et des origines CORS précises sera nécessaire.
- Ce pack ne remplace pas l'évaluation des 20 questions, le rapport et l'annexe IA.

## 7. Tracer le travail

Après validation, depuis la racine de votre dépôt :

```powershell
git add frontend src/assistant_scolarite/pdf_routes.py src/assistant_scolarite/api.py tests/test_pdf_routes.py
git diff --cached --stat
git commit -m "Ajoute interface Helianthe et consultation des PDF"
```

Corrigez le titre du commit selon votre convention. Vérifiez que `.env`,
`node_modules`, la base Chroma et les anciens dossiers de sauvegarde ne sont
pas ajoutés. Déclarer l'assistance IA pour le code et les caricatures dans l'annexe.

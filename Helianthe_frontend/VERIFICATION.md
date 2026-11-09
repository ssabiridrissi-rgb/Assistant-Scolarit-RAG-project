# Vérifications réalisées le 9 novembre 2026

- Installation npm et compilation TypeScript + Vite : réussies.
- 10 tests pytest du module PDF : réussis. Un avertissement de dépréciation
  Starlette/httpx a été affiché ; aucun échec.
- Les 7 PDF réels fournis ont été chargés dans un dossier temporaire : catalogue
  complet, ouverture et téléchargement vérifiés avec comparaison SHA-256 des octets.
- Tests navigateur Chromium automatisés : choix du compagnon, envoi avec paramètres,
  bouton désactivé pendant l'attente, citation [4] avec une seule source (numéros
  non consécutifs), lien PDF à la page, téléchargement, détail de score fermé par
  défaut, fermeture du panneau par Échap, refus exact et erreurs 422/502/503,
  filtre de documents et recherche avancée : réussis.
- Fenêtres 1440 × 1000 et 390 × 844 : captures inspectées, aucun débordement
  horizontal détecté sur l'accueil et la conversation mobile.
- Préférence système de réduction des animations : respectée.
- Aucune erreur JavaScript non interceptée pendant ces tests navigateur.

Les tests navigateur utilisent des réponses API simulées pour couvrir les états,
et ne valident pas le modèle Ollama sur votre PC. Ils ne remplacent pas les tests
du système RAG avec les questions de l'évaluation. Les captures d'accueil livrées
sont réalisées sans backend actif et affichent donc « Base indisponible ».

La compilation finale a été relancée après les derniers ajustements de présentation.
Le backend complet, sa génération et ses performances restent à vérifier chez vous.

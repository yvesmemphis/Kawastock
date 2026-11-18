# KawaStock — frontend Vue

Frontend Vue 3 + TypeScript connecté à l’API REST Django KawaStock. Le backend demeure la source de vérité pour les permissions et les règles métier.

## Lancer en local

Prérequis : Node.js et pnpm 10.18.0 (version épinglée dans `package.json`). Installer avec `pnpm install`. En développement local, laisser `VITE_API_BASE_URL` vide dans `.env.local` :

```dotenv
VITE_API_BASE_URL=
```

Le serveur Vite transmet `/api/v1/...` à Django sur `http://127.0.0.1:8001`, ce qui permet aussi d’ouvrir le frontend depuis une adresse LAN sans configuration CORS côté navigateur. Démarrer le client avec `pnpm dev:static` (port 3000). Si le backend est hébergé séparément en production, renseigner son origine sans `/api/v1` et autoriser l’origine du frontend dans Django/CORS.

## Tester sur téléphone avec ngrok

Pour tester le service worker/PWA, utilisez le build de production avec le serveur de prévisualisation (et non `dev:static`, qui n’enregistre pas le service worker). Gardez Django sur `127.0.0.1:8001`; le proxy du frontend relaie l’API, donc un seul tunnel public est nécessaire.

1. Démarrez Django dans un terminal depuis `backend` : `.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001`.
2. Dans un terminal depuis `frontend`, lancez `pnpm run build:static`, puis `pnpm run preview:static`.
3. Lancez `ngrok http 3000`. Les domaines ngrok usuels (`ngrok-free.app`, `ngrok.app` et `ngrok.io`) sont autorisés sans configuration d’adresse spécifique.
4. Ouvrez l’adresse HTTPS affichée par ngrok sur le téléphone. Chargez d’abord les pages et données à tester; vérifiez ensuite le mode avion, la mise en attente et la synchronisation après reconnexion.

Pour un domaine personnalisé qui n’utilise pas ces suffixes, renseignez son nom d’hôte dans `NGROK_HOST` dans `frontend/.env.local`, puis redémarrez le serveur. Le lien ngrok rend le frontend accessible depuis Internet : utilisez des données de test et arrêtez le tunnel après l’essai.

Si l’API doit elle-même être exposée séparément, configurez le nom d’hôte de son tunnel dans `DJANGO_ALLOWED_HOSTS`, l’origine HTTPS du frontend dans `DJANGO_CORS_ALLOWED_ORIGINS` et, si nécessaire, dans `DJANGO_CSRF_TRUSTED_ORIGINS`. Définissez alors `VITE_API_BASE_URL` à l’origine HTTPS de l’API avant le build. Ne faites pas cette exposition si le proxy frontend suffit.

## Vérification et build statique

`pnpm check` vérifie les composants Vue et TypeScript. `pnpm build:static` produit `dist/public`. Le serveur Vite sert `client/public/manus-routes.json` à `/manus-routes.json`.

## Tests du mode hors ligne

`pnpm test` exécute les tests Vitest sur la file IndexedDB et les requêtes HTTP réellement envoyées. Les données de ces tests sont simulées et isolées; aucun compte ni commerce réel n’est utilisé. Les tests backend associés peuvent être lancés depuis `backend` avec `.\.venv\Scripts\python.exe manage.py test sales.tests purchases.tests inventory.tests`.

Pour une validation manuelle sur téléphone, utilisez le build servi en HTTPS décrit plus haut :

1. Connectez-vous avec un compte de test, ouvrez le commerce de test, puis consultez en ligne les pages et données à utiliser.
2. Coupez le réseau (mode avion), créez une vente, un ajustement de stock, un achat, puis ajoutez la réception à la file.
3. Vérifiez que les opérations sont affichées comme en attente, puis réactivez le réseau et vérifiez leur synchronisation dans cet ordre. Confirmez également que la réception cible l’achat créé côté serveur.
4. Provoquez un conflit métier avec des données de test (par exemple une quantité qui ne peut plus être appliquée) et vérifiez qu’il reste affiché pour résolution; une indisponibilité réseau ou serveur doit rester en attente.

La file et les données hors ligne sont locales à l’appareil. Les jetons restent dans `sessionStorage` : ne considérez pas la session hors ligne comme persistante après fermeture de l’onglet.

## Authentification et commerce actif

La connexion utilise l’adresse e-mail et le mot de passe du backend (`/api/v1/auth/token/`). Les jetons access/refresh sont enregistrés dans `sessionStorage`; un jeton expiré est renouvelé avec le refresh token. Le profil `/auth/me/` fournit les commerces et leurs rôles; les ressources cloisonnées reçoivent `X-Shop-ID`. Les actions offertes dépendent du rôle, tandis que l’API reste l’autorité finale. Aucun secret ni jeu de données métier n’est inclus dans le build.

## Disponibilité hors ligne

En production, le service worker met en cache l’application et ses fichiers statiques. Les réponses déjà chargées du profil, des commerces, du tableau de bord, des produits, catégories, mouvements de stock, ventes, achats, fournisseurs, membres de l’équipe et rapports consultés sont conservées dans IndexedDB, séparées par utilisateur et commerce. Hors connexion, ces pages sont consultables en lecture seule avec les dernières réponses disponibles (les rapports ne sont disponibles que pour les périodes déjà consultées). Les ventes, ajustements, créations de commandes d’achat et réceptions peuvent être enregistrés dans une file locale; ils sont envoyés séquentiellement au retour du réseau avec une clé d’idempotence. Le serveur revalide chaque opération. Les erreurs métier restent visibles comme conflits et doivent être réessayées ou retirées explicitement; les erreurs réseau restent en attente. Les créations d’achat suivies d’une réception conservent leur dépendance.

Les autres pages restent en lecture seule ou indisponibles hors connexion. Les réponses locales peuvent être anciennes et se mettent à jour lorsque le réseau revient. La déconnexion supprime le cache métier et la file locale du navigateur.

Les jetons restent dans `sessionStorage` : l’accès hors ligne est prévu pendant la session du même onglet, pas après sa fermeture. Les service workers exigent aussi un contexte sécurisé : HTTPS en production, ou `localhost` en développement. Une adresse LAN en HTTP peut utiliser les données IndexedDB pendant que l’application est ouverte, mais ne permet pas de recharger l’application hors ligne; il faut servir le frontend en HTTPS pour cet usage.

## Visuels et palette
L’interface utilise une palette bleu marine et bleu clair. L’écran de connexion met en avant une commerçante dans sa boutique. Le visuel principal généré est référencé via le stockage du projet; le fichier `client/public/kawastock-shop-unsplash.jpg` sert de repli autonome dans l’archive ZIP et s’affiche automatiquement si le stockage Manus n’est pas disponible en local. Cette photo est décrite comme une commerçante africaine dans une petite boutique, à Dar es Salaam, en Tanzanie ([page photo Unsplash](https://unsplash.com/photos/a-woman-sitting-at-a-counter-in-a-store-EOkN2pRjFsg)). La [licence Unsplash](https://unsplash.com/license) autorise l’utilisation gratuite, y compris commerciale; le crédit est apprécié mais non obligatoire.

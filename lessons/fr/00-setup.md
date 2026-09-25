# Épisode 0 — Ce que nous construisons

**À l'écran :** un terminal vide, puis ce dépôt après `git clone`.

## Points à aborder

1. **Modèle vs application vs agent.** Un modèle prédit du texte. Une application
   encapsule un modèle dans une logique fixe. Un agent décide, à l'aide d'outils, de la
   prochaine action à entreprendre. Ce cours reste fermement du côté « lit des choses,
   répond, cite ses sources » de ce spectre — pas du côté « entreprend des actions
   autonomes ».
2. **Workflow vs agent.** L'essentiel de ce que nous construisons est un workflow
   déterministe (classifier → récupérer → répondre) avec une seule étape de
   planification bornée pour les questions de faisabilité de fonctionnalité. Nous
   précisons explicitement quelle partie est quoi, car « agent » n'est pas
   automatiquement meilleur que « workflow ».
3. **Prototype vs production.** Tout ici s'exécute localement, sans authentification,
   sur des données d'exemple. L'Épisode 17 dresse la liste complète de ce qui manque
   encore pour un déploiement réel — y compris la règle selon laquelle rien de tout cela
   ne touche au code ou aux données d'une entreprise réelle sans accord explicite.
4. **Développement local d'abord.** Aucune clé API payante n'est nécessaire pour suivre
   le cours — l'Épisode 2 introduit un faux `LLMClient` aux côtés d'un véritable
   adaptateur de fournisseur.
5. **Qui tape réellement.** Chaque ligne de ce dépôt a été produite en prompt-ant un
   agent de codage IA, jamais en écrivant l'implémentation à la main — et chaque leçon
   à partir de maintenant enseigne précisément le savoir qui rend cela possible : pas la
   syntaxe, mais pourquoi une conception est correcte, et comment vérifier qu'elle
   l'est. Voir [`lessons/prompting-the-build.md`](prompting-the-build.md) une fois que
   vous avez une bonne idée de quelques épisodes — cela concerne l'ensemble du cours,
   pas une étape en particulier.

## Visite guidée

- `sample_app/loopline/` — le SaaS fictif de gestion de tickets sur lequel le copilote
  répondra à des questions. Parcourez `docs/`, `app/models.py`, `schema.sql`, et
  `logs/app.log`.
- `src/saas_copilot/` — le copilote lui-même. Aujourd'hui, ce n'est que `config.py` et
  un endpoint `/health` ; tout le reste sera construit épisode après épisode.
- L'historique des commits jusqu'ici *est* la première leçon : squelette →
  application de Loopline → logs → docs → une correction de bug
  (`git log --oneline`) → cette leçon.

## À faire

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

python -m sample_app.loopline.app.seed
python -m uvicorn sample_app.loopline.app.main:app --reload --port 8001 &
curl http://localhost:8001/health

python -m uvicorn saas_copilot.api.main:app --reload --port 8000 &
curl http://localhost:8000/health

pytest
```

Vous devriez voir 3 tests passer et 1 `xfail` — c'est le bug de notification injecté
volontairement, pas un checkout cassé.

## Exercice

Reproduisez le bug injecté à la main : `POST /tickets/4/comments` avec un corps du
type `{"author_id": 2, "body": "test"}`. Ensuite, sans aucun outillage, trouvez la
ligne de code exacte qui déclenche le `KeyError` et la ligne de seed exacte qui
manque. C'est la forme de toute réponse que le copilote devra produire plus tard : une
affirmation plus une citation. L'Épisode 6 construit l'outil qui fait cela
automatiquement.

## Suite

L'Épisode 1 ajoute des modèles typés et une véritable suite de tests autour du code du
copilote lui-même.

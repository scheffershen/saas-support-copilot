# Épisode 1 — Fondations du projet Python

> **Note (ajoutée à l'Épisode 8) :** `Document.citation` omettait à l'origine le
> suffixe `#chunk-N` lorsque `chunk_id` valait 0, traitant 0 comme « ce document n'a
> pas été découpé en chunks ». Une fois que l'Épisode 8 ajoute un véritable découpage
> en chunks, le chunk 0 est un premier chunk authentique, pas une sentinelle — la
> citation l'inclut désormais toujours. Les concepts `Document`/`SourceFile`
> ci-dessous sont inchangés ; seule la sortie exacte de cette propriété l'est.

**À l'écran :** `src/saas_copilot/models.py`, vide, dans un éditeur ; le dépôt de
l'Épisode 0 s'exécutant dans un terminal divisé.

## Objectif d'apprentissage

Chaque épisode suivant fait transiter des données entre des fonctions, des outils et
le LLM. Définissez dès maintenant la forme de ces données, avec des types et des
tests, pour que rien en aval n'ait à deviner.

## Points à aborder

1. **Packages.** `src/saas_copilot/` est un véritable package installable —
   `pyproject.toml` le déclare (`packages = ["src/saas_copilot"]`), et
   `pip install -e ".[dev]"` de l'Épisode 0 est ce qui permet à
   `from saas_copilot.models import Document` de fonctionner depuis n'importe où, y
   compris depuis `tests/`.
2. **Annotations de type.** Chaque champ ci-dessous est annoté. Ce n'est pas de la
   décoration — c'est ce qui permet à votre éditeur de détecter une faute de frappe
   dès aujourd'hui, et ce qui permet à la sortie structurée du LLM (Épisode 3) de se
   valider par rapport à un schéma au lieu d'espérer que le modèle a produit la bonne
   forme.
3. **Dataclasses.** `@dataclass(frozen=True)` nous donne gratuitement l'égalité, le
   `repr`, et l'immutabilité. L'immutabilité compte particulièrement ici : une fois
   que le copilote a récupéré un `Document` pour répondre à une question, rien plus
   loin dans le pipeline ne devrait pouvoir modifier discrètement son contenu sous la
   citation que vous êtes sur le point d'afficher.
4. **Exceptions.** `SourceFile.line()` lève une `IndexError` avec un message précis et
   lisible plutôt que de laisser échapper une simple erreur d'index brute. Les outils
   de l'Épisode 5 interceptent exactement ce schéma et le transforment en une erreur
   d'appel d'outil propre plutôt qu'en une trace de pile atteignant l'utilisateur.
5. **Bases de l'asynchrone.** Les endpoints de Loopline et le `/health` du copilote
   sont encore de simples `def` — il n'y a pas encore d'E/S, donc `async def`
   n'apporterait rien. L'Épisode 5 transforme les fonctions d'appel d'outils en
   `async def`, car elles effectueront de véritables lectures de fichiers, de base de
   données et de logs, et nous ne voulons pas qu'un appel d'outil lent bloque toutes
   les autres requêtes.
6. **venv / pyproject.toml / verrouillage des dépendances.** Rappel de l'Épisode 0 :
   les plages `>=` dans `pyproject.toml` conviennent pour un cours que vous relancez
   aujourd'hui, mais un déploiement réel (Épisode 16) veut un ensemble de versions
   exact et verrouillé, pour que « ça marche sur ma machine » ne vous morde pas en
   production.
7. **pytest.** `tests/unit/test_models.py` établit le schéma pour le reste du cours :
   un chemin nominal (happy path) et un chemin d'échec par comportement, pas
   simplement un test par fonction.

## Implémentation

- [`src/saas_copilot/models.py`](../../src/saas_copilot/models.py) — `Document`, `SourceFile`.
- [`tests/unit/test_models.py`](../../tests/unit/test_models.py) — 6 tests.

## Exécution

```bash
pytest tests/unit/test_models.py -v
```

## Cas d'échec (à montrer en direct)

```pycon
>>> from saas_copilot.models import SourceFile
>>> f = SourceFile(path="app/notifications.py", language="python", content="a\nb\nc")
>>> f.line(10)
IndexError: app/notifications.py has no line 10 (file has 3 lines)
```

## Exercice

Ajoutez un troisième modèle, `LogEntry` (`path`, `line_number`, `level`, `message`),
avec la même discipline : une exception claire et précise en cas d'entrée invalide
plutôt qu'un simple plantage ou un `None` silencieux. Écrivez-le, puis écrivez ses
tests avant de continuer. Vous le brancherez pour de vrai dans l'outil de lecture de
logs de l'Épisode 5.

## Suite

L'Épisode 2 effectue le plus petit appel LLM réel possible, derrière un commutateur
de fournisseur factice/réel, afin que le cours continue de fonctionner sans clé API.

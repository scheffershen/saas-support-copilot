# Épisode 5 — Outils et contrats d'outils sûrs

> **Note :** L'épisode 2 annonçait que ces fonctions deviendraient des `async def`,
> « parce qu'elles feront de vraies lectures de fichiers, de base de données et de
> logs ». En les construisant, une simple fonction synchrone plus le wrapper de
> timeout à pool de threads de `ToolRegistry` s'est révélée plus simple - pas besoin
> de boucle d'événements dans les tests, et cela résout le même problème « ne pas
> laisser un appel lent tout bloquer » pour ce volume d'E/S. Le vrai `async def`
> apparaît quand même, mais à la couche où il gagne réellement sa place : le serveur
> FastAPI de l'épisode 14, qui gère de nombreuses requêtes concurrentes à la fois -
> et même là, FastAPI exécute automatiquement les fonctions de route synchrones dans
> un pool de threads, exactement le même schéma que `ToolRegistry` applique déjà ici
> à la main. Les plans changent quand ils rencontrent le vrai problème ; c'est ce qui
> s'est passé ici, pas une incohérence à camoufler.

**À l'écran :** `sample_app/loopline/` dans une arborescence de fichiers — docs/, app/,
et le `git log` de ce dépôt lui-même — les quatre éléments auxquels le copilote est
sur le point de recevoir un accès en lecture.

## Objectif d'apprentissage

Donner au copilote quelque chose à réellement regarder. Chaque outil construit ici est
en lecture seule, ses arguments sont validés, et il est confiné à une racine
en liste blanche — le contrat compte plus que chaque outil pris individuellement, parce
que la boucle d'agent de l'épisode 6 fera entièrement confiance à cette couche.

## Points à aborder

1. **Schémas d'outils.** Chaque outil reçoit un petit modèle Pydantic `*Args`
   (`SearchDocsArgs`, `ReadSourceArgs`, ...) — la même discipline « valider avant de
   faire confiance » que `Answer` à l'épisode 3, mais appliquée aux *entrées* des
   outils plutôt qu'aux *sorties* du LLM.
2. **Validation des arguments.** `SearchCodeArgs` rejette une regex invalide au niveau
   du schéma, avant même que `search_code()` ne s'exécute — `field_validator`
   transforme un « plantage profond dans la fonction » en un « rejet à la porte, avec
   un message clair ».
3. **Outils en lecture seule vs. outils modifiants.** `ToolRegistry.register()` refuse
   tout ce qui n'est pas marqué `read_only=True`. Il n'existe actuellement aucun moyen
   d'enregistrer un outil modifiant dans cette base de code — pas « le prompt dit de
   ne pas le faire », un chemin de code qui n'existe tout simplement pas.
4. **Listes blanches.** `resolve_within_root()` est la véritable frontière : chaque
   outil de fichier est lié à un répertoire via `functools.partial` *au moment de
   l'enregistrement* (`tools/__init__.py`), jamais passé comme argument fourni par
   l'appelant. Aucun argument qu'un LLM pourrait choisir ne peut rediriger un outil en
   dehors de l'endroit où le développeur l'a placé.
5. **Timeouts.** `ToolRegistry.call()` fait passer chaque gestionnaire par un
   `future.result(timeout=...)` de pool de threads — portable (les timeouts basés sur
   les signaux n'existent pas sous Windows) et uniforme (aucun outil individuel n'a à
   se souvenir de l'implémenter).
6. **Autorisation.** Deux niveaux différents, à ne pas confondre : les racines
   en liste blanche de cet épisode relèvent d'une autorisation de niveau *système* (ce
   que le processus a le droit de toucher, point final). L'autorisation de niveau
   *utilisateur* — ce que le rôle d'une personne donnée la laisse voir — c'est
   l'épisode 10.
7. **Limites de résultats.** `search_docs`/`search_code` plafonnent le nombre de
   résultats, `read_source` tronque au-delà de 20 000 caractères, `list_files` refuse
   de renvoyer plus de 200 entrées plutôt que de déverser silencieusement une
   arborescence entière dans le contexte du modèle.

## Deux vrais bugs, trouvés en construisant ceci

Aucun des deux n'a été planté pour la leçon — tous deux ont surgi en exécutant
réellement les tests, ce qui est bien tout l'intérêt de les exécuter.

**Un vrai piège de sécurité, démontré avant même d'être gardé contre.**
`Path("allowed/root") / "/etc/passwd"` en pathlib pur s'évalue en
`Path("/etc/passwd")` — l'opérateur `/` *jette le côté gauche* quand le côté droit est
absolu. Un garde-fou de chemin qui ne ferait qu'un contrôle de préfixe
(`candidate.resolve().is_relative_to(root)`, vérifié *après* une jointure naïve)
aurait déjà perdu la racine au moment où il s'exécute. `resolve_within_root()` vérifie
`Path(relative_path).is_absolute()` en premier, avant toute jointure, précisément à
cause de ça.

```pycon
>>> from pathlib import Path
>>> from saas_copilot.tools.source import read_source
>>> read_source("C:/Windows/win.ini", root=Path("sample_app/loopline/app"))
ToolError: path must be relative, got an absolute path: 'C:/Windows/win.ini'
```

**Un vrai bug dans `list_files`, capturé par son propre test.** La première version
résolvait `start` (via `resolve_within_root()`, qui renvoie un chemin absolu) mais
calculait les résultats avec `p.relative_to(root)` en utilisant le `root`
*original, non résolu*. Mélanger un chemin absolu résolu avec un chemin relatif non
résolu dans `relative_to()` lève une `ValueError` — pathlib ne traite pas un chemin et
sa propre forme résolue comme interchangeables à cet endroit.
`test_list_files_scoped_to_a_subdirectory` a échoué honnêtement ; le correctif a
consisté à résoudre `root` une seule fois, en amont, et à utiliser cette valeur
partout dans la fonction. Voir le commit `feat(copilot): search_docs, read_source,
search_code, list_files tools` pour l'échec complet et le correctif.

## Implémentation

- [`src/saas_copilot/tools/base.py`](../../src/saas_copilot/tools/base.py) — `ToolError`, `resolve_within_root`.
- [`src/saas_copilot/tools/registry.py`](../../src/saas_copilot/tools/registry.py) — `ToolSpec`, `ToolRegistry`.
- [`src/saas_copilot/tools/docs.py`](../../src/saas_copilot/tools/docs.py) — `search_docs`.
- [`src/saas_copilot/tools/source.py`](../../src/saas_copilot/tools/source.py) — `read_source`, `search_code`.
- [`src/saas_copilot/tools/files.py`](../../src/saas_copilot/tools/files.py) — `list_files`.
- [`src/saas_copilot/tools/git_history.py`](../../src/saas_copilot/tools/git_history.py) — `git_log`, `git_show` (subprocess, liste d'arguments uniquement, plus une garde stricte hexadécimal-seul sur `commit` — git traite un `-` initial comme un indicateur, donc un simple passage direct laisserait une valeur de commit forgée être lue comme une option plutôt que comme une référence).
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `build_default_registry()`.

## Exécution

```bash
pytest tests/unit/test_tools_base.py tests/unit/test_tools_registry.py \
       tests/unit/test_tools_docs.py tests/unit/test_tools_source.py \
       tests/unit/test_tools_files.py tests/unit/test_tools_git_history.py \
       tests/unit/test_tools_default_registry.py -v
```

Chaque fixture utilisée est réelle, pas synthétique : `search_code` trouvant
`"KeyError"` à `notifications.py:26` est exactement la ligne que l'épisode 0 a
vérifiée en direct dans une trace d'erreur ; `git_log` sur `services.py` renvoie la
véritable paire de commits feat-puis-fix de ce dépôt.

## Exercice

`ToolRegistry.call()` laisse actuellement Pydantic ignorer silencieusement les clés
inattendues dans `raw_args` (voir `test_call_rejects_extra_arguments_not_in_the_schema`
— il ne rejette en réalité rien du tout, le nom décrit le comportement actuel, pas une
garantie). Ajoutez `model_config = ConfigDict(extra="forbid")` à chaque schéma
`*Args`, et modifiez le nom et l'assertion de ce test pour refléter le nouveau
comportement, plus strict. Puis demandez-vous lequel est le plus correct pour un
schéma exposé à un LLM : abandonner silencieusement les champs que le modèle a
inventés, ou les rejeter bruyamment. (Il y a une vraie réponse, et l'épisode 13 est un
indice.)

## Suite

L'épisode 6 construit la boucle d'agent : `classify()` choisit un domaine, la boucle
choisit des outils dans ce registre, et le spécialiste `bug` doit rassembler de
véritables preuves — un appel à `read_source` ou `search_code`, pas une supposition —
avant d'avoir le droit de répondre.

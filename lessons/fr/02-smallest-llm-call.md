# Épisode 2 — Le plus petit appel LLM utile

**À l'écran :** `src/saas_copilot/llm/`, vide, puis construit fichier par fichier.

## Objectif d'apprentissage

Chaque fournisseur — hébergé ou local — parle à peu près le même langage : une liste
de messages en entrée, un message et un nombre de tokens en sortie. Construisez cette
forme une seule fois, derrière une interface, avant de toucher à une véritable clé
API.

## Points à aborder

1. **Messages.** Un appel de chat est une liste de tours `{role, content}` (`system`,
   `user`, `assistant`) — `Message` dans `llm/base.py`. Le message système contient
   les instructions, les messages utilisateur constituent la conversation ; rien dans
   cette liste n'est intrinsèquement fiable, ce qui compte énormément une fois que
   l'Épisode 13 y insère des documents récupérés.
2. **Prompts, tokens, fenêtres de contexte.** Un prompt n'est que la liste des
   messages rendue en texte ; les tokens sont l'unité du fournisseur à la fois pour le
   coût et pour le budget de la fenêtre de contexte. `FakeLLMClient` estime les tokens
   à ~4 caractères/token — suffisant pour raisonner sur des budgets, faux en tant que
   véritable tokenizer (l'Épisode 15 revient sur ce point pour un vrai suivi des
   coûts).
3. **Température.** `complete(..., temperature=0.2)` — une température basse pour un
   copilote de support censé répondre de manière cohérente à partir de preuves, pas
   faire du brainstorming.
4. **API des fournisseurs.** `OpenAICompatibleClient` parle du HTTP brut
   (`POST /chat/completions`) plutôt que d'encapsuler un SDK propriétaire, car c'est
   exactement la forme qu'Ollama, LM Studio, et vLLM exposent aussi en mode
   « compatible OpenAI » — changer de fournisseur plus tard se résume à un `base_url`
   et un `model`, pas à une réécriture.
5. **Délais d'expiration et nouvelles tentatives.** Le client réel retente une fois en
   cas de timeout puis abandonne avec une `LLMTimeoutError` claire ; un statut
   d'erreur HTTP (mauvaise clé, mauvais modèle) n'est *pas* retenté, car retenter un
   401 cinq fois ne fait que gaspiller cinq timeouts à redécouvrir ce que la première
   tentative avait déjà révélé.
6. **Abstraction de fournisseur.** `LLMClient` est une ABC avec une seule méthode.
   Rien d'autre dans cette base de code n'a le droit d'importer `httpx` ni de savoir
   ce que signifie « compatible OpenAI » — ce savoir reste confiné dans `llm/`.

## Implémentation

- [`src/saas_copilot/llm/base.py`](../../src/saas_copilot/llm/base.py) — `Message`,
  `Usage`, `LLMResponse`, `LLMError`, `LLMTimeoutError`, `LLMClient`.
- [`src/saas_copilot/llm/fake.py`](../../src/saas_copilot/llm/fake.py) — `FakeLLMClient`.
- [`src/saas_copilot/llm/openai_compatible.py`](../../src/saas_copilot/llm/openai_compatible.py) — `OpenAICompatibleClient`.
- [`src/saas_copilot/llm/__init__.py`](../../src/saas_copilot/llm/__init__.py) — `build_llm_client(settings)`.
- Config : `LLM_BASE_URL` / `LLM_MODEL` ajoutés à `.env.example` et `Settings`.

## Exécution

```bash
pytest tests/unit/test_llm.py -v
```

Pointez-le vers un véritable fournisseur (optionnel, nécessite une clé) :

```bash
export LLM_PROVIDER=openai LLM_API_KEY=sk-...
python -c "
from saas_copilot.config import settings
from saas_copilot.llm import build_llm_client
from saas_copilot.llm.base import Message
client = build_llm_client(settings)
print(client.complete([Message(role='user', content='Say hi in five words.')]).content)
"
```

## Cas d'échec (à montrer en direct)

`tests/unit/test_llm.py` prouve les deux chemins d'échec *sans jamais toucher au
réseau*, en utilisant `httpx.MockTransport` pour se substituer au fournisseur :

- `test_openai_compatible_client_retries_on_timeout_then_succeeds` — le premier appel
  expire, le second réussit, l'appelant ne voit jamais l'échec.
- `test_openai_compatible_client_raises_llm_timeout_error_after_exhausting_retries` —
  chaque appel expire → une `LLMTimeoutError` propre, et non une exception `httpx`
  brute qui fuiterait hors de l'abstraction.
- `test_openai_compatible_client_raises_llm_error_on_http_status_error` — un 401 lève
  une erreur immédiatement, sans nouvelle tentative.

## Exercice

Ajoutez un paramètre `max_tokens: int | None = None` à `LLMClient.complete()`.
Propagez-le dans le payload d'`OpenAICompatibleClient` (uniquement quand il n'est pas
`None`) ; faites en sorte que `FakeLLMClient` l'accepte et l'ignore. Écrivez un test
par client prouvant que le changement de signature n'a cassé aucune des deux
implémentations. C'est le schéma récurrent de l'extension d'une interface : chaque
implémentation doit s'aligner, et un test doit le prouver.

## Suite

L'Épisode 3 enveloppe la sortie de `LLMClient` dans un `Answer` typé et validé — et
montre précisément pourquoi un system prompt demandant poliment du JSON n'équivaut
pas à une garantie.

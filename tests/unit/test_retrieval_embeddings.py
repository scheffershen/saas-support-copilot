import math

from saas_copilot.retrieval.embeddings import cosine_similarity
from saas_copilot.retrieval.hashing_embeddings import DEFAULT_DIMENSIONS, HashingEmbeddingClient


def test_embed_is_deterministic() -> None:
    client = HashingEmbeddingClient()
    assert client.embed("how do I create a ticket") == client.embed("how do I create a ticket")


def test_embed_returns_a_unit_vector_for_non_empty_text() -> None:
    client = HashingEmbeddingClient()
    vector = client.embed("some real text")
    magnitude = math.sqrt(sum(v * v for v in vector))
    assert math.isclose(magnitude, 1.0, rel_tol=1e-9)


def test_embed_empty_text_is_the_zero_vector() -> None:
    vector = HashingEmbeddingClient().embed("")
    assert vector == tuple([0.0] * DEFAULT_DIMENSIONS)


def test_embed_respects_the_configured_dimensions() -> None:
    client = HashingEmbeddingClient(dimensions=16)
    assert len(client.embed("hello world")) == 16


def test_texts_sharing_words_are_more_similar_than_unrelated_texts() -> None:
    client = HashingEmbeddingClient()
    a = client.embed("how do I create a support ticket")
    b = client.embed("how do I create a new ticket for support")
    c = client.embed("the quarterly revenue report is due Friday")

    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_cosine_similarity_of_identical_vectors_is_one() -> None:
    v = (1.0, 2.0, 3.0)
    assert math.isclose(cosine_similarity(v, v), 1.0, rel_tol=1e-9)


def test_cosine_similarity_of_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == 0.0


def test_cosine_similarity_with_a_zero_vector_is_zero_not_a_crash() -> None:
    assert cosine_similarity((0.0, 0.0), (1.0, 1.0)) == 0.0

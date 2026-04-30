"""Local embedding via fastembed (BAAI/bge-small-en-v1.5)."""
import sys

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_MODEL = None


def _get_model():
    """Lazily load the embedding model."""
    global _MODEL
    if _MODEL is None:
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise RuntimeError(
                "fastembed not installed. Run: pip install fastembed\n"
                "This is needed for local, offline embedding generation."
            )
        _MODEL = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _MODEL


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings. Returns list of 384-dim L2-normalized vectors.

    First call lazily loads the model (~30MB download to ~/.cache/fastembed/).
    """
    if not texts:
        return []
    try:
        model = _get_model()
        return [list(v) for v in model.embed(texts)]
    except Exception as e:
        print(f"Embedding error: {e}", file=sys.stderr)
        raise


def embed_query(query: str) -> list[float]:
    """Embed a single query string with the recommended bge prefix."""
    prefix = "Represent this sentence for searching relevant passages: "
    return embed_texts([prefix + query])[0]


def chunk_text(body: str, *, target_words: int = 500, overlap_words: int = 50) -> list[str]:
    """Word-based chunker.

    If body has fewer than target_words words, returns [body].
    Otherwise returns sliding window with overlap.
    """
    words = body.split()
    if len(words) <= target_words:
        return [body]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start = end - overlap_words
        if start < 0:
            start = 0
        if start >= len(words):
            break

    return chunks

import numpy as np


def rank_segments(reference: np.ndarray, vectors: np.ndarray, top_k: int):
    reference = np.asarray(reference, dtype=np.float32)
    vectors = np.asarray(vectors, dtype=np.float32)
    if reference.ndim != 1 or vectors.ndim != 2 or vectors.shape[1] != reference.size:
        raise ValueError("Embedding dimension mismatch.")
    if not np.isfinite(reference).all() or not np.isfinite(vectors).all():
        raise ValueError("Embeddings must contain finite values.")
    norm = np.linalg.norm(reference)
    norms = np.linalg.norm(vectors, axis=1)
    if norm < 1e-8 or (norms < 1e-8).any():
        raise ValueError("Embeddings must have a nonzero norm.")
    if not 1 <= top_k <= 1000:
        raise ValueError("top_k must be between 1 and 1000.")
    scores = np.clip((vectors @ reference) / (norms * norm), -1., 1.)
    order = np.argsort(-scores, kind="stable")[:top_k]
    return [(int(index), float(scores[index])) for index in order]

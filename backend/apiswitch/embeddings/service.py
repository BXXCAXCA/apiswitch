from dataclasses import dataclass


@dataclass
class EmbeddingRequest:
    model: str
    input: str | list[str]


@dataclass
class EmbeddingResult:
    model: str
    vectors: list[list[float]]
    cache_hit: bool = False


async def create_embedding(request: EmbeddingRequest) -> EmbeddingResult:
    inputs = request.input if isinstance(request.input, list) else [request.input]
    return EmbeddingResult(model=request.model, vectors=[[0.0, 0.0, 0.0] for _ in inputs])

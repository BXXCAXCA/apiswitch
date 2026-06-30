from dataclasses import dataclass


@dataclass
class ImageUnderstandingRequest:
    image_ref: str
    prompt: str | None = None


async def describe_image(request: ImageUnderstandingRequest) -> str:
    return "Stage-1 image understanding placeholder."

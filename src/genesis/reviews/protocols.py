from typing import Any, Protocol

from genesis.reviews.models import AIReviewResult, ReviewType


class ReviewEngine(Protocol):
    review_type: ReviewType

    async def review(self, subject: dict[str, Any]) -> AIReviewResult: ...

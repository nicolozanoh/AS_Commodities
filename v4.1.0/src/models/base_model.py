from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SentimentResult:
    text: str
    label: str
    model: str
    score: float = None
    confidence: float = None
    date: datetime = field(default_factory=datetime.now)

class DailyRateLimitException(Exception):
    """Raised when the API rate limit is exceeded."""
    def __init__(self, message="Daily Rate limit exceeded. Please wait before retrying."):
        self.message = message
        super().__init__(self.message)

class BaseModel(ABC):

    def __init__(self, name: str):
        self.model = None
        self.name = name

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def predict(self, text: str) -> SentimentResult:
        pass

    @abstractmethod
    def predict_batch(self, texts: list[str]) -> list[tuple[str, float]]:
        pass


    
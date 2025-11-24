from typing import List
from core.models import Channel
from infra.db.favorites_repository import FavoritesRepository

class FavoritesService:
    def __init__(self, repository: FavoritesRepository):
        self.repository = repository

    def add_favorite(self, channel: Channel) -> bool:
        return self.repository.add_favorite(channel)

    def remove_favorite(self, url: str) -> bool:
        return self.repository.remove_favorite(url)

    def get_favorites(self) -> List[Channel]:
        return self.repository.get_favorites()

    def is_favorite(self, url: str) -> bool:
        return self.repository.is_favorite(url)

"""Payment provider contract. Local provider never transfers money."""

from typing import Protocol
from uuid import UUID


class PaymentProvider(Protocol):
    mode: str

    def pay(self, order_id: UUID, amount_fen: int) -> str: ...
    def refund(self, reference: str, amount_fen: int) -> None: ...


class LocalPaymentProvider:
    mode = "local_simulated"

    def pay(self, order_id: UUID, amount_fen: int) -> str:
        return f"local_{order_id}"

    def refund(self, reference: str, amount_fen: int) -> None:
        if not reference.startswith("local_"):
            raise ValueError("Cannot refund an unrelated payment provider")

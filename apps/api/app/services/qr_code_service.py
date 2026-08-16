"""
Module 6 -- QR code token generation for Plant Registration (FR-5,
`docs/architecture/02-low-level-design.md`'s `QRCodeService` internal
component of the "Plants (Digital Twin)" module).

This generates and guarantees uniqueness of the *token* the QR code
encodes (`plants.qr_code_token`, `UNIQUE` per migration 0001) -- rendering
that token into an actual scannable PNG/SVG image is a presentation
concern for Phase 7 (frontend) / a future print-label feature, not
something a backend token generator should own. What "QR generation
works" (the module's own pre-completion validation item) means at this
layer: every registered Plant gets a real, unique, collision-checked
token deterministically derivable back to a QR code by any standard QR
library the frontend chooses.
"""
from __future__ import annotations

import secrets

from app.repositories.interfaces import PlantRepository

_TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Crockford-ish: no 0/O/1/I ambiguity on a printed label
_TOKEN_LENGTH = 12
_MAX_ATTEMPTS = 5


class QRCodeService:
    """
    Stateless generator, injected with a `PlantRepository` only to check
    uniqueness against real data -- not to persist anything itself
    (`PlantService.register_plant` owns writing the Plant row that
    carries the generated token).
    """

    def __init__(self, plant_repo: PlantRepository) -> None:
        self._plants = plant_repo

    async def generate_unique_token(self) -> str:
        for _ in range(_MAX_ATTEMPTS):
            token = self._generate_candidate()
            if await self._plants.get_by_qr_token(token) is None:
                return token
        # Vanishingly unlikely at this alphabet/length (33^12 keyspace) --
        # a real collision after 5 tries almost certainly means something
        # else is wrong (e.g. a fake repo seeded with a fixed token in a
        # tight test loop), so surfacing a clear error beats silently
        # returning a non-unique token.
        raise RuntimeError("Could not generate a unique QR code token after 5 attempts.")

    @staticmethod
    def _generate_candidate() -> str:
        return "NVA-" + "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LENGTH))

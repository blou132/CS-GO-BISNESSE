import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FXRate

ECB_BASE_URL = "https://data-api.ecb.europa.eu"
ECB_PATH = "/service/data/EXR/D.USD+GBP+JPY+CHF+CNY.EUR.SP00.A"
ECB_SOURCE = "ECB Data Portal EXR daily reference rates"
SUPPORTED_ECB_CURRENCIES = ("USD", "GBP", "JPY", "CHF", "CNY")
MAX_RESPONSE_BYTES = 64 * 1024


class ECBRateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ECBReferenceRate:
    currency: str
    currency_per_eur: Decimal
    observed_at: datetime


class ECBRateClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(follow_redirects=False, timeout=15)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_latest(self) -> list[ECBReferenceRate]:
        try:
            response = await self._client.get(
                ECB_BASE_URL + ECB_PATH,
                params={
                    "lastNObservations": "1",
                    "detail": "dataonly",
                    "format": "csvdata",
                },
                headers={"Accept": "text/csv"},
            )
        except (httpx.TimeoutException, httpx.RequestError) as error:
            raise ECBRateError("Service de taux BCE indisponible.") from error
        if response.status_code != 200:
            raise ECBRateError(f"Réponse BCE inattendue (HTTP {response.status_code}).")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ECBRateError("Réponse BCE anormalement volumineuse.")
        return parse_ecb_csv(response.text)


def parse_ecb_csv(payload: str) -> list[ECBReferenceRate]:
    try:
        rows = list(csv.DictReader(io.StringIO(payload)))
    except (csv.Error, UnicodeError) as error:
        raise ECBRateError("CSV BCE invalide.") from error
    result: dict[str, ECBReferenceRate] = {}
    required = {
        "FREQ",
        "CURRENCY",
        "CURRENCY_DENOM",
        "EXR_TYPE",
        "EXR_SUFFIX",
        "TIME_PERIOD",
        "OBS_VALUE",
    }
    if not rows or not required.issubset(rows[0]):
        raise ECBRateError("Colonnes BCE requises absentes.")
    for row in rows:
        currency = row["CURRENCY"].upper()
        if currency not in SUPPORTED_ECB_CURRENCIES:
            continue
        if (
            row["FREQ"] != "D"
            or row["CURRENCY_DENOM"] != "EUR"
            or row["EXR_TYPE"] != "SP00"
            or row["EXR_SUFFIX"] != "A"
        ):
            raise ECBRateError("Série BCE inattendue.")
        try:
            value = Decimal(row["OBS_VALUE"])
            observed_at = datetime.strptime(row["TIME_PERIOD"], "%Y-%m-%d").replace(tzinfo=UTC)
        except (InvalidOperation, ValueError) as error:
            raise ECBRateError("Valeur ou date BCE invalide.") from error
        if not value.is_finite() or value <= 0:
            raise ECBRateError("Taux BCE non positif ou non fini.")
        result[currency] = ECBReferenceRate(currency, value, observed_at)
    missing = set(SUPPORTED_ECB_CURRENCIES) - result.keys()
    if missing:
        raise ECBRateError(f"Taux BCE manquants : {', '.join(sorted(missing))}.")
    return [result[currency] for currency in SUPPORTED_ECB_CURRENCIES]


def persist_ecb_rates(session: Session, rates: list[ECBReferenceRate]) -> int:
    created = 0
    for value in rates:
        existing = session.scalar(
            select(FXRate.id).where(
                FXRate.base_currency == "EUR",
                FXRate.quote_currency == value.currency,
                FXRate.source == ECB_SOURCE,
                FXRate.rate_type == "REFERENCE",
                FXRate.observed_at == value.observed_at,
            )
        )
        if existing is not None:
            continue
        session.add(
            FXRate(
                base_currency="EUR",
                quote_currency=value.currency,
                rate=value.currency_per_eur,
                source=ECB_SOURCE,
                observed_at=value.observed_at,
                rate_type="REFERENCE",
            )
        )
        created += 1
    session.flush()
    return created

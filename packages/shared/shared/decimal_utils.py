"""Decimal tabanli yardimci fonksiyonlar.

Binance USDS-M Futures API'si fiyat/miktar degerlerini string olarak
dondurur ve stepSize / tickSize gibi degerlerle hizalanmis miktarlar
bekler. Bu modul, tum sistemde binary float kullanimini engellemek icin
tek referans noktasidir.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal, InvalidOperation

ZERO = Decimal("0")


def to_decimal(value: Decimal | str | int | float | None, default: str = "0") -> Decimal:
    """Herhangi bir sayisal degeri guvenli sekilde Decimal'e cevirir.

    float girisi kabul edilir (ornegin Binance kline verisi bazi durumlarda
    float olarak gelebilir) ancak dogrudan Decimal(float) yapmak hassasiyet
    hatasina yol acabileceginden once str()'e cevrilir.
    """

    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:  # pragma: no cover - savunma amacli
        raise ValueError(f"Gecersiz sayisal deger: {value!r}") from exc


def quantize_step(value: Decimal, step: Decimal, rounding: str = ROUND_DOWN) -> Decimal:
    """``value`` degerini ``step`` adimina yuvarlar (varsayilan: asagi yuvarlama).

    Binance LOT_SIZE / MARKET_LOT_SIZE filtresindeki ``stepSize`` degeri icin
    kullanilir. stepSize sifir veya negatif olamaz.
    """

    if step <= ZERO:
        raise ValueError("step degeri pozitif olmalidir")
    steps = (value / step).to_integral_value(rounding=rounding)
    result = steps * step
    places = decimal_places(step)
    return Decimal(f"{result:.{places}f}")


def quantize_price(value: Decimal, tick_size: Decimal, rounding: str = ROUND_HALF_UP) -> Decimal:
    """Fiyati ``tick_size`` degerine yuvarlar (PRICE_FILTER)."""

    if tick_size <= ZERO:
        raise ValueError("tick_size degeri pozitif olmalidir")
    ticks = (value / tick_size).to_integral_value(rounding=rounding)
    return ticks * tick_size


def decimal_places(step: Decimal) -> int:
    """Bir step/tick degerinin ondalik basamak sayisini dondurur."""

    exponent = step.normalize().as_tuple().exponent
    if isinstance(exponent, int) and exponent < 0:
        return -exponent
    return 0


def round_up_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Minimum gereksinimleri karsilamak icin yukari yuvarlama (ornegin
    gerekli minimum teminati hesaplarken kullanilir)."""

    return quantize_step(value, step, rounding=ROUND_UP)


def safe_div(numerator: Decimal, denominator: Decimal, default: Decimal = ZERO) -> Decimal:
    """Sifira bolme hatasina karsi guvenli bolme islemi."""

    if denominator == ZERO:
        return default
    return numerator / denominator


def format_decimal_plain(value: Decimal) -> str:
    """Binance REST API icin bilimsel gosterim kullanmadan decimal string uretir."""

    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"

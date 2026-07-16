"""ROI tabanli take-profit / stop-loss fiyat hesaplamalari.

Sartname bolum 11: Admin panelindeki kar/zarar oranlari, fiyat degisim
yuzdesi degil, KALDIRACLI POZISYON ROI hedefidir. Bu modul; giris fiyati,
miktar, yon, kaldirac, komisyon ve funding varsayimlarini goz onunde
bulundurarak nihai tetikleme fiyatlarini hesaplar.

ROI tanimi (kaldirac ile normalize edilmis "yatirim getirisi"):

    ROI = (fiyat_degisimi_yuzdesi) * leverage

Bu nedenle hedef ROI'ye ulasmak icin gereken YAKLASIK fiyat hareketi:

    fiyat_degisimi_yuzdesi = ROI_hedefi / leverage

Ancak nihai tetikleme fiyati; acilis + kapanis komisyonu ve tahmini
funding giderini de telafi edecek sekilde hesaplanir, boylece gercek net
ROI hedefe daha yakin gerceklesir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .decimal_utils import ZERO, safe_div
from .enums import PositionSide

HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class RoiPriceInputs:
    entry_price: Decimal
    quantity: Decimal
    side: PositionSide
    leverage: Decimal
    take_profit_roi_pct: Decimal  # ornek: 10 => %10 ROI
    stop_loss_roi_pct: Decimal  # ornek: 5 => -%5 ROI (pozitif deger olarak girilir)
    taker_commission_rate: Decimal = Decimal("0.0004")
    estimated_funding_rate: Decimal = ZERO  # tek periyot icin tahmini funding orani


@dataclass(frozen=True, slots=True)
class RoiPriceResult:
    take_profit_price: Decimal
    stop_loss_price: Decimal
    take_profit_price_move_pct: Decimal
    stop_loss_price_move_pct: Decimal


def margin_of(entry_price: Decimal, quantity: Decimal, leverage: Decimal) -> Decimal:
    notional = entry_price * quantity
    return safe_div(notional, leverage)


def compute_roi_prices(inputs: RoiPriceInputs) -> RoiPriceResult:
    """Verilen ROI hedeflerine gore take-profit ve stop-loss fiyatlarini hesaplar.

    Hesap mantigi:
      notional = entry_price * quantity
      margin = notional / leverage
      acilis_komisyonu = notional * taker_commission_rate
      kapanis_komisyonu ~= notional * taker_commission_rate (fiyat degisimi kucuk oldugu icin yaklastirma)
      funding_gideri ~= notional * estimated_funding_rate

      hedef_kar_usdt = margin * (roi_pct / 100)
      gerekli_brut_kar = hedef_kar_usdt + acilis_komisyonu + kapanis_komisyonu + funding_gideri
      fiyat_degisimi = gerekli_brut_kar / quantity
    """

    if inputs.quantity <= ZERO:
        raise ValueError("quantity pozitif olmalidir")
    if inputs.leverage <= ZERO:
        raise ValueError("leverage pozitif olmalidir")

    notional = inputs.entry_price * inputs.quantity
    margin = safe_div(notional, inputs.leverage)
    open_commission = notional * inputs.taker_commission_rate
    close_commission_estimate = notional * inputs.taker_commission_rate
    funding_estimate = notional * inputs.estimated_funding_rate

    tp_target_profit = margin * (inputs.take_profit_roi_pct / HUNDRED)
    sl_target_loss = margin * (inputs.stop_loss_roi_pct / HUNDRED)

    tp_required_gross = tp_target_profit + open_commission + close_commission_estimate + funding_estimate
    sl_required_gross = sl_target_loss - open_commission - close_commission_estimate - funding_estimate
    if sl_required_gross < ZERO:
        sl_required_gross = ZERO

    tp_price_move = safe_div(tp_required_gross, inputs.quantity)
    sl_price_move = safe_div(sl_required_gross, inputs.quantity)

    if inputs.side == PositionSide.LONG:
        take_profit_price = inputs.entry_price + tp_price_move
        stop_loss_price = inputs.entry_price - sl_price_move
    else:
        take_profit_price = inputs.entry_price - tp_price_move
        stop_loss_price = inputs.entry_price + sl_price_move

    if stop_loss_price <= ZERO:
        raise ValueError("Hesaplanan stop-loss fiyati sifir veya negatif oldu")

    tp_move_pct = safe_div(tp_price_move, inputs.entry_price) * HUNDRED
    sl_move_pct = safe_div(sl_price_move, inputs.entry_price) * HUNDRED

    return RoiPriceResult(
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        take_profit_price_move_pct=tp_move_pct,
        stop_loss_price_move_pct=sl_move_pct,
    )


def estimate_liquidation_price(
    entry_price: Decimal,
    leverage: Decimal,
    side: PositionSide,
    maintenance_margin_rate: Decimal = Decimal("0.004"),
) -> Decimal:
    """Basitlestirilmis ISOLATED margin likidasyon fiyati tahmini.

    Gercek Binance likidasyon fiyati; leverage bracket'ine gore degisen
    bakim marjini orani (maintenance margin rate) ve bakim marjini
    tutarina (maintenance amount) baglidir. Bu fonksiyon, leverage
    bracket API'sinden gelen gercek ``maintenance_margin_rate`` degeri ile
    cagrildiginda dogru sonuca yakin bir yaklasik deger uretir; kesin
    deger icin Binance'in guncel bracket verisi kullanilmalidir.

    Basitlestirilmis ISOLATED formul (cross/isolated icin yaygin yaklasim):
        LONG:  liq_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)
        SHORT: liq_price = entry_price * (1 + 1/leverage - maintenance_margin_rate)
    """

    if leverage <= ZERO:
        raise ValueError("leverage pozitif olmalidir")
    inv_leverage = safe_div(Decimal("1"), leverage)
    if side == PositionSide.LONG:
        factor = Decimal("1") - inv_leverage + maintenance_margin_rate
    else:
        factor = Decimal("1") + inv_leverage - maintenance_margin_rate
    liquidation_price = entry_price * factor
    return liquidation_price if liquidation_price > ZERO else ZERO


def liquidation_distance_pct(
    stop_loss_price: Decimal, liquidation_price: Decimal, side: PositionSide
) -> Decimal:
    """Stop-loss fiyati ile likidasyon fiyati arasindaki yuzdesel mesafeyi
    hesaplar. Pozitif deger, stop-loss'un likidasyondan once tetiklenecegi
    (yani guvenli oldugu) anlamina gelir."""

    if liquidation_price <= ZERO:
        return Decimal("100")
    if side == PositionSide.LONG:
        diff = stop_loss_price - liquidation_price
    else:
        diff = liquidation_price - stop_loss_price
    return safe_div(diff, liquidation_price) * HUNDRED


def compute_realized_pnl(
    entry_price: Decimal, exit_price: Decimal, quantity: Decimal, side: PositionSide
) -> Decimal:
    """Kapanan bir pozisyonun brut (komisyon haric) gerceklesen PnL'ini hesaplar."""

    if side == PositionSide.LONG:
        return (exit_price - entry_price) * quantity
    return (entry_price - exit_price) * quantity


def compute_roi_from_prices(
    entry_price: Decimal,
    current_price: Decimal,
    quantity: Decimal,
    leverage: Decimal,
    side: PositionSide,
) -> Decimal:
    """Anlik ROI (%) hesaplar (gross, komisyon haric)."""

    margin = margin_of(entry_price, quantity, leverage)
    if margin == ZERO:
        return ZERO
    if side == PositionSide.LONG:
        pnl = (current_price - entry_price) * quantity
    else:
        pnl = (entry_price - current_price) * quantity
    return safe_div(pnl, margin) * HUNDRED

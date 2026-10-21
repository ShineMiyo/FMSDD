"""Club stock market: FM-driven simulated share prices for the ODD economy.

Every club in the save has a price.  A nation is one exchange, so the player
picks a country and gets a board of that country's clubs instead of a global
top list.  Prices are *not* a random walk and they are not stored either: the
quote of a club on a game day is a deterministic function of

* the FMODD club appraisal (``club_acquisition_valuation``), which is the same
  number the acquisition flow charges, so the market cap of a club and its
  acquisition price are one quantity instead of two independent ones, and
* live FM facts: the last five results - each weighted by the reputation of
  the competition it was played in, so a famous win moves the price further
  than an obscure one, and the whole form swing scaled by the average
  prestige of those matches - and the current league position.  A win is
  worth roughly six percent of the quote and a defeat half that, so the
  record always outweighs the random part, and
* the dated news of those same results: every result lands in full on the
  game day it was played - a 20:00 kick-off moves the same day's close, it
  does not wait for tomorrow - and then halves every ten days, so a winning
  run builds a visible trend while an old result fades out.  On top of that
  sits a bounded mean-reverting pseudo-random component that gives the market
  its texture and a daily coin toss of 0.6% on half of the game days.

Because the price is a pure function of (club, day) the market needs no
day-by-day simulation: opening the page late, reloading it twice, catching up
after a long break or rolling the save clock back all produce the same quotes.
The market is opt-in and scoped: nothing opens until the player enables whole
nations or single leagues in the exchange filter, so a save never pays for
tens of thousands of quotes it does not trade.  What the module persists is
the part that cannot be derived again: the enabled scope, which exchanges
opened and when, the index composition and base of each exchange, the
player's holdings, trades, notices and realised profit.  Removing a nation or
league from the scope deletes its exchange and freezes whatever the player
still held there at today's close: the shares stay on the account, the money
stays with the club, and both unlock when the exchange is listed again, so
closing and reopening an exchange never destroys a position.

The module owns that market document and returns explicit money plans so the
application service can charge or credit the ODD bank through
``club_economy``.  It never moves money itself.
"""

from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping

from tools.account_store import load_document, save_document
from tools.money import round_money


DOCUMENT = "stock_market"
SCHEMA_VERSION = 8

TRADE_FEE_RATE = 0.003
MIN_TRADE_FEE = 1.0
MIN_SHARE_PRICE = 0.01
MAX_SHARES_PER_ORDER = 1_000_000

# Share capital.  Every club lists with its own share count: the product of
# its four youth-facility levels (1..20 each) and its reputation (1..10_000),
# so a club with four level-20 facilities and full reputation lists exactly
# MAX_INITIAL_SHARES - 1.6 billion shares.  The product is floored at
# MIN_SHARES_OUTSTANDING (one million shares): a club whose facilities and
# reputation multiply out below it would otherwise list so few shares that a
# single one of them costs a fortune, which reads as a broken price rather
# than a small club.  The quote of the whole club still equals its appraisal,
# because the appraisal is driven by the same facts; the club itself holds
# every share it lists, so buying means buying from the club.
FACILITY_MAX = 20
REPUTATION_SCALE = 10_000
MAX_INITIAL_SHARES = FACILITY_MAX ** 4 * REPUTATION_SCALE
DEFAULT_REPUTATION = 5_000
MIN_SHARES_OUTSTANDING = 1_000_000

# Automatic share issues.  Once a club's quote doubles from its issue base the
# board would have no room left between one tick and the next, so the club
# expands its capital by a deterministic 100%..200% and the quote that forced
# the issue becomes the new base: a club that issued at three times its base
# needs three times that base again, not the old doubling level.  A holder's
# lot scales with the issue - shares up, average cost down - so nobody gains
# or loses on the day.
SHARE_SPLIT_TRIGGER = 2.0
SPLIT_RATIO_MIN = 1.00
SPLIT_RATIO_MAX = 2.00
MIN_SPLIT_ISSUE = 0.01
SPLIT_SEED = 0x5B117

# Builds up to V2.7.4beta priced every club against one global share count.
# A lot bought back then is repaired into the club's own capital once, so the
# model change never took value away from a holder: the shares it bought grow
# by the ratio the capital did and the average cost falls with them.
LEGACY_SHARES_OUTSTANDING = 10_000_000
LEGACY_PRICE_BAND = (0.25, 4.0)
CAPITAL_REPAIR_VERSION = 1

# One order never takes more than this share of a club's capital, and never
# more than the club still holds, so a click cannot swallow a whole club.  The
# share is the whole ceiling: a round lot of MAX_SHARES_PER_ORDER is what a
# ticket offers by default, never what the board allows, so a club large enough
# for the lot to sit under the two percent answers a click with its whole two
# percent instead of being pushed into a block application it does not need.
# It is also a budget for the day rather than a limit per click: every direct
# buy of one game day is counted against the same two percent, and once the
# day has spent it the account has to ask the club for a block trade - a
# player cannot take a fifth of a club home in ten clicks that each look small.
MAX_ORDER_SHARE_RATIO = 0.02

# Direct buys, block trades and financing.  One click buys at most DIRECT of a
# club's capital; anything above that is a block trade the club fills on the
# next game day, and one application may never ask for more than BLOCK of the
# capital.  Buying is refused once the account would pass MAX_BUY_STAKE of the
# capital, financing once it would pass MAX_FINANCE_STAKE: the club keeps
# control of itself either way.  Financing is a capital injection - the club
# issues the shares the account pays for and its own holding is untouched.
MAX_DIRECT_BUY_RATIO = 0.02
MAX_BLOCK_BUY_RATIO = 0.10
MAX_BUY_STAKE = 0.25
MIN_FINANCE_RATIO = 0.02
MAX_FINANCE_RATIO = 0.10
# The financing ceiling sits just under half so a backer can cross the 49%
# takeover gate; the gate itself is unchanged.  Leaving nine tenths of a point
# headroom also stops integer share rounding from parking an account one share
# short of the gate with no legal way to buy the last share.
MAX_FINANCE_STAKE = 0.499
BLOCK_PRICE_PREMIUM = 0.01
BLOCK_SIZE_WEIGHT = 1.25
MAX_PENDING_ORDERS = 8
ORDER_LOG_LIMIT = 60
RECEIPT_LIMIT = 40

# Financing appetite: what a club thinks of outside money.  A market cap far
# from the appraisal pushes it up from both sides - a club traded dear issues
# while its paper is expensive and one traded cheap is short of cash - and a
# club that is in the red pushes it up again for its own sake.  A club that is
# losing on the pitch wants the money too, while a fairly valued, healthy,
# mid-table club is the hard one to convince: the base is deliberately low, so
# most of the world says no and only a club in real need or real demand is
# worth offering to.  The appetite is a probability, not a verdict: the club
# answers once per game day (FINANCE_ACCEPT_FLOOR is the chance even a club
# that wants nothing still says yes), so an application can be turned down and
# the account has to weigh the club before offering to finance it.
FINANCE_APPETITE_BASE = 0.25
FINANCE_APPETITE_GAP = 0.35
FINANCE_APPETITE_DEBT = 0.35
FINANCE_APPETITE_SLUMP = 0.20
FINANCE_APPETITE_CAP = 0.92
FINANCE_ACCEPT_FLOOR = 0.05
FINANCE_GAP_SCALE = 0.40
FINANCE_DEBT_SCALE = 0.50
FINANCE_REASON_LIMIT = 3

# A club that was bought outright is not a lot on the board: the whole share
# register belongs to the group, so the market has nothing left to sell.  The
# register is not walled off, though - the group can always sell part of it
# back and always inject new capital, because the board that would answer
# those tickets is the group itself.
TAKEOVER_SOURCE = "takeover"

# What a group club must keep of its own capital.  Selling the club itself is
# a group decision, so the ticket may only sell part of the register: an
# outright owner that sold everything back would own a club without holding a
# share of it.
TAKEOVER_KEEP_NUMERATOR = 51
TAKEOVER_KEEP_DENOMINATOR = 100

# Money the group finances its own club with does not only buy shares: a tenth
# of it is left in the club's own balance, so a club the group owns can be
# funded on purpose instead of only bought.
CLUB_BALANCE_INJECTION_RATIO = 0.10

# A giant is not bought from the board alone.  From a hundred billion (100亿)
# the club only sells outright to an account that already owns 49% of its
# capital, so the exchange has to be worked before the club changes hands.
TAKEOVER_STAKE_GATE_VALUE = 10_000_000_000
TAKEOVER_STAKE_GATE_RATIO = 0.49

# How willing a board is to hand the club over today.  The takeover price is
# the appraisal times the market factor, so reading it against the appraisal
# says what the board is being offered: a quote far above the appraisal is a
# club that does not want to go, a quote far below is a club that does.  A run
# of rising closes works against the buyer as well - a board watching its own
# price climb is waiting for a better offer - and the answer is a probability
# drawn once per club and game day, exactly like a financing: a refusal is the
# board's mood today, not a verdict.
TAKEOVER_APPETITE_BASE = 0.60
TAKEOVER_APPETITE_PREMIUM = 0.55
TAKEOVER_APPETITE_DISCOUNT = 0.30
TAKEOVER_APPETITE_GAP_SCALE = 0.35
TAKEOVER_APPETITE_STREAK = 0.10
TAKEOVER_STREAK_LIMIT = 3
TAKEOVER_APPETITE_CAP = 0.95
TAKEOVER_APPETITE_FLOOR = 0.03
TAKEOVER_REASON_LIMIT = 3

# The one scope entry that is not a nation: a selection may say "the whole
# world" - every league of it, or every club the directory lists - without
# naming every nation and league of the save one by one.
GLOBAL_SCOPE = "*"

# A trade moves the quote by the share of the capital it took - a two percent
# order is worth about the daily coin toss, a block trade several days of news.
# The move decays exactly like the news of a result does, so a big buy lifts the
# quote for a while and then hands the price back to the club's own record.
TRADE_IMPACT_K = 0.75
TRADE_IMPACT_POW = 1.0
TRADE_IMPACT_HALF_LIFE = 10.0
TRADE_IMPACT_FLOOR = 0.30
TRADE_IMPACT_LIMIT = 40

# Market factor: 1.0 means "trades exactly at the FMODD appraisal".  The
# record carries the weight and the random parts stay under it: one extra win
# in the five-match window is worth 0.2 * FORM_WEIGHT = 5.2% of the quote,
# more than twice what the texture and the coin toss can move between two
# game days (about 2%), so a winning club is never priced below the day
# before by noise alone.
FORM_WEIGHT = 0.26
POSITION_WEIGHT = 0.12
NOISE_AMPLITUDE = 0.05
FACTOR_FLOOR = 0.55
FACTOR_CAP = 1.85

# News.  The five-match record is what a club is worth; this is what is
# happening to it right now.  Every result contributes an impulse that is
# paid in full on the game day the match was played, is scaled by the
# prestige of the competition and then fades towards NEWS_FLOOR of its value
# instead of vanishing: half of the pop is gone after NEWS_HALF_LIFE days,
# the remainder keeps supporting the quote until the result leaves the
# window.  NEWS_UNITS is the shape of the news: a win pays a full
# NEWS_WEIGHT (7%), a defeat gives back 70% of that and a draw is quiet.  A
# win is worth more than a defeat because the market rewards good news
# harder - and both stay far above one day of texture and coin toss, which
# is what makes a result day read as one.
NEWS_WEIGHT = 0.07
NEWS_HALF_LIFE = 10.0
NEWS_FLOOR = 0.30
NEWS_UNITS = {"胜": 1.0, "平": 0.0, "负": -0.7}

# Candle shadows: no intraday path is modelled, so one day's high/low comes
# from the same hash family as the texture, in a band of its own so a quiet
# market still draws readable candles.
CANDLE_SHADOW_MIN = 0.004
CANDLE_SHADOW_MAX = 0.020

# A result only counts for as much as the match was worth watching.  The
# weight scales one of the last five results by its competition reputation:
# an obscure fixture keeps 0.55, a world-famous one counts 1.5 times, so the
# same win (or draw, or loss) swings a price further when the competition is
# prestigious.  Reputation arrives on a 0..200 native scale; values above
# FORM_REPUTATION_SCALE are halved into the 0..100 model scale first.
FORM_REPUTATION_MIN_WEIGHT = 0.55
FORM_REPUTATION_MAX_WEIGHT = 1.50
FORM_REPUTATION_SCALE = 100.0

# Five wins out of five is a full record, an even record banks half of that,
# and the window is always read against the same ceiling and midpoint, so a
# save without match prestige prices exactly as it did before the weighting.
FORM_POINTS_MAX = 15.0
FORM_POINTS_NEUTRAL = 7.5

# The daily coin toss: on half of the game days a club gets an extra +0.5%
# or -0.5% on top of its results and texture; both signs are equally likely.
# It is deliberately small: the toss adds market texture, it must never flip
# the sign of a day that carried real news.
DAILY_SWING = 0.005
DAILY_SWING_CHANCE = 0.5

INDEX_BASE = 1000.0
INDEX_COMPONENTS = 24
INDEX_HISTORY_DAYS = 120
BOARD_PAGE_SIZE = 50
BOARD_MAX_PAGE_SIZE = 200
HISTORY_LIMIT = 30
NOTICE_LIMIT = 60
TRADE_LOG_LIMIT = 300
SURGE_THRESHOLD = 0.12

DAY_EPOCH = date(2020, 1, 1)

LOCK = threading.RLock()

_HASH_MASK = (1 << 64) - 1
_OCTAVES = ((29, 0.50), (11, 0.30), (4, 0.20))
_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def day_ordinal(value: Any) -> int | None:
    """Return the whole-day ordinal for an ISO game date, or ``None``."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return (date.fromisoformat(text[:10]) - DAY_EPOCH).days
    except ValueError:
        return None


def ordinal_date(ordinal: int) -> str:
    return (DAY_EPOCH + timedelta(days=int(ordinal))).isoformat()


def money(value: Any) -> float:
    """Round a cash amount to the account's two decimals."""
    try:
        return round_money(float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def quote(value: Any) -> float:
    """Round a share price; small clubs need four decimals to stay readable."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(number, 4) if number < 1 else round_money(number)


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _ratio(value: Any, maximum: float, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if maximum <= 0:
        return fallback
    return max(0.0, min(1.0, number / maximum))


# ---------------------------------------------------------------------------
# Fundamentals and the market factor
# ---------------------------------------------------------------------------


def club_form(results: Iterable[dict[str, Any]] | None) -> dict[str, int]:
    """Points and record from the most recent five completed matches."""
    wins = draws = losses = 0
    for row in list(results or [])[:5]:
        outcome = str((row or {}).get("result") or "").strip()
        if outcome == "胜":
            wins += 1
        elif outcome == "平":
            draws += 1
        elif outcome == "负":
            losses += 1
    return {
        "wins": wins, "draws": draws, "losses": losses,
        "points": wins * 3 + draws,
    }


def result_weight(reputation: Any) -> float:
    """How much one result counts, given the prestige of its match.

    ``None`` (the directory did not know the competition) keeps a neutral
    1.0, so a save without reputation data prices exactly as before.
    """
    if reputation is None:
        return 1.0
    value = _number(reputation)
    if value <= 0:
        return FORM_REPUTATION_MIN_WEIGHT
    if value > FORM_REPUTATION_SCALE:
        value = value / 2.0
    ratio = min(1.0, value / FORM_REPUTATION_SCALE)
    return FORM_REPUTATION_MIN_WEIGHT + ratio * (
        FORM_REPUTATION_MAX_WEIGHT - FORM_REPUTATION_MIN_WEIGHT
    )


def weighted_form(results: Iterable[dict[str, Any]] | None) -> dict[str, float]:
    """Read the last five results, counting each match for what it was worth.

    ``points`` is the usual three-one-zero record with every result scaled by
    the prestige of its competition, ``weight`` the average prestige of the
    matches that could be read (exactly ``1.0`` when the results carry no
    reputation) and ``count`` how many of the five slots were readable.
    """
    points = 0.0
    total_weight = 0.0
    counted = 0
    for row in list(results or [])[:5]:
        source = row or {}
        value = result_points(source.get("result"))
        if value is None:
            continue
        weight = result_weight(source.get("reputation"))
        points += value * weight
        total_weight += weight
        counted += 1
    return {
        "points": points,
        "count": float(counted),
        "weight": total_weight / counted if counted else 1.0,
    }


def weighted_tilt(
    results: Iterable[dict[str, Any]] | None, position: Any, team_count: Any,
) -> float:
    """Performance tilt from the last five results, weighted by match prestige.

    The window keeps the plain five-match reading: a full 15 points is five
    wins and 7.5 is an even record, so a save whose results carry no
    reputation prices exactly as it did before.  Prestige then works twice.
    It decides how much each of the five results is worth, and the average
    prestige of the window scales the whole deviation away from an even
    record - a club playing famous matches swings harder than one whose
    results nobody watched.
    """
    form = weighted_form(results)
    deviation = (
        form["points"] - FORM_POINTS_NEUTRAL * form["weight"]
    ) / FORM_POINTS_MAX
    ratio = 0.5 + deviation
    placed = position_ratio(position, team_count)
    place = 0.5 if placed is None else placed
    return (ratio - 0.5) * FORM_WEIGHT + (place - 0.5) * POSITION_WEIGHT


def position_ratio(position: Any, team_count: Any) -> float | None:
    try:
        place = int(position)
        total = int(team_count)
    except (TypeError, ValueError):
        return None
    if place <= 0 or total <= 1 or place > total:
        return None
    return 1.0 - (place - 1) / (total - 1)


def tilt_from(form_points: Any, position: Any, team_count: Any) -> float:
    """Performance tilt from an explicit last-five record and table place."""
    form_ratio = _ratio(form_points, 15, 0.5)
    placed = position_ratio(position, team_count)
    place = 0.5 if placed is None else placed
    return (form_ratio - 0.5) * FORM_WEIGHT + (place - 0.5) * POSITION_WEIGHT


def performance_tilt(row: Mapping[str, Any] | None) -> float:
    """How far results and table position push a club above its appraisal.

    Directory rows may arrive already reduced (``tilt``), which keeps a page
    view from re-deriving the same five results for every club in the world.
    """
    source = row or {}
    if source.get("tilt") is not None:
        return max(-0.5, min(0.5, _number(source.get("tilt"))))
    results = source.get("recent_results")
    if results:
        return max(-0.5, min(0.5, weighted_tilt(
            results, source.get("position"), source.get("team_count"),
        )))
    return tilt_from(
        source.get("form_points"), source.get("position"), source.get("team_count"),
    )


RESULT_POINTS = {"胜": 3.0, "平": 1.0, "负": 0.0}


def result_points(outcome: Any) -> float | None:
    """The league points of one result, or ``None`` for a row we cannot read."""
    return RESULT_POINTS.get(str(outcome or "").strip())


def result_day(row: Mapping[str, Any] | None) -> int | None:
    """The game day a result was played on.

    ``day`` (an ordinal the appraiser precomputed) wins over the ISO ``date``
    text, so a whole board reads its results without parsing a date twice.
    Rows without either - older caches, hand-built data - carry no news.
    """
    source = row or {}
    stored = source.get("day")
    if stored is not None:
        try:
            return int(stored)
        except (TypeError, ValueError):
            return None
    return day_ordinal(source.get("date"))


_DECAY_CACHE: dict[int, float] = {}


def news_decay(age: Any) -> float:
    """How much of a result's impulse is left *age* game days after the match.

    ``1.0`` on the day itself, ``NEWS_FLOOR`` (plus what has not decayed yet)
    afterwards, never below the floor.
    """
    try:
        days = max(0, int(age))
    except (TypeError, ValueError):
        return 1.0
    value = _DECAY_CACHE.get(days)
    if value is None:
        value = NEWS_FLOOR + (1.0 - NEWS_FLOOR) * (
            0.5 ** (days / NEWS_HALF_LIFE)
        )
        _DECAY_CACHE[days] = value
    return value


def result_news(row: Mapping[str, Any] | None, ordinal: Any) -> float:
    """The fresh-news impulse of one result on one game day.

    Zero before the match has been played (a candle never knows a result
    early), zero for a result without a date or without an outcome, ``+1``
    for a famous win on the day it was played and ``-0.7`` for a defeat.
    The impulse is read from :data:`NEWS_UNITS`, scaled by the prestige of
    the competition and decayed with :func:`news_decay` as the match ages.
    """
    source = row or {}
    outcome = str(source.get("result") or "").strip()
    if outcome not in NEWS_UNITS:
        return 0.0
    played = result_day(source)
    if played is None:
        return 0.0
    try:
        age = int(ordinal) - played
    except (TypeError, ValueError):
        return 0.0
    if age < 0:
        return 0.0
    return (
        NEWS_UNITS[outcome]
        * result_weight(source.get("reputation"))
        * news_decay(age)
    )


def news_tilt(results: Iterable[dict[str, Any]] | None, ordinal: Any) -> float:
    """Fresh-news tilt of the last five results as of one game day.

    This is the part of the quote that moves when a match ends: a win played
    today pays ``+NEWS_WEIGHT`` (times the prestige of its competition) on
    the same day's close and then fades, while the plain record in
    :func:`weighted_tilt` stays the club's baseline value.  A window without
    readable dates keeps the plain record and adds no news.
    """
    total = 0.0
    for row in list(results or [])[:5]:
        total += result_news(row, ordinal)
    return NEWS_WEIGHT * total


def _hash01(seed: int, index: int) -> float:
    """Deterministic 64-bit hash of two integers mapped to ``[-1, 1]``."""
    value = (
        int(seed) * 0x9E3779B97F4A7C15
        + int(index) * 0xBF58476D1CE4E5B9
        + 0x165667B19E3779F9
    ) & _HASH_MASK
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & _HASH_MASK
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & _HASH_MASK
    value ^= value >> 31
    return (value >> 11) / float(1 << 53) * 2.0 - 1.0


def _value_noise(seed: int, ordinal: int, period: int) -> float:
    """Smooth lattice noise: bounded, continuous and cheap to evaluate."""
    lattice = ordinal // period
    inner = ordinal % period
    left = _hash01(seed, lattice)
    right = _hash01(seed, lattice + 1)
    weight = inner / period
    eased = weight * weight * (3.0 - 2.0 * weight)
    return left + (right - left) * eased


def market_noise(club_id: Any, ordinal: int) -> float:
    """Mean-reverting market texture for one club on one game day."""
    seed = _int(club_id)
    total = 0.0
    for period, weight in _OCTAVES:
        total += weight * _value_noise(seed, int(ordinal), period)
    return NOISE_AMPLITUDE * total


def daily_swing(club_id: Any, ordinal: int) -> float:
    """The daily coin toss: ``+1.5%``, ``-1.5%`` or nothing for one club-day.

    Deterministic like the rest of the market - the same (club, day) pair
    always tosses the same coin - with a half chance of a swing and both
    signs equally likely on the days it lands.
    """
    draw = _hash01(_int(club_id) ^ 0x5A1E, int(ordinal))
    if abs(draw) < (1.0 - DAILY_SWING_CHANCE):
        return 0.0
    return DAILY_SWING if draw > 0 else -DAILY_SWING


def impact_decay(age: Any) -> float:
    """How much of a trade's price impact is still in the quote after ``age``."""
    value = max(0.0, _number(age))
    half_life = TRADE_IMPACT_HALF_LIFE if TRADE_IMPACT_HALF_LIFE > 0 else 1.0
    return max(TRADE_IMPACT_FLOOR, 0.5 ** (value / half_life))


def trade_impact_delta(
    qty: Any, shares: Any, side: Any, *, weight: float = 1.0,
) -> float:
    """The price move one trade leaves behind, signed by its side.

    The size of the move is the share of the club's capital the order took, so
    the same number of shares moves a small club further than a big one, and a
    block trade - which took several percent - moves it further still.
    """
    capital = max(1.0, _number(shares))
    ratio = min(1.0, max(0.0, _number(qty)) / capital)
    magnitude = TRADE_IMPACT_K * (ratio ** TRADE_IMPACT_POW) * _number(weight, 1.0)
    return magnitude if str(side) == "buy" else -magnitude


def trade_impact(events: Iterable[Any] | None, ordinal: Any) -> float:
    """Sum of the decaying trade impacts of one club on one game day."""
    total = 0.0
    for event in events or []:
        if not isinstance(event, (list, tuple)) or len(event) < 2:
            continue
        try:
            day = int(event[0])
        except (TypeError, ValueError):
            continue
        age = _int(ordinal) - day
        if age < 0:
            continue
        total += _number(event[1]) * impact_decay(age)
    return total


def _record_impact(
    state: dict[str, Any], club_id: Any, ordinal: Any, delta: float,
) -> None:
    """Remember one trade's price impact on the day it happened."""
    value = _number(delta)
    if not value:
        return
    identity = str(_int(club_id))
    events = state.setdefault("impact", {}).setdefault(identity, [])
    events.append([_int(ordinal), round(value, 6)])
    if len(events) > TRADE_IMPACT_LIMIT:
        del events[:-TRADE_IMPACT_LIMIT]


def plan_impact(plan: Mapping[str, Any], stock: Mapping[str, Any] | None = None) -> float:
    """The price move one planned trade leaves behind, signed by its side."""
    source = plan.get("stock") if stock is None else stock
    weight = BLOCK_SIZE_WEIGHT if str((plan or {}).get("kind")) == "block" else 1.0
    return trade_impact_delta(
        (plan or {}).get("qty"), (source or {}).get("shares"),
        (plan or {}).get("side"), weight=weight,
    )


def _drop_impact(state: dict[str, Any], club_id: Any, ordinal: Any, delta: float) -> None:
    """Forget one impact entry again, used when a trade had to be reverted."""
    key = str(_int(club_id))
    events = (state.get("impact") or {}).get(key)
    if not isinstance(events, list):
        return
    for index in range(len(events) - 1, -1, -1):
        entry = events[index]
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        if ordinal is not None and _int(entry[0]) != _int(ordinal):
            continue
        if abs(_number(entry[1]) - _number(delta)) > 1e-9:
            continue
        events.pop(index)
        break
    if not events:
        state["impact"].pop(key, None)


def market_extras(state: Mapping[str, Any] | None) -> dict[int, dict[str, Any]]:
    """Per-club player extras: the trade-impact series and the injected capital.

    The book of one club prices the club; these extras price what the account
    itself did to it.  Both are read by the same functions that read the share
    records, so a save without them prices exactly as it did before.
    """
    source = state if isinstance(state, Mapping) else {}
    raw_impact = source.get("impact") if isinstance(source.get("impact"), Mapping) else {}
    raw_finance = (
        source.get("finance") if isinstance(source.get("finance"), Mapping) else {}
    )
    ids = {_int(key) for key in raw_impact} | {_int(key) for key in raw_finance}
    extras: dict[int, dict[str, Any]] = {}
    for club_id in sorted(ids):
        if club_id <= 0:
            continue
        events = raw_impact.get(str(club_id)) or raw_impact.get(club_id) or []
        entries = raw_finance.get(str(club_id)) or raw_finance.get(club_id) or []
        if isinstance(entries, Mapping):
            entries = [[0, _number(entries.get("amount"))]]
        paid: list[list[Any]] = []
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                paid.append([_int(entry[0]), money(entry[1])])
        extras[club_id] = {
            "impact": list(events) if isinstance(events, list) else [],
            "finance": paid,
        }
    return extras


def finance_extras(state: Mapping[str, Any] | None) -> dict[int, dict[str, Any]]:
    """Extras without the trade impact, for the readings that must ignore it.

    An automatic share issue must follow the club's own market and not the
    account's own orders: a block trade that doubled the quote would otherwise
    force a capital increase and, once the impact decayed, leave the club priced
    far below its base.  The injected capital stays in, because it is real money
    the club holds and it never moves the quote on the day it arrives.
    """
    return {
        club_id: {**extra, "impact": []}
        for club_id, extra in market_extras(state).items()
    }


def extras_signature(extras: Mapping[int, Mapping[str, Any]] | None) -> tuple[int, float]:
    """A cheap fingerprint of the extras, so a cached board cannot go stale."""
    events = 0
    cash = 0.0
    for extra in (extras or {}).values():
        events += len(list((extra or {}).get("impact") or []))
        for entry in (extra or {}).get("finance") or []:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                cash += _number(entry[1])
    return (events, round(cash, 2))


def impact_of(extras: Mapping[int, Mapping[str, Any]] | None, club_id: Any) -> list[Any]:
    extra = (extras or {}).get(_int(club_id)) or {}
    return list(extra.get("impact") or [])


def finance_of(
    extras: Mapping[int, Mapping[str, Any]] | None, club_id: Any,
    ordinal: Any = None,
) -> float:
    """Injected capital of one club, up to and including one game day."""
    extra = (extras or {}).get(_int(club_id)) or {}
    total = 0.0
    for entry in extra.get("finance") or []:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        if ordinal is not None and _int(entry[0]) > _int(ordinal):
            continue
        total += _number(entry[1])
    return max(0.0, money(total))


def market_factor(
    row: Mapping[str, Any] | None, ordinal: int, club_id: Any = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> float:
    """Price multiplier applied to the FMODD appraisal of one club.

    The record and the table place are the club's baseline premium; the dated
    news of the last five results is what moves it from one day to the next,
    and the texture and the coin toss only add the last few tenths of a
    percent.  Because the news is read per game day, an evening match moves
    the same day's close instead of waiting for the next candle.

    The account's own trades are added on top: a buy lifts the quote for a
    while, a sale presses it down, and both fade back to the club's own number.
    """
    source = row or {}
    identity = _int(club_id if club_id is not None else source.get("id"))
    factor = (
        1.0 + performance_tilt(source)
        + news_tilt(source.get("recent_results"), ordinal)
        + trade_impact(impact_of(extras, identity), ordinal)
        + market_noise(identity, ordinal)
        + daily_swing(identity, ordinal)
    )
    return round(max(FACTOR_FLOOR, min(FACTOR_CAP, factor)), 6)


def intrinsic_value(row: Mapping[str, Any] | None) -> float:
    """The club appraisal in ODD money; the anchor of the whole market."""
    source = row or {}
    return max(1.0, _number(source.get("club_value")))


def market_cap(
    row: Mapping[str, Any] | None, ordinal: int,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> float:
    """Club value on the market: appraisal times the factor plus new capital.

    Money the account injected through a financing sits in the club, so it is
    part of what the club is worth: the issue grows the capital and the cap by
    the same amount, which is why the quote does not move when it happens.
    """
    source = row or {}
    identity = _int(source.get("id"))
    return intrinsic_value(source) * market_factor(
        source, ordinal, identity, extras,
    ) + finance_of(extras, identity, ordinal)


# ---------------------------------------------------------------------------
# Share capital and automatic issues
# ---------------------------------------------------------------------------


# The four facility scalars the share formula multiplies together, mapped from
# the native detail keys to the keys a directory row may carry instead.
_FACILITY_FIELDS = (
    ("training", "training"),
    ("youth", "youth"),
    ("junior_coaching", "junior"),
    ("youth_recruitment", "recruitment"),
)


def facility_levels(row: Mapping[str, Any] | None) -> dict[str, int]:
    """The four facility levels of a row that carries readable values.

    The product of these four numbers and the reputation is the share capital
    a club lists with, so one missing or out-of-range level discards the whole
    reading instead of pricing a club off a single broken byte.
    """
    source = row or {}
    raw = source.get("facilities")
    if not isinstance(raw, Mapping):
        return {}
    levels: dict[str, int] = {}
    for source_key, alias in _FACILITY_FIELDS:
        value = raw.get(source_key)
        if value is None:
            value = raw.get(alias)
        try:
            level = int(value)
        except (TypeError, ValueError):
            return {}
        if not 1 <= level <= FACILITY_MAX:
            return {}
        levels[source_key] = level
    return levels


def inferred_facility_level(reputation: Any) -> int:
    """The facility level the acquisition model assumes without detail.

    ``club_acquisition_valuation`` scores unread facilities as
    ``min(0.80, 0.20 + reputation * 0.60)``; the share formula reads the same
    proxy, so capital and appraisal never disagree about an unread club.
    """
    ratio = max(0.0, min(1.0, _number(reputation) / REPUTATION_SCALE))
    score = min(0.80, 0.20 + ratio * 0.60)
    return max(1, min(FACILITY_MAX, int(round(score * FACILITY_MAX))))


def initial_shares(row: Mapping[str, Any] | None) -> int:
    """The share capital one club lists with.

    Training facilities x youth facilities x junior coaching x youth
    recruitment x reputation, so four level-20 facilities and 10,000
    reputation give exactly :data:`MAX_INITIAL_SHARES`, 1.6 billion shares,
    and anything under :data:`MIN_SHARES_OUTSTANDING`, one million shares,
    is lifted to it - a listing of a few hundred shares would print a share
    price no one could read as money.
    """
    source = row or {}
    reputation = _int(source.get("reputation"))
    if not 0 < reputation <= REPUTATION_SCALE:
        reputation = DEFAULT_REPUTATION
    levels = facility_levels(source)
    product = 1
    if levels:
        for level in levels.values():
            product *= int(level)
    else:
        product = inferred_facility_level(reputation) ** 4
    return max(MIN_SHARES_OUTSTANDING, int(product) * int(reputation))


def split_ratio(club_id: Any, index: Any) -> float:
    """The deterministic size of a club's *index*-th issue (1.00x..2.00x).

    The club can at most double its capital in one issue.  A draw is never a
    no-op: the smallest issue prints at least :data:`MIN_SPLIT_ISSUE` more
    shares than the club already has.
    """
    draw = 0.5 + 0.5 * _hash01(_int(club_id) ^ SPLIT_SEED, _int(index))
    span = SPLIT_RATIO_MAX - SPLIT_RATIO_MIN
    ratio = round(SPLIT_RATIO_MIN + span * draw, 2)
    return max(SPLIT_RATIO_MIN + MIN_SPLIT_ISSUE, min(SPLIT_RATIO_MAX, ratio))


def share_splits(book: Mapping[str, Any] | None) -> list[int]:
    """The game days one club's capital was expanded on, oldest first."""
    record = book if isinstance(book, Mapping) else {}
    days: list[int] = []
    for item in record.get("s") or []:
        try:
            days.append(int(item))
        except (TypeError, ValueError):
            continue
    return days


def share_base(book: Mapping[str, Any] | None) -> float:
    """The quote a club's next issue is measured against; 0 when unknown."""
    record = book if isinstance(book, Mapping) else {}
    return max(0.0, _number(record.get("b")))


def listed_shares(
    row: Mapping[str, Any] | None, book: Mapping[str, Any] | None = None,
) -> int:
    """The capital one club listed with.

    The number is frozen into the share record the first time the club is
    listed, because it is the scale every quote of that club is measured
    against: a later facility reading, a reputation swing or a management
    change must not re-price the club, only an issue may change its capital.
    """
    record = book if isinstance(book, Mapping) else {}
    frozen = _int(record.get("i"))
    if frozen > 0:
        return frozen
    return initial_shares(row)


def shares_at(
    row: Mapping[str, Any] | None, ordinal: Any, book: Mapping[str, Any] | None = None,
) -> int:
    """Total shares of one club on one game day, issues included.

    An issue takes effect on the game day it was forced, so the board, the
    candles and the ticket all read the new capital on the same day.  The
    whole series stays a pure function of the frozen listing capital and the
    stored issue days.

    The club's own automatic issues and the issues the account paid for are
    replayed in day order, so a financing that happened before a later doubling
    is scaled by it exactly like the capital it joined.
    """
    source = row or {}
    club_id = _int(source.get("id"))
    shares = listed_shares(source, book)
    for day, kind, value in capital_events(book, club_id):
        if day > _int(ordinal):
            break
        if kind == "split":
            shares = max(shares + 1, int(round(shares * value)))
        else:
            shares += int(value)
    return shares


def financed_issues(book: Mapping[str, Any] | None) -> list[tuple[int, int]]:
    """Capital issues the account paid for: ``(game day, shares)`` in day order."""
    record = book if isinstance(book, Mapping) else {}
    events: list[tuple[int, int]] = []
    for entry in record.get("f") or []:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        day = _int(entry[0])
        shares = _int(entry[1])
        if day > 0 and shares > 0:
            events.append((day, shares))
    return sorted(events)


def financed_shares(book: Mapping[str, Any] | None, ordinal: Any) -> int:
    """How many of a club's shares were issued against the account's money."""
    return sum(
        shares for day, shares in financed_issues(book) if day <= _int(ordinal)
    )


def capital_events(book: Mapping[str, Any] | None, club_id: Any) -> list[tuple[int, str, float]]:
    """Every capital change of one club in day order.

    Splits come first whenever a day carries both, because the automatic issue
    is what the club did on its own and the financing is priced against the
    quote that issue left behind.
    """
    events: list[tuple[int, str, float]] = []
    for index, day in enumerate(share_splits(book)):
        events.append((int(day), "split", float(split_ratio(club_id, index))))
    for day, shares in financed_issues(book):
        events.append((int(day), "finance", float(shares)))
    events.sort(key=lambda item: (item[0], item[1] == "finance"))
    return events


def max_direct_shares(shares: Any) -> int:
    """One click buys at most this much of a club's capital: 2% of it.

    Two percent of the capital is the only ceiling a click has, whatever the
    club is worth: the round lot of a ticket is a default the account can edit,
    not a rule the board applies, so a club of a billion shares answers a click
    with twenty million of them and a club of a million shares with twenty
    thousand.  Only an order past the share is a block application.
    """
    try:
        capital = int(shares)
    except (TypeError, ValueError):
        capital = 0
    if capital <= 0:
        return MAX_SHARES_PER_ORDER
    return max(1, int(round(capital * MAX_DIRECT_BUY_RATIO)))


def max_block_shares(shares: Any) -> int:
    """One block application may ask for at most this much: 10% of the capital.

    A block is several clicks in one order, so it is ten times a click and
    still far below the quarter of a club the account may ever own.  There is
    no round lot here: ten percent of the capital floor is already a hundred
    thousand shares, and letting the lot raise it would hand a small club's
    whole allowance to one application.
    """
    try:
        capital = int(shares)
    except (TypeError, ValueError):
        capital = 0
    if capital <= 0:
        return MAX_SHARES_PER_ORDER
    return max(1, int(round(capital * MAX_BLOCK_BUY_RATIO)))


def max_shares_per_order(shares: Any) -> int:
    """Per-order cap of one club, the cap the ticket shows: a direct buy."""
    return max_direct_shares(shares)


def daily_direct_used(
    state: Mapping[str, Any] | None, club_id: Any, ordinal: Any,
) -> int:
    """Direct shares already bought today; another day never counts."""
    daily = (state or {}).get("daily")
    entry = daily.get(str(_int(club_id))) if isinstance(daily, Mapping) else None
    if not isinstance(entry, Mapping):
        return 0
    if _int(entry.get("ordinal")) != _int(ordinal):
        return 0
    return max(0, _int(entry.get("qty")))


def daily_direct_room(
    state: Mapping[str, Any] | None, club_id: Any, shares: Any, ordinal: Any,
) -> int:
    """What the day's two percent allowance of one club still has left.

    The two percent is a budget for the whole game day, not a limit per click:
    ten clicks of a fifth of it must not walk away with a fifth of the club.
    """
    return max(0, max_direct_shares(shares) - daily_direct_used(state, club_id, ordinal))


def record_direct_buy(
    state: dict[str, Any], club_id: Any, ordinal: Any, qty: Any,
) -> None:
    """Book one click against today's allowance; a new day starts it over."""
    shares = max(0, _int(qty))
    day = _int(ordinal)
    if shares <= 0 or day <= 0:
        return
    daily = state.get("daily")
    if not isinstance(daily, dict):
        daily = {}
        state["daily"] = daily
    key = str(_int(club_id))
    entry = daily.get(key)
    if not isinstance(entry, dict) or _int(entry.get("ordinal")) != day:
        entry = {"ordinal": day, "qty": 0}
        daily[key] = entry
    entry["qty"] = _int(entry.get("qty")) + shares


def forget_direct_buy(
    state: dict[str, Any], club_id: Any, ordinal: Any, qty: Any,
) -> None:
    """Hand one click's booking back after a trade had to be reverted."""
    shares = max(0, _int(qty))
    day = _int(ordinal)
    if shares <= 0 or day <= 0:
        return
    daily = state.get("daily")
    entry = daily.get(str(_int(club_id))) if isinstance(daily, dict) else None
    if not isinstance(entry, dict) or _int(entry.get("ordinal")) != day:
        return
    entry["qty"] = max(0, _int(entry.get("qty")) - shares)


def stake_of(qty: Any, shares: Any) -> float:
    """The share of a club's capital one lot holds, in percent."""
    capital = _number(shares)
    if capital <= 0:
        return 0.0
    return max(0.0, min(1.0, _number(qty) / capital))


def financed_amount(state: Mapping[str, Any] | None, club_id: Any) -> float:
    """Cash the account injected into one club through a financing."""
    source = state if isinstance(state, Mapping) else {}
    record = source.get("finance")
    if not isinstance(record, Mapping):
        return 0.0
    key = str(_int(club_id))
    return money(record.get(key) if key in record else record.get(_int(club_id)))


def split_threshold(book: Mapping[str, Any] | None) -> float:
    """The quote that forces the next issue; 0 when the base is unknown."""
    base = share_base(book)
    return quote(base * SHARE_SPLIT_TRIGGER) if base > 0 else 0.0


def share_books(state: Mapping[str, Any] | None) -> dict[int, dict[str, Any]]:
    """Every stored share record of one market document, keyed by club id."""
    books: dict[int, dict[str, Any]] = {}
    for entry in ((state or {}).get("nations") or {}).values():
        if not isinstance(entry, Mapping):
            continue
        stored = entry.get("shares")
        if not isinstance(stored, Mapping):
            continue
        for key, record in stored.items():
            if isinstance(record, Mapping):
                books[_int(key)] = record
    return books


def share_price(
    row: Mapping[str, Any] | None, ordinal: int, book: Mapping[str, Any] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> float:
    """Per-share quote derived from the market cap and that day's capital."""
    shares = shares_at(row, ordinal, book)
    return max(MIN_SHARE_PRICE, quote(market_cap(row, ordinal, extras) / shares))


def turnover_shares(
    row: Mapping[str, Any] | None, ordinal: int, change: float = 0.0,
    book: Mapping[str, Any] | None = None,
) -> float:
    """Deterministic traded volume so the board can show a live-looking tape."""
    club_id = _int((row or {}).get("id"))
    draw = 0.5 + 0.5 * _hash01(club_id ^ 0x5EED, int(ordinal))
    rate = 0.0006 + 0.024 * draw
    rate *= 1.0 + 5.0 * abs(float(change or 0.0))
    return round(shares_at(row, ordinal, book) * rate, 2)


def _price_from_factor(
    row: Mapping[str, Any] | None, factor: float, ordinal: Any,
    book: Mapping[str, Any] | None = None,
    extra_cash: Any = 0.0,
) -> float:
    """Per-share quote for an explicit market factor (candle wick levels)."""
    source = row or {}
    shares = shares_at(source, ordinal, book)
    price = (intrinsic_value(source) * float(factor) + _number(extra_cash)) / shares
    return max(MIN_SHARE_PRICE, quote(price))


def _day_range(club_id: Any, ordinal: int) -> tuple[float, float]:
    """Deterministic ``(upper, lower)`` intraday shadow of one day's candle.

    A close is a pure function of the day, so there is no intraday path to
    replay.  The shadows therefore come from the same hash family as the market
    texture: bounded, stable for a given (club, day) pair, and small enough
    that a candle keeps the shape of the day's move.
    """
    seed = _int(club_id)
    day = int(ordinal)
    strength = CANDLE_SHADOW_MIN + (CANDLE_SHADOW_MAX - CANDLE_SHADOW_MIN) * (
        0.5 + 0.5 * _hash01(seed ^ 0x9C5D, day)
    )
    upper = strength * (0.30 + 0.70 * (0.5 + 0.5 * _hash01(seed ^ 0x4E1F, day)))
    lower = strength * (0.30 + 0.70 * (0.5 + 0.5 * _hash01(seed ^ 0x77B3, day)))
    return upper, lower

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def _base36(value: int, width: int = 3) -> str:
    number = abs(int(value))
    digits = ""
    while number:
        number, remainder = divmod(number, 36)
        digits = _BASE36[remainder] + digits
    return (digits or "0").rjust(width, "0")


def stock_code(name: Any, short_name: Any = None, club_id: Any = None) -> str:
    """A readable, deterministic ticker such as ``MAN`` or ``CLB0K2``."""
    for candidate in (short_name, name):
        letters = "".join(ch for ch in str(candidate or "") if ch.isascii() and ch.isalpha())
        if len(letters) >= 3:
            return letters[:3].upper()
    return f"CLB{_base36(_int(club_id))[-3:]}"


def assign_codes(rows: Iterable[Mapping[str, Any]]) -> dict[int, str]:
    """Unique tickers inside one exchange, stable for a given club."""
    ordered = sorted(
        (row for row in rows or [] if _int((row or {}).get("id")) > 0),
        key=lambda row: _int(row.get("id")),
    )
    codes: dict[int, str] = {}
    used: set[str] = set()
    for row in ordered:
        club_id = _int(row.get("id"))
        base = stock_code(row.get("name"), row.get("short_name"), club_id)
        code = base
        suffix = 2
        while code in used:
            code = f"{base}{suffix}"
            suffix += 1
        used.add(code)
        codes[club_id] = code
    return codes


def _row_index(rows: Any) -> dict[int, dict[str, Any]]:
    """Index directory rows by club id; accepts a ready-made index as well."""
    if isinstance(rows, dict):
        return rows
    index: dict[int, dict[str, Any]] = {}
    for row in rows or []:
        club_id = _int((row or {}).get("id"))
        if club_id > 0:
            index[club_id] = row
    return index


def nation_of(row: Mapping[str, Any] | None) -> str:
    return str((row or {}).get("nation") or "").strip() or "未分类"


def _group_by_nation(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows or []:
        groups.setdefault(nation_of(row), []).append(row)
    return groups


# ---------------------------------------------------------------------------
# Exchange scope: which nations and leagues the player enabled
# ---------------------------------------------------------------------------


def empty_scope() -> dict[str, list[Any]]:
    return {"nations": [], "leagues": []}


def _scope_pairs(scope: Any) -> tuple[set[str], set[tuple[str, str]]]:
    source = scope if isinstance(scope, Mapping) else {}
    nations = {
        str(item).strip() for item in (source.get("nations") or [])
        if item is not None and str(item).strip()
    }
    leagues: set[tuple[str, str]] = set()
    for item in source.get("leagues") or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            nation = str(item[0] or "").strip()
            competition = str(item[1] or "").strip()
        elif isinstance(item, Mapping):
            nation = str(item.get("nation") or "").strip()
            competition = str(item.get("competition") or "").strip()
        else:
            continue
        if nation and competition:
            leagues.add((nation, competition))
    return nations, leagues


def normalize_scope(scope: Any) -> dict[str, list[Any]]:
    """Canonical scope document: sorted nations and sorted nation/league pairs."""
    nations, leagues = _scope_pairs(scope)
    return {
        "nations": sorted(nations),
        "leagues": [[nation, competition] for nation, competition in sorted(leagues)],
    }


def scope_signature(scope: Any) -> str:
    """Stable cache key for a scope document."""
    nations, leagues = _scope_pairs(scope)
    parts = [f"n:{name}" for name in sorted(nations)]
    parts += [f"l:{nation}\u0001{competition}" for nation, competition in sorted(leagues)]
    return "|".join(parts)


def suspended_pairs(state: Mapping[str, Any] | None) -> set[tuple[str, str]]:
    """The ticked leagues the last complete directory could not list.

    A tick is never deleted for a directory that could not serve it - the next
    read may be a database that lists the league again - so the tick is parked
    here and the board, the counters and the filter all leave it out until a
    read that can serve it releases it.
    """
    source = state if isinstance(state, Mapping) else {}
    _nations, leagues = _scope_pairs({"leagues": source.get("scope_suspended") or []})
    return leagues


def listed_scope(scope: Any, suspended: Any = None) -> dict[str, list[Any]]:
    """The stored scope without the leagues that are parked today."""
    _nations, leaving = _scope_pairs({"leagues": suspended or []})
    canonical = normalize_scope(scope)
    return {
        "nations": list(canonical["nations"]),
        "leagues": [
            [nation, competition]
            for nation, competition in canonical["leagues"]
            if (nation, competition) not in leaving
        ],
    }


def scope_without(scope: Any, leaving: Any = None) -> dict[str, list[Any]]:
    """The canonical scope with some nation/league pairs removed."""
    _nations, dropped = _scope_pairs({"leagues": leaving or []})
    canonical = normalize_scope(scope)
    return {
        "nations": list(canonical["nations"]),
        "leagues": [
            [nation, competition]
            for nation, competition in canonical["leagues"]
            if (nation, competition) not in dropped
        ],
    }


def market_enabled(state: Mapping[str, Any] | None) -> bool:
    """True when at least one nation or league is enabled for trading."""
    nations, leagues = _scope_pairs((state or {}).get("scope"))
    return bool(nations or leagues)


def row_competition_names(row: Mapping[str, Any] | None) -> list[str]:
    """Every competition label of one directory row, primary league first.

    A club is listed in its league and can have played in cups, continental
    leagues and the competitions the result archive knows about, and a ticked
    league may name any of them, so all of them count.
    """
    source = row or {}
    names: list[str] = []
    primary = str(source.get("competition") or "").strip()
    if primary:
        names.append(primary)
    for item in source.get("competitions") or []:
        label = str(item or "").strip()
        if label and label not in names:
            names.append(label)
    return names


def in_scope(row: Mapping[str, Any] | None, scope: Any) -> bool:
    """A club is tradable when its nation or its league is enabled."""
    nations, leagues = _scope_pairs(scope)
    if not nations and not leagues:
        return False
    if GLOBAL_SCOPE in nations:
        return True
    nation = nation_of(row)
    if nation in nations:
        return True
    if (GLOBAL_SCOPE, GLOBAL_SCOPE) in leagues:
        # The world's leagues, not the whole world: a club with no league of
        # its own is not part of a selection made league by league.
        return bool(row_competition_names(row))
    return any((nation, name) in leagues for name in row_competition_names(row))


def scope_rows(rows: Iterable[Mapping[str, Any]], scope: Any) -> list[Mapping[str, Any]]:
    """Keep only the clubs inside the enabled scope; an empty scope keeps none."""
    nations, leagues = _scope_pairs(scope)
    if not nations and not leagues:
        return []
    everywhere = GLOBAL_SCOPE in nations
    every_league = (GLOBAL_SCOPE, GLOBAL_SCOPE) in leagues
    kept: list[Mapping[str, Any]] = []
    for row in rows or []:
        if everywhere:
            kept.append(row)
            continue
        nation = nation_of(row)
        if nation in nations:
            kept.append(row)
            continue
        names = row_competition_names(row)
        if every_league and names:
            kept.append(row)
            continue
        if any((nation, name) in leagues for name in names):
            kept.append(row)
    return kept


def scope_league_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Which nation/league pairs a directory can list, and their aliases.

    ``pairs`` is what the exchange filter offers; ``aliases`` maps every name
    a league is known by - the short label of the fixture scan, the full name
    of the club scan, the names the result archive prints - onto the pair that
    is actually listed, so a scope stored with an older label still resolves.

    ``world`` tells a directory that read the world club database from one that
    only lists the fixtures of the day: the second can name what it has, never
    what the save keeps, and a league missing from it proves nothing.
    """
    pairs: set[tuple[str, str]] = set()
    aliases: dict[tuple[str, str], tuple[str, str]] = {}
    world = False
    for row in rows or []:
        if not world and str((row or {}).get("source") or "") == "native_scan":
            world = True
        nation = nation_of(row)
        primary = str((row or {}).get("competition") or "").strip()
        if not primary:
            continue
        pairs.add((nation, primary))
        for name in row_competition_names(row):
            key = (nation, name)
            if key not in aliases:
                aliases[key] = (nation, primary)
    return {"pairs": pairs, "aliases": aliases, "world": world}


def canonicalize_scope(scope: Any, index: Mapping[str, Any] | None) -> dict[str, Any]:
    """Rewrite a stored scope onto the names the directory lists today.

    A save that was set up before a league was renamed - or with the short
    label the fixture scan printed while the club scan now prints the full
    name - keeps its clubs: every league that resolves through an alias, and
    every league an old scan filed under the shared ``未分类`` bucket while
    exactly one nation hosts it, is folded onto the listed pair.  Anything
    that resolves nowhere is kept as it is, so nothing is ever dropped.
    """
    nations, leagues = _scope_pairs(scope)
    source = index if isinstance(index, Mapping) else {}
    pairs = set(source.get("pairs") or ())
    aliases = source.get("aliases") or {}
    folded: list[tuple[str, str]] = []
    for nation, competition in sorted(leagues):
        if (nation, competition) in pairs:
            folded.append((nation, competition))
            continue
        target = aliases.get((nation, competition))
        if target is not None:
            folded.append(target)
            continue
        if nation in {"", "未分类", "未知"}:
            hosts = sorted({name for name, label in pairs if label == competition})
            if len(hosts) == 1:
                folded.append((hosts[0], competition))
                continue
        folded.append((nation, competition))
    return {
        "nations": sorted(nations),
        "leagues": [[nation, competition] for nation, competition in sorted(set(folded))],
    }


def reconcile_scope(
    scope: Any, index: Mapping[str, Any] | None, *, authoritative: bool = True,
) -> dict[str, Any]:
    """Fold a stored scope onto the listed leagues and name what is left.

    A scope can name a league this directory cannot serve: a save that was
    traded under a different club database, a league the world scan has never
    seen, or a label of a save that is no longer connected.  Such an entry can
    never list a club, yet it would still be counted as an enabled exchange and
    the filter would promise markets the board cannot open.  Entries that
    resolve through an alias stay, everything the directory cannot resolve is
    reported, and a directory that knows no league at all proves nothing, so
    nothing is ever dropped from an empty one.

    ``authoritative`` says the directory read the world club database instead of
    the fixtures of one day.  A window of fixtures is written by the odds scan
    of the moment - a narrower market scan empties it, a new game day shifts it -
    and a league missing from it is a league the window did not reach, not a
    league the save lost.  Only a world directory may park a tick, so a scope
    read through a fixture window is folded and reported, never narrowed.
    """
    canonical = canonicalize_scope(scope, index)
    source = index if isinstance(index, Mapping) else {}
    known = set(source.get("pairs") or ())
    known.update((source.get("aliases") or {}).keys())
    if not known:
        return {"scope": canonical, "dropped": [], "confirmed": False}
    kept: list[list[str]] = []
    dropped: list[list[str]] = []
    for nation, competition in canonical["leagues"]:
        # The world entry names no league a directory could list, so it is
        # never a label of a save that is gone: it stays, whatever is known.
        listed = nation == GLOBAL_SCOPE or (nation, competition) in known
        target = kept if listed else dropped
        target.append([nation, competition])
    if not dropped:
        return {"scope": canonical, "dropped": [], "confirmed": True}
    if not authoritative:
        return {"scope": canonical, "dropped": dropped, "confirmed": False}
    canonical = {**canonical, "leagues": kept}
    return {"scope": canonical, "dropped": dropped, "confirmed": True}


def apply_scope_repair(
    state: dict[str, Any], dropped: Any, *, game_date: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    """Park the ticked leagues a world directory cannot list; release the rest.

    A league a *complete* world club directory cannot list opens no exchange,
    yet the tick that named it is not the directory's to delete: a directory
    that read the fixtures of one day lists a window, not the database, so the
    next read - the world club scan, a wider market scan - can list the league
    again, and its clubs must then rejoin the board with the candles, the share
    books and the lots they had.  The tick therefore stays where it is and is
    only parked in ``scope_suspended``, which the board, the counters, the
    filter and the settlement all leave out until a read can serve it.

    ``confirmed`` is what :func:`reconcile_scope` answered: a directory that
    proves nothing parks nothing and releases nothing, so a half-read world
    database never empties an exchange.  Only a change of the parked set is
    written as a notice, so a long run of ticks stays quiet about a league that
    simply waits for its clubs to be read.
    """
    pairs = sorted({
        (str(item[0]).strip(), str(item[1]).strip())
        for item in dropped or []
        if isinstance(item, (list, tuple)) and len(item) == 2
        and str(item[0]).strip() and str(item[1]).strip()
    })
    before = suspended_pairs(state)
    if not confirmed:
        return {
            "suspended": sorted([list(pair) for pair in before]),
            "resumed": [], "notice": None, "notice_resume": None,
        }
    _nations, ticked = _scope_pairs(state.get("scope"))
    parked = sorted({pair for pair in pairs if pair in ticked})
    after = set(parked)
    resumed = sorted(pair for pair in before if pair in ticked and pair not in after)
    state["scope_suspended"] = [[nation, competition] for nation, competition in parked]
    notice = None
    if after - before:
        notice = _notice(
            state, "scope_suspend", game_date, count=len(after - before),
            total=len(after), competitions=[list(pair) for pair in sorted(after - before)],
        )
    notice_resume = None
    if resumed:
        notice_resume = _notice(
            state, "scope_resume", game_date, count=len(resumed),
            competitions=[list(pair) for pair in resumed],
        )
    return {
        "suspended": [[nation, competition] for nation, competition in parked],
        "resumed": [[nation, competition] for nation, competition in resumed],
        "notice": notice, "notice_resume": notice_resume,
    }


def restore_pruned_scope(
    state: dict[str, Any], index: Mapping[str, Any] | None, *,
    game_date: str = "", authoritative: bool = False,
) -> dict[str, Any]:
    """Put back, once, the leagues an earlier build deleted from this save.

    V2.8.0beta deleted every ticked league the directory of the day could not
    list, and the directory of the day could be a fixture window: a scope of
    hundreds of leagues collapsed to the handful of the window with the notice
    naming hundreds of leagues "not in this save" that a world club read lists
    perfectly.  A scope parked by :func:`apply_scope_repair` is never deleted
    again, so this is the one-off that gives such a save its exchanges back:
    the newest prune notice is read, every pair it names that today's world
    directory can list is ticked again, and the club rows, candles and share
    books those clubs still own return to the board where they left off.

    Nothing happens while the directory is not the world database, and a save
    where nothing came back keeps its chance: the notice is read again on the
    next tick, which is how a league whose clubs arrive with a later scan is
    still served.  Only a repair that really ticked a league back is recorded,
    so the pairs are never added a second time.
    """
    if state.get("scope_pruned_restored"):
        return {"restored": [], "notice": None}
    notice = next(
        (
            row for row in reversed(list(state.get("notices") or []))
            if isinstance(row, Mapping) and str(row.get("kind") or "") == "scope_prune"
        ),
        None,
    )
    if notice is None:
        # Nothing was ever deleted here, so nothing is recorded: a save that
        # keeps no prune notice pays one scan of an empty match and stays open
        # to a repair, in case an older build prunes it later.
        return {"restored": [], "notice": None}
    pairs = [
        (str(item[0]).strip(), str(item[1]).strip())
        for item in notice.get("competitions") or []
        if isinstance(item, (list, tuple)) and len(item) == 2
    ]
    if not authoritative:
        return {"restored": [], "notice": None}
    source = index if isinstance(index, Mapping) else {}
    known = set(source.get("pairs") or ())
    known.update((source.get("aliases") or {}).keys())
    scope = normalize_scope(state.get("scope"))
    ticked = {(nation, competition) for nation, competition in scope["leagues"]}
    folded = canonicalize_scope(
        {"nations": [], "leagues": [[nation, competition] for nation, competition in pairs]},
        index,
    )
    restored = sorted({
        (nation, competition) for nation, competition in (
            (str(item[0]), str(item[1])) for item in folded["leagues"]
        )
        if (nation, competition) in known and (nation, competition) not in ticked
    })
    if not restored:
        # The notice names leagues this directory cannot list either - a
        # competition the save really dropped.  The chance stays open so a
        # later world read can still serve it, and nothing is written.
        return {"restored": [], "notice": None}
    state["scope_pruned_restored"] = 1
    state["scope"] = {
        "nations": list(scope["nations"]),
        "leagues": sorted(
            [list(pair) for pair in ticked]
            + [[nation, competition] for nation, competition in restored],
        ),
    }
    entry = _notice(
        state, "scope_restore", game_date, count=len(restored),
        competitions=[list(pair) for pair in restored],
    )
    return {"restored": [[nation, competition] for nation, competition in restored], "notice": entry}


def save_competition_index(output: dict[str, Any]) -> tuple[frozenset[int], frozenset[str]]:
    """The competition ids and names the connected save actually runs.

    Two scans of the same save feed this index: ``competition_formats``, which
    carries the parsed stage tables, and ``competitions``, the plain list the
    fixture scan compiles for every competition the save knows about.  A
    competition the format parser could not answer for - a league whose table
    sits outside the scanned window, for instance - is still a competition of
    this save, and leaving it out of the index hid it from the exchange filter,
    so both scans are read.  A save that has not been read yet (or a payload
    without either list) yields an empty index, and every club then counts as
    outside the save instead of being mislabelled.
    """
    ids: set[int] = set()
    names: set[str] = set()
    for row in (
        *((output or {}).get("competition_formats") or []),
        *((output or {}).get("competitions") or []),
    ):
        if not isinstance(row, dict):
            continue
        if str(row.get("competition_kind") or row.get("kind") or "") not in {"league", "cup"}:
            continue
        try:
            competition_id = int(row.get("competition_id") or row.get("id") or 0)
        except (TypeError, ValueError):
            competition_id = 0
        if competition_id > 0:
            ids.add(competition_id)
        name = str(row.get("competition_name") or row.get("name") or "").strip()
        if name:
            names.add(name)
    return frozenset(ids), frozenset(names)


def club_in_save(
    row: Mapping[str, Any] | None,
    ids: frozenset[int] | set[int],
    names: frozenset[str] | set[str],
) -> bool:
    """Whether one directory club plays in a competition of the save."""
    if not ids and not names:
        return False
    value = row or {}
    try:
        competition_id = int(value.get("competition_id") or 0)
    except (TypeError, ValueError):
        competition_id = 0
    if competition_id > 0 and competition_id in ids:
        return True
    if str(value.get("competition") or "").strip() in names:
        return True
    for name in value.get("competitions") or []:
        if str(name or "").strip() in names:
            return True
    return False


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def empty_state() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "initialized": False,
        "initialized_at": "",
        "initialized_game_date": "",
        "initialized_ordinal": 0,
        "last_seen_ordinal": 0,
        "last_game_date": "",
        "season": "",
        "scope": {"nations": [], "leagues": []},
        "nations": {},
        "holdings": {},
        "missing": {},
        "daily": {},
        "receipts": [],
        "impact": {},
        "finance": {},
        "orders": [],
        "watchlist": [],
        "realized_profit": 0.0,
        "notices": [],
        "trades": [],
    }


def _migrate_legacy(state: dict[str, Any]) -> bool:
    """Carry older documents over to the scoped nation markets.

    A V1 document stored one ready-made stock per listed club; prices are
    derived now, so only the account history is worth keeping.  A V2 document
    listed every nation on the first visit; it keeps exactly those exchanges
    enabled so an upgraded save does not lose its board.
    """
    migrated = False
    legacy_stocks = state.pop("stocks", None)
    legacy_stocks = legacy_stocks if isinstance(legacy_stocks, dict) else {}
    state.pop("index", None)
    for key, holding in (state.get("holdings") or {}).items():
        if not isinstance(holding, dict):
            continue
        stock = legacy_stocks.get(str(key))
        stock = stock if isinstance(stock, dict) else {}
        holding["code"] = str(holding.get("code") or stock.get("code") or "")
        holding["name"] = str(holding.get("name") or stock.get("name") or "")
        holding["nation"] = str(holding.get("nation") or stock.get("nation") or "")
        holding["competition"] = str(holding.get("competition") or stock.get("competition") or "")
        last = _number(holding.get("last_price"))
        if last <= 0:
            last = _number(stock.get("price")) or _number(holding.get("avg_cost"))
        holding["last_price"] = quote(last)
    migrated = migrated or bool(legacy_stocks)
    if "scope" not in state:
        nations = sorted({
            str(name) for name in (state.get("nations") or {}) if str(name)
        })
        if nations:
            state["scope"] = {"nations": nations, "leagues": []}
            migrated = True
    return migrated


def _normalize(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        return empty_state()
    migrated = _migrate_legacy(state)
    base = empty_state()
    for key, value in base.items():
        state.setdefault(key, value)
    for key in ("nations", "holdings", "missing", "impact", "finance", "daily"):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    for key in ("notices", "trades", "watchlist", "orders", "receipts"):
        if not isinstance(state.get(key), list):
            state[key] = []
    state["scope"] = normalize_scope(state.get("scope"))
    try:
        state["version"] = int(state.get("version") or SCHEMA_VERSION)
    except (TypeError, ValueError):
        state["version"] = SCHEMA_VERSION
    # Normalising brings the document up to the current shape: every field the
    # current schema knows about now exists, so the stamp follows.  A document
    # is therefore never left claiming an older shape than it has, and a newer
    # one written by a later build is never rewritten backwards.
    if migrated or state["version"] < SCHEMA_VERSION:
        state["version"] = SCHEMA_VERSION
    return state


def market_lock() -> threading.RLock:
    """Serialise a whole load -> mutate -> save trading cycle."""
    return LOCK


def load_state(scope_id: str | None = None) -> dict[str, Any]:
    with LOCK:
        payload = load_document(DOCUMENT, None, scope_id)
        if not isinstance(payload, dict):
            return empty_state()
        return _normalize(payload)


def save_state(state: dict[str, Any], scope_id: str | None = None) -> None:
    state["updated_at"] = _now()
    state["version"] = SCHEMA_VERSION
    with LOCK:
        save_document(DOCUMENT, state, scope_id)


def _notice(state: dict[str, Any], kind: str, game_date: str, **fields: Any) -> dict[str, Any]:
    entry = {
        "id": str(uuid.uuid4()), "at": _now(), "game_date": str(game_date or ""),
        "kind": kind, **fields,
    }
    state["notices"].append(entry)
    state["notices"] = state["notices"][-NOTICE_LIMIT:]
    return entry


def receipt(
    state: dict[str, Any], kind: str, game_date: str, **fields: Any,
) -> dict[str, Any]:
    """A settlement slip: what a queued application did when it cleared.

    Notices are the running tape of the exchange; a receipt is the one slip the
    account is shown the moment a block trade or a reserved sale lands, so the
    player can read the capital share and the price they moved without opening
    the order book.
    """
    entry = {
        "id": str(uuid.uuid4()), "at": _now(), "game_date": str(game_date or ""),
        "kind": kind, **fields,
    }
    slips = state.get("receipts")
    if not isinstance(slips, list):
        slips = []
        state["receipts"] = slips
    slips.append(entry)
    del slips[:max(0, len(slips) - max(1, RECEIPT_LIMIT))]
    return entry


# ---------------------------------------------------------------------------
# Exchange registry
# ---------------------------------------------------------------------------


def _select_components(rows: Iterable[Mapping[str, Any]]) -> list[list[Any]]:
    ranked = sorted(
        (row for row in rows or [] if _int((row or {}).get("id")) > 0),
        key=lambda row: (-intrinsic_value(row), _int(row.get("id"))),
    )[:INDEX_COMPONENTS]
    return [[_int(row.get("id")), int(intrinsic_value(row))] for row in ranked]


def _nation_entry(state: dict[str, Any], nation: str) -> dict[str, Any]:
    entry = state["nations"].get(nation)
    if not isinstance(entry, dict):
        entry = {}
        state["nations"][nation] = entry
    return entry


def _sync_share_book(
    entry: dict[str, Any], group: Iterable[Mapping[str, Any]], ordinal: int,
) -> int:
    """Keep one share record per listed club; return (new, frozen) counts.

    The record freezes the three facts a quote cannot re-derive: the capital
    the club listed with (``i``), the price the next issue is measured
    against (``b``) and the days an issue was forced (``s``).  A club that
    joins an already open exchange lists at today's quote, exactly like a
    club that enters the save in a January window; a club that leaves keeps
    its record, because a directory that is still being read, a league the
    player froze and a club that simply dropped out of the enabled leagues must
    all come back to the capital history they left with - a fresh listing would
    erase the issues the account paid for.
    """
    rows = [row for row in group or [] if _int((row or {}).get("id")) > 0]
    stored = entry.get("shares")
    stored = stored if isinstance(stored, dict) else {}
    book: dict[str, Any] = {
        key: record for key, record in stored.items() if isinstance(record, dict)
    }
    added = 0
    frozen = 0
    for row in rows:
        key = str(_int(row.get("id")))
        record = stored.get(key)
        if not isinstance(record, dict) or share_base(record) <= 0:
            record = {"i": initial_shares(row), "b": share_price(row, ordinal), "s": []}
            added += 1
        elif _int(record.get("i")) <= 0:
            # A record written before the capital was frozen.  It keeps the
            # capital that was in effect until now, so freezing never moves a
            # quote by itself, and an issue base left on another scale falls
            # back to today's quote instead of pointing at a level the club
            # can no longer reach.
            record["i"] = shares_at(row, ordinal, record)
            current = share_price(row, ordinal, record)
            base = share_base(record)
            if current > 0 and base > current * LEGACY_PRICE_BAND[1]:
                record["b"] = current
            frozen += 1
        book[key] = record
    entry["shares"] = book
    return added, frozen


def registry_sync(
    state: dict[str, Any], rows: Any, *, game_date: str, ordinal: int, season: str = "",
    confirm_absent: bool = True, ignore: Iterable[Any] = (),
) -> dict[str, Any]:
    """Open new exchanges, keep the index composition current, settle departures.

    Runs once per load.  Nothing here simulates a price: the exchange registry
    only records what cannot be derived again - which nation opened, when, and
    the index base that makes its chart continuous across rebalances.

    ``confirm_absent`` is false while the save is still being read: a directory
    that is only half filled is not a club database that lost its clubs, so
    nothing may be read as delisted from it.  ``ignore`` names the clubs of a
    parked exchange: their league is only waiting for a directory that can list
    it, so their absence is the directory's, never the save's.
    """
    rows_by_id = _row_index(rows)
    result: dict[str, Any] = {
        "initialized": False, "opened": [], "settlements": [],
        "cash_credit": 0.0, "clubs": len(rows_by_id), "nations": 0,
        "rebalanced": False, "club_change": 0, "share_book": 0,
        "share_frozen": 0, "unconfirmed": 0, "listing_repaired": 0,
        "enabled": market_enabled(state),
    }
    if not rows_by_id:
        return result
    with LOCK:
        groups = _group_by_nation(rows_by_id.values())
        result["nations"] = len(groups)
        opening = not state.get("initialized")
        if opening:
            state["initialized"] = True
            state["initialized_at"] = _now()
            state["initialized_game_date"] = str(game_date or "")
            state["initialized_ordinal"] = int(ordinal)
            result["initialized"] = True

        rebalance = opening or str(season or "") != str(state.get("season") or "")
        club_change = 0
        listing_repaired = 0
        opened: list[str] = []
        for nation, group in groups.items():
            entry = _nation_entry(state, nation)
            fresh = "listed_ordinal" not in entry
            resync = bool(entry.pop("scope_resync", False))
            if not fresh and _int(entry.get("listed_ordinal")) > int(ordinal):
                # A game day that went backwards leaves the exchange listing in
                # a future the save no longer reaches.  The registry puts it
                # back on the day the board is really quoting, so the exchange
                # stops reading as "opened today" and its charts fill again.
                entry["listed_ordinal"] = int(ordinal)
                entry["listed_game_date"] = str(game_date or "")
                listing_repaired += 1
            if fresh:
                entry["listed_ordinal"] = int(ordinal)
                entry["listed_game_date"] = str(game_date or "")
                opened.append(nation)
            previous = _int(entry.get("clubs"))
            entry["clubs"] = len(group)
            added, frozen = _sync_share_book(entry, group, ordinal)
            result["share_book"] += added
            result["share_frozen"] += frozen
            if not fresh and not resync:
                club_change += abs(int(entry["clubs"]) - previous)
            if rebalance:
                entry["components"] = _select_components(group)
                continue
            if not entry.get("components"):
                entry["components"] = _select_components(group)
                continue
            if resync:
                _rebase_nation(entry, group, rows_by_id, ordinal)
                continue
            known = {
                _int(item[0]) for item in entry.get("components") or []
                if isinstance(item, (list, tuple)) and len(item) == 2
            }
            if any(club_id not in rows_by_id for club_id in known):
                entry["components"] = _select_components(group)

        if rebalance:
            _rebase_components(state, groups, rows_by_id, ordinal)
            state["season"] = str(season or "")
            result["rebalanced"] = True

        if opening:
            _notice(
                state, "init", game_date, nations=len(groups), clubs=len(rows_by_id),
            )
        else:
            if opened:
                _notice(state, "listing", game_date, nations=len(opened), items=opened[:12])
            if club_change:
                _notice(state, "club_change", game_date, count=club_change, nations=len(groups))
            if result["rebalanced"]:
                _notice(state, "rebalance", game_date, nations=len(groups))

        result["opened"] = opened
        result["club_change"] = club_change
        result["listing_repaired"] = listing_repaired
        settlements, credited, unconfirmed, forgotten = _settle_missing_holdings(
            state, rows_by_id, game_date, ordinal, confirm=confirm_absent,
            ignore=ignore,
        )
        result["settlements"] = settlements
        result["cash_credit"] = credited
        result["unconfirmed"] = unconfirmed
        result["missing_forgotten"] = forgotten
        state["last_game_date"] = str(game_date or "")
        state["last_seen_ordinal"] = int(ordinal)
    return result


def detect_splits(
    state: dict[str, Any], rows: Any, *, game_date: str, ordinal: int,
) -> dict[str, Any]:
    """Expand the capital of every club whose quote doubled since its base.

    Called once per game day by the refresh hook, after the registry has made
    sure every listed club carries a share record.  An issue is worth its
    round size: the club buys no shares back and the holdings of the account
    scale by the same ratio (shares up, average cost down), so a lot keeps its
    stake instead of gaining or losing on the day.  The quote that forced the
    issue is reported, then the diluted close right after the capital increase
    becomes the base of the next one: every issue - the first included - needs
    the quote to double from its own base, and capital only ever grows.
    """
    rows_by_id = _row_index(rows)
    events: list[dict[str, Any]] = []
    # The account's own orders must not force an issue: the trigger is the
    # club's market plus the capital it was given, never the price an order of
    # the account itself pushed up for a few days.
    quiet = finance_extras(state)
    for nation, entry in (state.get("nations") or {}).items():
        if not isinstance(entry, dict):
            continue
        book = entry.get("shares")
        if not isinstance(book, dict):
            continue
        for key, record in book.items():
            if not isinstance(record, dict):
                continue
            club_id = _int(key)
            row = rows_by_id.get(club_id)
            if row is None:
                continue
            base = share_base(record)
            if base <= 0:
                continue
            shares_before = shares_at(row, ordinal, record)
            price = share_price(row, ordinal, record, quiet)
            if price + 1e-9 < base * SHARE_SPLIT_TRIGGER:
                continue
            index = len(share_splits(record))
            record.setdefault("s", []).append(int(ordinal))
            shares_after = shares_at(row, ordinal, record)
            # The issue dilutes the quote on the same close: the ex-rights
            # price is the new base, so the next issue needs another doubling
            # measured from the price the holders actually see now.
            ex_rights = quote(share_price(row, ordinal, record, quiet))
            record["b"] = ex_rights
            event = {
                "nation": nation, "club_id": club_id,
                "name": str(row.get("name") or ""),
                "code": stock_code(row.get("name"), row.get("short_name"), club_id),
                "issue": index + 1, "ratio": split_ratio(club_id, index),
                "price": quote(price), "base": ex_rights,
                "shares_before": shares_before, "shares_after": shares_after,
            }
            holding = state["holdings"].get(key)
            if isinstance(holding, dict) and _int(holding.get("qty")) > 0:
                qty = _int(holding.get("qty"))
                cost = qty * _number(holding.get("avg_cost"))
                scaled = max(1, int(round(qty * shares_after / shares_before)))
                holding["qty"] = scaled
                holding["avg_cost"] = quote(cost / scaled)
                event["holding_qty"] = scaled
            _notice(
                state, "split", game_date, club_id=club_id, code=event["code"],
                name=event["name"], ratio=event["ratio"], issue=event["issue"],
                before=shares_before, after=shares_after, trigger=event["price"],
                base=ex_rights,
            )
            events.append(event)
    return {"events": events, "count": len(events)}


def legacy_priced(price: Any, capital: Any, cap_now: Any) -> bool:
    """Whether one trade price belongs to one capital scale.

    A trade of a club with ``capital`` shares implies a market cap of
    ``price * capital``; a club's cap moves slowly, so a price whose implied
    cap lands inside :data:`LEGACY_PRICE_BAND` around today's cap was printed
    on that scale.
    """
    rate = _number(price)
    shares = _number(capital)
    cap = _number(cap_now)
    if rate <= 0 or shares <= 0 or cap <= 0:
        return False
    low, high = LEGACY_PRICE_BAND
    implied = rate * shares
    return cap * low <= implied <= cap * high


def reads_legacy_capital(
    price: Any, *, capital: int, cap_now: float,
) -> bool:
    """Whether one printed trade price belongs to the legacy share count.

    Both models price the whole club at the same market cap, so the reading
    whose implied capitalisation lands closest to today's is the one the trade
    was printed on.  The legacy reading must also be inside
    :data:`LEGACY_PRICE_BAND` of today's cap, and a tie keeps today's reading:
    a lot that already trades on the club's own capital must never be scaled
    by the repair.
    """
    rate = _number(price)
    if rate <= 0 or capital <= 0 or cap_now <= 0:
        return False
    if not legacy_priced(rate, LEGACY_SHARES_OUTSTANDING, cap_now):
        return False
    legacy_gap = abs(rate * LEGACY_SHARES_OUTSTANDING - cap_now)
    today_gap = abs(rate * capital - cap_now)
    return legacy_gap < today_gap


def _legacy_lot(
    history: Iterable[Mapping[str, Any]], *, capital: int, cap_now: float,
    price_now: float,
) -> tuple[float, float, bool]:
    """Re-read one club's trade log in today's capital scale.

    A trade printed against the legacy global share count bought
    ``price_then / price_now`` times the shares it recorded, so the money a
    holder put in still buys the same slice of the club; a trade that was
    already on the club's own scale is read as it stands.
    """
    qty = 0.0
    cost = 0.0
    touched = False
    for trade in history:
        shares = _int(trade.get("qty"))
        price = _number(trade.get("price"))
        if shares <= 0 or price <= 0:
            continue
        scale = 1.0
        if reads_legacy_capital(price, capital=capital, cap_now=cap_now):
            scale = price / price_now
            touched = True
        side = str(trade.get("side") or "")
        if side == "buy":
            qty += shares * scale
            cost += _number(trade.get("amount")) + _number(trade.get("fee"))
        elif side in {"sell", "delist"}:
            average = cost / qty if qty > 0 else 0.0
            sold = min(qty, shares * scale)
            qty -= sold
            cost -= sold * average
    return qty, cost, touched


def repair_legacy_capital(
    state: dict[str, Any], rows: Any, *, game_date: str, ordinal: int,
) -> dict[str, Any]:
    """Rebase lots bought against the legacy global share count, once.

    Builds up to V2.7.4beta priced every club against one global share count
    (:data:`LEGACY_SHARES_OUTSTANDING`); a club now lists with its own
    capital, and the two scales are orders of magnitude apart.  A lot bought
    on the old one keeps its value: the trade log is replayed in today's
    scale and the holding is written back with the shares - and the average
    cost - the same money buys today, so nobody lost on a number that never
    traded.  The repair runs once per save and never touches the capital.
    """
    result: dict[str, Any] = {"repairs": [], "count": 0, "checked": False}
    if _int(state.get("capital_repair")) >= CAPITAL_REPAIR_VERSION:
        return result
    result["checked"] = True
    rows_by_id = _row_index(rows)
    books = share_books(state)
    trades_by_club: dict[int, list[Mapping[str, Any]]] = {}
    for trade in state.get("trades") or []:
        if isinstance(trade, Mapping):
            trades_by_club.setdefault(_int(trade.get("club_id")), []).append(trade)
    for key, holding in state["holdings"].items():
        if not isinstance(holding, dict) or _int(holding.get("qty")) <= 0:
            continue
        club_id = _int(key)
        row = rows_by_id.get(club_id)
        book = books.get(club_id)
        history = [
            trade for trade in trades_by_club.get(club_id, [])
            if _int(trade.get("qty")) > 0 and _number(trade.get("price")) > 0
        ]
        if row is None or not book or not history:
            continue
        capital = listed_shares(row, book)
        cap_now = market_cap(row, ordinal)
        price_now = share_price(row, ordinal, book)
        if capital <= 0 or cap_now <= 0 or price_now <= 0:
            continue
        qty, cost, touched = _legacy_lot(
            history, capital=capital, cap_now=cap_now, price_now=price_now,
        )
        shares_now = int(round(qty))
        if not touched or shares_now <= 0:
            continue
        before = _int(holding.get("qty"))
        holding["qty"] = shares_now
        holding["avg_cost"] = quote(max(0.0, cost) / shares_now)
        if _int(holding.get("locked_qty")) > 0:
            holding["locked_qty"] = shares_now
        event = {
            "nation": nation_of(row), "club_id": club_id, "code": str(holding.get("code") or ""),
            "name": str(row.get("name") or holding.get("name") or ""),
            "shares_before": before, "shares_after": shares_now,
            "avg_cost": holding["avg_cost"], "capital": capital,
        }
        _notice(
            state, "capital", game_date, club_id=club_id, code=event["code"],
            name=event["name"], before=before, after=shares_now,
        )
        result["repairs"].append(event)
    state["capital_repair"] = CAPITAL_REPAIR_VERSION
    result["count"] = len(result["repairs"])
    return result


def _rebase_components(
    state: dict[str, Any], groups: Mapping[str, list[Mapping[str, Any]]],
    rows_by_id: dict[int, dict[str, Any]], ordinal: int,
) -> None:
    """Keep each exchange index level continuous across a composition change.

    The new base adds up to the current market cap scaled so that the index
    keeps yesterday's level: a rebalance changes who is measured, not how rich
    the exchange looked the moment before.
    """
    for nation, entry in state["nations"].items():
        if not isinstance(entry, dict):
            continue
        _rebase_nation(entry, groups.get(nation) or [], rows_by_id, ordinal)


def _rebase_nation(
    entry: dict[str, Any], group: Iterable[Mapping[str, Any]],
    rows_by_id: Mapping[int, Mapping[str, Any]], ordinal: int,
) -> None:
    """Rebase one exchange so a composition change keeps its index level."""
    rows = [row for row in group or [] if _int((row or {}).get("id")) > 0]
    if not rows:
        return
    previous = nation_index(entry, rows_by_id, ordinal - 1).get("value") or INDEX_BASE
    share = INDEX_BASE / previous if previous > 0 else 1.0
    components = _select_components(rows)
    entry["components"] = [
        [club_id, int(max(1.0, market_cap(rows_by_id.get(club_id), ordinal) * share))]
        for club_id, _base in components
    ]
    entry["rebalanced_ordinal"] = int(ordinal)


def _settle_holdings(
    state: dict[str, Any], keys: Iterable[Any], *, game_date: str, price_for: Any,
) -> tuple[list[dict[str, Any]], float]:
    """Remove holdings, settling each at ``price_for(key, holding)``."""
    settlements: list[dict[str, Any]] = []
    credited = 0.0
    realized = 0.0
    for key in sorted({str(item) for item in keys}, key=lambda item: _int(item)):
        holding = state["holdings"].get(key)
        if not isinstance(holding, dict):
            state["holdings"].pop(key, None)
            continue
        if str(holding.get("source") or "") == TAKEOVER_SOURCE:
            # A club the group bought outright is not delisted and not sold
            # back at the board's price: it is kept until the group sells it.
            continue
        state["holdings"].pop(key, None)
        qty = _int(holding.get("qty"))
        if qty <= 0:
            continue
        price = quote(price_for(key, holding))
        if price <= 0:
            price = quote(holding.get("avg_cost"))
        avg_cost = _number(holding.get("avg_cost"))
        proceeds = money(qty * price)
        profit = money(proceeds - qty * avg_cost)
        credited += proceeds
        realized += profit
        entry = {
            "club_id": _int(key), "code": str(holding.get("code") or ""),
            "name": str(holding.get("name") or ""), "qty": qty,
            "price": price, "avg_cost": money(avg_cost),
            "amount": proceeds, "profit": profit,
        }
        settlements.append(entry)
        state["trades"].append({
            "id": str(uuid.uuid4()), "at": _now(), "game_date": str(game_date or ""),
            "side": "delist", "club_id": _int(key), "code": entry["code"],
            "name": entry["name"], "qty": qty, "price": price,
            "amount": proceeds, "fee": 0.0, "realized": profit,
            "nation": str(holding.get("nation") or ""),
        })
        state["trades"] = state["trades"][-TRADE_LOG_LIMIT:]
        _notice(
            state, "delisting", game_date, club_id=_int(key), code=entry["code"],
            name=entry["name"], qty=qty, price=price, amount=proceeds,
        )
    if realized:
        state["realized_profit"] = money(_number(state.get("realized_profit")) + realized)
    return settlements, money(credited)


def watched_club_keys(state: Mapping[str, Any] | None) -> list[str]:
    """Every club the market is still waiting on an answer for.

    A club is watched while it carries a lot of the account and while an
    application of the account names it: both a settlement and a withdrawal are
    answers the account must be given, so both wait for the same proof that the
    club really left the database.
    """
    source = state if isinstance(state, Mapping) else {}
    keys = {str(key) for key in (source.get("holdings") or {})}
    for order in pending_orders(source):
        club_id = _int(order.get("club_id"))
        if club_id > 0:
            keys.add(str(club_id))
    return sorted(keys, key=_int)


def parked_clubs(
    state: Mapping[str, Any] | None, parked: Any = None,
) -> list[int]:
    """The watched clubs whose exchange waits for a directory that lists it.

    A parked league lists no club while it waits, and a settlement reads that
    silence as a delisting.  It is not one: the lots of the exchange are kept
    off the board, never sold, so every watched club of a parked league is
    named here and left out of the reading.  A lot carries the nation and the
    league it was bought under, so the parked pairs name their clubs exactly;
    a lot without a league label waits with the nation it traded in.
    """
    source = state if isinstance(state, Mapping) else {}
    pairs = {
        (str(pair[0]).strip(), str(pair[1]).strip())
        for pair in (parked if parked is not None else suspended_pairs(source))
        if isinstance(pair, (list, tuple)) and len(pair) == 2
    }
    if not pairs:
        return []
    nations = {nation for nation, _competition in pairs}
    stored = source.get("holdings")
    stored = stored if isinstance(stored, Mapping) else {}
    waiting: set[int] = set()
    for key in watched_club_keys(source):
        holding = stored.get(str(key))
        holding = holding if isinstance(holding, Mapping) else {}
        nation = str(holding.get("nation") or "").strip()
        competition = str(holding.get("competition") or "").strip()
        if (nation, competition) in pairs:
            waiting.add(_int(key))
        elif nation and not competition and nation in nations:
            waiting.add(_int(key))
    return sorted(waiting)


def _absence_confirmed(state: Mapping[str, Any], club_id: Any, ordinal: Any) -> bool:
    """Whether a club has been missing from the directory since an earlier day.

    The daily tick appends and the app's scan fills the directory in over
    minutes, so one reading without a club says nothing: only a club that was
    still gone on an earlier game day is read as one that left the database.
    """
    absent = (state or {}).get("missing") if isinstance(state, Mapping) else None
    if not isinstance(absent, Mapping):
        return False
    first = _int(absent.get(str(_int(club_id))))
    today = _int(ordinal)
    return bool(first) and (today <= 0 or first < today)


def _remember_absence(state: dict[str, Any], key: Any, ordinal: Any) -> None:
    """Write the first day a watched club was seen missing, once."""
    absent = state.get("missing")
    if not isinstance(absent, dict):
        absent = {}
        state["missing"] = absent
    name = str(key)
    if not _int(absent.get(name)):
        absent[name] = _int(ordinal) or 1


def _forget_absence(state: dict[str, Any], key: Any) -> None:
    """Drop the sighting of a club that was answered for or settled."""
    absent = state.get("missing")
    if isinstance(absent, dict):
        absent.pop(str(key), None)


def _settle_missing_holdings(
    state: dict[str, Any], rows_by_id: dict[int, dict[str, Any]], game_date: str,
    ordinal: Any = None, *, confirm: bool = True, ignore: Iterable[Any] = (),
) -> tuple[list[dict[str, Any]], float, int, int]:
    """Clubs that left the database are bought out at their last known quote.

    The daily tick only sees the clubs of the enabled exchanges, so a club
    outside that list is not necessarily gone.  A frozen lot is parked on
    purpose - its exchange is closed, not deleted - and is released again by
    :func:`_unfreeze_holdings`, never by a delisting settlement.  Neither is a
    club that a directory which is still being read has not reached yet: one
    reading without it is a sighting, kept in ``state["missing"]`` so the next
    game day can tell a database that lost a club from a scan that has not
    finished with one.

    The reading covers every club the market is waiting on, not only the lots of
    the account: an application that names a club which never reached a holding
    is cancelled by the queue, and it needs the same sighting to get there.
    """
    today = _int(ordinal)
    previous = state.get("missing")
    previous = previous if isinstance(previous, dict) else {}
    parked = {_int(item) for item in ignore or ()}
    missing: list[str] = []
    unconfirmed = 0
    absent: dict[str, Any] = {}
    for key in watched_club_keys(state):
        holding = state["holdings"].get(key)
        if _int(key) in rows_by_id:
            continue
        # A parked exchange lists no club while it waits for the directory that
        # can serve it: the club is not gone, the read is.
        if _int(key) in parked:
            continue
        if isinstance(holding, dict) and holding.get("frozen"):
            continue
        first = _int(previous.get(key))
        if confirm and first and (today <= 0 or first < today):
            # Confirmed gone: the lot is settled here and an application of
            # the same club is withdrawn by the queue, which still needs the
            # sighting to be on the record when it runs.
            absent[key] = first
            if isinstance(holding, dict):
                missing.append(key)
            continue
        absent[key] = first or today or 1
        unconfirmed += 1
    state["missing"] = absent
    # Clubs the document was still watching and no longer is: the sighting must
    # not outlive the watch, or the next absence of the same club would be read
    # as an old one and confirm itself on its very first day.
    forgotten = sum(1 for key in previous if key not in absent)
    settlements, credited = _settle_holdings(
        state, missing, game_date=game_date,
        price_for=lambda _key, holding: (
            holding.get("last_price") or holding.get("avg_cost")
        ),
    )
    return settlements, credited, unconfirmed, forgotten


def _freeze_holdings(
    state: dict[str, Any], keys: Iterable[Any], *, game_date: str, price_for: Any,
) -> tuple[list[dict[str, Any]], float]:
    """Lock the lots of a closed exchange instead of selling them.

    Closing an exchange must never destroy a position, so nothing is settled:
    the shares stay on the account, the money stays with the club, and the lot
    is marked frozen with the closing quote of the day it left the scope.  The
    frozen quote is what the panel keeps valuing the lot at, so the capital is
    visibly parked rather than spent.
    """
    frozen: list[dict[str, Any]] = []
    value = 0.0
    for key in sorted({str(item) for item in keys}, key=lambda item: _int(item)):
        holding = state["holdings"].get(key)
        if not isinstance(holding, dict):
            continue
        qty = _int(holding.get("qty"))
        if qty <= 0:
            continue
        price = quote(price_for(key, holding))
        if price <= 0:
            price = quote(holding.get("last_price") or holding.get("avg_cost"))
        amount = money(qty * price)
        holding["frozen"] = True
        holding["frozen_game_date"] = str(game_date or "")
        holding["last_price"] = price
        value += amount
        frozen.append({
            "club_id": _int(key), "code": str(holding.get("code") or ""),
            "name": str(holding.get("name") or ""), "qty": qty,
            "price": price, "amount": money(amount),
        })
    return frozen, money(value)


def _unfreeze_holdings(state: dict[str, Any], keys: Iterable[Any]) -> int:
    """Release the frozen lots of an exchange that just reopened.

    The exchange itself starts from scratch, but the shares the player kept
    through the freeze are owned again and sellable on the new board.
    """
    released = 0
    for key in {str(item) for item in keys}:
        holding = state["holdings"].get(key)
        if not isinstance(holding, dict) or not holding.pop("frozen", False):
            continue
        holding.pop("frozen_game_date", None)
        released += 1
    return released


def apply_scope(
    state: dict[str, Any], rows: Any, scope: Any, *, game_date: str, ordinal: int,
    prices: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Enable or disable exchanges; anything that leaves the scope is frozen.

    ``rows`` is the full club directory, so a club that leaves the scope can
    still be priced at today's close instead of a stale quote.  ``prices``
    carries the appraisals of the clubs that actually need a closing price
    (the application appraises only what it must) and falls back to the last
    stored quote.  A removed exchange keeps its lots as frozen holdings - the
    shares and the capital are locked, not sold - and re-adding that exchange
    releases them again; the surviving exchanges are flagged for a composition
    rebase, so their index level stays continuous while re-enabling a scope
    later lists it from scratch.
    """
    before = normalize_scope(state.get("scope"))
    after = normalize_scope(scope)
    before_nations, before_leagues = _scope_pairs(before)
    after_nations, after_leagues = _scope_pairs(after)

    before_ids: set[int] = set()
    after_ids: set[int] = set()
    nations_after: set[str] = set()
    # The world entry names no nation and no league a directory could match,
    # so membership is read through the same helper the board uses: ticked
    # once it lists every league of the directory, ticked twice every club.
    for row in rows or []:
        club_id = _int((row or {}).get("id"))
        if club_id <= 0:
            continue
        if in_scope(row, before):
            before_ids.add(club_id)
        if in_scope(row, after):
            after_ids.add(club_id)
            nations_after.add(nation_of(row))

    added_leagues = sorted(after_leagues - before_leagues)
    removed_leagues = sorted(before_leagues - after_leagues)
    added_nations = sorted(after_nations - before_nations)
    removed_nations = sorted(before_nations - after_nations)
    result: dict[str, Any] = {
        "scope": after,
        "enabled": bool(after_nations or after_leagues),
        "changed": before != after,
        "added": {
            "nations": added_nations,
            "leagues": [list(item) for item in added_leagues],
            "clubs": len(after_ids - before_ids) if before != after else 0,
        },
        "removed": {
            "nations": removed_nations,
            "leagues": [list(item) for item in removed_leagues],
            "clubs": len(before_ids - after_ids) if before != after else 0,
        },
        "settlements": [],
        "cash_credit": 0.0,
        "listed": len(after_ids),
    }
    if before == after:
        return result

    priced = prices or {}
    books = share_books(state)

    def _close_price(key: Any, holding: Mapping[str, Any]) -> float:
        row = priced.get(_int(key))
        if isinstance(row, Mapping):
            return share_price(row, ordinal, books.get(_int(key)))
        return _number(holding.get("last_price") or holding.get("avg_cost"))

    # A club that leaves the scope cannot deliver a block application any
    # more, so the queue of the closed exchange is withdrawn with it and the
    # money it held is handed back to the account.
    cancelled_orders, order_refund = cancel_orders_for(
        state, sorted(before_ids - after_ids), game_date=game_date,
        reason="交易所已关闭，委托已撤销",
    )
    frozen_lots, frozen_value = _freeze_holdings(
        state, (str(club_id) for club_id in sorted(before_ids - after_ids)),
        game_date=game_date, price_for=_close_price,
    )
    released = _unfreeze_holdings(
        state, (str(club_id) for club_id in sorted(after_ids - before_ids)),
    )
    result["settlements"] = []
    result["cash_credit"] = money(order_refund)
    result["order_cancels"] = cancelled_orders
    result["frozen"] = {
        "lots": frozen_lots, "count": len(frozen_lots), "value": frozen_value,
    }
    result["unfrozen"] = released

    state["nations"] = {
        name: entry for name, entry in state["nations"].items()
        if name in nations_after and isinstance(entry, dict)
    }
    for entry in state["nations"].values():
        entry["scope_resync"] = True
    state["watchlist"] = sorted({
        _int(item) for item in state.get("watchlist") or [] if _int(item) in after_ids
    })
    state["scope"] = after
    parked = suspended_pairs(state)
    if parked:
        # A parked league the player unticks is not waiting for anything any
        # more: the bookkeeping follows the ticks, never outlives them.
        state["scope_suspended"] = [
            [nation, competition] for nation, competition in sorted(parked)
            if (nation, competition) in after_leagues
        ]

    if added_nations or added_leagues:
        _notice(
            state, "scope_add", game_date, nations=len(added_nations),
            leagues=len(added_leagues), clubs=result["added"]["clubs"],
            total=len(after_ids),
        )
    if removed_nations or removed_leagues:
        _notice(
            state, "scope_freeze", game_date, nations=len(removed_nations),
            leagues=len(removed_leagues), clubs=result["removed"]["clubs"],
            lots=len(frozen_lots), value=frozen_value, total=len(after_ids),
        )
    if released:
        _notice(
            state, "scope_unfreeze", game_date, lots=released,
            total=len(after_ids),
        )
    if after_nations or after_leagues:
        state["last_game_date"] = str(game_date or "")
        state["last_seen_ordinal"] = int(ordinal)
    return result

# ---------------------------------------------------------------------------
# Snapshot and board
# ---------------------------------------------------------------------------


def fundamentals_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
    source = row or {}
    if source.get("form_points") is not None and source.get("form_wins") is not None:
        form = {
            "points": _int(source.get("form_points")),
            "wins": _int(source.get("form_wins")),
            "draws": _int(source.get("form_draws")),
            "losses": _int(source.get("form_losses")),
        }
    else:
        form = club_form(source.get("recent_results"))
    return {
        "reputation": _int(source.get("reputation")),
        "club_value": int(intrinsic_value(source)),
        "form_points": int(form["points"]),
        "form_wins": int(form["wins"]),
        "form_draws": int(form["draws"]),
        "form_losses": int(form["losses"]),
        "position": _int(source.get("position")) or None,
        "team_count": _int(source.get("team_count")) or None,
        "competition": str(source.get("competition") or ""),
    }


def listing_day(since: Any, ordinal: Any) -> int | None:
    """The exchange day a club started trading, or ``None`` when there is none.

    A day the save has not reached yet is not a listing: it is a day that only
    existed in a game the save came back from - the exchange was opened while
    the clock stood ahead of the save that is loaded now.  Quoting it as one
    would freeze the whole exchange, every change reading zero and every chart
    empty, until the calendar caught up with a day that no longer happens.
    Such a day is ignored instead, so the exchange trades on its record.
    """
    day = _int(since)
    today = _int(ordinal)
    if day <= 0 or (today > 0 and day > today):
        return None
    return day


def stock_public(
    row: Mapping[str, Any], ordinal: int, *,
    code: str = "", holding: Mapping[str, Any] | None = None,
    history: bool = False, watched: bool = False, since: Any = None,
    book: Mapping[str, Any] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """One tradable club: quote, capital, fundamentals and the player's lot.

    ``since`` is the exchange day the club started trading: before it, the
    change is zero instead of a phantom move from a day it was not listed.
    ``book`` is the club's stored share record (issue base and issue days);
    without it the club prices on its initial capital alone.
    """
    source = dict(row or {})
    club_id = _int(source.get("id"))
    factor = market_factor(source, ordinal, club_id, extras)
    injected = finance_of(extras, club_id, ordinal)
    cap = intrinsic_value(source) * factor + injected
    shares = shares_at(source, ordinal, book)
    price = max(MIN_SHARE_PRICE, quote(cap / shares))
    listed = listing_day(since, ordinal)
    previous_ordinal = ordinal - 1 if listed is None or ordinal - 1 >= listed else ordinal
    # The previous close is quoted on today's capital, exactly like the
    # candle of a day a club issued shares: an issue is not a move of its own,
    # and the cash injected after the previous close already belongs to the
    # capital the day is priced against.
    previous_cap = intrinsic_value(source) * market_factor(
        source, previous_ordinal, club_id, extras,
    ) + finance_of(extras, club_id, ordinal)
    previous = max(MIN_SHARE_PRICE, quote(previous_cap / shares))
    change = ((price - previous) / previous) if previous else 0.0
    qty = _int((holding or {}).get("qty"))
    avg_cost = _number((holding or {}).get("avg_cost"))
    market_value = money(qty * price)
    cost = money(qty * avg_cost)
    base_price = quote(share_base(book)) or price
    public = {
        "club_id": club_id,
        "name": str(source.get("name") or ""),
        "short_name": str(source.get("short_name") or ""),
        "code": str(code or stock_code(source.get("name"), source.get("short_name"), club_id)),
        "nation": nation_of(source),
        "competition": str(source.get("competition") or ""),
        "reputation": _int(source.get("reputation")),
        "price": price,
        "prev_close": previous,
        "change": round(change, 6),
        "factor": round(factor, 6),
        "premium": round(factor - 1.0, 6),
        "intrinsic": int(intrinsic_value(source)),
        "market_cap": int(round(cap)),
        "shares": shares,
        "initial_shares": listed_shares(source, book),
        "club_shares": max(0, shares - qty),
        "max_order": max_shares_per_order(shares),
        "share_base": base_price,
        "split_price": split_threshold(book),
        "split_count": len(share_splits(book)),
        "financed_shares": financed_shares(book, ordinal),
        "financed_cash": money(finance_of(extras, club_id, ordinal)),
        "impact": round(trade_impact(impact_of(extras, club_id), ordinal), 6),
        "turnover": turnover_shares(source, ordinal, change, book),
        "fundamentals": fundamentals_row(source),
        "watched": bool(watched),
        "qty": qty,
        "avg_cost": quote(avg_cost),
        "holding_value": market_value,
        "holding_cost": cost,
        "profit": money(market_value - cost) if qty else 0.0,
        "profit_ratio": round((price - avg_cost) / avg_cost, 6) if qty and avg_cost else 0.0,
    }
    if history:
        public["history"] = price_history(
            source, ordinal, since=listed, book=book, extras=extras,
        )
    return public


def price_history(
    row: Mapping[str, Any] | None, ordinal: int, *, days: int = HISTORY_LIMIT,
    since: Any = None, book: Mapping[str, Any] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Daily candles for one club: open, high, low, close and volume.

    The close is the same pure quote the board shows and the open is the
    previous close, so a candle body is exactly the day's change and the tape
    never disagrees with the chart.  The shadows come from :func:`_day_range`
    and the volume from :func:`turnover_shares` of the same day.  Nothing is
    stored: the whole series can be rebuilt for any day of the save.
    """
    source = row or {}
    span = max(2, min(int(days or HISTORY_LIMIT), INDEX_HISTORY_DAYS))
    first = int(ordinal) - span + 1
    listed = listing_day(since, ordinal)
    if listed is not None:
        first = max(first, listed)
    days_back = list(range(first, int(ordinal) + 1))
    if len(days_back) == 1:
        days_back = [first, first]
    club_id = _int(source.get("id"))
    factors: dict[int, float] = {}

    def factor_at(day: int) -> float:
        cached = factors.get(int(day))
        if cached is None:
            cached = market_factor(source, day, club_id, extras)
            factors[int(day)] = cached
        return cached

    candles: list[dict[str, Any]] = []
    for day in days_back:
        previous_day = day - 1 if listed is None or day - 1 >= listed else day
        factor = factor_at(day)
        previous_factor = factor_at(previous_day)
        cash = finance_of(extras, club_id, day)
        previous_cash = finance_of(extras, club_id, previous_day)
        # Candles are the as-traded record: a capital issue is drawn as the
        # dilution it is (the ticket's daily change, which is quoted against
        # an issue-adjusted previous close, is what stays split-free).
        open_price = _price_from_factor(
            source, previous_factor, previous_day, book, previous_cash,
        )
        close_price = _price_from_factor(source, factor, day, book, cash)
        upper, lower = _day_range(club_id, day)
        high = _price_from_factor(
            source, min(FACTOR_CAP, factor + upper), day, book, cash,
        )
        low = _price_from_factor(
            source, max(FACTOR_FLOOR, factor - lower), day, book, cash,
        )
        change = ((close_price - open_price) / open_price) if open_price else 0.0
        candles.append({
            "d": ordinal_date(day),
            "o": open_price,
            "h": max(high, open_price, close_price),
            "l": min(low, open_price, close_price),
            "c": close_price,
            "v": turnover_shares(source, day, change, book),
        })
    return candles


def nation_summary(
    rows: Iterable[Mapping[str, Any]], ordinal: int,
    books: Mapping[int, Mapping[str, Any]] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Whole-world aggregates per nation; the selector and cards read this."""
    summary: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        nation = nation_of(row)
        bucket = summary.get(nation)
        if bucket is None:
            bucket = summary[nation] = {
                "name": nation, "clubs": 0, "cap": 0.0, "cap_prev": 0.0,
                "gainers": 0, "losers": 0, "flat": 0, "turnover": 0.0,
                "reputation": 0, "top": None,
            }
        club_id = _int(row.get("id"))
        base = intrinsic_value(row)
        factor = market_factor(row, ordinal, club_id, extras)
        previous = market_factor(row, ordinal - 1, club_id, extras)
        cash = finance_of(extras, club_id, ordinal)
        previous_cash = finance_of(extras, club_id, ordinal - 1)
        bucket["clubs"] += 1
        bucket["cap"] += base * factor + cash
        bucket["cap_prev"] += base * previous + previous_cash
        bucket["reputation"] += _int(row.get("reputation"))
        edge = (base * factor + cash) - (base * previous + previous_cash)
        if edge > 1e-9:
            bucket["gainers"] += 1
        elif edge < -1e-9:
            bucket["losers"] += 1
        else:
            bucket["flat"] += 1
        bucket["turnover"] += turnover_shares(
            row, ordinal, 0.0, (books or {}).get(club_id),
        )
        top = bucket["top"]
        if top is None or base > top[0]:
            bucket["top"] = (base, club_id)
    for bucket in summary.values():
        bucket["cap"] = money(bucket["cap"])
        bucket["cap_prev"] = money(bucket["cap_prev"])
        bucket["change"] = (
            round((bucket["cap"] - bucket["cap_prev"]) / bucket["cap_prev"], 6)
            if bucket["cap_prev"] > 0 else 0.0
        )
        top = bucket.pop("top", None)
        bucket["top_club"] = top[1] if top else 0
    return summary


def nation_board(
    rows: Iterable[Mapping[str, Any]], ordinal: int, *,
    nations: Iterable[str] | None = None, since: Any = None,
    books: Mapping[int, Mapping[str, Any]] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Full price board per exchange, tickers assigned inside each nation.

    Deliberately free of player state: the same board can be cached for a whole
    game day and then decorated with one account's lots by ``market_view``.
    """
    groups: dict[str, list[Mapping[str, Any]]] = {}
    wanted = {str(item) for item in nations or []}
    for row in rows or []:
        nation = nation_of(row)
        if wanted and nation not in wanted:
            continue
        groups.setdefault(nation, []).append(row)
    boards: dict[str, list[dict[str, Any]]] = {}
    for nation, group in groups.items():
        codes = assign_codes(group)
        boards[nation] = [
            stock_public(
                row, ordinal, code=codes.get(_int(row.get("id")), ""), since=since,
                book=(books or {}).get(_int(row.get("id"))),
                extras=extras,
            )
            for row in group
        ]
    return boards


def nation_index(
    entry: Mapping[str, Any] | None, rows_by_id: Mapping[int, Mapping[str, Any]],
    ordinal: int, *, since: Any = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cap-weighted index over the exchange's stored components."""
    components = [
        (item[0], item[1]) for item in ((entry or {}).get("components") or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    ]
    base_total = sum(_number(base) for _club_id, base in components)
    if not components:
        empty_cap = sum(
            intrinsic_value(row) for row in (rows_by_id or {}).values()
        )
        base_total = empty_cap or 1.0
        components = [
            (_int(row.get("id")), int(intrinsic_value(row)))
            for row in (rows_by_id or {}).values()
        ][:INDEX_COMPONENTS]
    previous_ordinal = int(ordinal) - 1
    listed = listing_day(since, ordinal)
    if listed is not None and previous_ordinal < listed:
        previous_ordinal = int(ordinal)
    return {
        "value": _index_value(components, rows_by_id, ordinal, base_total, extras),
        "prev_close": _index_value(
            components, rows_by_id, previous_ordinal, base_total, extras,
        ),
        "base": INDEX_BASE,
        "components": [club_id for club_id, _base in components],
    }


def _index_value(
    components: Iterable[tuple[int, float]], rows_by_id: Mapping[int, Mapping[str, Any]],
    ordinal: int, base_total: float,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> float:
    if base_total <= 0:
        return INDEX_BASE
    total = 0.0
    for club_id, base in components:
        row = (rows_by_id or {}).get(_int(club_id))
        total += market_cap(row, ordinal, extras) if row else _number(base)
    if total <= 0:
        return INDEX_BASE
    return round(INDEX_BASE * total / base_total, 2)


def index_series(
    entry: Mapping[str, Any] | None, rows_by_id: Mapping[int, Mapping[str, Any]],
    ordinal: int, *, days: int = INDEX_HISTORY_DAYS, since: Any = None,
    books: Mapping[int, Mapping[str, Any]] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Index candles for the last *days* game days, recomputed from components.

    One index candle aggregates the component candles of the same day, so the
    exchange chart and the club charts are drawn from one walk and never
    disagree.  The close stays exactly the value :func:`_index_value` reports.
    """
    span = max(2, min(int(days or INDEX_HISTORY_DAYS), INDEX_HISTORY_DAYS))
    components = [
        (_int(item[0]), _number(item[1]))
        for item in ((entry or {}).get("components") or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    ]
    base_total = sum(base for _club_id, base in components)
    if not components:
        return []
    first = int(ordinal) - span + 1
    listed = listing_day(since, ordinal)
    if listed is not None:
        first = max(first, listed)
    days_back = list(range(first, int(ordinal) + 1))
    if len(days_back) == 1:
        days_back = [first, first]
    rows = rows_by_id or {}
    factors: dict[tuple[int, int], float] = {}

    def factor_at(row: Mapping[str, Any], club_id: int, day: int) -> float:
        key = (int(club_id), int(day))
        cached = factors.get(key)
        if cached is None:
            cached = market_factor(row, day, club_id, extras)
            factors[key] = cached
        return cached

    def scaled(total: float) -> float:
        if base_total <= 0:
            return INDEX_BASE
        return round(INDEX_BASE * total / base_total, 2)

    candles: list[dict[str, Any]] = []
    for day in days_back:
        previous_day = day - 1 if listed is None or day - 1 >= listed else day
        open_total = high_total = low_total = close_total = 0.0
        volume = 0.0
        for club_id, base in components:
            row = rows.get(_int(club_id))
            if not row:
                open_total += _number(base)
                high_total += _number(base)
                low_total += _number(base)
                close_total += _number(base)
                continue
            identity = _int(club_id)
            close_factor = factor_at(row, identity, day)
            open_factor = factor_at(row, identity, previous_day)
            upper, lower = _day_range(identity, day)
            intrinsic = intrinsic_value(row)
            cash = finance_of(extras, identity, day)
            previous_cash = finance_of(extras, identity, previous_day)
            open_total += intrinsic * open_factor + previous_cash
            close_total += intrinsic * close_factor + cash
            high_total += intrinsic * max(
                min(FACTOR_CAP, close_factor + upper), open_factor, close_factor,
            ) + cash
            low_total += intrinsic * min(
                max(FACTOR_FLOOR, close_factor - lower), open_factor, close_factor,
            ) + cash
            change = ((close_factor - open_factor) / open_factor) if open_factor else 0.0
            volume += turnover_shares(row, day, change, (books or {}).get(identity))
        candles.append({
            "d": ordinal_date(day),
            "o": scaled(open_total),
            "h": scaled(high_total),
            "l": scaled(low_total),
            "c": scaled(close_total),
            "v": round(volume, 2),
        })
    return candles

# ---------------------------------------------------------------------------
# Trading
# ---------------------------------------------------------------------------


def trade_fee(amount: float) -> float:
    if amount <= 0:
        return 0.0
    return max(MIN_TRADE_FEE, round_money(amount * TRADE_FEE_RATE))


def _record_trade(
    state: dict[str, Any], stock: Mapping[str, Any], side: str,
    qty: int, price: float, amount: float, fee: float, game_date: str,
    *, realized: float | None = None,
) -> dict[str, Any]:
    source = stock or {}
    entry = {
        "id": str(uuid.uuid4()), "at": _now(), "game_date": str(game_date or ""),
        "side": side, "club_id": _int(source.get("club_id") or source.get("id")),
        "code": str(source.get("code") or ""), "name": str(source.get("name") or ""),
        "nation": str(source.get("nation") or ""),
        "qty": int(qty), "price": quote(price), "amount": money(amount),
        "fee": money(fee),
    }
    if realized is not None:
        entry["realized"] = money(realized)
    state["trades"].append(entry)
    state["trades"] = state["trades"][-TRADE_LOG_LIMIT:]
    return entry


def holding_for(state: dict[str, Any], stock: Mapping[str, Any]) -> dict[str, Any]:
    """Create or refresh the lot of one club, keeping its identity for later."""
    club_id = _int((stock or {}).get("club_id") or (stock or {}).get("id"))
    holding = state["holdings"].setdefault(str(club_id), {
        "qty": 0, "avg_cost": 0.0, "locked_qty": 0, "locked_ordinal": 0,
    })
    for field, value in (
        ("code", str((stock or {}).get("code") or "")),
        ("name", str((stock or {}).get("name") or "")),
        ("nation", str((stock or {}).get("nation") or "")),
        ("competition", str((stock or {}).get("competition") or "")),
    ):
        if value:
            holding[field] = value
    return holding


def sellable_qty(state: dict[str, Any], club_id: int, ordinal: int | None) -> int:
    holding = state["holdings"].get(str(int(club_id)))
    if not holding:
        return 0
    if holding.get("frozen"):
        return 0
    qty = _int(holding.get("qty"))
    locked = _int(holding.get("locked_qty"))
    if not locked:
        return max(0, qty)
    current = _int(ordinal)
    if _int(holding.get("locked_ordinal")) >= current:
        return max(0, qty - locked)
    return max(0, qty)


def takeover_ids(state: Mapping[str, Any] | None) -> set[int]:
    """Clubs the group owns outright, so the market has nothing to trade."""
    holdings = (state or {}).get("holdings")
    if not isinstance(holdings, Mapping):
        return set()
    owned: set[int] = set()
    for key, holding in holdings.items():
        if not isinstance(holding, Mapping):
            continue
        if str(holding.get("source") or "") != TAKEOVER_SOURCE:
            continue
        club_id = _int(key)
        if club_id > 0:
            owned.add(club_id)
    return owned


def takeover_lot(
    state: Mapping[str, Any] | None, club_id: Any,
) -> dict[str, Any] | None:
    """The group's own lot of one club, or ``None`` when it is a market one."""
    holdings = (state or {}).get("holdings")
    if not isinstance(holdings, Mapping):
        return None
    holding = holdings.get(str(_int(club_id)))
    if not isinstance(holding, Mapping):
        return None
    if str(holding.get("source") or "") != TAKEOVER_SOURCE:
        return None
    return dict(holding)


def takeover_keep_qty(shares: Any) -> int:
    """Shares a group club keeps of its own capital whatever the ticket says.

    Selling the club is a group decision, and a club that has sold every share
    back would still be owned without the group holding any of it, so a sale
    stops at the control stake.
    """
    capital = _int(shares)
    if capital <= 0:
        return 0
    keep = -(-capital * TAKEOVER_KEEP_NUMERATOR // TAKEOVER_KEEP_DENOMINATOR)
    return min(capital, max(0, keep))


def holding_capital(holding: Mapping[str, Any] | None) -> float:
    """What the account actually put into the shares of one lot.

    The average cost of a lot is the money per share it was built with, so the
    capital still in it is that price times the shares still held.  A takeover
    charges the price of the whole club minus exactly this figure: the group
    already paid for part of the club through the exchange.
    """
    source = holding if isinstance(holding, Mapping) else {}
    qty = _int(source.get("qty"))
    if qty <= 0:
        return 0.0
    return money(qty * _number(source.get("avg_cost")))


def takeover_charge(price: Any, credit: Any = 0) -> dict[str, Any]:
    """What a takeover costs once the shares already held are counted."""
    gross = max(0.0, money(_number(price)))
    paid_in = max(0.0, money(_number(credit)))
    return {
        "gross": gross, "credit": paid_in, "net": money(max(0.0, gross - paid_in)),
    }


def take_over_club(
    state: dict[str, Any], row: Mapping[str, Any] | None, *, club_id: Any,
    shares: Any, price: Any, game_date: str = "", ordinal: Any = None,
    code: str = "", name: str = "", sold: Any = 0,
) -> dict[str, Any]:
    """Hand the whole share register of an acquired club to the group.

    Buying a club is not a share purchase that leaves the club holding its own
    capital: the board hands every share over, so the account is the only
    holder left and the trade book has nothing to sell.  The lot is marked as
    a takeover - that mark is what keeps the club out of the market, keeps the
    shares out of every sale ticket and shows the group as the owner in the
    register - until the club is sold back.
    """
    identity = _int(club_id or (row or {}).get("id"))
    if identity <= 0:
        raise ValueError("俱乐部 ID 无效")
    capital = max(0, _int(shares))
    if capital <= 0:
        raise ValueError("该俱乐部尚未登记股本")
    # A register handed over once stays handed over: the shares the group has
    # since sold back to the club are part of the lot's own history, so a club
    # re-read after an issue or a reopening keeps the lot it has.
    released = max(0, min(_int(sold), capital))
    total = money(_number(price))
    unit = quote(total / capital) if capital else 0.0
    source = row or {}
    holding = {
        "qty": capital - released,
        "avg_cost": unit,
        "locked_qty": 0,
        "source": TAKEOVER_SOURCE,
        "code": str(code or ""),
        "name": str(name or source.get("name") or ""),
        "nation": nation_of(source),
        "competition": str(source.get("competition") or ""),
        "last_price": unit,
        "takeover_price": total,
        "takeover_capital": capital,
        "takeover_sold": released,
        "takeover_game_date": str(game_date or ""),
        "takeover_ordinal": _int(ordinal),
    }
    state.setdefault("holdings", {})[str(identity)] = holding
    # An application the club still owes shares on cannot survive the board
    # handing the register over, so every pending ticket of the club is closed
    # at the takeover: nothing may be delivered from a register the account now
    # owns whole.  A withdrawn application hands its escrow back, and that
    # money is reported here so the caller books it into the bank.
    closed, refund = cancel_orders_for(
        state, [identity], game_date=str(game_date or ""),
        reason="俱乐部已被您的集团收购，委托已撤销",
    )
    return {"club_id": identity, "qty": int(holding["qty"]), "cost": unit,
            "holding": holding, "capital": capital, "sold": released,
            "cancelled": closed, "refund": money(refund)}


def release_takeover(state: dict[str, Any], club_id: Any) -> dict[str, Any] | None:
    """Take a sold club's register back out of the group's book."""
    identity = _int(club_id)
    holdings = state.get("holdings")
    if not isinstance(holdings, dict):
        return None
    holding = holdings.get(str(identity))
    if not isinstance(holding, Mapping):
        return None
    if str(holding.get("source") or "") != TAKEOVER_SOURCE:
        return None
    holdings.pop(str(identity), None)
    state["watchlist"] = [
        item for item in state.get("watchlist") or [] if _int(item) != identity
    ]
    return dict(holding)


def sync_takeovers(
    state: dict[str, Any], rows: Any, owned: Mapping[int, Any], *,
    game_date: str = "", ordinal: Any = None,
) -> dict[str, Any]:
    """Keep the register following the group's own clubs, both ways.

    A club bought outright is not a market lot: its whole capital belongs to
    the group and the club itself holds nothing.  The market therefore hands
    over every owned club of the enabled scope - and hands one back the moment
    the group sells it - instead of trusting a single event that may have been
    missed (a takeover of a club whose exchange was still closed, a market
    written before this rule existed, a club sold while the market was off).
    Reading the market is enough to repair the register, and an existing lot
    keeps the price it was taken over for while its quantity follows the
    capital of the day.
    """
    rows_by_id = _row_index(rows)
    holdings = state.setdefault("holdings", {})
    books = share_books(state)
    granted: list[dict[str, Any]] = []
    released: list[dict[str, Any]] = []
    refund = 0.0
    wanted = {
        _int(club_id): price for club_id, price in (owned or {}).items()
        if _int(club_id) > 0
    }
    for key in list(holdings):
        holding = holdings.get(key)
        if not isinstance(holding, Mapping):
            continue
        if str(holding.get("source") or "") != TAKEOVER_SOURCE:
            continue
        club_id = _int(key)
        if club_id in wanted:
            continue
        if _int(holding.get("qty")) <= 0:
            holdings.pop(key, None)
            continue
        released.append({
            "club_id": club_id, "name": str(holding.get("name") or ""),
            "qty": _int(holding.get("qty")),
        })
        holdings.pop(key, None)
    for club_id, price in sorted(wanted.items()):
        row = rows_by_id.get(club_id)
        if row is None:
            # The club is not on a board of this save: its exchange is closed
            # or the directory cannot answer for it, so there is nothing to
            # hand over yet.  Nothing is dropped either.
            continue
        capital = shares_at(row, _int(ordinal), books.get(club_id))
        if capital <= 0:
            continue
        current = holdings.get(str(club_id))
        if isinstance(current, Mapping) and str(current.get("source") or "") != TAKEOVER_SOURCE:
            # A club the group bought after trading it on the board: the
            # market lot is replaced by the takeover of the whole capital.
            holdings.pop(str(club_id), None)
            current = None
        sold = _int((current or {}).get("takeover_sold")) if isinstance(current, Mapping) else 0
        handed = _int((current or {}).get("takeover_capital")) if isinstance(current, Mapping) else 0
        if handed > 0 and handed != capital:
            # A capital issue moves the whole register: the shares the group
            # sold back are diluted by the same ratio as the ones it keeps.
            sold = max(0, int(round(sold * capital / handed)))
        expected = max(0, capital - max(0, min(sold, capital)))
        if isinstance(current, Mapping) and _int(current.get("qty")) == expected:
            holding = holdings.get(str(club_id))
            if isinstance(holding, dict):
                holding["takeover_capital"] = capital
                holding["takeover_sold"] = sold
            continue
        cost = _number((current or {}).get("avg_cost")) if isinstance(current, Mapping) else 0.0
        record = take_over_club(
            state, row, club_id=club_id, shares=capital,
            price=(cost * capital) if cost > 0 else price,
            game_date=game_date, ordinal=ordinal,
            code=stock_code(row.get("name"), row.get("short_name"), club_id),
            name=str(row.get("name") or ""), sold=sold,
        )
        refund += _number(record.get("refund"))
        granted.append({
            "club_id": club_id, "name": str(row.get("name") or ""),
            "qty": int(record["qty"]), "cancelled": list(record.get("cancelled") or []),
            "refund": money(record.get("refund")),
        })
    return {
        "granted": granted, "released": released,
        "count": len(granted) + len(released), "refund": money(refund),
        "cancelled": [
            item for record in granted for item in record.get("cancelled") or []
        ],
    }


def assert_tradable(stock: Mapping[str, Any] | None, side: str = "buy") -> None:
    """A club the group owns outright trades with the group alone.

    A takeover hands the whole register over, so the board has no market lot
    left to sell to a buyer: what stays with the club is its own book - the
    shares the group sold back to it.  Those are the two moves an owned club
    answers: sell part of the register back to the club ("sell") and take it
    into the group's lot again ("buy"), plus financing it at any time
    ("finance"), because the board that answers all three tickets is the group
    itself.  Everything else - selling the club - belongs to the group module.
    """
    if not (stock or {}).get("owned"):
        return
    if side in ("sell", "buy", "finance"):
        return
    raise ValueError(
        "该俱乐部已被您的集团收购，只能出售或回收股份；"
        "如需彻底退出请在集团模块中出售俱乐部"
    )


def buy_plan(
    stock: Mapping[str, Any], qty: Any, *, kind: str = "direct", used: Any = 0,
) -> dict[str, Any]:
    """Validate a buy and return its money plan without mutating anything.

    A click may take at most two percent of the club's capital *for the whole
    game day*: ``used`` is what the day already spent on this club, and once the
    budget is gone the account has to ask for a block trade.  Anything above a
    click is that block trade: the same plan, submitted as an application the
    club fills on the next game day, and never more than ten percent of the
    capital in one application.  Buying is refused outright once the account
    would pass a quarter of the club - the club keeps control of itself.
    """
    assert_tradable(stock, "buy")
    source = dict(stock or {})
    club_id = _int(source.get("club_id") or source.get("id"))
    if club_id <= 0 or not source.get("code"):
        raise ValueError("股票不存在")
    try:
        shares = int(qty)
    except (TypeError, ValueError):
        raise ValueError("请输入大于0的股数") from None
    if shares <= 0:
        raise ValueError("请输入大于0的股数")
    kind = str(kind or "direct").strip() or "direct"
    if kind not in ("direct", "block"):
        kind = "direct"
    owned = bool(source.get("owned"))
    # The club is the only seller, so its own book is checked first: what is
    # not for sale cannot be bought at any size, however large the order room.
    # For a club the group owns that book is the register the group sold back
    # to it, and buying from it is a recovery rather than a purchase.
    available = source.get("club_shares")
    if available is not None:
        available = max(0, _int(available))
        if available <= 0:
            raise ValueError(
                "俱乐部手中已无股份可回收" if owned else "俱乐部已无可售股份"
            )
        if shares > available:
            raise ValueError(
                f"俱乐部手中仅剩 {available} 股可回收" if owned
                else "俱乐部可售股份不足"
            )
    capital = _int(source.get("shares"))
    held = _int(source.get("qty"))
    if owned and capital > 0:
        # A recovery is not a takeover: the quarter of the capital that stops
        # a market buyer is not a ceiling for the owner, so the club's own
        # book is the whole room.  The day keeps its pacing all the same,
        # because the club delivers these shares the way it delivers any other
        # order: a click is what today's direct budget still holds, anything
        # above it is an application the club fills on the next game day.
        room = max(0, capital - held)
        if kind == "block":
            cap = max_block_shares(capital)
            if shares > cap:
                raise ValueError(
                    f"单次大宗回收申请上限为 {cap} 股"
                    f"（股本的 {MAX_BLOCK_BUY_RATIO * 100:.0f}%）"
                )
        else:
            cap = max_direct_shares(capital)
            left = max(0, cap - max(0, _int(used)))
            if shares > left:
                if shares > cap:
                    raise ValueError("单笔股数过大")
                raise ValueError(
                    f"该俱乐部今日回收额度还剩 {left} 股"
                    f"（每日上限为股本的 {MAX_DIRECT_BUY_RATIO * 100:.0f}%）；"
                    "继续回收请提交大宗回收申请"
                )
        if shares > room:
            raise ValueError(f"俱乐部手中仅剩 {room} 股可回收")
    elif capital > 0:
        stake = stake_of(held, capital)
        if stake >= MAX_BUY_STAKE - 1e-9:
            raise ValueError(
                f"已持有该俱乐部 {stake * 100:.2f}%，达到 {MAX_BUY_STAKE * 100:.0f}% 上限；"
                "只能卖出，不能再买入或提交大宗买入申请"
            )
        room = max(0, int(capital * MAX_BUY_STAKE) - held)
        if kind == "block":
            cap = max_block_shares(capital)
            if shares > cap:
                raise ValueError(
                    f"单次大宗交易申请上限为 {cap} 股（股本的 {MAX_BLOCK_BUY_RATIO * 100:.0f}%）"
                )
        else:
            cap = max_direct_shares(capital)
            left = max(0, cap - max(0, _int(used)))
            if shares > left:
                if shares > cap:
                    raise ValueError("单笔股数过大")
                raise ValueError(
                    f"该俱乐部今日市价买入额度还剩 {left} 股（每日上限为股本的 "
                    f"{MAX_DIRECT_BUY_RATIO * 100:.0f}%）；继续买入请提交大宗交易申请"
                )
        if shares > room:
            raise ValueError(
                f"本次买入后持股将达到 {(held + shares) / capital * 100:.2f}%，"
                f"超过 {MAX_BUY_STAKE * 100:.0f}% 上限；本次最多可买 {room} 股"
            )
    price = quote(source.get("price"))
    if price <= 0:
        raise ValueError("当前无有效报价")
    if kind == "block":
        # A block is several clicks of stock in one order and the club
        # delivers it on the next game day, so it clears at a small premium
        # over the close of the day the application was placed.
        price = quote(price * (1.0 + BLOCK_PRICE_PREMIUM))
    amount = money(shares * price)
    fee = trade_fee(amount)
    return {
        "club_id": club_id, "side": "buy", "kind": kind, "qty": shares, "price": price,
        "amount": amount, "fee": fee, "total": money(amount + fee), "stock": source,
    }


def sell_plan(
    state: dict[str, Any], stock: Mapping[str, Any], qty: Any, *, ordinal: int | None,
    limit: Any = None,
) -> dict[str, Any]:
    """Validate a sale: a market order now, or a limit order waiting for its price.

    A limit sale is the same lot promised at a price of the account's own
    choosing: the shares are reserved the moment it is placed, the fill happens
    on the first reading at or above that price, and the price it fills at is
    the price the seller asked for.
    """
    assert_tradable(stock, "sell")
    source = dict(stock or {})
    club_id = _int(source.get("club_id") or source.get("id"))
    if club_id <= 0 or not source.get("code"):
        raise ValueError("股票不存在")
    try:
        shares = int(qty)
    except (TypeError, ValueError):
        raise ValueError("请输入大于0的股数") from None
    if shares <= 0:
        raise ValueError("请输入大于0的股数")
    available = sellable_qty(state, club_id, ordinal)
    holding = state["holdings"].get(str(club_id))
    if isinstance(holding, Mapping) and holding.get("frozen"):
        raise ValueError("该交易所已关闭，持仓已冻结；重新开启交易所后即可解锁")
    # Shares already promised to an open limit sale are not on offer twice.
    reserved = reserved_qty(state, club_id)
    available = max(0, available - reserved)
    if source.get("owned"):
        keep = takeover_keep_qty(source.get("shares"))
        room = _int(source.get("qty")) - keep
        if room <= 0:
            raise ValueError(
                f"集团旗下俱乐部至少要保留 "
                f"{TAKEOVER_KEEP_NUMERATOR}% 股权（{keep} 股）；"
                f"如需完全退出，请在集团模块中出售俱乐部"
            )
        if shares > room:
            raise ValueError(
                f"集团旗下俱乐部至少要保留 "
                f"{TAKEOVER_KEEP_NUMERATOR}% 股权（{keep} 股）；"
                f"当前最多可卖 {room} 股；"
                f"如需完全退出，请在集团模块中出售俱乐部"
            )
        available = min(available, room)
    if available <= 0:
        if reserved:
            raise ValueError("持仓已全部委托定价抛售，请先撤销委托")
        raise ValueError("当日买入的股票需等待下一个比赛日才能卖出")
    if shares > available:
        raise ValueError(f"可卖持仓不足，当前最多可卖 {available} 股")
    kind = "market"
    price = quote(source.get("price"))
    if limit is not None and str(limit) != "":
        try:
            wanted = float(limit)
        except (TypeError, ValueError):
            raise ValueError("请输入大于0的定价") from None
        if wanted <= 0:
            raise ValueError("请输入大于0的定价")
        kind = "limit"
        price = quote(wanted)
    amount = money(shares * price)
    fee = trade_fee(amount)
    return {
        "club_id": club_id, "side": "sell", "kind": kind, "qty": shares, "price": price,
        "amount": amount, "fee": fee, "net": money(max(0.0, amount - fee)),
        "stock": source,
    }


def commit_buy(
    state: dict[str, Any], stock: Mapping[str, Any], plan: Mapping[str, Any], *,
    game_date: str, ordinal: int | None,
) -> dict[str, Any]:
    holding = holding_for(state, stock)
    previous_qty = _int(holding.get("qty"))
    previous_cost = round_money(previous_qty * _number(holding.get("avg_cost")))
    shares = int(plan["qty"])
    paid = money(_number(plan.get("amount")) + _number(plan.get("fee")))
    holding["qty"] = previous_qty + shares
    holding["avg_cost"] = quote((previous_cost + paid) / holding["qty"])
    holding["last_price"] = quote(plan.get("price"))
    current = _int(ordinal)
    if _int(holding.get("locked_ordinal")) >= current:
        holding["locked_qty"] = _int(holding.get("locked_qty")) + shares
    else:
        holding["locked_qty"] = shares
        holding["locked_ordinal"] = current
    if str(holding.get("source") or "") == TAKEOVER_SOURCE:
        # A recovery takes the shares back into the group's own lot, so the
        # club owes none of them any more: this figure is what the next open
        # of the exchange counts the register from, and leaving it alone would
        # hand the same shares over a second time.
        holding["takeover_sold"] = max(
            0, _int(holding.get("takeover_sold")) - shares,
        )
    if str(plan.get("kind")) == "direct":
        record_direct_buy(state, plan.get("club_id"), ordinal, shares)
    trade = _record_trade(
        state, stock, "buy", shares, plan["price"], plan["amount"], plan["fee"], game_date,
    )
    # The order the account just placed is itself part of the quote from today
    # on: a block trade counts for more than a click, and the move fades.
    _record_impact(state, plan.get("club_id"), ordinal, plan_impact(plan, stock))
    return trade


def commit_sell(
    state: dict[str, Any], stock: Mapping[str, Any], plan: Mapping[str, Any], *,
    game_date: str, ordinal: int | None,
) -> dict[str, Any]:
    holding = holding_for(state, stock)
    shares = int(plan["qty"])
    previous_qty = _int(holding.get("qty"))
    avg_cost = _number(holding.get("avg_cost"))
    realized = money((_number(plan.get("price")) - avg_cost) * shares - _number(plan.get("fee")))
    holding["qty"] = max(0, previous_qty - shares)
    holding["locked_qty"] = max(0, _int(holding.get("locked_qty")) - shares)
    holding["last_price"] = quote(plan.get("price"))
    if holding["qty"] <= 0:
        if str(holding.get("source") or "") == TAKEOVER_SOURCE:
            # The group still owns the club even when it has sold its whole
            # lot back: the empty lot is what says so, and what stops the next
            # open from handing the same register over a second time.
            holding["qty"] = 0
        else:
            state["holdings"].pop(str(_int(plan.get("club_id"))), None)
    if str(holding.get("source") or "") == TAKEOVER_SOURCE:
        # What the group sold back is remembered, because the register follows
        # the group's clubs: without it the next open would hand the sold
        # shares over again.
        holding["takeover_sold"] = _int(holding.get("takeover_sold")) + shares
    state["realized_profit"] = money(_number(state.get("realized_profit")) + realized)
    trade = _record_trade(
        state, stock, "sell", shares, plan["price"], plan["amount"], plan["fee"],
        game_date, realized=realized,
    )
    _record_impact(state, plan.get("club_id"), ordinal, plan_impact(plan, stock))
    return trade


def _last_matching_trade(
    state: dict[str, Any], key: str, plan: Mapping[str, Any], side: str,
) -> dict[str, Any] | None:
    """Newest trade row matching a plan, used when a caller lost the receipt."""
    shares = int(plan.get("qty") or 0)
    for row in reversed(state.get("trades") or []):
        if not isinstance(row, dict) or row.get("side") != side:
            continue
        if str(_int(row.get("club_id"))) == key and _int(row.get("qty")) == shares:
            return row
    return None


def revert_buy(
    state: dict[str, Any], plan: Mapping[str, Any], *, ordinal: int | None,
    trade: dict[str, Any] | None = None,
) -> None:
    """Undo ``commit_buy`` when the money movement could not be recorded."""
    key = str(_int(plan.get("club_id")))
    if str(plan.get("kind")) == "direct":
        forget_direct_buy(state, plan.get("club_id"), ordinal, plan.get("qty"))
    _drop_impact(state, key, ordinal, plan_impact(plan))
    if trade is None:
        trade = _last_matching_trade(state, key, plan, "buy")
    if trade:
        state["trades"] = [row for row in state["trades"] if row.get("id") != trade.get("id")]
    holding = state["holdings"].get(key)
    if not holding:
        return
    shares = int(plan["qty"])
    holding["qty"] = max(0, _int(holding.get("qty")) - shares)
    holding["locked_qty"] = max(0, _int(holding.get("locked_qty")) - shares)
    if str(holding.get("source") or "") == TAKEOVER_SOURCE:
        # The recovery was rolled back, so the club owes the shares again.
        holding["takeover_sold"] = _int(holding.get("takeover_sold")) + shares
    if holding["qty"] <= 0:
        state["holdings"].pop(key, None)
    else:
        paid = money(_number(plan.get("amount")) + _number(plan.get("fee")))
        total = round_money(holding["qty"] * _number(holding.get("avg_cost"))) - paid
        holding["avg_cost"] = quote(max(0.0, total) / holding["qty"])


def revert_sell(
    state: dict[str, Any], plan: Mapping[str, Any], trade: dict[str, Any] | None,
) -> None:
    """Undo ``commit_sell`` when the credit could not be recorded."""
    stock = dict(plan.get("stock") or {"club_id": plan.get("club_id")})
    _drop_impact(state, plan.get("club_id"), None, plan_impact(plan, stock))
    holding = holding_for(state, stock)
    holding["qty"] = _int(holding.get("qty")) + int(plan["qty"])
    if trade:
        state["trades"] = [row for row in state["trades"] if row.get("id") != trade.get("id")]
        state["realized_profit"] = money(
            _number(state.get("realized_profit")) - _number(trade.get("realized"))
        )


# ---------------------------------------------------------------------------
# Orders: block applications and limit sales
# ---------------------------------------------------------------------------


def pending_orders(
    state: Mapping[str, Any] | None, club_id: Any = None,
) -> list[dict[str, Any]]:
    """The applications of this account that are still waiting to be filled.

    ``club_id`` narrows the reading to one club, so a trade ticket can list its
    own queue; without it the whole queue comes back, newest first, which is
    what the queue panel and the refresh hook read.
    """
    identity = None if club_id is None else _int(club_id)
    rows: list[dict[str, Any]] = []
    for order in (state or {}).get("orders") or []:
        if not isinstance(order, Mapping):
            continue
        if str(order.get("status") or "pending") != "pending":
            continue
        if identity is not None and _int(order.get("club_id")) != identity:
            continue
        rows.append(dict(order))
    rows.sort(
        key=lambda item: (-_int(item.get("ordinal")), str(item.get("created_at") or ""))
    )
    return rows


def order_by_id(state: Mapping[str, Any] | None, order_id: Any) -> dict[str, Any] | None:
    """The live order document behind one id, or ``None``."""
    wanted = str(order_id or "").strip()
    if not wanted:
        return None
    for order in (state or {}).get("orders") or []:
        if isinstance(order, dict) and str(order.get("id") or "") == wanted:
            return order
    return None


def order_slots(state: Mapping[str, Any] | None) -> int:
    """How many more applications this account may keep open."""
    return max(0, MAX_PENDING_ORDERS - len(pending_orders(state)))


def _trim_orders(state: dict[str, Any]) -> None:
    """Keep the queue short: open applications are never dropped, history is."""
    orders = state.get("orders")
    if not isinstance(orders, list) or len(orders) <= ORDER_LOG_LIMIT:
        return
    drop = len(orders) - ORDER_LOG_LIMIT
    kept: list[Any] = []
    for order in orders:
        waiting = (
            isinstance(order, Mapping)
            and str(order.get("status") or "pending") == "pending"
        )
        if drop > 0 and not waiting:
            drop -= 1
            continue
        kept.append(order)
    state["orders"] = kept


def _order_identity(stock: Mapping[str, Any]) -> dict[str, Any]:
    """The club fields an order keeps, so it can be filled after a reload."""
    source = stock or {}
    return {
        "club_id": _int(source.get("club_id") or source.get("id")),
        "code": str(source.get("code") or ""),
        "name": str(source.get("name") or ""),
        "nation": str(source.get("nation") or ""),
        "competition": str(source.get("competition") or ""),
    }


def _order_slot_error() -> ValueError:
    return ValueError(
        f"最多同时保留 {MAX_PENDING_ORDERS} 笔未成交委托，请先撤销部分委托"
    )


def submit_block_order(
    state: dict[str, Any], stock: Mapping[str, Any], qty: Any, *,
    game_date: str, ordinal: int | None, plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Queue a block application the club fills on the next game day.

    A click may take two percent of a club; anything above it is a block, and
    the club delivers it one day later at the close of the day the application
    was placed plus a small premium for the size.  The money leaves the bank
    the moment the application is placed - the club is told to deliver, not
    asked whether it would like to - so the account can never be short when the
    shares arrive, and withdrawing the application gives the exact sum back.
    """
    if order_slots(state) <= 0:
        raise _order_slot_error()
    plan = buy_plan(stock, qty, kind="block") if plan is None else dict(plan)
    order = {
        "id": str(uuid.uuid4()),
        "created_at": _now(),
        "kind": "block",
        "side": "buy",
        "status": "pending",
        "game_date": str(game_date or ""),
        "ordinal": _int(ordinal),
        **_order_identity(stock),
        "shares": _int((stock or {}).get("shares")),
        "qty": int(plan["qty"]),
        "price": quote(plan["price"]),
        "amount": money(plan["amount"]),
        "fee": money(plan["fee"]),
        "total": money(plan["total"]),
    }
    state["orders"].append(order)
    _trim_orders(state)
    _notice(
        state, "order", game_date, order_id=order["id"], order_kind="block",
        club_id=order["club_id"], code=order["code"], name=order["name"],
        qty=order["qty"], price=order["price"], total=order["total"],
    )
    return order


def place_limit_sell(
    state: dict[str, Any], stock: Mapping[str, Any], qty: Any, limit: Any, *,
    game_date: str, ordinal: int | None,
) -> dict[str, Any]:
    """Promise a lot at a price of the account's own choosing.

    The shares are reserved the moment the promise is made, the sale fills on
    the first reading at or above that price, and it is then paid the market
    price of that day - never less than the seller asked for.  The promise can
    be withdrawn at any time and the shares are sellable again on the spot.
    """
    if order_slots(state) <= 0:
        raise _order_slot_error()
    plan = sell_plan(state, stock, qty, ordinal=ordinal, limit=limit)
    order = {
        "id": str(uuid.uuid4()),
        "created_at": _now(),
        "kind": "limit",
        "side": "sell",
        "status": "pending",
        "game_date": str(game_date or ""),
        "ordinal": _int(ordinal),
        **_order_identity(stock),
        "shares": _int((stock or {}).get("shares")),
        "qty": int(plan["qty"]),
        "price": quote(plan["price"]),
    }
    state["orders"].append(order)
    _trim_orders(state)
    _notice(
        state, "order", game_date, order_id=order["id"], order_kind="limit",
        club_id=order["club_id"], code=order["code"], name=order["name"],
        qty=order["qty"], price=order["price"],
        total=money(int(plan["qty"]) * quote(plan["price"])),
    )
    return order


def cancel_order(
    state: dict[str, Any], order_id: Any, *, game_date: str,
) -> dict[str, Any]:
    """Withdraw one open application; reports the money that has to come back."""
    order = order_by_id(state, order_id)
    if order is None:
        raise ValueError("找不到这笔委托")
    if str(order.get("status") or "pending") != "pending":
        raise ValueError("这笔委托已经结束")
    return _close_order(state, order, game_date, reason="已撤销")


def _close_order(
    state: dict[str, Any], order: dict[str, Any], game_date: str, *,
    reason: str, refund: Any = None, status: str = "cancelled",
) -> dict[str, Any]:
    """Finish one application and report the money the caller has to credit."""
    order["status"] = str(status or "cancelled")
    order["closed_at"] = _now()
    order["closed_game_date"] = str(game_date or "")
    if reason:
        order["reason"] = str(reason)
    value = 0.0
    if str(order.get("side")) == "buy":
        value = money(
            _number(order.get("total")) if refund is None else _number(refund)
        )
    if order["status"] == "cancelled":
        # Every withdrawal is reported, even one that hands no money back: a
        # reserved sale that disappears quietly is exactly the answer the
        # account must not be left guessing about.
        _notice(
            state, "order_cancel", game_date, order_id=order.get("id"),
            order_kind=str(order.get("kind") or ""),
            club_id=order.get("club_id"), code=order.get("code"),
            name=order.get("name"), qty=order.get("qty"), refund=value,
            value=value, reason=str(reason or ""),
        )
    return {"order": dict(order), "reason": str(reason or ""), "refund": value}


def cancel_orders_for(
    state: dict[str, Any], club_ids: Iterable[Any], *, game_date: str, reason: str,
) -> tuple[list[dict[str, Any]], float]:
    """Withdraw every open application of a few clubs and sum the refunds.

    Used when an exchange closes: the lots freeze, so a block application the
    player left waiting must not be filled by a club that is no longer listed.
    """
    wanted = {_int(item) for item in club_ids or []}
    closed: list[dict[str, Any]] = []
    refund = 0.0
    if not wanted:
        return closed, 0.0
    for order in pending_orders(state):
        if _int(order.get("club_id")) not in wanted:
            continue
        live = order_by_id(state, order.get("id"))
        if live is None:
            continue
        result = _close_order(state, live, game_date, reason=reason)
        refund += _number(result.get("refund"))
        closed.append(result)
    return closed, money(refund)


def drop_order(state: dict[str, Any], order_id: Any) -> dict[str, Any] | None:
    """Forget an application that was never booked, e.g. when the bank refused."""
    orders = state.get("orders")
    if not isinstance(orders, list):
        return None
    wanted = str(order_id or "")
    for index in range(len(orders) - 1, -1, -1):
        entry = orders[index]
        if isinstance(entry, dict) and str(entry.get("id") or "") == wanted:
            orders.pop(index)
            state["notices"] = [
                row for row in state.get("notices") or []
                if str((row or {}).get("order_id") or "") != wanted
            ]
            return entry
    return None


def restore_order(state: dict[str, Any], snapshot: Mapping[str, Any]) -> None:
    """Put a closed application back in the queue after a failed money movement."""
    live = order_by_id(state, (snapshot or {}).get("id"))
    if live is None:
        return
    live["status"] = "pending"
    for key in (
        "closed_at", "closed_game_date", "reason", "filled_at", "filled_game_date",
        "filled_price", "filled_qty", "cancelled_qty", "trade_id",
    ):
        live.pop(key, None)
    state["notices"] = [
        row for row in state.get("notices") or []
        if str((row or {}).get("order_id") or "") != str(live.get("id") or "")
        or str((row or {}).get("kind") or "") == "order"
    ]


def fill_pending_orders(
    state: dict[str, Any], rows: Any, ordinal: int, *, game_date: str,
    books: Mapping[int, Mapping[str, Any]] | None = None,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Advance the queue one game day and fill whatever the day allows.

    A block application is filled by the club on the first game day after the
    one it was placed on, at the price it named; a limit sale fills on the
    first reading at or above its own price.  The module never touches an
    account, so every fill and every withdrawal reports the money the caller
    has to credit back to the bank and the caller books it.
    """
    rows_by_id = _row_index(rows)
    books = share_books(state) if books is None else books
    extras = market_extras(state) if extras is None else extras
    today = _int(ordinal)
    fills: list[dict[str, Any]] = []
    cancels: list[dict[str, Any]] = []
    held_back = 0
    for waiting in pending_orders(state):
        club_id = _int(waiting.get("club_id"))
        order = order_by_id(state, waiting.get("id"))
        if order is None:
            continue
        row = rows_by_id.get(club_id)
        if row is None:
            # A directory that has not finished reading must not take an
            # application back, so the queue is withdrawn only once the club
            # has been missing since an earlier game day.  Until then the day
            # is remembered, which is what lets the next one decide.
            if _absence_confirmed(state, club_id, today):
                _forget_absence(state, club_id)
                cancels.append(_close_order(
                    state, order, game_date, reason="该俱乐部已不在当前存档",
                ))
            else:
                _remember_absence(state, club_id, today)
                held_back += 1
            continue
        book = books.get(club_id)
        if str(order.get("kind")) == "limit":
            price = share_price(row, today, book, extras)
            if price + 1e-9 < _number(order.get("price")):
                continue
            qty = _int(order.get("qty"))
            amount = money(qty * price)
            fee = trade_fee(amount)
            plan = {
                "club_id": club_id, "side": "sell", "kind": "limit", "qty": qty,
                "price": quote(price), "amount": amount, "fee": fee,
                "net": money(max(0.0, amount - fee)), "stock": order,
            }
            capital = shares_at(row, today, book)
            holding = state["holdings"].get(str(club_id))
            held_before = _int(holding.get("qty")) if isinstance(holding, Mapping) else 0
            trade = commit_sell(state, order, plan, game_date=game_date, ordinal=today)
            after = market_extras(state)
            close_after = quote(share_price(row, today, book, after))
            held_after = max(0, held_before - qty)
            receipt(
                state, "limit_fill", game_date,
                order_id=str(order.get("id") or ""), club_id=club_id,
                code=str(order.get("code") or ""), name=str(order.get("name") or ""),
                nation=str(order.get("nation") or ""), side="sell", qty=qty,
                price=quote(price), close_before=quote(price), close=close_after,
                amount=amount, fee=fee, net=money(plan["net"]),
                capital=int(capital),
                qty_before=held_before, qty_after=held_after,
                stake_before=round(stake_of(held_before, capital), 6),
                stake_after=round(stake_of(held_after, capital), 6),
                change=(
                    round((close_after - price) / price, 6) if price else 0.0
                ),
            )
            order["filled_at"] = _now()
            order["filled_game_date"] = str(game_date or "")
            order["filled_price"] = quote(price)
            order["trade_id"] = str(trade.get("id") or "")
            _close_order(
                state, order, game_date, reason="", status="filled",
                refund=_number(plan["net"]),
            )
            _notice(
                state, "order_fill", game_date, order_id=order.get("id"),
                order_kind="limit", club_id=club_id, code=order.get("code"),
                name=order.get("name"), qty=qty, price=quote(price),
                total=money(plan["net"]),
            )
            fills.append({
                "order": dict(order), "trade": trade, "side": "sell",
                "kind": "limit", "qty": qty, "price": quote(price),
                "credit": money(plan["net"]),
            })
            continue
        if today <= _int(order.get("ordinal")):
            continue
        capital = shares_at(row, today, book)
        holding = state["holdings"].get(str(club_id))
        held = _int(holding.get("qty")) if isinstance(holding, Mapping) else 0
        # A club the group owns delivers a recovery out of its own book - the
        # register the group sold back to it - so the quarter of the market
        # that stops a buyer is not the ceiling of an owner here either.
        owned_club = str((holding or {}).get("source") or "") == TAKEOVER_SOURCE
        room = (
            max(0, capital - held) if owned_club
            else max(0, int(capital * MAX_BUY_STAKE) - held)
        )
        close_before = quote(share_price(row, today, book, extras))
        price = quote(order.get("price"))
        can_pay = _int(order.get("qty"))
        affordable = _int(max(0.0, _number(order.get("total"))) // max(price, MIN_SHARE_PRICE))
        qty = min(can_pay, room, affordable)
        if qty <= 0:
            if owned_club:
                reason = (
                    "俱乐部手中已无股份可回收" if room <= 0
                    else "可回收股份或资金不足"
                )
            else:
                reason = (
                    "买入后持股将超过 25% 上限" if room <= 0
                    else "可售股份或资金不足"
                )
            cancels.append(_close_order(state, order, game_date, reason=reason))
            continue
        amount = money(qty * price)
        fee = trade_fee(amount)
        total = money(amount + fee)
        plan = {
            "club_id": club_id, "side": "buy", "kind": "block", "qty": qty,
            "price": price, "amount": amount, "fee": fee, "total": total,
            "stock": order,
        }
        trade = commit_buy(state, order, plan, game_date=game_date, ordinal=today)
        after = market_extras(state)
        close_after = quote(share_price(row, today, book, after))
        order["filled_at"] = _now()
        order["filled_game_date"] = str(game_date or "")
        order["filled_qty"] = qty
        order["cancelled_qty"] = _int(order.get("qty")) - qty
        order["trade_id"] = str(trade.get("id") or "")
        refund = money(_number(order.get("total")) - total)
        _close_order(
            state, order, game_date, reason="", status="filled", refund=refund,
        )
        _notice(
            state, "order_fill", game_date, order_id=order.get("id"),
            order_kind="block", club_id=club_id, code=order.get("code"),
            name=order.get("name"), qty=qty, price=price, total=total,
            refund=refund, dropped=_int(order.get("cancelled_qty")),
        )
        receipt(
            state, "block_fill", game_date,
            order_id=str(order.get("id") or ""), club_id=club_id,
            code=str(order.get("code") or ""), name=str(order.get("name") or ""),
            nation=str(order.get("nation") or ""), side="buy", qty=qty,
            requested=_int(order.get("qty")),
            dropped=_int(order.get("cancelled_qty")),
            price=price, close_before=close_before, close=close_after,
            amount=amount, fee=fee, total=total, refund=refund,
            capital=int(capital), capital_before=int(capital),
            qty_before=held, qty_after=held + qty,
            stake_before=round(stake_of(held, capital), 6),
            stake_after=round(stake_of(held + qty, capital), 6),
            change=(
                round((close_after - close_before) / close_before, 6)
                if close_before else 0.0
            ),
        )
        fills.append({
            "order": dict(order), "trade": trade, "side": "buy", "kind": "block",
            "qty": qty, "price": price, "credit": 0.0, "refund": refund,
        })
    proceeds = money(sum(_number(item.get("credit")) for item in fills))
    refunds = money(
        sum(_number(item.get("refund")) for item in fills)
        + sum(_number(item.get("refund")) for item in cancels)
    )
    return {
        "fills": fills, "cancels": cancels,
        "proceeds": proceeds, "refunds": refunds,
        "credit": money(proceeds + refunds),
        # Applications the directory could not answer for today: they stay in
        # the queue and the day is remembered, so nothing is withdrawn from one
        # reading of a scan that is still running.
        "unconfirmed": held_back,
    }


# ---------------------------------------------------------------------------
# Financing: the account pays the club for new shares
# ---------------------------------------------------------------------------


def form_slump(fundamentals: Mapping[str, Any] | None) -> float:
    """How badly a club is doing on the pitch, ``0`` (flying) to ``1`` (awful).

    The window is the club's last five matches, so the share of the points it
    could have won is the whole reading: a club with thirteen of fifteen points
    wants nothing, one that lost the lot wants the money badly.
    """
    source = fundamentals if isinstance(fundamentals, Mapping) else {}
    wins = _int(source.get("form_wins"))
    draws = _int(source.get("form_draws"))
    losses = _int(source.get("form_losses"))
    played = wins + draws + losses
    if played <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - int(source.get("form_points")) / (3.0 * played)))


def finance_appetite(
    row: Mapping[str, Any] | None, stock: Mapping[str, Any] | None, ordinal: Any,
) -> dict[str, Any]:
    """How much one club wants outside money today, and its answer.

    Three things raise the appetite: a market cap far from the appraisal - an
    expensive club issues dear and a cheap one is short of cash - a club that
    is in the red, and a club that is losing on the pitch.  A healthy, fairly
    valued club is the hard one to convince, so an application can be turned
    down.  The answer is drawn once per club and game day from the same
    deterministic hash the rest of the market uses, so the same offer always
    gets the same answer inside one day and asking again tomorrow is a new one.

    The distance that matters is the one between two *totals*: the quote is a
    price per share while the appraisal values the whole club, so the market
    cap is what compares with it.  Comparing a price per share with an
    appraisal of ten figures made every club look a hundred times too cheap
    and every appetite sat at the cap.
    """
    source = dict(row or {})
    listed = dict(stock or {})
    club_id = _int(source.get("id") or listed.get("club_id"))
    price = _number(listed.get("price"))
    intrinsic = _number(listed.get("intrinsic"))
    shares = _int(listed.get("shares"))
    market_cap = _number(listed.get("market_cap")) or price * shares
    gap = (
        abs(market_cap / intrinsic - 1.0)
        if market_cap > 0 and intrinsic > 0 else 0.0
    )
    gap_bonus = (
        min(1.0, gap / FINANCE_GAP_SCALE) * FINANCE_APPETITE_GAP
        if FINANCE_GAP_SCALE > 0 else 0.0
    )
    reasons: list[dict[str, Any]] = []
    if gap_bonus > 0:
        reasons.append({
            "key": "gap", "weight": round(gap_bonus, 6), "gap": round(gap, 6),
        })
    balance = _number(source.get("balance"))
    club_value = max(1.0, _number(source.get("club_value")) or intrinsic)
    debt_bonus = 0.0
    if balance < 0:
        depth = min(1.0, abs(balance) / club_value)
        debt_bonus = FINANCE_APPETITE_DEBT * (1.0 + FINANCE_DEBT_SCALE * depth)
        reasons.append({
            "key": "debt", "weight": round(debt_bonus, 6), "depth": round(depth, 6),
        })
    slump = form_slump(listed.get("fundamentals"))
    slump_bonus = slump * FINANCE_APPETITE_SLUMP
    if slump_bonus > 0:
        reasons.append({
            "key": "slump", "weight": round(slump_bonus, 6), "slump": round(slump, 6),
        })
    value = FINANCE_APPETITE_BASE + gap_bonus + debt_bonus + slump_bonus
    chance = max(FINANCE_ACCEPT_FLOOR, min(FINANCE_APPETITE_CAP, value))
    day = _int(ordinal)
    draw = (_hash01(club_id ^ 0x2F17, day) + 1.0) / 2.0
    return {
        "club_id": club_id,
        "value": round(chance, 6),
        "raw": round(value, 6),
        "draw": round(draw, 6),
        "accept": draw < chance,
        "floor": FINANCE_ACCEPT_FLOOR,
        "reasons": reasons[:max(1, FINANCE_REASON_LIMIT)],
    }


def price_streak(history: Iterable[Mapping[str, Any]] | None) -> int:
    """How many closes in a row rose at the end of a candle series.

    The board watches the same tape the player does, so the run is counted on
    the closes of the club's own candles: a club that has risen for days is a
    club whose board expects to be paid for that.
    """
    closes: list[float] = []
    for row in history or []:
        if not isinstance(row, Mapping):
            continue
        close = _number(row.get("c"))
        if close > 0:
            closes.append(close)
    streak = 0
    for previous, current in zip(reversed(closes[:-1]), reversed(closes)):
        if current > previous:
            streak += 1
            continue
        break
    return streak


def takeover_appetite(
    row: Mapping[str, Any] | None, stock: Mapping[str, Any] | None, ordinal: Any, *,
    price: Any = None, intrinsic: Any = None, streak: Any = 0,
) -> dict[str, Any]:
    """How willing one board is to hand the club over today, and its answer.

    The takeover price is the appraisal times the market factor, so reading it
    against the appraisal says what the board is being offered: far above it
    the club does not want to go, far below it does.  A run of rising closes
    works against the buyer as well, and the answer is a probability drawn
    once per club and game day from the same deterministic hash the rest of
    the market uses - a refusal is the board's mood today, not a verdict.
    """
    source = dict(row or {})
    listed = dict(stock or {})
    club_id = _int(source.get("id") or listed.get("club_id"))
    quoted = _number(price) or _number(listed.get("price"))
    anchor = (
        _number(intrinsic)
        or _number(listed.get("intrinsic"))
        or _number(source.get("club_value"))
    )
    gap = (quoted / anchor - 1.0) if quoted > 0 and anchor > 0 else 0.0
    discount = 0.0
    premium = 0.0
    if TAKEOVER_APPETITE_GAP_SCALE > 0:
        if gap > 0:
            premium = (
                min(1.0, gap / TAKEOVER_APPETITE_GAP_SCALE)
                * TAKEOVER_APPETITE_PREMIUM
            )
        elif gap < 0:
            discount = (
                min(1.0, -gap / TAKEOVER_APPETITE_GAP_SCALE)
                * TAKEOVER_APPETITE_DISCOUNT
            )
    rises = max(0, _int(streak))
    streak_penalty = min(TAKEOVER_STREAK_LIMIT, rises) * TAKEOVER_APPETITE_STREAK
    value = TAKEOVER_APPETITE_BASE + discount - premium - streak_penalty
    chance = max(TAKEOVER_APPETITE_FLOOR, min(TAKEOVER_APPETITE_CAP, value))
    day = _int(ordinal)
    draw = (_hash01(club_id ^ 0x51D7, day) + 1.0) / 2.0
    reasons: list[dict[str, Any]] = []
    if premium > 0:
        reasons.append({
            "key": "premium", "weight": round(premium, 6), "gap": round(gap, 6),
        })
    if streak_penalty > 0:
        reasons.append({
            "key": "streak", "weight": round(streak_penalty, 6), "streak": rises,
        })
    if discount > 0:
        reasons.append({
            "key": "discount", "weight": round(discount, 6), "gap": round(gap, 6),
        })
    return {
        "club_id": club_id,
        "value": round(chance, 6),
        "raw": round(value, 6),
        "draw": round(draw, 6),
        "accept": draw < chance,
        "floor": TAKEOVER_APPETITE_FLOOR,
        "gap": round(gap, 6),
        "streak": rises,
        "reasons": reasons[:max(1, TAKEOVER_REASON_LIMIT)],
    }


def takeover_stake_gate(
    row: Mapping[str, Any] | None = None, stock: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Whether a club is big enough to need a 49% stake before it sells.

    From a hundred billion the club is not bought from the board alone: the
    account has to own 49% of it first, which means working the exchange.  The
    reading is the club's market cap where the exchange lists it and its
    appraisal where it does not, so a closed exchange cannot make a giant
    cheap.  The share count comes with the market row: without a listing there
    is nothing to own a stake of, and the gate then reports what it needs
    without pretending the account holds any of it.
    """
    source = dict(row or {})
    listed = dict(stock or {})
    cap = _number(listed.get("market_cap")) or intrinsic_value(source)
    shares = _int(listed.get("shares"))
    held = _int(listed.get("qty"))
    stake = stake_of(held, shares) if shares > 0 else 0.0
    required = cap >= TAKEOVER_STAKE_GATE_VALUE
    return {
        "required": bool(required),
        "market_cap": int(round(cap)),
        "threshold": TAKEOVER_STAKE_GATE_VALUE,
        "ratio": TAKEOVER_STAKE_GATE_RATIO,
        "shares": shares,
        "held": held,
        "stake": round(stake, 6),
        "ok": (not required) or stake >= TAKEOVER_STAKE_GATE_RATIO,
    }


def max_finance_shares(qty: Any, shares: Any) -> int:
    """Largest financing that still leaves the account under its stake cap.

    An issue grows the capital as well as the lot, so the room is not simply
    ``49% - held``: it is the issue that solves
    ``(held + issue) / (capital + issue) = MAX_FINANCE_STAKE``.
    """
    capital = _number(shares)
    if capital <= 0:
        return 0
    room = (MAX_FINANCE_STAKE * capital - _number(qty)) / (1.0 - MAX_FINANCE_STAKE)
    return max(0, int(room))


def share_record(state: Mapping[str, Any] | None, club_id: Any) -> dict[str, Any] | None:
    """The live share record of one club inside a state document."""
    key = str(_int(club_id))
    for entry in ((state or {}).get("nations") or {}).values():
        if not isinstance(entry, Mapping):
            continue
        stored = entry.get("shares")
        if isinstance(stored, Mapping) and isinstance(stored.get(key), dict):
            return stored[key]
    return None


def finance_plan(
    state: dict[str, Any], stock: Mapping[str, Any], qty: Any, *,
    appetite: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a financing and price it without mutating anything.

    Financing is a capital injection: the account hands the club money at
    today's quote and the club issues the shares that money bought.  The club's
    own holding is untouched and the quote does not move - capital and value
    grow by the same amount - so the only limits are the ones the board set:
    never less than two percent of the capital in one round, never more than
    ten, and never past 49.9% of the club.  The club itself has to want the money
    as well: ``appetite`` is its answer for today, and a club that says no
    refuses the offer outright.
    """
    assert_tradable(stock, "finance")
    source = dict(stock or {})
    club_id = _int(source.get("club_id") or source.get("id"))
    if club_id <= 0 or not source.get("code"):
        raise ValueError("股票不存在")
    try:
        shares = int(qty)
    except (TypeError, ValueError):
        raise ValueError("请输入大于0的股数") from None
    if shares <= 0:
        raise ValueError("请输入大于0的股数")
    capital = _int(source.get("shares"))
    if capital <= 0:
        raise ValueError("该俱乐部尚未登记股本")
    held = _int(source.get("qty"))
    owned = bool(source.get("owned"))
    floor = max(1, int(capital * MIN_FINANCE_RATIO))
    ceiling = max(1, int(capital * MAX_FINANCE_RATIO))
    room = capital if owned else max_finance_shares(held, capital)
    # Near the ceiling the remaining room can be smaller than the normal
    # two-percent round.  Refusing every ticket there would leave an account
    # one share below the 49% takeover gate with no way to close the gap, so a
    # final top-up may be as small as one share while room remains.
    top_up = room > 0 and room < floor
    if top_up:
        # The smallest issue that clears the takeover gate: issuing shares
        # grows the denominator too, so one share is not always enough.
        needed = (
            TAKEOVER_STAKE_GATE_RATIO * capital - held
        ) / (1.0 - TAKEOVER_STAKE_GATE_RATIO)
        minimum = max(1, min(room, int(needed) + 1))
    else:
        minimum = floor
    if shares < minimum:
        raise ValueError(
            f"单次融资最低 {floor} 股（现有股本的 {MIN_FINANCE_RATIO * 100:.0f}%）"
        )
    if shares > ceiling:
        raise ValueError(
            f"单次融资最多 {ceiling} 股（现有股本的 {MAX_FINANCE_RATIO * 100:.0f}%）"
        )
    if shares > room:
        raise ValueError(
            f"本次融资后持股将达到 "
            f"{(held + shares) / (capital + shares) * 100:.2f}%，"
            f"超过 {MAX_FINANCE_STAKE * 100:.0f}% 上限；本次最多可融资 {room} 股"
        )
    price = quote(source.get("price"))
    if price <= 0:
        raise ValueError("当前无有效报价")
    holding = state["holdings"].get(str(club_id))
    if isinstance(holding, Mapping) and holding.get("frozen"):
        raise ValueError("该交易所已关闭，持仓已冻结；重新开启交易所后即可解锁")
    # The board of a club the group owns is the group: it does not have to be
    # convinced, so the appetite of the day is only read for other clubs.
    if not owned and isinstance(appetite, Mapping) and not appetite.get("accept"):
        raise ValueError(
            f"俱乐部暂时不缺资金，拒绝了本次融资（融资意愿 "
            f"{_number(appetite.get('value')) * 100:.0f}%）；换一天再谈或许会答应"
        )
    amount = money(shares * price)
    return {
        "club_id": club_id, "side": "finance", "kind": "finance",
        "owned": owned,
        "injection": (
            money(amount * CLUB_BALANCE_INJECTION_RATIO) if owned else 0.0
        ),
        "appetite": dict(appetite) if isinstance(appetite, Mapping) else None,
        "qty": shares, "price": price, "amount": amount, "fee": 0.0,
        "total": amount, "stock": source,
        "shares_before": capital, "shares_after": capital + shares,
        "stake_after": round(stake_of(held + shares, capital + shares), 6),
    }


def commit_finance(
    state: dict[str, Any], stock: Mapping[str, Any], plan: Mapping[str, Any], *,
    game_date: str, ordinal: int | None,
) -> dict[str, Any]:
    """Book a paid-for issue: new shares, new capital and a fresh lot.

    The share record is the only place a capital change can come from, so the
    issue is appended there, read back through :func:`shares_at` and rolled
    back whole if the readback does not match what the plan promised.
    """
    club_id = _int(plan.get("club_id"))
    record = share_record(state, club_id)
    if record is None:
        raise ValueError("该俱乐部尚未登记股本")
    shares = int(plan["qty"])
    amount = money(plan.get("amount"))
    before = shares_at({"id": club_id}, _int(ordinal), record)
    if _int(plan.get("shares_before")) and before != _int(plan.get("shares_before")):
        raise ValueError("该俱乐部股本已变化，请刷新后重新融资")
    events = record.setdefault("f", [])
    events.append([_int(ordinal), shares])
    after = shares_at({"id": club_id}, _int(ordinal), record)
    if after != _int(plan.get("shares_after")):
        events.pop()
        raise ValueError("融资增发未能生效，请重试")
    holding = holding_for(state, stock)
    previous_qty = _int(holding.get("qty"))
    previous_cost = round_money(previous_qty * _number(holding.get("avg_cost")))
    holding["qty"] = previous_qty + shares
    holding["avg_cost"] = quote((previous_cost + amount) / holding["qty"])
    holding["last_price"] = quote(plan.get("price"))
    # The issue is a purchase at today's quote like any other, so the new lot
    # waits for the next game day exactly as a bought one does.
    current = _int(ordinal)
    if _int(holding.get("locked_ordinal")) >= current:
        holding["locked_qty"] = _int(holding.get("locked_qty")) + shares
    else:
        holding["locked_qty"] = shares
        holding["locked_ordinal"] = current
    state["finance"].setdefault(str(club_id), []).append([_int(ordinal), amount])
    trade = _record_trade(
        state, stock, "finance", shares, plan["price"], amount, 0.0, game_date,
    )
    trade["shares_after"] = int(after)
    _notice(
        state, "finance", game_date, club_id=club_id,
        code=str((stock or {}).get("code") or ""),
        name=str((stock or {}).get("name") or ""), qty=shares,
        price=quote(plan.get("price")), amount=amount,
        before=int(before), after=int(after),
        stake=round(stake_of(_int(holding.get("qty")), int(after)), 6),
    )
    return trade


def revert_finance(
    state: dict[str, Any], plan: Mapping[str, Any],
    trade: dict[str, Any] | None = None,
) -> None:
    """Undo :func:`commit_finance` when the money movement was not recorded."""
    club_id = _int(plan.get("club_id"))
    key = str(club_id)
    shares = int(plan.get("qty") or 0)
    record = share_record(state, club_id)
    if isinstance(record, dict) and isinstance(record.get("f"), list):
        events = record["f"]
        for index in range(len(events) - 1, -1, -1):
            entry = events[index]
            if (
                isinstance(entry, (list, tuple)) and len(entry) >= 2
                and _int(entry[1]) == shares
            ):
                events.pop(index)
                break
    paid = state.get("finance")
    if isinstance(paid, dict):
        entries = paid.get(key)
        if isinstance(entries, list) and entries:
            entries.pop()
            if not entries:
                paid.pop(key, None)
    if trade is None:
        trade = _last_matching_trade(state, key, plan, "finance")
    if trade:
        state["trades"] = [
            row for row in state["trades"] if row.get("id") != trade.get("id")
        ]
    holding = state["holdings"].get(key)
    if not holding:
        return
    holding["qty"] = max(0, _int(holding.get("qty")) - shares)
    if holding["qty"] <= 0:
        state["holdings"].pop(key, None)
    else:
        paid = money(_number(plan.get("amount")))
        total = round_money(holding["qty"] * _number(holding.get("avg_cost"))) - paid
        holding["avg_cost"] = quote(max(0.0, total) / holding["qty"])


def trading_limits() -> dict[str, Any]:
    """The board limits the ticket quotes, so the dialog never hard-codes one."""
    return {
        "direct": MAX_DIRECT_BUY_RATIO,
        "block": MAX_BLOCK_BUY_RATIO,
        "stake": MAX_BUY_STAKE,
        "keep": TAKEOVER_KEEP_NUMERATOR / TAKEOVER_KEEP_DENOMINATOR,
        "finance_min": MIN_FINANCE_RATIO,
        "finance_max": MAX_FINANCE_RATIO,
        "finance_stake": MAX_FINANCE_STAKE,
        "takeover_gate": TAKEOVER_STAKE_GATE_RATIO,
        "block_premium": BLOCK_PRICE_PREMIUM,
        "block_weight": BLOCK_SIZE_WEIGHT,
        "impact_k": TRADE_IMPACT_K,
        "impact_half_life": TRADE_IMPACT_HALF_LIFE,
        "orders": MAX_PENDING_ORDERS,
        "fee_rate": TRADE_FEE_RATE,
        "min_fee": MIN_TRADE_FEE,
        "daily_direct": MAX_DIRECT_BUY_RATIO,
        "appetite_floor": FINANCE_ACCEPT_FLOOR,
        "appetite_base": FINANCE_APPETITE_BASE,
        "appetite_cap": FINANCE_APPETITE_CAP,
    }


def toggle_watch(state: dict[str, Any], club_id: Any) -> bool:
    """Add or remove one club from the watch list; returns the new state."""
    identity = _int(club_id)
    if identity <= 0:
        raise ValueError("股票不存在")
    watched = [_int(item) for item in state.get("watchlist") or []]
    if identity in watched:
        state["watchlist"] = [item for item in watched if item != identity]
        return False
    watched.append(identity)
    state["watchlist"] = sorted(set(watched))
    return True


def sync_holding_quotes(state: dict[str, Any], rows: Any, ordinal: int) -> bool:
    """Refresh the last known quote of every holding; returns True when saved."""
    rows_by_id = _row_index(rows)
    books = share_books(state)
    extras = market_extras(state)
    changed = False
    for key, holding in list(state["holdings"].items()):
        if not isinstance(holding, dict):
            continue
        row = rows_by_id.get(_int(key))
        price = share_price(row, ordinal, books.get(_int(key)), extras) if row else 0.0
        if price <= 0:
            continue
        previous = _number(holding.get("last_price"))
        if previous <= 0 or abs(price - previous) / price > 0.005:
            holding["last_price"] = price
            changed = True
    return changed

# ---------------------------------------------------------------------------
# Acquisition coupling
# ---------------------------------------------------------------------------


def club_factor(
    rows: Any, club_id: Any, ordinal: int,
    extras: Mapping[int, Mapping[str, Any]] | None = None,
) -> float:
    """Market factor of one club; 1.0 when the club is not in the directory.

    The acquisition price is the appraisal times this factor, so the record,
    the news and the account's own trades reach the price FMODD charges for
    the club itself - the two never drift apart.
    """
    row = _row_index(rows).get(_int(club_id))
    if not row:
        return 1.0
    return market_factor(row, ordinal, club_id, extras)


def apply_factor(price: Any, factor: Any) -> int:
    """Scale an FMODD appraisal into the price the market charges today."""
    bounded = max(FACTOR_FLOOR, min(FACTOR_CAP, _number(factor, 1.0)))
    return max(0, int(round(_number(price) * bounded)))


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

SORT_KEYS = ("change", "price", "value", "reputation", "holding", "turnover", "name")
_SORT_FIELDS = {
    "change": "change", "price": "price", "value": "market_cap",
    "reputation": "reputation", "holding": "holding_value",
    "turnover": "turnover", "name": "name",
}


def _decorate(
    stock: dict[str, Any], holding: Mapping[str, Any] | None, ordinal: int | None,
    watched: bool,
) -> dict[str, Any]:
    club_id = _int(stock.get("club_id"))
    qty = _int((holding or {}).get("qty"))
    avg_cost = _number((holding or {}).get("avg_cost"))
    price = _number(stock.get("price"))
    stock["watched"] = bool(watched)
    frozen = bool((holding or {}).get("frozen"))
    stock["frozen"] = frozen
    # A club bought outright is held whole by the group: the mark travels with
    # the row so the board, the ticket and the register all agree about it.
    stock["owned"] = str((holding or {}).get("source") or "") == TAKEOVER_SOURCE
    stock["qty"] = qty
    stock["avg_cost"] = quote(avg_cost)
    stock["holding_value"] = money(qty * price)
    stock["holding_cost"] = money(qty * avg_cost)
    stock["profit"] = money(qty * (price - avg_cost)) if qty else 0.0
    stock["profit_ratio"] = (
        round((price - avg_cost) / avg_cost, 6) if qty and avg_cost else 0.0
    )
    shares = _int(stock.get("shares"))
    stock["club_shares"] = max(0, shares - qty)
    stock["max_order"] = max_shares_per_order(shares)
    stock["block_order"] = max_block_shares(shares)
    stock["stake"] = round(stake_of(qty, shares), 6)
    stock["buy_room"] = max(0, int(shares * MAX_BUY_STAKE) - qty)
    # The stake cap is a market rule: it stops an account from taking a club
    # over through the ticket.  A club the group already owns is past it, so
    # its room is the whole capital and only the board's size limits remain.
    stock["finance_room"] = (
        max(0, shares) if stock["owned"] else max_finance_shares(qty, shares)
    )
    stock["finance_min"] = max(1, int(shares * MIN_FINANCE_RATIO))
    stock["finance_max"] = max(
        0, min(int(shares * MAX_FINANCE_RATIO), stock["finance_room"]),
    )
    locked = _int((holding or {}).get("locked_qty"))
    if frozen:
        stock["sellable"] = 0
    elif not locked:
        stock["sellable"] = max(0, qty)
    elif _int((holding or {}).get("locked_ordinal")) >= _int(ordinal):
        stock["sellable"] = max(0, qty - locked)
    else:
        stock["sellable"] = max(0, qty)
    if stock["owned"]:
        # Selling the club itself is a group decision, so the ticket never
        # offers the whole register: what is left of the group's own capital
        # is the most it may sell back to the club.
        keep = takeover_keep_qty(shares)
        stock["keep_shares"] = keep
        stock["sellable"] = max(0, min(_int(stock.get("sellable")), qty - keep))
        # The other direction reads the same book: whatever the club holds is
        # exactly the register the group sold back, so it is what the ticket
        # may take into the group's lot again.  The quarter-of-the-market
        # ceiling of a buyer is not the ceiling of an owner, so the room a
        # ticket quotes for an owned club is that book.
        stock["buyback_room"] = max(0, shares - qty)
        stock["buy_room"] = stock["buyback_room"]
    return stock


def reserved_qty(state: Mapping[str, Any] | None, club_id: Any) -> int:
    """Shares already promised to a pending limit sale of one club."""
    identity = _int(club_id)
    total = 0
    for order in (state or {}).get("orders") or []:
        if not isinstance(order, Mapping):
            continue
        if str(order.get("kind") or "") != "limit":
            continue
        if str(order.get("status") or "pending") != "pending":
            continue
        if _int(order.get("club_id")) == identity:
            total += _int(order.get("qty"))
    return total


def trading_quote(
    state: Mapping[str, Any], row: Mapping[str, Any], ordinal: int, *,
    code: str = "", since: Any = None, book: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One club priced for the account that is about to trade it.

    The board is cached for the whole game day and stays free of player state,
    so a trade resolves its own quote instead of reusing the cached row: the
    shares still on the club's book are counted against what this account
    already owns, and the ticket trades exactly the numbers it was shown.
    """
    source = row or {}
    club_id = _int(source.get("id"))
    holdings = (state or {}).get("holdings") if isinstance(state, Mapping) else None
    holding = holdings.get(str(club_id)) if isinstance(holdings, Mapping) else None
    holding = dict(holding) if isinstance(holding, Mapping) else None
    watched = club_id in {_int(item) for item in ((state or {}).get("watchlist") or [])}
    stock = stock_public(
        source, ordinal, code=code, since=since, book=book, holding=holding,
        extras=market_extras(state),
    )
    stock = _decorate(stock, holding, ordinal, watched)
    stock["takeover"] = takeover_lot(state, club_id) if stock["owned"] else None
    stock["direct_used"] = daily_direct_used(state, club_id, ordinal)
    stock["direct_room"] = daily_direct_room(
        state, club_id, stock.get("shares"), ordinal,
    )
    stock["appetite"] = finance_appetite(source, stock, ordinal)
    stock["sellable"] = max(
        0, _int(stock.get("sellable")) - reserved_qty(state, club_id),
    )
    stock["orders"] = pending_orders(state, club_id=club_id)
    return stock


def club_lot_view(
    state: Mapping[str, Any], row: Mapping[str, Any], ordinal: int, *,
    since: Any = None, book: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One club quoted for the account, with the candles its ticket draws.

    The board is cached for a whole game day and is free of player state, while
    the trade ticket can be opened from pages that never loaded it (a club
    profile, for instance).  This is the row such a dialog trades on: quote,
    appraisal, capital, the account's own lot and the price history in one
    object, all read from the same day and the same capital.
    """
    lot = trading_quote(state, row, ordinal, since=since, book=book)
    lot["history"] = price_history(
        row, ordinal, since=since, book=book, extras=market_extras(state),
    )
    return lot


def holding_lots(
    state: dict[str, Any], rows_by_id: Mapping[int, Mapping[str, Any]], ordinal: int,
    books: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every lot of the account, quoted like the board that can trade it.

    A lot is read through :func:`club_lot_view`, so a holding that belongs to
    an exchange the player is not looking at still carries the appraisal, the
    factor, the capital and the candles its trade ticket draws - the ticket
    must never open on zeros just because another exchange is on screen.
    """
    books = share_books(state) if books is None else books
    extras = market_extras(state)
    watchlist = {_int(item) for item in (state.get("watchlist") or [])}
    lots: list[dict[str, Any]] = []
    for key, holding in state["holdings"].items():
        if not isinstance(holding, dict):
            continue
        club_id = _int(key)
        qty = _int(holding.get("qty"))
        if qty <= 0:
            continue
        row = rows_by_id.get(club_id)
        book = books.get(club_id)
        if row is not None:
            nation = nation_of(row)
            entry = (state.get("nations") or {}).get(nation) or {}
            since = entry.get("listed_ordinal") if isinstance(entry, Mapping) else None
            lot = club_lot_view(state, row, ordinal, since=since, book=book)
        else:
            avg_cost = _number(holding.get("avg_cost"))
            price = quote(holding.get("last_price")) or quote(avg_cost)
            lot = {
                "club_id": club_id,
                "code": str(holding.get("code") or ""),
                "name": str(holding.get("name") or ""),
                "nation": str(holding.get("nation") or ""),
                "competition": str(holding.get("competition") or ""),
                "price": price, "prev_close": price, "change": 0.0,
                "factor": 1.0, "premium": 0.0, "intrinsic": 0, "market_cap": 0,
                "reputation": 0, "shares": 0, "initial_shares": 0,
                "share_base": price, "split_price": 0.0, "split_count": 0,
                "turnover": 0.0, "fundamentals": {}, "history": [],
                "watched": club_id in watchlist, "qty": qty,
                "avg_cost": quote(avg_cost), "sellable": 0,
                "club_shares": 0, "stake": 0.0,
                "impact": 0.0, "financed_cash": 0.0, "financed_shares": 0,
                "holding_value": money(qty * price),
                "holding_cost": money(qty * avg_cost),
                "profit": money(qty * (price - avg_cost)),
                "profit_ratio": (
                    round((price - avg_cost) / avg_cost, 6) if avg_cost else 0.0
                ),
            }
        lot["value"] = money(lot.get("holding_value"))
        lot["cost"] = money(lot.get("holding_cost"))
        lot["profit"] = money(lot.get("profit"))
        lot["profit_ratio"] = round(_number(lot.get("profit_ratio")), 6)
        lot["locked_qty"] = _int(holding.get("locked_qty"))
        lot["frozen"] = bool(holding.get("frozen"))
        lot["owned"] = str(holding.get("source") or "") == TAKEOVER_SOURCE
        lot["source"] = str(holding.get("source") or "")
        lot["reserved"] = reserved_qty(state, club_id)
        lot["orders"] = pending_orders(state, club_id=club_id)
        if lot["frozen"]:
            lot["sellable"] = 0
        else:
            lot["sellable"] = max(0, _int(lot.get("sellable")) - _int(lot["reserved"]))
        lots.append(lot)
    lots.sort(key=lambda item: -_number(item["value"]))
    return lots


def _empty_view(
    state: dict[str, Any], *, scope_id: str, game_date: str, ordinal: int,
) -> dict[str, Any]:
    """Payload for a save whose club directory is not readable yet."""
    return {
        "ready": True, "scope_id": scope_id, "game_date": str(game_date or ""),
        "ordinal": ordinal, "initialized": bool(state.get("initialized")),
        "initialized_game_date": str(state.get("initialized_game_date") or ""),
        "enabled": market_enabled(state),
        "scope": listed_scope(state.get("scope"), state.get("scope_suspended")),
        "scope_suspended": [
            [nation, competition] for nation, competition in sorted(suspended_pairs(state))
        ],
        "share_trigger": SHARE_SPLIT_TRIGGER, "fee_rate": TRADE_FEE_RATE,
        "min_fee": MIN_TRADE_FEE, "max_shares_per_order": MAX_SHARES_PER_ORDER,
        "max_order_ratio": MAX_ORDER_SHARE_RATIO,
        "limits": trading_limits(),
        "orders": pending_orders(state),
        "nations": [], "nation": "",
        "index": {
            "value": INDEX_BASE, "prev_close": INDEX_BASE, "base": INDEX_BASE,
            "change": 0.0, "history": [], "components": [], "nation": "",
        },
        "summary": {
            "name": "", "clubs": 0, "cap": 0.0, "change": 0.0, "gainers": 0,
            "losers": 0, "flat": 0, "turnover": 0.0, "my_value": 0.0,
            "my_cost": 0.0, "my_profit": 0.0, "components": 0,
        },
        "pagination": {
            "page": 1, "page_size": BOARD_PAGE_SIZE, "page_count": 1,
            "total": 0, "from": 0, "to": 0,
        },
        "stocks": [], "holdings": [], "watchlist": [],
        "trades": list(reversed(state.get("trades") or [])),
        "notices": list(reversed(state.get("notices") or [])),
        "receipts": list(reversed(state.get("receipts") or [])),
        "totals": {
            "market_value": 0.0, "cost": 0.0, "profit": 0.0,
            "frozen_value": 0.0, "frozen_count": 0,
            "realized_profit": money(state.get("realized_profit")),
        },
    }


def market_view(
    state: dict[str, Any], rows: Any, *, game_date: str, scope_id: str = "",
    nation: str = "", search: str = "", sort: str = "change", order: str = "desc",
    page: Any = 1, page_size: Any = BOARD_PAGE_SIZE, watch_only: bool = False,
    board: Mapping[str, list] | None = None,
    summary: Mapping[str, dict] | None = None,
    books: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Public market snapshot for the web UI, one exchange at a time."""
    rows_by_id = _row_index(rows)
    books = share_books(state) if books is None else books
    extras = market_extras(state)
    ordinal = day_ordinal(game_date)
    if ordinal is None:
        ordinal = _int(state.get("last_seen_ordinal"))
    if not rows_by_id:
        return _empty_view(state, scope_id=str(scope_id or ""), game_date=game_date, ordinal=ordinal)
    summary = dict(summary or nation_summary(rows_by_id.values(), ordinal))
    nations = sorted(
        summary.values(), key=lambda item: (-item["cap"], str(item["name"])),
    )
    selected = str(nation or "").strip()
    if selected not in summary:
        selected = str(nations[0]["name"]) if nations else ""
    entry = state["nations"].get(selected) if isinstance(state["nations"], dict) else {}
    entry = entry if isinstance(entry, dict) else {}
    since = listing_day(entry.get("listed_ordinal"), ordinal)
    watchlist = {_int(item) for item in state.get("watchlist") or []}
    if board is not None:
        stocks = [dict(item) for item in (board.get(selected) or [])]
    else:
        stocks = nation_board(
            rows_by_id.values(), ordinal, nations=[selected], since=since,
            books=books, extras=extras,
        ).get(selected, [])
    holdings_by_id = {
        _int(key): value for key, value in state["holdings"].items()
        if isinstance(value, dict)
    }
    stocks = [
        _decorate(stock, holdings_by_id.get(_int(stock.get("club_id"))), ordinal,
                  _int(stock.get("club_id")) in watchlist)
        for stock in stocks
    ]
    query = str(search or "").strip().casefold()
    if query:
        stocks = [
            stock for stock in stocks
            if query in str(stock.get("name") or "").casefold()
            or query in str(stock.get("code") or "").casefold()
            or query in str(stock.get("competition") or "").casefold()
        ]
    if watch_only:
        stocks = [stock for stock in stocks if stock.get("watched")]
    field = _SORT_FIELDS.get(str(sort or "change"), "change")
    reverse = str(order or "desc").strip().lower() != "asc"
    if field == "name":
        stocks.sort(key=lambda item: str(item.get("name") or "").casefold(), reverse=reverse)
    else:
        stocks.sort(key=lambda item: item.get(field) or 0, reverse=reverse)
    size = max(10, min(BOARD_MAX_PAGE_SIZE, _int(page_size, BOARD_PAGE_SIZE) or BOARD_PAGE_SIZE))
    number = max(1, _int(page, 1))
    total = len(stocks)
    page_count = max(1, (total + size - 1) // size)
    number = min(number, page_count)
    window = stocks[(number - 1) * size: number * size]
    for stock in window:
        club_id = _int(stock.get("club_id"))
        row = rows_by_id.get(club_id)
        stock["history"] = price_history(
            row, ordinal, since=since, book=books.get(club_id), extras=extras,
        )
        # The page trades straight off these rows, so the budget the day has
        # left and the mood of the club ride along with the quote: a ticket
        # opened from the board reads exactly what a ticket opened from a lot
        # does, without a second round trip.
        stock["direct_used"] = daily_direct_used(state, club_id, ordinal)
        stock["direct_room"] = daily_direct_room(
            state, club_id, stock.get("shares"), ordinal,
        )
        stock["appetite"] = finance_appetite(row, stock, ordinal)

    index = nation_index(entry, rows_by_id, ordinal, since=since, extras=extras)
    index["history"] = index_series(
        entry, rows_by_id, ordinal, since=since, books=books, extras=extras,
    )
    previous = _number(index.get("prev_close"))
    index["change"] = ((_number(index.get("value")) - previous) / previous) if previous else 0.0
    index["nation"] = selected

    lots = holding_lots(state, rows_by_id, ordinal, books=books)
    holdings_value = money(sum(item["value"] for item in lots))
    holdings_cost = money(sum(item["cost"] for item in lots))
    frozen_lots = [item for item in lots if item.get("frozen")]
    frozen_value = money(sum(item["value"] for item in frozen_lots))
    selected_lots = [item for item in lots if item["nation"] == selected]
    nation_summary_row = dict(summary.get(selected) or {
        "name": selected, "clubs": 0, "cap": 0.0, "change": 0.0, "gainers": 0,
        "losers": 0, "flat": 0, "turnover": 0.0,
    })
    nation_summary_row.update({
        "listed_game_date": entry.get("listed_game_date"),
        "listed_ordinal": entry.get("listed_ordinal"),
        "components": len(entry.get("components") or []),
        "my_value": money(sum(item["value"] for item in selected_lots)),
        "my_cost": money(sum(item["cost"] for item in selected_lots)),
    })
    nation_summary_row["my_profit"] = money(
        nation_summary_row["my_value"] - nation_summary_row["my_cost"]
    )
    board_rows = []
    for item in nations:
        name = str(item.get("name") or "")
        entry_row = state["nations"].get(name) if isinstance(state["nations"], dict) else {}
        entry_row = entry_row if isinstance(entry_row, dict) else {}
        listed = listing_day(entry_row.get("listed_ordinal"), ordinal)
        fresh = listed is not None and listed >= int(ordinal)
        board_rows.append({
            "name": name, "clubs": _int(item.get("clubs")),
            "cap": money(item.get("cap")),
            "change": 0.0 if fresh else round(_number(item.get("change")), 6),
            "gainers": _int(item.get("gainers")), "losers": _int(item.get("losers")),
            "my_value": money(sum(
                lot["value"] for lot in lots if lot["nation"] == name
            )),
        })
    return {
        "ready": True,
        "scope_id": str(scope_id or ""),
        "game_date": str(game_date or state.get("last_game_date") or ""),
        "ordinal": ordinal,
        "initialized": bool(state.get("initialized")),
        "initialized_game_date": str(state.get("initialized_game_date") or ""),
        "enabled": market_enabled(state),
        "scope": listed_scope(state.get("scope"), state.get("scope_suspended")),
        "scope_suspended": [
            [nation, competition] for nation, competition in sorted(suspended_pairs(state))
        ],
        "share_trigger": SHARE_SPLIT_TRIGGER,
        "fee_rate": TRADE_FEE_RATE,
        "min_fee": MIN_TRADE_FEE,
        "max_shares_per_order": MAX_SHARES_PER_ORDER,
        "max_order_ratio": MAX_ORDER_SHARE_RATIO,
        "limits": trading_limits(),
        "orders": pending_orders(state),
        "nations": board_rows,
        "nation": selected,
        "index": index,
        "summary": nation_summary_row,
        "pagination": {
            "page": number, "page_size": size, "page_count": page_count,
            "total": total, "from": (number - 1) * size + 1 if total else 0,
            "to": min(total, number * size),
        },
        "stocks": window,
        "holdings": lots,
        "watchlist": sorted(watchlist),
        "trades": list(reversed(state.get("trades") or [])),
        "notices": list(reversed(state.get("notices") or [])),
        "receipts": list(reversed(state.get("receipts") or [])),
        "totals": {
            "market_value": holdings_value,
            "cost": holdings_cost,
            "profit": money(holdings_value - holdings_cost),
            "frozen_value": frozen_value,
            "frozen_count": len(frozen_lots),
            "realized_profit": money(state.get("realized_profit")),
        },
    }

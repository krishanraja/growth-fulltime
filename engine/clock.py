"""Europe/London time without third-party data.

zoneinfo reads the system time zone database, which Windows does not have: there it
needs the tzdata package, and this repository is standard library only. When
zoneinfo cannot find Europe/London, UK rules apply instead: British Summer Time
(UTC+1) from 01:00 UTC on the last Sunday of March until 01:00 UTC on the last
Sunday of October, otherwise Greenwich Mean Time (UTC+0). Those have been the UK
rules since 1996.
"""
import datetime as dt

HOUR = dt.timedelta(hours=1)
ZERO = dt.timedelta(0)


def _last_sunday(year, month):
    day = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return day - dt.timedelta(days=(day.weekday() + 1) % 7)


def _summer_utc(year):
    """The UTC instants British Summer Time starts and ends in this year, naive."""
    start, end = _last_sunday(year, 3), _last_sunday(year, 10)
    return dt.datetime(start.year, start.month, start.day, 1), dt.datetime(end.year, end.month, end.day, 1)


class UKTime(dt.tzinfo):
    """Europe/London by UK rules, for when the system has no time zone database."""

    def utcoffset(self, moment):
        return self._offset(moment)

    def dst(self, moment):
        return self._offset(moment)

    def tzname(self, moment):
        return 'BST' if self._offset(moment) else 'GMT'

    def _offset(self, moment):
        if moment is None:
            return ZERO
        start, end = _summer_utc(moment.year)
        wall = moment.replace(tzinfo=None)
        # PEP 495, as zoneinfo reads it: in the skipped spring hour (01:00-02:00) fold 0
        # takes the winter offset and fold 1 the summer one; in the repeated autumn hour
        # (01:00-02:00) fold 0 is the first, summer pass and fold 1 the second.
        fold = getattr(moment, 'fold', 0)
        if start <= wall < start + HOUR:
            return HOUR if fold else ZERO
        if end <= wall < end + HOUR:
            return ZERO if fold else HOUR
        return HOUR if start + HOUR <= wall < end else ZERO

    def fromutc(self, moment):
        start, end = _summer_utc(moment.year)
        naive = moment.replace(tzinfo=None)
        if start <= naive < end:
            local = naive + HOUR
            return local.replace(tzinfo=self, fold=0)
        local = naive.replace(tzinfo=self)
        # The repeated hour after summer ends is the second pass.
        return local.replace(fold=1) if end <= naive < end + HOUR else local

    def __repr__(self):
        return 'UKTime()'


def london():
    """The Europe/London tzinfo: zoneinfo when the system has it, else UK rules."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Europe/London')
    except Exception:       # ZoneInfoNotFoundError, or no zoneinfo module at all
        return UKTime()


LONDON = london()

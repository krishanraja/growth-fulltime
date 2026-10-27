import datetime as dt
import unittest
from unittest import mock

from engine import clock
from engine.clock import UKTime

UTC = dt.timezone.utc
UK = UKTime()


class UKRules(unittest.TestCase):
    """Known UK instants, so the fallback is proved even where zoneinfo is absent (Windows)."""

    def local(self, *utc):
        return dt.datetime(*utc, tzinfo=UTC).astimezone(UK)

    def test_summer_starts_at_one_utc_on_the_last_sunday_of_march(self):
        before = self.local(2026, 3, 29, 0, 59)
        after = self.local(2026, 3, 29, 1, 0)
        self.assertEqual((before.hour, before.minute, before.tzname()), (0, 59, 'GMT'))
        self.assertEqual((after.hour, after.tzname()), (2, 'BST'))

    def test_summer_ends_at_one_utc_on_the_last_sunday_of_october(self):
        first = self.local(2026, 10, 25, 0, 30)
        second = self.local(2026, 10, 25, 1, 30)
        self.assertEqual((first.hour, first.minute, first.fold, first.tzname()), (1, 30, 0, 'BST'))
        self.assertEqual((second.hour, second.minute, second.fold, second.tzname()), (1, 30, 1, 'GMT'))
        self.assertEqual(first.astimezone(UTC).hour, 0)
        self.assertEqual(second.astimezone(UTC).hour, 1)

    def test_winter_and_summer_dates(self):
        self.assertEqual(dt.datetime(2026, 1, 15, 12, tzinfo=UK).utcoffset(), dt.timedelta(0))
        self.assertEqual(dt.datetime(2026, 7, 15, 12, tzinfo=UK).utcoffset(), dt.timedelta(hours=1))

    def test_falls_back_when_the_system_has_no_time_zone_data(self):
        with mock.patch('zoneinfo.ZoneInfo', side_effect=Exception('no tzdata')):
            self.assertIsInstance(clock.london(), UKTime)


class MatchesZoneinfo(unittest.TestCase):
    def setUp(self):
        try:
            from zoneinfo import ZoneInfo
            self.zone = ZoneInfo('Europe/London')
        except Exception:
            self.skipTest('this system has no time zone database')

    def test_every_quarter_hour_around_each_change_from_2020_to_2030(self):
        for year in range(2020, 2031):
            for month in (3, 10):
                change = clock._last_sunday(year, month)
                moment = dt.datetime(change.year, change.month, change.day, tzinfo=UTC) - dt.timedelta(hours=6)
                for _ in range(12 * 4):
                    a, b = moment.astimezone(self.zone), moment.astimezone(UK)
                    self.assertEqual((a.replace(tzinfo=None), a.utcoffset(), a.fold),
                                     (b.replace(tzinfo=None), b.utcoffset(), b.fold), moment)
                    for fold in (0, 1):
                        wall = a.replace(tzinfo=None, fold=fold)
                        self.assertEqual(wall.replace(tzinfo=self.zone).utcoffset(),
                                         wall.replace(tzinfo=UK).utcoffset(), (wall, fold))
                    moment += dt.timedelta(minutes=15)


if __name__ == '__main__':
    unittest.main()

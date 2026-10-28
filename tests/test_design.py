"""Independent scheduling enumeration and behavioral placement checks."""
import itertools
import unittest

from shapely.geometry import box
from network_design.geography import Countries, Geography, Site, distance_km
from network_design.score import ScoreOptimizer, SearchSettings, coordinates, vector
from network_design.evaluation import Pass, schedule, NetworkEvaluator, FixedRateLink


class SchedulingTests(unittest.TestCase):
    def test_matches_exhaustive_schedule(self):
        passes = [(0, Pass('a', 0, 10, 1, 1)), (1, Pass('a', 5, 15, 1, 1)),
                  (0, Pass('b', 5, 12, 1, 1)), (1, Pass('b', 15, 20, 1, 1)),
                  (2, Pass('c', 0, 20, 1, 1))]
        volumes = [10, 20, 11, 7, 3]
        best = 0
        for mask in itertools.product([0, 1], repeat=len(passes)):
            selected = [passes[i] for i, keep in enumerate(mask) if keep]
            valid = True
            for (station_a, a), (station_b, b) in itertools.combinations(selected, 2):
                overlap = a.start_s < b.end_s and b.start_s < a.end_s
                if overlap and (station_a == station_b or a.satellite == b.satellite):
                    valid = False
            if valid:
                best = max(best, sum(v for v, keep in zip(volumes, mask) if keep))
        actual, chosen = schedule(passes, volumes)
        self.assertEqual(actual, best)
        self.assertEqual(actual, sum(volumes[i] for i in chosen))

    def test_back_to_back_and_empty(self):
        contacts = [(0, Pass('a', 0, 10, 1, 1)), (0, Pass('a', 10, 20, 1, 1))]
        self.assertEqual(schedule(contacts, [10, 10])[0], 20)
        self.assertEqual(schedule([], []), (0, []))

    def test_link_hook_and_duration_filter(self):
        class Provider:
            def contacts(self, site):
                return (Pass('a', 0, 10, 8, 16), Pass('a', 20, 22, 8, 16))
        class HalfRate:
            def data_bits(self, contact, site):
                return FixedRateLink().data_bits(contact, site)/2
        sites = [Site(0, 0)]
        original = NetworkEvaluator(Provider(), FixedRateLink(), 5).details(sites)
        changed = NetworkEvaluator(Provider(), HalfRate(), 5).details(sites)
        self.assertEqual(original['eligible_contacts'], 1)
        self.assertEqual(original['data_bits'], 80)
        self.assertEqual(changed['data_bits'], 40)


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.countries = Countries({'AAA': box(-40, -30, -10, 30), 'BBB': box(10, -30, 40, 30)})

    def test_invalid_requirements(self):
        for kwargs in [dict(country_minimums={'AAA': 3}), dict(country_minimums={'BAD': 1}),
                       dict(country_minimums={'AAA': 1}, excluded_countries=['AAA']),
                       dict(country_minimums={'AAA': 2}, country_maximums={'AAA': 1}),
                       dict(country_maximums={'AAA': 0, 'BBB': 1})]:
            with self.assertRaises(ValueError):
                Geography(self.countries, 2, **kwargs)

    def test_country_and_separation_checks(self):
        geo = Geography(self.countries, 2, {'AAA': 1, 'BBB': 1}, min_separation_km=100)
        self.assertEqual(geo.violations([Site(-20, 0), Site(20, 0)]), [])
        self.assertIn('country minimum', geo.violations([Site(-20, 0), Site(-21, 1)]))
        self.assertIn('station separation', geo.violations([Site(-20, 0), Site(-20, 0)]))
        self.assertIsNone(self.countries.country(Site(0, 0)))

    def test_spherical_coordinates(self):
        for s in [Site(179, 45), Site(-179, -45), Site(0, 90)]:
            self.assertLess(distance_km(s, coordinates(vector(s))), 1e-6)

    def test_exclusions_and_maximums_are_enforced(self):
        geo = Geography(self.countries, 2, country_maximums={'AAA': 1})
        self.assertIn('country maximum', geo.violations([Site(-20, 0), Site(-30, 0)]))
        geo = Geography(self.countries, 2, excluded_countries=['BBB'])
        self.assertIn('excluded country', geo.violations([Site(-20, 0), Site(20, 0)]))

    def test_score_reproducible_feasible_and_monotone(self):
        geo = Geography(self.countries, 2, {'AAA': 1, 'BBB': 1}, min_separation_km=100)
        def objective(sites):
            return sum(1000 - (abs(s.longitude)-25)**2 - s.latitude**2 for s in sites)
        settings = SearchSettings(seed=17, starts_per_move=2, evaluations_per_start=35, max_cycles=2)
        first = ScoreOptimizer(objective, geo, settings).solve()
        second = ScoreOptimizer(objective, geo, settings).solve()
        self.assertEqual(first, second)
        self.assertEqual(first['country_counts'], {'AAA': 1, 'BBB': 1})
        self.assertEqual(first['constraint_violations'], [])
        self.assertGreater(first['objective'], 1900)
        values = [e['objective'] for e in first['history'] if len(e['sites']) == 2]
        self.assertTrue(all(b >= a for a, b in zip(values, values[1:])))


if __name__ == '__main__':
    unittest.main()

import unittest
from shapely.geometry import box
from network_design.geography import Countries,Geography,Site
from network_design.score import ScoreOptimizer,SearchSettings
from network_design.scenario import normalize

class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.countries=Countries({'AAA':box(-40,-30,-10,30),'BBB':box(10,-30,40,30)})
        self.existing=[Site(-30,0)]
        self.settings=SearchSettings(starts_per_move=1,evaluations_per_start=15,max_cycles=2)

    def test_existing_fixed_and_counted(self):
        g=Geography(self.countries,2,{'AAA':1,'BBB':1},{'AAA':1})
        r=ScoreOptimizer(lambda sites:sum(1000-s.latitude**2 for s in sites),g,self.settings).solve(self.existing)
        self.assertEqual(r['sites'][0],{'longitude':-30,'latitude':0})
        self.assertEqual(r['country_counts'],{'AAA':1,'BBB':1})
        self.assertEqual(r['existing_objective'],1000)
        for e in r['history']:
            self.assertEqual(e['sites'][0],r['sites'][0])

    def test_evaluation_only(self):
        g=Geography(self.countries,1,{'AAA':1})
        r=ScoreOptimizer(lambda sites:7,g,self.settings).solve(self.existing)
        self.assertEqual(r['sites'],[{'longitude':-30,'latitude':0}])
        self.assertEqual(r['objective'],7)
        self.assertEqual(r['evaluations'],1)

    def test_existing_conflicts_fail_before_search(self):
        cases=[Geography(self.countries,2,{'BBB':2}),Geography(self.countries,2,country_maximums={'AAA':0}),
               Geography(self.countries,2,excluded_countries=['AAA'])]
        for g in cases:
            with self.assertRaisesRegex(ValueError,'Existing sites'):
                ScoreOptimizer(lambda sites:self.fail('Must validate before evaluating'),g,self.settings).solve(self.existing)

    def test_scenario_presets_and_counts(self):
        c={'existing_sites':[{'name':'A','longitude':-30,'latitude':0}],'new_sites':2,
           'satellites':[{'name':'M','preset':'MEO'},{'name':'L','preset':'LEO','altitude_km':600}]}
        normalized,_=normalize(c)
        self.assertEqual(normalized['geography']['station_count'],3)
        self.assertGreater(normalized['orbits'][0]['semi_major_axis_km'],26000)
        self.assertAlmostEqual(normalized['orbits'][1]['semi_major_axis_km'],6978.137)
        self.assertNotIn('geography',c)
        normalized,_=normalize({'satellites':[{'name':'custom','preset':'MEO','semi_major_axis_km':27000,'eccentricity':.1}]})
        self.assertEqual(normalized['orbits'][0]['semi_major_axis_km'],27000)

    def test_ambiguous_config_rejected(self):
        for c in [{'new_sites':-1},{'new_sites':True},{'new_sites':1,'geography':{'station_count':3}},
                  {'satellites':[],'orbits':[]}, {'satellites':[{'name':'x','preset':'wrong'}]},
                  {'satellites':[{'name':'x','preset':'MEO','eccentricity':.1}]}]:
            with self.assertRaises(ValueError):normalize(c)

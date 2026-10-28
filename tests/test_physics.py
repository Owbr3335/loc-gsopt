import unittest
import numpy as np
from scipy.integrate import solve_ivp
from network_design.orbits import Orbit,OrbitContacts,MU,OMEGA
from network_design.geography import Site
from network_design.links import RFLink,RFSettings

class PhysicsTests(unittest.TestCase):
    def test_ellipse_against_independent_ode(self):
        o=Orbit('HEO',26600,.72)
        a=o.semi_major_axis_km*1000; r=a*(1-o.eccentricity)
        initial=[r,0,0,0,np.sqrt(MU*(1+o.eccentricity)/r),0]
        ts=np.linspace(0,o.period_s,101)
        def rhs(t,y): return np.r_[y[3:],-MU*y[:3]/np.linalg.norm(y[:3])**3]
        numerical=solve_ivp(rhs,[0,o.period_s],initial,t_eval=ts,rtol=1e-11,atol=1e-4).y[:3].T
        self.assertLess(np.max(np.linalg.norm(numerical-o.position(ts),axis=1)),1)
        self.assertAlmostEqual(np.linalg.norm(o.position(o.period_s/2)),a*(1+o.eccentricity),places=3)

    def test_geo_continuous_and_hidden(self):
        o=Orbit('GEO',(MU/OMEGA**2)**(1/3)/1000)
        p=OrbitContacts([o]); c=p.contacts(Site(0,0))
        self.assertEqual(len(c),1); self.assertEqual(c[0].end_s,86400)
        self.assertEqual(p.contacts(Site(180,0)),())
        d,e=p.geometry(Site(0,0),'GEO',np.array([0,43200,86400]))
        self.assertTrue(np.allclose(e,90)); self.assertLess(np.ptp(d),1e-6)

    def test_contact_step_convergence(self):
        o=Orbit('LEO',6878,0,51.6)
        results=[]
        for step in [60,15]:
            p=OrbitContacts([o],step_s=step)
            results.append([(c.start_s,c.end_s) for c in p.contacts(Site(-105,40))])
        self.assertGreater(len(results[0]),0)
        np.testing.assert_allclose(results[0],results[1],atol=.01)

    def test_link_scaling(self):
        clear=RFLink(None,RFSettings(zenith_atmospheric_loss_db=0))
        r=clear.rate(1e7,90,1e30)
        self.assertAlmostEqual(clear.rate(2e7,90,1e30)/r,.25)
        cloudy=RFLink(None,RFSettings(zenith_atmospheric_loss_db=3))
        self.assertAlmostEqual(cloudy.rate(1e7,90,1e30)/r,10**(-.3))
        self.assertLess(cloudy.rate(1e7,10,1e30),cloudy.rate(1e7,90,1e30))
        self.assertEqual(clear.rate(1e7,90,10),10)
        self.assertEqual(RFLink(None,RFSettings(availability=0)).rate(1e7,90,10),0)

    def test_rf_contact_integral(self):
        from network_design.evaluation import Pass
        class ConstantGeometry:
            def geometry(self, site, satellite, seconds):
                return np.full_like(seconds,1e7),np.full_like(seconds,90)
        link=RFLink(ConstantGeometry(),RFSettings(zenith_atmospheric_loss_db=0))
        contact=Pass('test',0,123,1e30,1e30)
        expected=float(link.rate(1e7,90,1e30))*123
        self.assertAlmostEqual(link.data_bits(contact,Site(0,0))/expected,1)

    def test_invalid_physics(self):
        for kwargs in [{'eccentricity':1},{'semi_major_axis_km':6000},{'rate_bps':-1}]:
            params={'name':'bad','semi_major_axis_km':7000,**kwargs}
            with self.assertRaises(ValueError): Orbit(**params)
        with self.assertRaises(ValueError): RFSettings(availability=1.1)

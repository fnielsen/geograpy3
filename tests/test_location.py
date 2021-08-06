'''
Created on 2021-06-09

@author: wf
'''
import unittest
import numpy as np
from geograpy.locator import Locator, CityManager, CountryManager, RegionManager, Country,  LocationContext
from sklearn.neighbors import BallTree

from math import radians


class TestLocationHierarchy(unittest.TestCase):
    '''
    tests for the location hierarchy
    '''

    def setUp(self):
        self.debug=False
        pass

    def tearDown(self):
        pass

    def testDistance(self):
        '''
        test calculcating the distance of two points using the haversine function
        '''
        # https://stackoverflow.com/a/64585765/1497139
        earth_radius = 6371000 # meters in earth
        test_radius = 1300000 # meters
        
        test_points = [[32.027240,-81.093190],[41.981876,-87.969982]]
        test_points_rad = np.array([[radians(x[0]), radians(x[1])] for x in test_points ])
        
        tree = BallTree(test_points_rad, metric = 'haversine')
        ind,results = tree.query_radius(test_points_rad, r=test_radius/earth_radius, 
        return_distance  = True)
        if self.debug:
            print(ind)
            print(results * earth_radius/1000)

    def testIssue45_BallTree(self):
        '''
        test calculation a ball tree for a given list of locations
        '''
        countryList=CountryManager.fromErdem()
        ballTree,validList=countryList.getBallTuple()
        self.assertEqual(245,len(validList))
        self.assertEqual("BallTree",type(ballTree).__name__)
        self.assertAlmostEqual(245, ballTree.sum_weight, delta=0.1)
        pass

    def checkLocationListWithDistances(self,locationListWithDistances,expectedCount,expectedClosest,expectedDistance):
        '''
        check the location list with the given distances
        '''
        if self.debug:
            for i,locationWithDistance in enumerate(locationListWithDistances):
                location,distance=locationWithDistance
                print(f"{i}:{location}-{distance:.0f} km")
        self.assertEqual(len(locationListWithDistances),expectedCount)
        closestLocation,distance=locationListWithDistances[0]
        self.assertEqual(expectedClosest,closestLocation.name)
        self.assertAlmostEqual(expectedDistance, distance,delta=1)

    def testClosestLocation(self):
        '''
        test getting the closes Location to a given location
        '''
        # sample Country: Germany
        country = Country()
        country.name= 'Germany'
        country.lat = 51.0
        country.lon = 9.0
        # get a country list
        lookupCountryManager = CountryManager.fromErdem()
        # get the closest 2 locations for the given countryList
        countryListWithDistances= country.getNClosestLocations(lookupCountryManager,2)
        self.checkLocationListWithDistances(countryListWithDistances, 2, "Luxembourg", 244)

        countryListWithDistances=country.getLocationsWithinRadius(lookupCountryManager, 300)
        self.checkLocationListWithDistances(countryListWithDistances, 2, "Luxembourg", 244)

    def testRegionMatching(self):
        '''
        test region matches
        '''
        locator=Locator()
        if not locator.db_has_data():
            locator.populate_db()
        countryList=CountryManager.fromErdem()
        regionList=RegionManager.from_sqlDb(locator.sqlDB)
        for country in countryList.countries:
            locationListWithDistances=country.getNClosestLocations(regionList,3)
            if self.debug:
                print(f"{country}{country.lat:.2f},{country.lon:.2f}")
            for i,locationWithDistance in enumerate(locationListWithDistances):
                location,distance=locationWithDistance
                if self.debug:
                    print(f"    {i}:{location}-{distance:.0f} km")
        pass

    def testLocationListLoading(self):
        '''
        test loading the locations from Json
        '''
        samples="""
        {
            "countries": [
                {
                    "name": "Afghanistan",
                    "wikidataid": "Q889",
                    "lat": 34,
                    "lon": 66,
                    "coordinates": "34,66",
                    "partOf": null,
                    "level": 3,
                    "locationKind": "Country",
                    "comment": null,
                    "iso": "AF"
                },
                {
                    "name": "United States of America",
                    "wikidataid": "Q30",
                    "lat": 39.82818,
                    "lon": -98.5795,
                    "partOf": "Noth America",
                    "level": 3,
                    "locationKind": "Country",
                    "comment": null,
                    "labels": [
                        "America",
                        "UNITED STATES OF AMERICA",
                        "USA",
                        "United States",
                        "United States of America (the)"
                    ],
                    "iso": "US"
                },
                {
                    "name": "Australia",
                    "wikidataid": "Q408",
                    "lat": -28,
                    "lon": 137,
                    "coordinates": "-28,137",
                    "partOf": null,
                    "level": 3,
                    "locationKind": "Country",
                    "comment": null,
                    "labels": [
                        "AUS"
                    ],
                    "iso": "AU"
                }
            ]
        }
        """
        countries = CountryManager().restoreFromJsonStr(samples)
        # USA is a country that should always be in the list test if present
        us_present = False
        for country in countries:
            if 'wikidataid' in country.__dict__:
                if country.wikidataid == "Q30":
                    us_present = True
                    break
        self.assertTrue(us_present)

    def testCountryManagerFromWikidata(self):
        '''
        tests if the CountryManager id correctly loaded from Wikidata query result
        '''
        countryList=CountryManager.fromWikidata()
        self.assertTrue(len(countryList.countries)>=190)

    def testCityManagerFromJSONBackup(self):
        '''
        tests the loading and parsing of the cityList form the json backup file
        '''
        cityList=CityManager().fromJSONBackup()
        self.assertTrue('cities' in cityList.__dict__)
        self.assertTrue(len(cityList.cities)>=50000)
        # check if Los Angeles is in the list (popular city should always be in the list)
        la_present = False
        for city in cityList.cities:
            if 'wikidataid' in city.__dict__:
                if city.wikidataid == "Q65":
                    la_present = True
                    break
        self.assertTrue(la_present)

    def testRegionManagerFromJSONBackup(self):
        '''
        tests the loading and parsing of the RegionManager form the json backup file
        '''
        regionList=RegionManager.fromJSONBackup()
        self.assertTrue('regions' in regionList.__dict__)
        self.assertTrue(len(regionList.regions) >= 1000)
        # check if California is in the list
        ca_present=False
        for region in regionList.regions:
            if 'wikidataid' in region.__dict__:
                if region.wikidataid == "Q99":
                    ca_present = True
                    break
        self.assertTrue(ca_present)

    def testCountryManagerFromJSONBackup(self):
        '''
        tests the loading and parsing of the RegionManager form the json backup file
        '''
        countryList=CountryManager.fromJSONBackup()
        self.assertTrue('countries' in countryList.__dict__)
        self.assertTrue(len(countryList.countries) >= 180)
        # check if California is in the list
        us_present=False
        for country in countryList.countries:
            if 'wikidataid' in country.__dict__:
                if country.wikidataid == "Q30":
                    us_present = True
                    break
        self.assertTrue(us_present)


    def test_getLocationByID(self):
        '''
        tests if the correct location for a given wikidataid is returned
        '''
        countryList=CountryManager.fromJSONBackup()
        country=countryList.getLocationByID("Q30")   # wikidataid of USA
        self.assertTrue('iso' in country.__dict__)
        self.assertEqual(country.iso, 'US')

    def test_RegionManagerFromWikidata(self):
        '''
        tests the loading of the RegionManager from wikidata query results
        '''
        regionList = RegionManager.fromWikidata()
        #check amount of regions
        self.assertTrue(len(regionList.regions)>3500)
        # check if california is present
        ca=regionList.getLocationByID("Q99")
        self.assertIsNotNone(ca)
        self.assertEqual(ca.name, "California")

    def test_CityManagerFromWikidata(self):
        '''
        tests the loading of the RegionManager from wikidata query results
        '''
        regions=["Q1198"]
        cityList=CityManager.fromWikidata(regionIDs=regions, fromBackup=False)
        #check amount of regions
        self.assertTrue(len(cityList.cities)>1300)
        # check if NRW is present (region of Germany)
        aachen=cityList.getLocationByID("Q1017")
        self.assertIsNotNone(aachen)
        self.assertEqual(aachen.name, "Aachen")


    def test_LocationContext(self):
        '''
        tests the LocationContext class
        '''
        locationContext=LocationContext.fromJSONBackup()
        # test interlinking of city with region and country
        cities=locationContext.getCities('Los Angeles')
        la=[x for x in cities if x.wikidataid =="Q65"][0]
        self.assertEqual(la.name, 'Los Angeles')
        ca=la.region
        self.assertEqual(ca.name, 'California')
        us=la.country
        self.assertEqual(us.wikidataid, 'Q30')
        self.assertEqual(la.country, ca.country)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
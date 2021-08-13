'''
Created on 2021-08-13

@author: wf
'''
import unittest
from tests.basetest import Geograpy3Test
from geograpy.locator import LocationManager,CityManager,RegionManager,CountryManager

class TestLocationContext(Geograpy3Test):
    '''
    test the location Context - these are potentially long running tests
    '''
    
    def checkNoDuplicateWikidataIds(self, locationManager:LocationManager):
        '''
        check that there are no duplicate Wikidata Q identifiers in the given
        
        '''
        locationsByWikiDataId, duplicates = locationManager.getLookup("wikidataid")
        if len(duplicates) > 0:
            for i, duplicate in enumerate(duplicates):
                    print(f"{i}:{duplicate}")
        self.assertEqual(len(duplicates), 0)
        return locationsByWikiDataId

    def testCityManagerFromJSONBackup(self):
        '''
        tests the loading and parsing of the cityList form the json backup file
        '''
        cityManager = CityManager().fromJSONBackup()
        self.assertTrue(hasattr(cityManager, 'cities'))
        self.assertTrue(len(cityManager.cities) >= 400000)
        # check if Los Angeles is in the list (popular city should always be in the list)
        citiesByWikiDataId = self.checkNoDuplicateWikidataIds(cityManager)
        self.assertTrue("Q65" in citiesByWikiDataId)

    def testRegionManagerFromJSONBackup(self):
        '''
        tests the loading and parsing of the RegionManager form the json backup file
        '''
        regionManager = RegionManager.fromJSONBackup()
        self.assertTrue(hasattr(regionManager,'regions'))
        self.assertTrue(len(regionManager.regions) >= 1000)
        regionsByWikidataId = self.checkNoDuplicateWikidataIds(regionManager)
        self.assertTrue("Q99" in regionsByWikidataId)

    def testCountryManagerFromJSONBackup(self):
        '''
        tests the loading and parsing of the RegionManager form the json backup file
        '''
        countryManager = CountryManager.fromJSONBackup()
        self.assertTrue(hasattr(countryManager,'countries'))
        self.assertTrue(len(countryManager.countries) >= 190)
        # check if California is in the list
        countriesByWikidataId=self.checkNoDuplicateWikidataIds(countryManager)
        self.assertTrue("Q30" in countriesByWikidataId)
        
    def testCountryManagerFromWikidata(self):
        '''
        tests if the CountryManager id correctly loaded from Wikidata query result
        '''
        # wikidata query results are unreliable
        if self.inCI() or self.testWikidata:
            try:
                countryManager = CountryManager.fromWikidata()
                self.assertTrue(len(countryManager.countries) >= 190)
                countriesByWikiDataId = self.checkNoDuplicateWikidataIds(countryManager)
                self.assertTrue("Q40" in countriesByWikiDataId)
                
            except Exception as ex:
                self.handleWikidataException(ex)
                
    def test_RegionManagerFromWikidata(self):
        '''
        tests the loading of the RegionManager from wikidata query results
        '''
        # wikidata query results are unreliable
        if self.inCI() or self.testWikidata:
            try:
                regionManager = RegionManager.fromWikidata()
                # check amount of regions
                self.assertTrue(len(regionManager.regions) > 3500)
                regionsByWikiDataId = self.checkNoDuplicateWikidataIds(regionManager)
                # check if california is present
                self.assertTrue("Q99" in regionsByWikiDataId)
                ca = regionManager.getLocationByID("Q99")
                self.assertIsNotNone(ca)
                self.assertEqual(ca.name, "California")
            except Exception as ex:
                self.handleWikidataException(ex)

    def test_CityManagerFromWikidata(self):
        '''
        tests the loading of the RegionManager from wikidata query results
        '''
        # wikidata query results are unreliable
        self.testWikidata = True
        if self.inCI() or self.testWikidata:
            try:
                regions = ["Q1198"]
                cityManager = CityManager.fromWikidata(regionIDs=regions, fromBackup=False)
                # check amount of regions
                self.assertTrue(len(cityManager.cities) > 1300)
                citiesByWikiDataId = self.checkNoDuplicateWikidataIds(cityManager)
                self.assertTrue("Q1017" in citiesByWikiDataId)
                # check if NRW is present (region of Germany)
                aachen = cityManager.getLocationByID("Q1017")
                self.assertIsNotNone(aachen)
                self.assertEqual(aachen.name, "Aachen")
            except Exception as ex:
                self.handleWikidataException(ex)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
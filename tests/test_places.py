from geograpy.places import PlaceContext
from geograpy.locator import Locator
import unittest
from tests.basetest import Geograpy3Test

class TestPlaces(Geograpy3Test):
    '''
    test Places 
    '''


    def setUp(self):
        super().setUp()
        Locator.resetInstance()
        self.debug=True
        pass


    def tearDown(self):
        pass
    
    def testGetRegionNames(self):
        '''
        test getting region names
        '''
        pc=PlaceContext(place_names=["Berlin"])
        regions=pc.getRegions("Germany")
        self.assertEqual(16,len(regions))
        for region in regions:
            if self.debug:
                print(region)
            self.assertTrue(region.iso.startswith("DE"))
        regionNames=pc.get_region_names("Germany")
        self.assertEqual(16,len(regionNames))
        if self.debug:
            print(regionNames)
    
    
    def testPlaces(self):
        '''
        test places
        '''
        pc = PlaceContext(['Ngong', 'Nairobi', 'Kenya'],setAll=False)
        pc.setAll()
       
        
        if self.debug:
            print (pc)
            
        self.assertEqual(1,len(pc.countries))
        self.assertEqual("Kenya",pc.countries[0])
        self.assertEqual(2,len(pc.cities))
        cityNames=['Nairobi','Ohio','Amsterdam']
        countries=['Kenya','United States','Netherlands']
        for index,cityName in enumerate(cityNames):
            cities=pc.cities_for_name(cityName)
            country=cities[0].country
            self.assertEqual(countries[index],country.name)
    
        pc = PlaceContext(['Mumbai'])
        if self.debug:
            print(pc)


if __name__ == "__main__":
    unittest.main()

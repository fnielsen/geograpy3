'''
The locator module allows to get detailed city 
information including the region and country of a city from a 
location string.

Examples for location strings are:

    Amsterdam, Netherlands
    Vienna, Austria
    Vienna, IL
    Paris - Texas
    Paris TX
    
the locator will lookup the cities and try to disambiguate the result based on the country or region information found.

The results in string representationa are:
    
    Amsterdam (NH(North Holland) - NL(Netherlands))
    Vienna (9(Vienna) - AT(Austria))
    Vienna (IL(Illinois) - US(United States))
    Paris (TX(Texas) - US(United States)) 
    Paris (TX(Texas) - US(United States))
    
Each city returned has a city.region and city.country attribute with the details of the city.
    

Created on 2020-09-18

@author: wf
'''
import os
import urllib
import re
import csv
import pycountry
from geograpy.prefixtree import PrefixTree
from geograpy.wikidata import Wikidata
from lodstorage.sql import SQLDB
from .utils import remove_non_ascii
from geograpy import wikidata

class City(object):
    '''
    a single city as an object
    '''
    def __init__(self):
        pass
    
    def __str__(self):
        text="%s (%s - %s)" % (self.name,self.region,self.country)
        return text
    
    
    def setValue(self,name,record):
        '''
        set a field value with the given name  to
        the given record dicts corresponding entry or none
        
        Args:
            name(string): the name of the field
            record(dict): the dict to get the value from
        '''
        if name in record:
            value=record[name]
        else:
            value=None
        self.__dict__[name]=value
            
    @staticmethod
    def fromGeoLite2(record):
        city=City()
        city.name=record['name']
        city.setValue('population',record)
        city.setValue('gdp',record)
        city.region=Region.fromGeoLite2(record)
        city.country=Country.fromGeoLite2(record)
        return city
    
class Region(object):
    '''
    a Region (Subdivision)
    '''
    def __init__(self):
        pass
    
    def __str__(self):
        text="%s(%s)" % (self.iso,self.name)
        return text
    
    @staticmethod
    def fromGeoLite2(record):
        '''
        create  a region from a Geolite2 record
        
        Args:
            record(dict): the records as returned from a Query
            
        Returns:
            Region: the corresponding region information
        '''
        region=Region()
        region.name=record['regionName']
        region.iso=record['regionIsoCode'] 
        return region   
    
class Country(object):
    '''
    a country
    '''
    def __init__(self):
        pass
    
    def __str__(self):
        text="%s(%s)" % (self.iso,self.name)
        return text
    
    @staticmethod 
    def fromGeoLite2(record):
        '''
        create a country from a geolite2 record
        '''
        country=Country()
        country.name=record['countryName']
        country.iso=record['countryIsoCode']
        return country
    
    @staticmethod
    def fromPyCountry(pcountry):
        '''
        Args:
            pcountry(PyCountry): a country as gotten from pycountry
        Returns: 
            Country: the country 
        '''
        country=Country()
        country.name=pcountry.name
        country.iso=pcountry.alpha_2
        return country

class Locator(object):
    '''
    location handling
    '''
    
    # singleton instance
    locator=None
    useWikiData=False

    def __init__(self, db_file=None,correctMisspelling=False,debug=False):
        '''
        Constructor
        
        Args:
            db_file(str): the path to the database file
            correctMispelling(bool): if True correct typical misspellings
            debug(bool): if True show debug information
        '''
        self.debug=debug
        self.correctMisspelling=correctMisspelling
        self.db_path=os.path.dirname(os.path.realpath(__file__)) 
        self.db_file = db_file or self.db_path+"/locs.db"
        self.sqlDB=SQLDB(self.db_file,errorDebug=True)
        
    @staticmethod
    def resetInstance():
        Locator.locator=None    
    
    @staticmethod
    def getInstance(correctMisspelling=False,debug=False):
        '''
        get the singleton instance of the Locator. If parameters are changed on further calls
        the initial parameters will still be in effect since the original instance will be returned!
        
        Args:
            correctMispelling(bool): if True correct typical misspellings
            debug(bool): if True show debug information
        '''
        if Locator.locator is None:
            Locator.locator=Locator(correctMisspelling=correctMisspelling,debug=debug)
        return Locator.locator
        
    def locate(self,places):
        '''
        locate a city, region country combination based on the places information
        
        Args:
            places(list): a list of place tokens e.g. "Vienna, Austria"
        
        Returns:
            City: a city with country and region details
        '''
        # make sure the database is populated
        self.populate_db()
        country=None
        cities=[]
        regions=[]
        level=1
        prefix=''
        for place in places:
            isPrefix=self.isPrefix(prefix+place,level)
            isAmbigous=False
            if not isPrefix:
                prefix=''
            checkPlace=prefix+place
            if isPrefix:
                isAmbigous=self.isAmbiguousPrefix(prefix+place)
                level+=1
                prefix="%s%s " % (prefix,place)
            if not isPrefix or isAmbigous:
                foundCountry=self.getCountry(checkPlace)
                if foundCountry is not None:
                    country=foundCountry
                foundCities=self.cities_for_name(checkPlace)
                cities.extend(foundCities)
                foundRegions=self.regions_for_name(checkPlace)
                regions.extend(foundRegions)
        foundCity=self.disambiguate(country, regions, cities)
        return foundCity
    
    def isAmbiguousPrefix(self,name):
        '''
        check if the given name is an ambiguous prefix
        
        Args:
            name(string): the city name to check
            
        Returns:
            bool: True if this is a known prefix that is ambigous that is there is also a city with 
            such a name    
        '''
        query="select name from ambiguous where name=?"
        params=(name,)
        aResult=self.sqlDB.query(query,params)
        result=len(aResult)>0
        return result
    
    def isISO(self,s):
        '''
        check if the given string is an ISO code
        
        Returns:
            bool: True if the string is an ISO Code
        '''
        m=re.search(r"^[0-9A-Z]{1,3}$",s)
        result=m is not None
        return result

    def isPrefix(self,name,level):
        '''
        check if the given name is a city prefix at the given level
        
        Args:
            name(string): the city name to check
            level(int): the level on which to check (number of words)
            
        Returns:
            bool: True if this is a known prefix of multiple cities e.g. "San", "New", "Los"
        '''
        query="SELECT count from prefixes where prefix=? and level=?"
        params=(name,level)
        prefixResult=self.sqlDB.query(query,params)
        result=len(prefixResult)>0
        return result
               
    def disambiguate(self,country,regions,cities): 
        '''
        try determining country, regions and city from the potential choices
        
        Args:
            country(Country): a matching country found
            regions(list): a list of matching Regions found
            cities(list): a list of matching cities found
            
        Return:
            City: the found city or None
        '''
        if self.debug:
            print("countries: %s " % country)
            print("regions: %s" % regions)
            print("cities: %s" % cities)
        foundCity=None
        # is the city information unique?
        if len(cities)==1:
            foundCity=cities[0]
        else: 
            if len(cities)>1 and country is not None:
                for city in cities:
                    if self.debug:
                        print("city %s: " %(city))
                    if city.country.iso==country.iso:
                        foundCity=city
                        break
            if len(cities)>1 and len(regions)>0:
                for region in regions:
                    for city in cities:
                        if city.region.iso==region.iso and not city.region.name==city.name:
                            foundCity=city
                            break;
                    if foundCity is not None:
                        break
        return foundCity    
    
    def cities_for_name(self, cityName):
        '''
        find cities with the given cityName
        
        Args:
            cityName(string): the potential name of a city
        
        Returns:
            a list of city records
        '''
        cities=[]
        cityRecords=self.places_by_name(cityName, 'name')
        for cityRecord in cityRecords:
            cities.append(City.fromGeoLite2(cityRecord))
        return cities

    def regions_for_name(self, region_name):
        '''
        get the regions for the given region_name (which might be an ISO code)
        
        Args:
            region_name(string): region name
            
        Returns:
            list: the list of cities for this region
        '''
        regions=[]
        if self.isISO(region_name):
            regionRecords=self.places_by_name(region_name,'regionIsoCode')
        else:
            regionRecords=self.places_by_name(region_name, 'regionName')
        for regionRecord in regionRecords:
            regions.append(Region.fromGeoLite2(regionRecord))
        return regions                     
    
    def correct_country_misspelling(self, name):
        '''
        correct potential misspellings 
        Args:
            name(string): the name of the country potentially misspelled
        Return:
            string: correct name of unchanged
        '''
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        with open(cur_dir + "/data/ISO3166ErrorDictionary.csv") as info:
            reader = csv.reader(info)
            for row in reader:
                if name in remove_non_ascii(row[0]):
                    return row[2]
        return name

    def is_a_country(self, name):
        '''
        check if the given string name is a country
        
        Args:
            name(string): the string to check
        Returns:
            True: if pycountry thinks the string is a country
        '''
        country=self.getCountry(name)
        result=country is not None
        return result
       
    def getCountry(self,name):
        '''
        get the country for the given name    
        Args:
            name(string): the name of the country to lookup
        Returns:     
            country: the country if one was found or None if not
        '''
        if self.isISO(name):
            pcountry=pycountry.countries.get(alpha_2=name)
        else:
            if self.correctMisspelling:
                name = self.correct_country_misspelling(name)
            pcountry=pycountry.countries.get(name=name)
        country=None
        if pcountry is not None:
            country=Country.fromPyCountry(pcountry)
        return country
    
    def getView(self):
        '''
        get the view to be used
        
        Returns:
            str: the SQL view to be use for CityLookups e.g. GeoLite2CityLookup or WikidataCityLookup
        '''
        if Locator.useWikiData:
            view="WikidataCityLookup"
        else:
            view="GeoLite2CityLookup"
        return view
 
    def places_by_name(self, placeName, columnName):
        '''
        get places by name and column
        Args:
            placeName(string): the name of the place
            columnName(string): the column to look at
        '''
        if not self.db_has_data():
            self.populate_db()
        view=self.getView()
        query='SELECT * FROM %s WHERE %s = (?)' % (view,columnName)
        params=(placeName,)
        cities=self.sqlDB.query(query,params)
        return cities
    
    def getGeolite2Cities(self):
        '''
        get the Geolite2 City-Locations as a list of Dicts
        
        Returns:
            list: a list of Geolite2 City-Locator dicts
        '''
        cities=[]
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        csvfile=cur_dir + "/data/GeoLite2-City-Locations-en.csv"
        with open(csvfile) as info:
            reader = csv.DictReader(info)
            for row in reader:
                cities.append(row)
        return cities
                
    def populate_db(self,force=False):
        '''
        populate the cities SQL database which caches the information from the GeoLite2-City-Locations.csv file
        '''
        if not self.db_has_data() or force:
            self.populate_Cities(self.sqlDB)
            if Locator.useWikiData:
                self.populate_Countries(self.sqlDB)
                self.populate_Regions(self.sqlDB)
                self.populate_Cities_FromWikidata(self.sqlDB)
                viewDDLs=["DROP VIEW IF EXISTS WikidataCityLookup","""
CREATE VIEW WikidataCityLookup AS
SELECT 
  name AS name,
  regionLabel as regionName,
  regionIsoCode as regionIsoCode,
  countryLabel as countryName,
  countryIsoCode as countryIsoCode,
  cityPopulation as population,
  countryGDP_perCapita as gdp
FROM City_wikidata
"""]
#                  subdivision_1_name AS regionName,
#  subdivision_1_iso_code as regionIsoCode,
#  country_name AS countryName,
#  country_iso_code as countryIsoCode

                for viewDDL in viewDDLs:
                    self.sqlDB.execute(viewDDL)
            self.populate_PrefixTree(self.sqlDB)
            self.populate_PrefixAmbiguities(self.sqlDB)
           
    def populate_Countries(self,sqlDB):
        '''
        populate database with countries from wikiData
        '''
        print("retrieving Country data from wikidata ... (this might take a few seconds)")
        wikidata=Wikidata()
        wikidata.getCountries()
        entityInfo=sqlDB.createTable(wikidata.countryList[:100],"countries","countryIsoCode",withDrop=True)
        sqlDB.store(wikidata.countryList,entityInfo)

    def populate_Regions(self,sqlDB):
        '''
        populate database with regions from wikiData
        '''
        print("retrieving Region data from wikidata ... (this might take a minute)")
        wikidata=Wikidata()
        wikidata.getRegions()
        entityInfo=sqlDB.createTable(wikidata.regionList[:100],"regions",primaryKey=None,withDrop=True)
        sqlDB.store(wikidata.regionList,entityInfo,fixNone=True)
   
    def populate_Cities_FromWikidata(self,sqlDB):
        '''
        populate the given sqlDB with the Wikidata Cities
        
        Args:
            sqlDB(SQLDB): target SQL database
        '''
        dbFile=self.db_path+"/City_wikidata.db"
        if not os.path.exists(dbFile):
            print("Downloading %s ... this might take a few seconds" % dbFile)
            dbUrl="http://wiki.bitplan.com/images/confident/City_wikidata.db"
            urllib.request.urlretrieve(dbUrl,dbFile)
        wikiCitiesDB=SQLDB(dbFile)
        wikiCitiesDB.copyTo(sqlDB)
        
    def getWikidataCityPopulation(self,sqlDB,endpoint=None):
        '''
        Args:
            sqlDB(SQLDB): target SQL database
            endpoint(str): url of the wikidata endpoint or None if default should be used
        '''
        dbFile=self.db_path+"/city_wikidata_population.db"
        rawTableName="cityPops"
        # is the wikidata population database available?
        if not os.path.exists(dbFile):
            # shall we created it from a wikidata query?
            if endpoint is not None:
                wikidata=Wikidata()
                wikidata.endpoint=endpoint
                cityList=wikidata.getCityPopulations()
                wikiCitiesDB=SQLDB(dbFile) 
                entityInfo=wikiCitiesDB.createTable(cityList[:300],rawTableName,primaryKey=None,withDrop=True)
                wikiCitiesDB.store(cityList,entityInfo,fixNone=True)
            else:
                # just download a copy 
                print("Downloading %s ... this might take a few seconds" % dbFile)
                dbUrl="http://wiki.bitplan.com/images/confident/city_wikidata_population.db"
                urllib.request.urlretrieve(dbUrl,dbFile)
        # (re) open the database
        wikiCitiesDB=SQLDB(dbFile) 
          
        # check whether the table is populated
        tableList=sqlDB.getTableList()        
        tableName="citiesWithPopulation"     
      
        if self.db_recordCount(tableList, tableName)<10000:
            # check that database is writable
            # https://stackoverflow.com/a/44707371/1497139
            sqlDB.execute("pragma user_version=0")
            # makes sure both tables are in target sqlDB
            wikiCitiesDB.copyTo(sqlDB)
            # create joined table
            sqlQuery="""
            select c.*,city as wikidataurl,cityPop 
            from cities c 
            join cityPops cp 
            on c.geoname_id=cp.geoNameId 
            group by geoNameId
            order by cityPop desc
            """
            cityList=sqlDB.query(sqlQuery)    
            entityInfo=sqlDB.createTable(cityList[:10],tableName,primaryKey=None,withDrop=True)
            sqlDB.store(cityList,entityInfo,fixNone=True)
            # remove raw Table
            #sqlCmd="DROP TABLE %s " %rawTableName
            #sqlDB.execute(sqlCmd)
            
     
    def populate_Cities(self,sqlDB):
        '''
        populate the given sqlDB with the Geolite2 Cities
        
        Args:
            sqlDB(SQLDB): the SQL database to use
        '''
        cities=self.getGeolite2Cities()
        entityName="cities"
        primaryKey="geoname_id"
        entityInfo=sqlDB.createTable(cities[:100],entityName,primaryKey,withDrop=True)
        sqlDB.store(cities,entityInfo,executeMany=False)
        viewDDLs=["DROP VIEW IF EXISTS GeoLite2CityLookup","""
CREATE VIEW GeoLite2CityLookup AS
SELECT 
  city_name AS name,
  subdivision_1_name AS regionName,
  subdivision_1_iso_code as regionIsoCode,
  country_name AS countryName,
  country_iso_code as countryIsoCode
FROM Cities
"""]
        for viewDDL in viewDDLs:
            sqlDB.execute(viewDDL)
        
    def populate_PrefixAmbiguities(self,sqlDB):
        '''
        create a table with ambiguous prefixes
        
        Args:
            sqlDB(SQLDB): the SQL database to use
        '''
        query="""SELECT distinct name 
from %s c join prefixes p on c.name=p.prefix
order by name""" % self.getView()
        ambigousPrefixes=sqlDB.query(query)
        entityInfo=sqlDB.createTable(ambigousPrefixes, "ambiguous","name",withDrop=True)
        sqlDB.store(ambigousPrefixes,entityInfo)
        return ambigousPrefixes
        
    def populate_PrefixTree(self,sqlDB):
        '''
        calculate the PrefixTree info
        
        Args:
            sqlDb: the SQL Database to use
        
        Returns:
            PrefixTree: the prefix tree
        '''
        query="SELECT  name from %s" % self.getView()
        nameRecords=sqlDB.query(query)
        trie=PrefixTree()   
        for nameRecord in nameRecords:
            name=nameRecord['name']
            trie.add(name)
        trie.store(sqlDB)   
        return trie     
    
    def db_recordCount(self,tableList,tableName):
        '''
        count the number of records for the given tableName
        
        Args:
            tableList(list): the list of table to check
            tableName(str): the name of the table to check
            
        Returns
            int: the number of records found for the table 
        '''
        tableFound=False
        for table in tableList:
            if table['name']==tableName:
                tableFound=True
                break
        count=0
        if tableFound:    
            query="SELECT Count(*) AS count FROM %s" % tableName
            countResult=self.sqlDB.query(query)
            count=countResult[0]['count']
        return count
     
    def db_has_data(self):
        '''
        check whether the database has data / is populated
        
        Returns:
            boolean: True if the cities table exists and has more than one record
        '''
        tableList=self.sqlDB.getTableList()
        hasCities=self.db_recordCount(tableList,"cities")>10000
        ok=hasCities
        if Locator.useWikiData:
            hasCountries=self.db_recordCount(tableList,"countries")>100
            hasRegions=self.db_recordCount(tableList,"regions")>1000
            hasWikidataCities=self.db_recordCount(tableList,'City_wikidata')>100000
            ok=hasCities and hasWikidataCities and hasRegions and hasCountries
        return ok
        
        

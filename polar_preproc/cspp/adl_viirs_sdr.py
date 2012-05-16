#!/usr/bin/env python
# encoding: utf-8
"""
$Id: adl_viirs_sdr.py 8055 2012-05-13 13:54:17Z ras $

Purpose: Run the VIIRS SDR using Raytheon ADL 3.1

Input:
    One or more HDF5 VIIRS RDR input files, aggregated or single-granule.
    You need one granule before and one granule after a given granule to process.
    A work directory, typically, empty, in which to unpack the granules and generate the output.
    If the work directory specified does not exist, it will be created.
    
Output:
    ADL VIIRS SDR blob files, .asc metadata files, and HDF5 output granules will be created.

Details:
    If you input a series of granules, the software will scan the work directory.
    Thus, for N input RDR granules, you may get up to N-2 output SDR granules if they are all contiguous.
    It is ambiguous to provide several copies of the same granule in the work directory;
    this will result in an error abort.
    The unpacker gives each unpacking of a given granule its own 
    
Preconditions:
    Requires ADL_HOME, CSPP_HOME, CSPP_ANC_CACHE_DIR, CSPP_ANC_HOME  environment variables are set.
    Requires that any needed LD_LIBRARY_PATH is set.
    Requires that DSTATICDATA is set.
    

Copyright (c) 2011 University of Wisconsin Regents. 
Licensed under GNU GPLv3.
"""

import os, sys, logging, glob, traceback
import datetime as dt
import subprocess
#import repair_metadata
from subprocess import CalledProcessError, call
from subprocess import Popen, PIPE, STDOUT 
# skim and convert routines for reading .asc metadata fields of interest
from adl_asc import skim_dir, contiguous_granule_groups, granule_groups_contain, effective_anc_contains, RDR_REQUIRED_KEYS, POLARWANDER_REQUIRED_KEYS

import adl_log, adl_geo_ref
import  adl_anc_retrieval 

import xml.etree.ElementTree as ET

import site_utils # DMI utils

# maximum delay between granule end time and next granule start time to consider them contiguous
MAX_CONTIGUOUS_SDR_DELTA=dt.timedelta(seconds = 600)


# ancillary search and unpacker common routines
from adl_common import sh, anc_files_needed, link_ancillary_to_work_dir, missing_granules_check, unpack, env, ADL_HOME, CSPP_ANC_PATH, CSPP_ANC_CACHE_DIR

# every module should have a LOG object
LOG = logging.getLogger('adl_viirs_sdr')

# keys used in metadata dictionaries
K_FILENAME = '_asc_filename'


# locations of ADL executables
try:
    ADL_HOME=os.environ['ADL_HOME']
except:
    print "no ADL_HOME set, please update environment and re-try"
    sys.exit(9)
    
try:
    CSPP_HOME=os.environ['CSPP_HOME']
except:
    print "no CSPP_HOME set, please update environment and re-try"
    sys.exit(9)
 
 
 
try:
    CSPP_ANC_TILE_PATH=os.environ['CSPP_ANC_TILE_PATH']
except:
    print "no CSPP_ANC_TILE_PATH set, please update environment and re-try"
    sys.exit(9)
 

 
try:
    CSPP_ANC_CACHE_DIR=os.environ['CSPP_ANC_CACHE_DIR']
except:
    print "no CSPP_ANC_CACHE_DIR set, please update environment and re-try"
    sys.exit(9)
 
  
  
   
    
ADL_PACKER=os.path.join(ADL_HOME, 'tools', 'bin', 'ADL_Packer.exe')
GUIDE_LIST=os.path.join(ADL_HOME, 'cfg', 'ProSdrViirsDB_GuideList.cfg')

ANCILLARY_SUB_DIR="linked_data"


# locations of executables in ADL 3.1
ADL_VIIRS_SDR=os.path.join(ADL_HOME, 'bin', 'ProSdrViirsController.exe')

# directories in which we find the ancillary files
ADL_ANC_DIRS = CSPP_ANC_PATH + [os.path.join(ADL_HOME, 'data/repositories/cache')]

# and the patterns we're looking for
ADL_VIIRS_ANC_GLOBS =  (
    
#  ProSdrCmnGeo   
    '*CMNGEO-PARAM-LUT_npp*',
    '*off_Planet-Eph-ANC*',
    '*off_USNO-PolarWander*',
    '*CmnGeo-SAA-AC_npp*',
    '*Terrain-Eco-ANC-Tile*',
# RDR processing

# GEO processing
    '*S-SDR-F-LUT*',
    '*VIIRS-SDR-GEO-DNB-PARAM-LUT_npp*',
    '*VIIRS-SDR-GEO-IMG-PARAM-LUT_npp*',   
    '*VIIRS-SDR-GEO-MOD-PARAM-LUT_npp*',
    '*VIIRS-SDR-QA-LUT_npp*',
## CAL Processing

    '*VIIRS-SDR-DNB-DN0-LUT_npp*',
    '*VIIRS-SDR-DNB-RVF-LUT_npp*',
    '*VIIRS-SDR-DG-ANOMALY-DN-LIMITS-LUT_npp*',
    '*VIIRS-SDR-DNB-STRAY-LIGHT-LUT_npp*',
    '*VIIRS-SDR-DNB-FRAME-TO-ZONE-LUT_npp*',
    '*VIIRS-SDR-F-LUT_npp*',

    '*VIIRS-SDR-GAIN-LUT_npp*',
    '*VIIRS-SDR-HAM-ER-LUT*',
    '*VIIRS-SDR-RTA-ER-LUT*',
    '*VIIRS-SDR-OBC-ER-LUT_npp*',
    '*VIIRS-SDR-OBC-RR-LUT_npp*',
    '*VIIRS-SDR-EBBT-LUT_npp*',
    '*VIIRS-SDR-TELE-COEFFS-LUT_npp*',
    '*VIIRS-SDR-SOLAR-IRAD-LUT_npp*',
    '*VIIRS-SDR-RSR-LUT_npp*',
    '*VIIRS-SDR-OBS-TO-PIXELS-LUT_npp*',
    '*VIIRS-SOLAR-DIFF-VOLT-LUT_npp*',
    '*VIIRS-SDR-RADIOMETRIC-PARAM-LUT_npp*',
    '*VIIRS-SDR-QA-LUT_npp*',
    '*VIIRS-SDR-EMISSIVE-LUT_npp*',
    '*VIIRS-SDR-REFLECTIVE-LUT_npp*',
    '*VIIRS-SDR-RVF-LUT_npp*',
    '*VIIRS-SDR-BB-TEMP-COEFFS-LUT_npp*',
    '*VIIRS-SDR-DNB-C-COEFFS-LUT_npp*',
    '*VIIRS-SDR-DELTA-C-LUT_npp*',
    '*VIIRS-SDR-COEFF-A-LUT_npp*',
    '*VIIRS-SDR-COEFF-B-LUT_npp*',     
        '*TLE-AUX*'                
                    )


ADL_VIIRS_GEO_PRODUCT_SHORTNAMES = [
    'VIIRS-DNB-GEO',
    'VIIRS-IMG-GEO',
    'VIIRS-MOD-UNAGG-GEO',
    'VIIRS-IMG-GEO-TC',
    'VIIRS-DualGain-Cal-IP',
    'VIIRS-OBC-IP'
    ]

ADL_VIIRS_SDR_PRODUCT_SHORTNAMES = [

    'VIIRS-I1-SDR',
    'VIIRS-I2-SDR',
    'VIIRS-I3-SDR',
    'VIIRS-I4-SDR',
    'VIIRS-I5-SDR',
    'VIIRS-M1-SDR',
    'VIIRS-M2-SDR',
    'VIIRS-M3-SDR',
    'VIIRS-M4-SDR',
    'VIIRS-M5-SDR',
    'VIIRS-M6-SDR',
    'VIIRS-M7-SDR',
    'VIIRS-M8-SDR',
    'VIIRS-M9-SDR',
    'VIIRS-M10-SDR',
    'VIIRS-M11-SDR',
    'VIIRS-M12-SDR',
    'VIIRS-M13-SDR',
    'VIIRS-M14-SDR',
    'VIIRS-M15-SDR',
    'VIIRS-M16-SDR'
]

ADL_VIIRS_SDR_intermediate_SHORTNAMES = {
    'VIIRS-IMG-RGEO',
    'VIIRS-MOD-RGEO',
    'VIIRS-MOD-GEO',
    'VIIRS-MOD-GEO-TC',
#    'VIIRS-OBC-IP',   
    'VIIRS-DNB-SDR',
    'VIIRS-I1-FSDR',
    'VIIRS-I2-FSDR',
    'VIIRS-I3-FSDR',
    'VIIRS-I4-FSDR',
    'VIIRS-I5-FSDR',
    'VIIRS-M1-FSDR',
    'VIIRS-M2-FSDR',
    'VIIRS-M3-FSDR',
    'VIIRS-M4-FSDR',
    'VIIRS-M5-FSDR',
    'VIIRS-M6-FSDR',
    'VIIRS-M7-FSDR',
    'VIIRS-M8-FSDR',
    'VIIRS-M10-FSDR',
    'VIIRS-M12-FSDR',
    'VIIRS-M14-FSDR',
    'VIIRS-M15-FSDR',
    'VIIRS-M16-FSDR',
    'VIIRS-DNB-SDR',
    'VIIRS-MOD-RGEO',
    'VIIRS-MOD-RGEO-TC'
}


def _ldd_verify(exe):
    "check that a program is ready to run"
    rc = call(['ldd', exe], stdout=os.tmpfile(), stderr=os.tmpfile())
    return (rc==0)
    

def _check_env():
    " Check that needed environment variables are set"
    if 'DPE_SITE_ID' not in os.environ:
        LOG.warning("DPE_SITE_ID should be set in environment - see https://jpss-adl-wiki.ssec.wisc.edu/mediawiki/index.php/NPP_Product_Domains")
    if 'DPE_DOMAIN' not in os.environ:
        LOG.warning("DPE_SITE_ID should be set in environment - see https://jpss-adl-wiki.ssec.wisc.edu/mediawiki/index.php/NPP_Product_Domains")
    if 'DSTATICDATA' not in os.environ:
        LOG.warning("DSTATICDATA should be set in environment - used for IET time reference")
    if 'NPP_GRANULE_ID_BASETIME' not in os.environ:
        LOG.warning("NPP_GRANULE_ID_BASETIME should be set in environment - launch reference time")
    from adl_common import ADL_UNPACKER
    if not _ldd_verify(ADL_UNPACKER):
        LOG.warning("%r executable is unlikely to run, is LD_LIBRARY_PATH set?" % ADL_UNPACKER)
    if not _ldd_verify(ADL_VIIRS_SDR):
        LOG.warning("%r executable is unlikely to run, is LD_LIBRARY_PATH set?" % ADL_VIIRS_SDR)
  
        
# XML template for ProSdrViirsController.exe
XML_TMPL_VIIRS_SDR = """<InfTkConfig>
  <idpProcessName>ProSdrViirsController.exe</idpProcessName>
  <siSoftwareId></siSoftwareId>
  <isRestart>FALSE</isRestart>
  <useExtSiWriter>FALSE</useExtSiWriter>
  <debugLogLevel>NORMAL</debugLogLevel>
  <debugLevel>DBG_HIGH</debugLevel>
  <enablePerf>FALSE</enablePerf>
  <perfPath>/home/RH5B/perf</perfPath>
  <dbgPath>${WORK_DIR}/log</dbgPath>
  <initData>
     <domain>OPS</domain>
     <subDomain>SUBDOMAIN</subDomain>
     <startMode>INF_STARTMODE_COLD</startMode>
     <executionMode>INF_EXEMODE_PRIMARY</executionMode>
     <healthTimeoutPeriod>30</healthTimeoutPeriod>
  </initData>
  <lockinMem>FALSE</lockinMem>
  <rootDir>${WORK_DIR}/log</rootDir>
  <inputPath>${WORK_DIR}:${LINKED_ANCILLARY}:${CSPP_ANC_TILE_PATH}</inputPath>
  <outputPath>${WORK_DIR}</outputPath>
  <dataStartIET>0000000000000000</dataStartIET>
  <dataEndIET>1111111111111111</dataEndIET>
  <actualScans>48</actualScans>
  <previousActualScans>48</previousActualScans>
  <nextActualScans>48</nextActualScans> 
  <usingMetadata>TRUE</usingMetadata>
  <configGuideName>ProSdrViirsDB_GuideList.cfg</configGuideName>

  <task>
    <taskType>SDR</taskType>
    <taskDetails1>%(N_Granule_ID)s</taskDetails1>
    <taskDetails2>A1</taskDetails2>
    <taskDetails3>NPP</taskDetails3>
    <taskDetails4>VIIRS</taskDetails4>
  </task>

  <task>
    <taskType>SHUTDOWN</taskType>
    <taskDetails1></taskDetails1>
    <taskDetails2></taskDetails2>
    <taskDetails3></taskDetails3>
    <taskDetails4></taskDetails4>
  </task>
</InfTkConfig>
"""


    
def sift_metadata_for_viirs_sdr(work_dir='.'):
    """
    search through the ASC metadata in a directory,
    grouping in StartTime order
    look for back-to-back granules and break into contiguous sequences
    check that S/C diary RDRs are available for granules of interest
    yield sequence of granules we can process
    """
    LOG.info('Collecting information for S/C diary RDRs')
#    diaries = list(contiguous_granule_groups(skim_dir(work_dir, N_Collection_Short_Name='SPACECRAFT-DIARY-RDR')))
    diaries = list(contiguous_granule_groups(skim_dir(work_dir,required_keys=RDR_REQUIRED_KEYS, N_Collection_Short_Name='SPACECRAFT-DIARY-RDR')))

    LOG.debug('sifting science RDR data for processing opportunities')
    Viirs_Science_RDRs = list(skim_dir(work_dir, N_Collection_Short_Name="VIIRS-SCIENCE-RDR"))
    
    LOG.info("Total Viirs Science RDRs: "+ str(len(Viirs_Science_RDRs)))
    
    for group in contiguous_granule_groups(Viirs_Science_RDRs,MAX_CONTIGUOUS_SDR_DELTA):
        
        # for VIIRS, we can process everything but the first and last granule
        # for CrIS, use [4:-4]
        LOG.debug('contiguous granule group: %r' % (group,))
#        for gran in group[1:-1]:
        for gran in group:
            if not granule_groups_contain(diaries, gran):
                LOG.info("Insufficient S/C Diary RDR coverage to process %s @ %s (%s)" % (gran['N_Granule_ID'], gran['StartTime'], gran['URID']))
            else:
                LOG.info('Processing opportunity: %r at %s with uuid %s' % (gran['N_Granule_ID'], gran['StartTime'], gran['URID']))            
            yield gran # FIXME DEBUG this shouldnt happen if we d on't have SC diary


def generate_sdr_xml(work_dir,gran):
        LOG.info("Generate ADL controller XML for "+gran['N_Granule_ID'])
        name = gran['N_Granule_ID']
        fnxml = 'sdr_viirs_%s.xml' % name
        LOG.debug('writing XML file %r' % fnxml)
        fpxml = file(os.path.join(work_dir, fnxml), 'wt')
        fpxml.write(XML_TMPL_VIIRS_SDR % gran)
        return fnxml


# table of ADL LOG error messages and the associated hint to correcting the problem
viirs_sdr_log_check_table = [
                             ("PRO_FAIL Required input not available","Missing or out of date ancillary input"), \
                             ("PRO_FAIL runAlgorithm()","Algorithm failed"),("Completed unsuccessfully","Algorithm failed"), \
                             ("The DMS directory is not valid:","Check configuration"), \
                             ("arbitrary time is invalid","Problem with input RDR,check NPP_GRANULE_ID_BASETIME"), \
                             ("Error retrieving data for USNO-POLARWANDER-UT1","POLAR WANDER file needs update,check NPP_GRANULE_ID_BASETIME"), \
                             ("Algorithm failed","Controller did not run, check log"), \
                             ("ERROR - CMN GEO satellite position and attitude failure","Problem with S/C Diary"), \
                             ("PRO_CROSSGRAN_FAIL Required input not available for Shortname:","Prerequisite Missing")\
    ] 

# Look through new log files for completed messages
def checkADLLogForSuccess(work_dir,pid,xml, remove_list) :
    """
    Find the log file 
    Look for success
    Return True if found
    Display log message and hint if problem occurred
    """
    
    # retrieve exe name and log path from lw file
    logDir = os.path.join(work_dir,"log")
    logExpression="*"+ str ( pid )+"*.lo*"
    
    
    files = glob.glob(os.path.join(logDir, logExpression))
    
    n_err=0
    for logFile in files :
        count=0
        LOG.info( "Checking Log file " +logFile +" for errors.")
        
        count = adl_log.scan_log_file(viirs_sdr_log_check_table, logFile)
        if count == 0 :
            LOG.debug("Append:" + logFile)
            remove_list.append(logFile)
            
        n_err += count
        
    if n_err == 0 :
        LOG.info("Processing of file: "+ xml + " Completed successfully" )

#        LOG.info("Log file: "+logFile)
        return True
    else :
        LOG.error("Processing of file: "+ xml + " Completed unsuccessfully" )
        LOG.error("Log file: "+logFile)

        return False

def is_granule_on_list(work_dir, wanted, found_granule_seq):
    """verify that granules matching an incoming sequence and specification were created
    returns sequence of granules that need to be converted
    example: blob_products_to_h5(work_dir, my_source_granules, adl_asc.skim_dir(work_dir, N_Collection_Short_Name='ATMS-SDR'))
    """
    found = dict((g['N_Granule_ID'],g) for g in found_granule_seq)

    name = wanted['N_Granule_ID']
             
    if name in found:
        LOG.debug('found granule for %s' % name)
        it=found.get(name)
        try :
            return it
        except KeyError: 
            LOG.error("No blob file for "+name)

    return None

CHECK_REQUIRED_KEYS = ['N_Granule_ID', 'N_Collection_Short_Name']

def check_for_products(work_dir, gran, remove_list) :
    """ Checks that proper products were produced.
    If product h5 file was produced blob and asc files are deleted
    If product was not produced files are left alone
    
    DMI, collect and return a set of product time stamps.
    """
    # look for all products that should have been produced
    # convert the products to H5
    
    LOG.info("Granule: "+gran['N_Granule_ID']+" complete, Check that all products were produced.")

    gran_id=gran['N_Granule_ID']
    problem=True
    product_times = set()
    for short_name in  sorted (ADL_VIIRS_SDR_PRODUCT_SHORTNAMES) + \
            sorted(ADL_VIIRS_GEO_PRODUCT_SHORTNAMES):

        # must require granule id but I do not know it is used.  
        gran_list = list(skim_dir(work_dir,
                                  required_keys=CHECK_REQUIRED_KEYS,
                                  N_Collection_Short_Name=short_name,
                                  N_Granule_ID=gran_id))
        
        if len(gran_list) < 1 :
            try :
                LOG.error("Problem : "+short_name+" No product produced.")
                SHORTNAME_2_PRODUCTID[short_name]
                problem = True
            except KeyError:
                LOG.info("Short name not in product map:" + short_name)
        else :
            for it in  gran_list :
                LOG.debug( it )         

                sdr_name=SHORTNAME_2_PRODUCTID[short_name]
                dObj=it['ObservedStartTime']
                time_id_str  = dObj.strftime("_npp_d%Y%m%d_t%H%M%S")
         
                #  Name Example: SVI04_npp_d20111121_t1805421_e1807062_b00346_c20120127203200212753_cspp_dev.h5
                sdr_name=sdr_name+time_id_str+"*.h5"  
                files = glob.glob(os.path.join(work_dir, sdr_name))
                if  len( files ) == 1 :
                    fullname= files[0]
                    product_times.add(dObj)
                    LOG.info("Product: "+fullname+" produced.")
                    problem = False;
                    " Night passes do not create a blob file for all asc files." 
                    ascname="noproperty"
                    blobname="noproperty"
                                
                    try :
                        blobname=it['BlobPath']   
                    except KeyError:  
                        LOG.debug("Key error on blob property")
                                    
                    try :
                        ascname=it['_filename']
                    except KeyError:  
                        LOG.debug("Key error on asc property")
                        LOG.debug("Blob: "+blobname )
                        b=blobname.split( ".")    
                        ascname=b[0]+".asc";
                                       
                    if  os.path.exists(ascname) :
                        LOG.debug("Append:" + ascname)
                        remove_list.append( ascname )
                                    
                    if  os.path.exists(blobname) :
                        LOG.debug("Append:" + blobname)
                        remove_list.append( blobname )
                else :
                    LOG.error("H5 output: "+sdr_name+ " is missing")
                    a_exists=False;
                    b_exists=False;
                    if '_filename' in it.keys() :
                        ascname=it['_filename']
                        a_exists=os.path.exists(ascname)
                    if 'BlobPath' in it.keys() :		
                        blobname=it['BlobPath']
                        b_exists=os.path.exists(blobname)
                    LOG.error("Exists? "+a_exists+" "+ascname)
                    LOG.error("Exists? "+b_exists+" "+blobname) 
#                        LOG.info( it )
                                          
#                except KeyError:
#                            LOG.info("H5 not produced for Short name:" + short_name+" "+sdr_name)
#                    LOG.info( it )

                
            
    return problem, list(product_times)


def run_xml_file(work_dir, xml_file, remove_list, setup_only=False):
    "run each VIIRS SDR XML input in sequence"
    error_files=[]
    ran_ok=False
    cmd = [ADL_VIIRS_SDR, xml_file]
    if setup_only:
        print ' '.join(cmd)
    else:
        LOG.info('Executing %r with WORK_DIR=%r' % (cmd, work_dir))
        try:
                #pid = sh(cmd, env=env(WORK_DIR=work_dir), cwd=work_dir)
                
            pid = sh(cmd, env=env(WORK_DIR=work_dir, LINKED_ANCILLARY=ANCILLARY_SUB_DIR), cwd=work_dir)
            LOG.debug("%r ran as pid %d" % (cmd, pid))
            ran_ok=checkADLLogForSuccess(work_dir,pid,xml_file, remove_list)
                
                # FUTURE: check log files created for this PID
        except CalledProcessError as oops:
            LOG.debug(traceback.format_exc())
            LOG.error('ProSdrViirsController.exe failed on %r: %r. Continuing...' % (xml_file, oops))
            error_files.append(xml_file)
    if error_files:
        LOG.warning('Had problems running these XML files: %r' % (error_files,))
    return ran_ok


    

# table of NPP short names to data product ids
DDS_PRODUCT_FILE = os.path.join(ADL_HOME,"cfg","DDS_PRODUCT_IDS.xml")
PRODUCTID_2_SHORTNAME= dict()
SHORTNAME_2_PRODUCTID = dict()
  
    
def build_product_name_maps():
    """ Read ADL short name to product map
    and create dictionaries for name convertion
    """ 
    tree= ET.parse(DDS_PRODUCT_FILE)
    p = tree.find("group/group") 
    
    links = list(p.iter("config"))   # Returns list of all links

    for i in links:
        productid=i.find('configValue').text
        shortname=i.find('name').text
        
        PRODUCTID_2_SHORTNAME[productid] = shortname
        SHORTNAME_2_PRODUCTID[shortname]= productid
#        LOG.info("Short: "+shortname+" Prod: "+productid)

def get_created_blobs_list(work_dir, wanted, found_granule_seq):
    """verify that granules matching an incoming sequence and specification were created
    returns sequence of granules that need to be converted
    example: blob_products_to_h5(work_dir, my_source_granules, adl_asc.skim_dir(work_dir, N_Collection_Short_Name='ATMS-SDR'))
    """
    found = dict((g['N_Granule_ID'],g) for g in found_granule_seq)

    name = wanted['N_Granule_ID']
             
    if name in found:
        LOG.debug('found granule for %s' % name)
        it=found.get(name)
        try :
            pa = it['BlobPath']
            yield it
        except KeyError: 
            LOG.debug("No blob file for "+name)

    else:
            LOG.debug('no product for granule %s' % name)
  
     
def add_geo_attribute_to_h5(work_dir, gran) :
    """ For all the geo files produced
    add the the N_GEO_Ref property
    """

    # Do this for all inputs
   
#    LOG.info( gran )

    # Every VIIRS SDR must have GEO location property added
    for short_name in sorted ( ADL_VIIRS_SDR_PRODUCT_SHORTNAMES ):
        LOG.debug("short name: "+ short_name +  " productId " + SHORTNAME_2_PRODUCTID[short_name] )

        #  need to use short name to build h5 file
        # for the give granules get asc files that have been produced
        created_products = list(get_created_blobs_list(work_dir, gran, 
                                                       skim_dir(work_dir, N_Collection_Short_Name=short_name)))
        
        for ascDics in created_products:
            # use the Observer start time of the data with the short name to create npp product file name
            dObj=ascDics['ObservedStartTime']
            time_id_str  = dObj.strftime("_npp_d%Y%m%d_t%H%M%S")
            #  Name Example: SVI04_npp_d20111121_t1805421_e1807062_b00346_c20120127203200212753_cspp_dev.h5
        
            try : 
                SDR_name=SHORTNAME_2_PRODUCTID[short_name]+time_id_str+"*.h5"
                # fine the file on disk, get the full name and path
                files = glob.glob(os.path.join(work_dir, SDR_name))
                # update the GEO property
                for afile in files:
                    adl_geo_ref.write_geo_ref(afile)
                    for filename in glob.glob(os.path.join(work_dir, SDR_name)):
                        # update the GEO property
                        LOG.info("Add N_GEO_Ref property to: "+ filename)
                        adl_geo_ref.write_geo_ref(filename)
            except KeyError:
                LOG.eoor("No: "+short_name)
 
def check_for_intemidiate(work_dir, gran, remove_list) :
    """ Checks that proper products were produced.
    If product h5 file was produced blob and asc files are deleted
    If product was not produced files are left alone
    """
       # look for all products that should have been produced
    # convert the products to H5
    
    LOG.info("Granule: "+gran['N_Granule_ID']+" Clean up intermediate products")

    gran_id=gran['N_Granule_ID']
    problem=True
    for short_name in  sorted ( ADL_VIIRS_SDR_intermediate_SHORTNAMES)  :
# must require granule id but I do not know it is used.  
        gran_list = list(skim_dir(work_dir,required_keys=CHECK_REQUIRED_KEYS,N_Collection_Short_Name=short_name,N_Granule_ID=gran_id))
        for it in  gran_list : 
                " Night passes do not create a blob file for all asc files." 
                ascname="noproperty"
                blobname="noproperty"
                        
                try :
                        blobname=it['BlobPath']   
                except KeyError:  
                        LOG.debug("Key error on blob property")

                try :
                        ascname=it['_filename']
                except KeyError:  
                        LOG.debug("Key error on asc property")
                        LOG.debug("Blob: "+blobname )
                        b=blobname.split( ".")    
                        ascname=b[0]+".asc";


                               
                if  os.path.exists(ascname) :
                    LOG.debug("Append:" + ascname)
                    remove_list.append( ascname )
                            
                if  os.path.exists(blobname) :
                    LOG.debug("Append:" + blobname)
                    remove_list.append( blobname )
            
    return problem


def cleanup_intermediate_products(work_dir, remove_list) :
    LOG.info("Clean up intermediate products")
    for short_name in ADL_VIIRS_SDR_intermediate_SHORTNAMES:
        pattern="*"+short_name
        for blobname in glob.glob(os.path.join(work_dir, pattern)):
            LOG.debug("Blob: "+blobname )
            b=blobname.split( ".")    
            ref=b[0]+".asc";
            LOG.debug("Append:" + ref)
            remove_list.append(blobname);
            remove_list.append(ref);
            LOG.debug("Append:" + blobname)


def remove_inputs(work_dir) :
    viirs_inputs = "VIIRS-SCIENCE-RDR,SPACECRAFT-DIARY-RDR" 
    for input_name in viirs_inputs:
        pattern="*"+input_name
        for fn in glob.glob(os.path.join(work_dir, pattern)):
            b=fn.split( ".")            
            blob_id=b[0]+".asc"; 
            if os.path.exists(blob_id) :          
                os.remove(blob_id)
            if os.path.exists(fn ) :
                os.remove(fn)
    
def setup_directories(work_dir,anc_dir):
    # create work directory
    
    "Create the working directory and a subdirectory for the logs"
    log_dir = os.path.join(work_dir, 'log')
    
    if not os.path.isdir(work_dir):
        LOG.info('creating directory %s' % work_dir)
        os.makedirs(work_dir)
        
    log_dir = os.path.join(work_dir, 'log')
    if not os.path.isdir(log_dir):
        LOG.info('creating log directory %s' % log_dir)
        os.makedirs(log_dir)
        

    if not os.path.exists( anc_dir ) :
        os.mkdir(anc_dir)

        
    
def unpack_inputs(work_dir, h5_names) :
    problematic = False
    ## unpack HDF5 RDRs to work directory
    for fn in h5_names:
        try:
            unpack(work_dir, fn)
        except CalledProcessError as oops:
            LOG.debug(traceback.format_exc())
            LOG.error('ADL_Unpacker failed on %r: %r . Continuing' % (fn, oops))
            problematic = True   # My food is problematic.
    return problematic

def find_granules_and_build_xml(work_dir):
    # read through ascii metadata and build up information table
    LOG.info('sifting through metadata to find VIIRS SDR processing candidates')
    
    granules_to_process=[]
    for gran in sift_metadata_for_viirs_sdr(work_dir) :
        granules_to_process.append( gran )
    
    
#    granules_to_process = list(sift_metadata_for_viirs_sdr(work_dir))
     
    LOG.debug(', '.join(x['N_Granule_ID'] for x in granules_to_process))
    if not granules_to_process:
        LOG.error("Found no granules to process!")
        return 5
    else :
        LOG.info("Found %d granules to process.",len(granules_to_process))
    
    return granules_to_process
       

def stage_the_ancillary_data() :
    """
    Stage all the ancillary data needed for the granules
    """
                 

def viirs_sdr(work_dir, h5_names, setup_only=False, out_dir='.', signal=''):
    "process VIIRS RDR data in HDF5 format (any aggregation) to SDRs in an arbitrary work directory"

    problematic = False 
    
    anc_dir=os.path.join(work_dir,ANCILLARY_SUB_DIR)
     
    "Create the working directory and a subdirectory for the logs" 
    setup_directories(work_dir, anc_dir)
    
    LOG.info("Unpack the supplied inputs")
    problematic =  unpack_inputs(work_dir, h5_names) 
     
    LOG.info("Search through the inputs for legal granule combinations")
    granules_to_process = find_granules_and_build_xml(work_dir)
    try:
        len(granules_to_process)
    except TypeError:
        return 5
    
    # used to create H5 file names
    build_product_name_maps()
  
    ####   EVALUATE AND RETRIEVE ANCILLARY DATA ##################
    LOG.info("Link the required ancillary data into the workspace")
        
    search_dirs = [CSPP_ANC_CACHE_DIR if CSPP_ANC_CACHE_DIR is not None else anc_dir] + ADL_ANC_DIRS
    problems_detected=0
    problem=False
    try:
       
        # get list of dynamic ancillary files.  Servicing may pull files from remote server.
        dynamic_ancillary_file_list = adl_anc_retrieval.service_remote_ancillary(work_dir,granules_to_process,adl_anc_retrieval.kPOLAR)
       
        dynamic_ancillary_file_list2 = adl_anc_retrieval.service_remote_ancillary(work_dir,granules_to_process,adl_anc_retrieval.kTLE)
        for src_path in dynamic_ancillary_file_list2:
           dynamic_ancillary_file_list.append( src_path )
        
        
        # get the static ancillary files needed
        ancillary_files_neeeded=anc_files_needed(ADL_VIIRS_ANC_GLOBS, search_dirs, granules_to_process)
        
        # create list of all ancillary needed
        for src_path in ancillary_files_neeeded:
           dynamic_ancillary_file_list.append( src_path )
        
        # link all the ancillary files to the ancillary directory.
        link_ancillary_to_work_dir(anc_dir, dynamic_ancillary_file_list)
        
        ##########  RUN THE VIIRS SDR  ##################3
        files_to_remove=[]
        file_that_will_be_removed  = []

   
        
        for gran in granules_to_process:
            " For VIIRS files from previous granule need to stay around for next"
            " However we can remove then after they have been used to reduce parse time"
            " For ADL and error checking"
            LOG.info("")
            
            for file in files_to_remove:
                LOG.debug("Remove: "+ file)
                if os.path.exists(file) :
                	os.remove(file)
                else :
                    LOG.debug("Unable to remove:"+file)
                
           
            files_to_remove = file_that_will_be_removed
            file_that_will_be_removed = []
            
            LOG.debug("Process: " + str(gran))
            viirs_sdr_xml = generate_sdr_xml(work_dir,gran)
            
            ran_ok = run_xml_file(work_dir, viirs_sdr_xml,
                                  file_that_will_be_removed,
                                  setup_only=setup_only)
            if ran_ok == False :
                LOG.info("Log indicates some problems.")
                

            LOG.debug("Checking that output granule blobs exist for granule: "+ gran['N_Granule_ID'])
            ################   Check For Products/ Errors  #####################3
            problem, product_times = check_for_products(work_dir, gran, file_that_will_be_removed)
            ###############   PATCH THE OUTPUTS ####################3  
                     
            add_geo_attribute_to_h5(work_dir, gran)     
    
            if problem == False :
                check_for_intemidiate(work_dir,gran,file_that_will_be_removed)
                os.remove(viirs_sdr_xml)
                
            if ran_ok == False or problem == True  :   
                LOG.info("Run problem with: "+ gran['N_Granule_ID'])
                " Do not clean up files "
                file_that_will_be_removed=[]
                problems_detected+=1
                    
            ################   Notify  #####################3
            # DMI, signal
            site_utils.notify(work_dir, product_times, out_dir=out_dir, signal=signal)
                    
        for file in files_to_remove + file_that_will_be_removed:      
            if os.path.exists(file) :
                LOG.debug( "Remove: " + file )
                os.remove( file )
            else :
                LOG.debug("Unable to remove:"+file)


        if problem or problematic or (problems_detected>0) : 
            LOG.warning("Done, but problems occurred. Review logs."+str(problem)+" "+str(problematic))
            return 5
        
        if problem == False :
            remove_inputs(work_dir)
        
    except EnvironmentError:
        LOG.warning("Environment Error, Done, but problems occurred. Review logs.")
        return 5
    if problem == False and (problems_detected == 0):
        LOG.info("Done; no problems detected.")
    return 0  

def _test_anc_names():
    "list ancillary files that would be processed"
    from pprint import pprint
    print "ancillary files:"
    pprint(list(anc_files_needed(ADL_VIIRS_ANC_GLOBS, ADL_ANC_DIRS, [])))


def _test_sdr_granules(work_dir):
    "list granules we'd generate XML for"
    granules_to_process = list(sift_metadata_for_viirs_sdr(work_dir))
    from pprint import pprint
    pprint([x['N_Granule_ID'] for x in granules_to_process])
    return granules_to_process


def main():
    """ Run Viirs SDR proccessing
    """   
    

    import argparse
    desc = """Build VIIRS SDR ProSdrViirsDBController work directory and run VIIRS SDR."""
    parser = argparse.ArgumentParser(description = desc)
    parser.add_argument('-t', '--test',
                    action="store_true", default=False, help="run self-tests")  
    parser.add_argument('-W', '--work-dir', metavar='work_dir', default='.',
                    help='work directory which all activity will occur in, defaults to current dir')
    parser.add_argument('-O', '--out-dir', metavar='out_dir', default=None,
                    help='out directory where final h5 files will be moved to')
    parser.add_argument('-S', '--signal', metavar='signal', default='',
                    help='signal option')
    parser.add_argument('-v', '--verbosity', action="count", default=0,
                    help='each occurrence increases verbosity 1 level through ERROR-WARNING-INFO-DEBUG')
    parser.add_argument('filenames', metavar='filename', type=str, nargs='+',
                   help='HDF5 VIIRS RDR file/s to process')

    args = parser.parse_args()

    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level = levels[args.verbosity if args.verbosity<4 else 3])

    work_dir = os.path.abspath(args.work_dir)
    out_dir = os.path.abspath(args.out_dir or work_dir)
    signal = args.signal

    LOG.info('CSPP execution work directory is %r' % work_dir)
    LOG.info('Final H5 files will be moved to %r' % out_dir)
    LOG.info('Signal option is %r' % signal)

    if args.test:
        _check_env()
 #       _test_anc_names()
        grans = _test_sdr_granules(work_dir)
        if grans:
            LOG.debug('building XML files')
   
        sys.exit(2)

    if not args: 
        parser.print_help()
        return 9

    _check_env()
    return viirs_sdr(work_dir, args.filenames, out_dir=out_dir, signal=signal)

if __name__=='__main__':
    sys.exit(main())
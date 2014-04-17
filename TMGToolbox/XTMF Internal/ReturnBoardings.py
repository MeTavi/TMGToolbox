#---LICENSE----------------------
'''
    Copyright 2014 Travel Modelling Group, Department of Civil Engineering, University of Toronto

    This file is part of the TMG Toolbox.

    The TMG Toolbox is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    The TMG Toolbox is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with the TMG Toolbox.  If not, see <http://www.gnu.org/licenses/>.
'''
#---METADATA---------------------
'''
Returb Boardings

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Returns a 'serialized' (e.g. string repr) of transit line boardings to XTMF.
    See XTMF for documentation.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-02-05 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from json import loads
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ReturnBoardings(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters necessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get initialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    xtmf_LineAggregationFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker

        
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Return Boardings",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
            
    def __call__(self, xtmf_ScenarioNumber, xtmf_LineAggregationFile):
        
        _m.logbook_write("Extracting boarding results")
        
        #---1 Set up scenario
        scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        if not scenario.has_transit_results:
            raise Exception("Scenario %s does not have transit assignment results" %xtmf_ScenarioNumber)              
        
        self.xtmf_LineAggregationFile = xtmf_LineAggregationFile
        
        try:
            return self._Execute(scenario)
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    def _Execute(self, scenario):
        lineAggregation = self._LoadLineAggregationFile()
        print "Loaded line aggregation file."
        
        network = scenario.get_network()
        print "Loaded network"
        
        self._CheckAggregationFile(network, lineAggregation)
        print "Aggregation file checked."
        
        results = {}
        self.TRACKER.startProcess(network.element_totals['transit_segments'])
        for segment in network.transit_segments():
            if segment.link == None: continue #Skip hidden segments
            
            lineId = segment.line.id
            if not lineId in lineAggregation: continue #Skip unmapped lines
            lineGroupId = lineAggregation[lineId]
            
            if lineGroupId in results:
                results[lineGroupId] += segment.transit_boardings
            else:
                results[lineGroupId] = segment.transit_boardings
        self.TRACKER.completeTask()
        print "Done extracting results in Python."
        return str(results)            
    
    def _LoadLineAggregationFile(self):
        mapping = {}
        with open(self.xtmf_LineAggregationFile) as reader:
            reader.readline()
            for line in reader:
                cells = line.strip().split(',')
                key = cells[0].strip()
                val = cells[1].strip()
                mapping[key] = val
        return mapping
    
    def _CheckAggregationFile(self, network, lineAggregation):
        netSet = set([line.id for line in network.transit_lines()])
        aggSet = set([key for key in lineAggregation.iterkeys()])
        
        linesInNetworkButNotMapped = [id for id in (netSet - aggSet)]
        linesMappedButNotInNetwork = [id for id in (aggSet - netSet)]
        
        if len(linesMappedButNotInNetwork) > 0:
            msg = "%s lines have been found in the network without a line grouping: " %len(linesInNetworkButNotMapped)
            msg += ",".join(linesInNetworkButNotMapped[:10])
            if len(linesInNetworkButNotMapped) > 10:
                msg += "...(%s more)" %(len(linesInNetworkButNotMapped) - 10)
            print msg
            
        if len(linesMappedButNotInNetwork) > 0:
            msg = "%s lines have been found in the aggregation file but do not exist in the network: " %len(linesMappedButNotInNetwork)
            msg += ",".join(linesMappedButNotInNetwork[:10])
            if len(linesMappedButNotInNetwork) > 10:
                msg += "...(%s more)" %(len(linesMappedButNotInNetwork) - 10)
            print msg
    
    ##########################################################################################################


    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        
'''
    Copyright 2015-2017 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Toll-Based Road Assignment

    Authors: David King, Eric Miller

    Latest revision by: dKingII
    
    Executes a multi-class road assignment which allows for the generalized penalty of road tolls.
    
    V 1.0.0

    V 1.1.0 Added link volume attributes for increased resolution of analysis.

    V 1.1.1 Updated to allow for multi-threaded matrix calcs in 4.2.1+
        
'''

import inro.modeller as _m
import traceback as _traceback
import multiprocessing
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
EMME_VERSION = _util.getEmmeVersion(tuple)

##########################################################################################################

@contextmanager
def blankManager(obj):
    try:
        yield obj
    finally:
        pass

class MultiClassRoadAssignment(_m.Tool()):
    
    version = '1.1.1'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    #---Variable definitions
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
        
    #DemandMatrix = _m.Attribute(_m.InstanceType) #remove?
        
    LinkTollAttributeId = _m.Attribute(str)
    
    TimesMatrixId = _m.Attribute(str)
    CostMatrixId = _m.Attribute(str)
    TollsMatrixId = _m.Attribute(str)
    RunTitle = _m.Attribute(str)
    
    
    Mode_List = _m.Attribute(str) #Must be passed as a string, with modes comma separated (e.g. 'a,b,c') cov => ['a','b','c']
    xtmf_Demand_String = _m.Attribute(str)#Must be passed as a string, with demand matricies comma separated (e.g. 'a,b,c') cov => ['a','b','c']
    Demand_List = _m.Attribute(str) #The Demand Matrix List
    
    PeakHourFactor = _m.Attribute(float)
    LinkCost = _m.Attribute(str)
    TollWeight = _m.Attribute(str)
    Iterations = _m.Attribute(int)
    rGap = _m.Attribute(float)
    brGap = _m.Attribute(float)
    normGap = _m.Attribute(float)
    
    PerformanceFlag = _m.Attribute(bool)
    SOLAFlag = _m.Attribute(bool)
    xtmf_NameString = _m.Attribute(str)
    ResultAttributes = _m.Attribute(str)
    xtmf_AggAttributes = _m.Attribute(str)
    xtmf_aggAttributesMatrixId = _m.Attribute(str)
    aggAttributes = _m.Attribute(str)
    aggAttributesMatrixId = _m.Attribute(str)
    aggAttributesClass = _m.Attribute(str)
    aggAttributesClassMatrix = _m.Attribute(str)

    NumberOfProcessors = _m.Attribute(int)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        
        self.Scenario = _MODELLER.scenario
        
        #Old Demand Matrix Definition
        #mf10 = _MODELLER.emmebank.matrix('mf10')
        #if mf10 != None:
            #self.DemandMatrix = mf10
        
        self.PeakHourFactor = 0.43
        self.LinkCost = 0
        self.TollWeight = 0
        self.Iterations = 100
        self.rGap = 0
        self.brGap = 0.1
        self.normGap = 0.05
        self.PerformanceFlag = False
        self.RunTitle = ""
        self.LinkTollAttributeId = "@toll"

        self.NumberOfProcessors = multiprocessing.cpu_count()
        
             
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Multi-Class Road Assignment",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
             
    def __call__(self, xtmf_ScenarioNumber, Mode_List, xtmf_Demand_String, TimesMatrixId,
                 CostMatrixId, TollsMatrixId, PeakHourFactor, LinkCost,
                 TollWeight, Iterations, rGap, brGap, normGap, PerformanceFlag,
                 RunTitle, LinkTollAttributeId, xtmf_NameString, ResultAttributes, xtmf_AggAttributes, xtmf_aggAttributesMatrixId):
        #---1 Set up Scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        #:List will be passed as follows: xtmf_Demand_String = "mf10,mf11,mf12", Will be parsed into a list
         
        self.Demand_List = xtmf_Demand_String.split(",")
        
        #Splitting the Time, Cost and Toll string into Lists, and Modes for denoting results
        self.ResultAttributes = ResultAttributes
        self.TimesMatrixId = TimesMatrixId.split(",")
        self.CostMatrixId = CostMatrixId.split(",")
        self.TollsMatrixId = TollsMatrixId.split(",")
        self.Mode_List_Split = Mode_List.split(",")
        self.ClassNames = [x for x in xtmf_NameString.split(",")]
        self.TollWeight = [float (x) for x in TollWeight.split(",")]
        self.LinkCost = [float(x) for x in LinkCost.split(",")]
        self.LinkTollAttributeId = [x for x in LinkTollAttributeId.split(",")]
        self.aggAttributes = [x for x in xtmf_AggAttributes.split("|")]
        self.aggAttributesMatrixId = [x for x in xtmf_aggAttributesMatrixId.split("|")]
        self.aggAttributesClass = []
        self.aggAttributesClassMatrix = []
        for i in range(len(self.Mode_List_Split)):
            self.aggAttributesClass.append([x for x in self.aggAttributes[i].split(",")])
            self.aggAttributesClassMatrix.append([x for x in self.aggAttributesMatrixId[i].split(",")])
            for j in range(len(self.aggAttributesClass[i])):
                if self.aggAttributesClass[i][j] == '':
                    self.aggAttributesClass[i][j] = None #make the blank attributes None for better use in spec
                if self.aggAttributesClassMatrix[i][j] == 'mf0' or self.aggAttributesClassMatrix[i][j] == '':
                    self.aggAttributesClassMatrix[i][j] = None # make mf0 matrices None for better use in spec
        self.DemandMatrixList = []
        for demandMatrix in self.Demand_List:
            if _MODELLER.emmebank.matrix(demandMatrix) == None:
                raise Exception('Matrix %s was not found!' % demandMatrix)
            else:
                self.DemandMatrixList.append(_MODELLER.emmebank.matrix(demandMatrix))
        
        #---2. Pass in remaining args
        self.PeakHourFactor = PeakHourFactor
        self.Iterations = Iterations
        self.rGap = rGap
        self.brGap = brGap
        self.normGap = normGap      
        self.RunTitle = RunTitle[:25]

        #---3. Run
        try:          
                print "Starting assignment."
                self._execute()
                print "Assignment complete."  
        except Exception, e:
            raise Exception(_util.formatReverseStack())
    
    ##########################################################################################################    
    
    
    def _execute(self):
        
        with _m.logbook_trace(name="%s (%s v%s)" %(self.RunTitle, self.__class__.__name__, self.version),
                                     attributes=self._getAtts()):
            
            self._tracker.reset()            
           
            matrixCalcTool = _MODELLER.tool("inro.emme.matrix_calculation.matrix_calculator")
            networkCalculationTool = _MODELLER.tool("inro.emme.network_calculation.network_calculator")                
            trafficAssignmentTool = _MODELLER.tool('inro.emme.traffic_assignment.sola_traffic_assignment')
               
            
            self._tracker.startProcess(5)
            
            self._initOutputMatrices(self.Mode_List_Split)
            self._tracker.completeSubtask()
            
            
            with nested(self._costAttributeMANAGER(), self._transitTrafficAttributeMANAGER(), self._timeAttributeMANAGER()) \
                     as (costAttribute, bgTransitAttribute, timeAttribute): #bgTransitAttribute is None          
               
           
                #Adding @ for the process of generating link cost attributes and declaring list variables
                
                def get_attribute_name(at):
                    if at.startswith("@"):
                        return at
                    else:
                        return "@" + at

                Mode_List_for_attributes = [ get_attribute_name(at)
                                             for at in self.ResultAttributes.split(',')]
                
                for name in Mode_List_for_attributes:
                    if name == "@None":
                        name = None
                        continue
                    if self.Scenario.extra_attribute(name) is not None:
                        _m.logbook_write("Deleting Previous Extra Attributes.")
                        self.Scenario.delete_extra_attribute(name)
                    _m.logbook_write("Creating link cost attribute '@(mode)'.")
                    self.Scenario.create_extra_attribute('LINK',name, default_value=0)
                    
                
                with nested (*(_util.tempMatrixMANAGER(description="Peak hour matrix") \
                               for Demand in self.Demand_List)) as peakHourMatrix:                
                                         
                        with _m.logbook_trace("Calculating transit background traffic"): #Do Once
                            networkCalculationTool(self._getTransitBGSpec(), scenario=self.Scenario)
                            self._tracker.completeSubtask()
                            
                        with _m.logbook_trace("Calculating link costs"): #Do for each class
                            for i in range(len(self.Mode_List_Split)):
                                networkCalculationTool(self._getLinkCostCalcSpec(costAttribute[i].id, self.LinkCost[i], self.LinkTollAttributeId[i]), scenario=self.Scenario)
                                self._tracker.completeSubtask()
                        
                          
                        with _m.logbook_trace("Calculating peak hour matrix"):  #For each class
                            for i in range(len(self.Demand_List)):
                                if EMME_VERSION >= (4,2,1):
                                    matrixCalcTool(self._getPeakHourSpec(peakHourMatrix[i].id, self.Demand_List[i]), 
                                                   num_processors=self.NumberOfProcessors)
                                else:
                                    matrixCalcTool(self._getPeakHourSpec(peakHourMatrix[i].id, self.Demand_List[i].id))                        
                            self._tracker.completeSubtask()
                            
                        
                        appliedTollFactor = self._calculateAppliedTollFactor()
                        self._tracker.completeTask()
                        
                        with _m.logbook_trace("Running Road Assignments."):
                            y = 0 # init assignment flag. if assignment done, then trip flag
                            x = 0 # init flag. if list has something defined, then trip flag
                            for i in range(len(self.CostMatrixId)): #check to see if any cost matrices defined
                                if self.CostMatrixId[i] != None:
                                    x = 1
                            if x == 1: # if something, then do the assignment
                                #get cost matrix
                                attribute = []
                                for i in range(len(costAttribute)):
                                    attribute.append(costAttribute[i].id)                                           
                                spec = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.Mode_List_Split,\
                                                            Mode_List_for_attributes, costAttribute, attribute, self.CostMatrixId)
                                report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                                y = 1
                            x = 0
                            for i in range(len(self.TollsMatrixId)): #check to see if any toll matrices defined
                                if self.TollsMatrixId[i] != None:
                                    x = 1
                            if x == 1: # if something, then do the assignment
                                # get tolls matrix
                                spec = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.Mode_List_Split,\
                                                            Mode_List_for_attributes, costAttribute, self.LinkTollAttributeId, self.TollsMatrixId)
                                report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                                y = 1
                            x = 0
                            for i in range(len(self.aggAttributesClass)): # check to see if any aggregation attributes defined
                                for j in range(len(self.aggAttributesClass[i])):
                                    if self.aggAttributesClass[i][j] != None:
                                        x = 1
                            if x == 1: # if something is defined, then do the assignment
                                # get the max number of aggregation attributes for all the classes
                                max = 0
                                for i in range(len(self.aggAttributesClass)): 
                                    if (len(self.aggAttributesClass[i])) > max:
                                        max = len(self.aggAttributesClass[i])
                                attributes = []
                                matrices = []
                                for i in range(max):
                                    attributes.append([])
                                    matrices.append([])
                                    for j in range(len(self.aggAttributesClass)):
                                        if (len(self.aggAttributesClass[j]) > i):
                                            attributes[i].append(self.aggAttributesClass[j][i])
                                            matrices[i].append(self.aggAttributesClassMatrix[j][i])
                                        else:
                                            attributes[i].append(None)
                                            matrices[i].append(None)
                                for i in range(len(attributes)):
                                    specAttribute = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.Mode_List_Split,\
                                                                 Mode_List_for_attributes, costAttribute, attributes[i], matrices[i])
                                    report = self._tracker.runTool(trafficAssignmentTool, specAttribute, scenario=self.Scenario)
                                    y = 1
                            x = 0
                            for i in range(len(self.TimesMatrixId)): #check to see if any time matrices defined
                                if self.TimesMatrixId[i] != None:
                                    x = 1
                            if x == 1: # if something, then do the assignment
                                if y == 0:
                                    # need to do blank assignment in order to get auto times saved in timeau
                                    attribute = []
                                    matrices = []
                                    for i in range(len(self.Mode_List_Split)):
                                        attribute.append(None)
                                        matrices.append(None)
                                    spec = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.Mode_List_Split,\
                                                            Mode_List_for_attributes, costAttribute, attribute, matrices)
                                    report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                                # get true times matrix
                                with _m.logbook_trace("Calculating link time"): #Do for each class 
                                    for i in range(len(self.Mode_List_Split)):
                                        networkCalculationTool(self._getSaveAutoTimesSpec(timeAttribute[i].id), scenario=self.Scenario)
                                        self._tracker.completeSubtask()
                                attribute = []
                                for i in range(len(timeAttribute)):
                                    attribute.append(timeAttribute[i].id)  
                                spec = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.Mode_List_Split,\
                                                            Mode_List_for_attributes, costAttribute, attribute, self.TimesMatrixId)
                                report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                                y = 1
                            if y == 0: # if no assignment has been done, do an assignment
                                attribute = []
                                matrices = []
                                for i in range(len(self.Mode_List_Split)):
                                    attribute.append(None)
                                    matrices.append(None)
                                spec = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.Mode_List_Split,\
                                                            Mode_List_for_attributes, costAttribute, attribute, matrices)
                                report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                            stoppingCriterion = report['stopping_criterion']
                            iterations = report['iterations']
                            if len(iterations) > 0: finalIteration = iterations[-1]
                            else:
                                finalIteration = {'number': 0}
                                stoppingCriterion = 'MAX_ITERATIONS'
                            number = finalIteration['number']
                            
                            if stoppingCriterion == 'MAX_ITERATIONS':
                                val = finalIteration['number']
                            elif stoppingCriterion == 'RELATIVE_GAP':
                                val = finalIteration['gaps']['relative']
                            elif stoppingCriterion == 'NORMALIZED_GAP':
                                val = finalIteration['gaps']['normalized']
                            elif stoppingCriterion == 'BEST_RELATIVE_GAP':
                                val = finalIteration['gaps']['best_relative']
                            else:
                                val = 'undefined'
                            
                            print "Primary assignment complete at %s iterations." %number
                            print "Stopping criterion was %s with a value of %s." %(stoppingCriterion, val)
        
    ##########################################################################################################
            
    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _AoNScenarioMANAGER(self):
        #Code here is executed upon entry
        
        tempScenarioNumber = _util.getAvailableScenarioNumber()
        
        if tempScenarioNumber == None:
            raise Exception("No additional scenarios are available!")
        
        scenario = _MODELLER.emmebank.copy_scenario(self.Scenario.id, tempScenarioNumber, 
                                                    copy_path_files= False, 
                                                    copy_strat_files= False, 
                                                    copy_db_files= False)
        scenario.title = "All-or-nothing assignment"
        
        _m.logbook_write("Created temporary Scenario %s for all-or-nothing assignment." %tempScenarioNumber)
        
        try:
            yield scenario
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _MODELLER.emmebank.delete_scenario(tempScenarioNumber)
            _m.logbook_write("Deleted temporary Scenario %s" %tempScenarioNumber)
            
    @contextmanager
    def _timeAttributeMANAGER(self):
        #Code here is executed upon entry
        timeAttributes = []
        attributes = {}
        for i in range(len(self.Mode_List_Split)):
            attributeCreated = False
            at = '@ltime'+str(i+1)
            timeAttribute = self.Scenario.extra_attribute(at)
            if timeAttribute == None:
                #@ltime hasn't been defined
                _m.logbook_write("Creating temporary link cost attribute '@ltime"+str(i+1)+"'.")
                timeAttribute = self.Scenario.create_extra_attribute('LINK', at, default_value=0)
                timeAttributes.append(timeAttribute)
                attributeCreated = True
                attributes[timeAttribute.id] = attributeCreated
            elif self.Scenario.extra_attribute(at).type != 'LINK':
                #for some reason '@ltime' exists, but is not a link attribute
                _m.logbook_write("Creating temporary link cost attribute '@ltim"+str(i+2)+"'.")
                at = '@ltim'+str(i+2)
                timeAttribute = self.Scenario.create_extra_attribute('LINK', at, default_value=0)
                timeAttributes.append(timeAttribute)
                attributeCreated = True
                attributes[timeAttribute.id] = attributeCreated
        
            if not attributeCreated:
                timeAttribute.initialize()
                timeAttributes.append(timeAttribute)
                attributes[timeAttribute.id] = attributeCreated
                _m.logbook_write("Initialized link cost attribute to 0.")
        
        try:
            yield timeAttributes
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            for key in attributes:
                if attributes[key] == True: 
                    _m.logbook_write("Deleting temporary link cost attribute.")
                    self.Scenario.delete_extra_attribute(key)
                    # Delete the extra cost attribute only if it didn't exist before.
                     
    @contextmanager
    def _costAttributeMANAGER(self):
        #Code here is executed upon entry
        costAttributes = []
        attributes = {}
        for i in range(len(self.Mode_List_Split)):
            attributeCreated = False
            at = '@lkcst'+str(i+1)
            costAttribute = self.Scenario.extra_attribute(at)
            if costAttribute == None:
                #@lkcst hasn't been defined
                _m.logbook_write("Creating temporary link cost attribute '@lkcst"+str(i+1)+"'.")
                costAttribute = self.Scenario.create_extra_attribute('LINK', at, default_value=0)
                costAttributes.append(costAttribute)
                attributeCreated = True
                attributes[costAttribute.id] = attributeCreated
            
            elif self.Scenario.extra_attribute(at).type != 'LINK':
                #for some reason '@lkcst' exists, but is not a link attribute
                _m.logbook_write("Creating temporary link cost attribute '@lcost"+str(i+2)+"'.")
                at = '@lcost'+str(i+2)
                costAttribute = self.Scenario.create_extra_attribute('LINK', at, default_value=0)
                costAttributes.append(costAttribute)
                attributeCreated = True
                attributes[costAttribute.id] = attributeCreated
        
            if not attributeCreated:
                costAttribute.initialize()
                costAttributes.append(costAttribute)
                attributes[costAttribute.id] = attributeCreated
                _m.logbook_write("Initialized link cost attribute to 0.")
        
        try:
            yield costAttributes
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            for key in attributes:
               if attributes[key] == True:
                   _m.logbook_write("Deleting temporary link cost attribute.")
                   self.Scenario.delete_extra_attribute(key)
                   # Delete the extra cost attribute only if it didn't exist before.    
    @contextmanager
    def _transitTrafficAttributeMANAGER(self):
        
        attributeCreated = False
        bgTrafficAttribute = self.Scenario.extra_attribute('@tvph')
        
        if bgTrafficAttribute == None:
            bgTrafficAttribute = self.Scenario.create_extra_attribute('LINK','@tvph', 0)
            attributeCreated = True
            _m.logbook_write("Created extra attribute '@tvph'")
        else:
            bgTrafficAttribute.initialize(0)
            _m.logbook_write("Initialized existing extra attribute '@tvph' to 0.")
        
        if EMME_VERSION >= 4:
            extraParameterTool = _MODELLER.tool('inro.emme.traffic_assignment.set_extra_function_parameters')
        else:
            extraParameterTool = _MODELLER.tool('inro.emme.standard.traffic_assignment.set_extra_function_parameters')
        
        extraParameterTool(el1 = '@tvph')
        
        try:
            yield
        finally:
            if attributeCreated:
                self.Scenario.delete_extra_attribute("@tvph")
                _m.logbook_write("Deleted extra attribute '@tvph'")
            extraParameterTool(el1 = '0')
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = { "Run Title": self.RunTitle,
                "Scenario" : str(self.Scenario.id),                
                "Times Matrix" : str(self.TimesMatrixId),
                "Peak Hour Factor" : str(self.PeakHourFactor),
                "Link Cost" : str(self.LinkCost),
                "Iterations" : str(self.Iterations),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts       
        
    def _getTransitBGSpec(self):
        return {
                "result": "@tvph",
                "expression": "(60 / hdw) * (vauteq) * (ttf == 3)",
                "aggregation": "+",
                "selections": {
                                "link": "all",
                                "transit_line": "all"
                                },
                "type": "NETWORK_CALCULATION"
                }
    #CostMatrixID="12,13"
    #CostMatrixID=[12,13]
    def _initOutputMatrices(self, Mode):
        with _m.logbook_trace("Initializing output matrices:"):
            for i in range(len(self.Demand_List)):
                if self.CostMatrixId[i] == 'mf0':
                    self.CostMatrixId[i] = None
                else:
                    _util.initializeMatrix(self.CostMatrixId[i], name='acost', description='AUTO COST FOR MODE: %s' %Mode[i])
                if self.TimesMatrixId[i] == 'mf0':
                    self.TimesMatrixId[i] = None
                else:
                    _util.initializeMatrix(self.TimesMatrixId[i], name='aivtt', description='AUTO TIME FOR MODE: %s' %Mode[i])
                if self.TollsMatrixId[i] == 'mf0':
                    self.TollsMatrixId[i] = None
                else:
                    _util.initializeMatrix(self.TollsMatrixId[i], name='atoll', description='AUTO TOLL FOR MODE: %s' %Mode[i])
            for i in range(len(self.aggAttributesClassMatrix)):
                for j in range(len(self.aggAttributesClassMatrix[i])):
                    if self.aggAttributesClassMatrix[i][j] != None:
                        _util.initializeMatrix(self.aggAttributesClassMatrix[i][j], name=self.aggAttributesClass[i][j], description='Aggregate Attribute %s Matrix' %self.aggAttributesClass[i][j])
    
    def _getLinkCostCalcSpec(self, costAttributeId, linkCost, linkTollAttributeId):
        return {
                "result": costAttributeId,
                "expression": "length * %f + %s" %(linkCost, linkTollAttributeId),
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _getPeakHourSpec(self, peakHourMatrixId, Demand_MatrixId): #Was passed the matrix id VALUE, but here it uses it as a parameter
        return {
                "expression": Demand_MatrixId + "*" + str(self.PeakHourFactor), 
                "result": peakHourMatrixId,
                "constraint": {
                                "by_value": None,
                                "by_zone": None
                                },
                "aggregation": {
                                "origins": None,
                                "destinations": None
                                },
                "type": "MATRIX_CALCULATION"
                }
        
    def _calculateAppliedTollFactor(self):
        appliedTollFactor = []
        if self.TollWeight != None:
            for i in range(0,len(self.TollWeight)):
                #Toll weight is in $/hr, needs to be converted to min/$
                appliedTollFactor.append(60.0 / self.TollWeight[i]) 
        return appliedTollFactor

    def _getSaveAutoTimesSpec(self, timeAttribute):
        return {
                "result": timeAttribute,
                "expression": "timau",
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
                 
    def _getPrimarySOLASpec(self, peakHourMatrixId, appliedTollFactor, Mode_List, \
            linkvolumeattributes, costAttribute, attribute, matrixId):
        
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 1, 1)
        
               
        #Generic Spec for SOLA
        SOLA_spec = {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes":[],
                "path_analysis": None,
                "cutoff_analysis": None,
                "traversal_analysis": None,
                "performance_settings": {
                    "number_of_processors": numberOfPocessors
                },
                "background_traffic": None,
                "stopping_criteria": {
                    "max_iterations": self.Iterations,
                    "relative_gap": self.rGap,
                    "best_relative_gap": self.brGap,
                    "normalized_gap": self.normGap
                }
            }
        #defines the aggregator     
        SOLA_path_analysis = []
        for i in range(len(Mode_List)):
            if attribute[i] == None:
                SOLA_path_analysis.append(None)
            else:
                path = {
                        "link_component": attribute[i],
                        "turn_component": None,
                        "operator": "+",
                        "selection_threshold": {
                            "lower": None,
                            "upper": None
                        },
                        "path_to_od_composition": {
                            "considered_paths": "ALL",
                            "multiply_path_proportions_by": {
                                "analyzed_demand": False,
                                "path_value": True
                            }
                        }
                    }
                SOLA_path_analysis.append(path)
        #Creates a list entry for each mode specified in the Mode List and its associated Demand Matrix
        SOLA_Class_Generator = [{
                    "mode": Mode_List[i],
                    "demand": peakHourMatrixId[i].id,
                    "generalized_cost": {
                        "link_costs": costAttribute[i].id,
                        "perception_factor": appliedTollFactor[i]
                    },
                    "results": {
                        "link_volumes": linkvolumeattributes[i],
                        "turn_volumes": None,
                        "od_travel_times": {
                            "shortest_paths": None
                        }
                    },
                    "path_analysis": SOLA_path_analysis[i],
                    "cutoff_analysis": None,
                    "traversal_analysis": None,
                    "analysis": {
                        "analyzed_demand": None,
                        "results": {
                            "od_values": matrixId[i],
                            "selected_link_volumes": None,
                            "selected_turn_volumes": None
                        }
                    }
                } for i in range(len(Mode_List))]        
        SOLA_spec['classes'] = SOLA_Class_Generator

        return SOLA_spec

    def _getSaveAutoTimesSpec(self, timeAttribute):
        return {
                "result": timeAttribute,
                "expression": "timau",
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _modifyFunctionForAoNAssignment(self):
        allOrNothingFunc = _MODELLER.emmebank.function('fd98')
        if allOrNothingFunc == None:
            allOrNothingFunc = _MODELLER.emmebank.create_function('fd98', 'ul2')
        else:
            allOrNothingFunc.expression = 'ul2'
        
    def _getChangeLinkVDFto98Spec(self):
        return {
                "result": "vdf",
                "expression": "98",
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def _GetSelectAttributeOptionsHTML(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            if not att.type == 'LINK': continue
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)
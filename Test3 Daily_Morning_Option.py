from __future__ import print_function

# -*- coding: utf-8 -*-
"""
Created on Wed Jun 08 16:45:57 2016

@author: thoma
"""

# -*- coding: utf-8 -*-
"""
Created on Wed Jun 01 11:44:46 2016

@author: thoma
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-

# intraday_mr.py


import datetime
import numpy as np
import pandas as pd
import statsmodels.api as sm
from strategy import Strategy

try:
    import Queue as queue
except ImportError:
    import queue

from LiveExecutionContainer import LiveExecutionContainer

from ib.ext import Contract
#from MyAlgoSystem.bar import LiveFeed
#from MyAlgoSystem.IbBroker import MyIbBroker
#from MyAlgoSystem.strategy import MyLiveStrategy


from numpy import append 
import time
from lib.Contract import makeStkContrcat,makeForexContract,makeOptContract,buildContractRepresentation
from barfeed import LiveIBDataHandler
###########,


class MyStrategy(Strategy):
    """
    Uses ordinary least squares (OLS) to perform a rolling linear
    regression to determine the hedge ratio between a pair of equities.
    The z-score of the residuals time series is then calculated in a
    rolling fashion and if it exceeds an interval of thresholds
    (defaulting to [0.5, 3.0]) then a long/short signal pair are generated
    (for the high threshold) or an exit signal pair are generated (for the
    low threshold).
    """
    
    def __init__(
        self,strategy_name, Ibroker ,contract_list
    ):
        """
        Initialises the stat arb strategy.

        Parameters:
        bars - The DataHandler object that provides bar information
        events - The Event Queue object.
        """
        self.strategy_name=strategy_name
        self.run_number=0
        
        self.stockBar = []
        
        self.myEVentQueue   =   queue.Queue()

        self.stockPrice      =   np.array(1) 
        self.callPrice       =   np.array(1)
        self.putPrice        =   np.array(1)
        self.delta           =   np.array(1)

        self.i=0


        self.long=False
        self.short=False

        self.IbBroker       =   Ibroker
        self.contract_list  =   contract_list
        self.data_handler       =   None

        self.callOrderId    = None
        self.putOrderId     = None
        
        self.callOption     = None
        self.putOption      = None
        
        self.callPnl        = None
        self.putPnl         = None
        
        self.callPriceCost  = None
        self.putPriceCost   = None
        
        self.callPosition   = None
        self.putPosition    = None


        
    def initPut(self):
        print("@@@ INIT Put @@@")
        price        = self.stockPrice[-1]
        optionExpiry = self.IbBroker.getOptionExpiry(6)
        p_strike     = float(round(price)+1)

        #quantity     = round(5000/(150))
        self.putOption     =   self.IbBroker.makeOptContract(
                        IbContract  =   self.contract_list[0],
                        m_right     =   'P', 
                        m_expiry    =   optionExpiry, 
                        m_strike    =   p_strike,)
        #print("@@@ putOption @@@")
        #print("@@@ %s @@@" %(self.IbBroker.buildContractRepresentation(self.putOption )))
        
    def initCall(self):
        print("@@@ INIT Call@@@")
        price        = self.stockPrice[-1]
        optionExpiry = self.IbBroker.getOptionExpiry(6)
        c_strike     = float(round(price)-1)
        
        self.callOption     =   self.IbBroker.makeOptContract(
                        IbContract  =   self.contract_list[0],
                        m_right     =   'C', 
                        m_expiry    =   optionExpiry, 
                        m_strike    =   c_strike,)
        #print("@@@ callOption @@@")
        #print("@@@ %s @@@" %(self.IbBroker.buildContractRepresentation(self.callOption )))



        """
        contract_list   = [self.callOption, self.putOption]
        self.data_handler   =   LiveIBDataHandler(
                                    contract    =   contract_list,
                                    eventQueue  =   self.myEVentQueue,
                                    host        =   "localhost",
                                    port        =   7496,
                                    warmupBars  =   0, 
                                    debug       =   True,
                                    fileOutput  =   None)

        """
    def getOptionsPrice(self):
        try:
            print("@@@ getOptionsPrice @@@")
           
            event = self.myEVentQueue.get(False)
            if event is not None:
                if event.type == 'OPTION MARKET EVENT':
                    contract_code   =   self.IbBroker.buildContractRepresentation(event.bar['contract'])
                    print("@@@ "+contract_code+" @@@")
                    
                    if event.bar['contract'] == self.callOption:
                        self.callPrice  =   np.append(self.callPrice,self.stockBar[-1]['Close'])
                        print("@@@ Call %s @@@"%(self.callPrice))
                        
                    if event.bar['contract'] == self.putOption:
                        self.putPrice   =   np.append(self.putPrice,self.stockBar[-1]['Close'])
                        print("@@@ Put %s @@@"%(self.putPrice))

                    else:
                        print("@@@ ERROR getOptionsPrice Contract not in the Bar@@@")
                    print("@@@ END OPTION MARKET EVENT @@@")
        except queue.Empty:
            print("@@@ Option Queue Empty @@@")
        except Exception as e:
            print("@@@ Error : %s @@@" %(e))

    
    def getPosition(self,contract_code,dic):
        #print("getPosition")
        #print("contract_code to search:  %s" %(contract_code))
        for key in dic.keys():
            #print(key.m_symbol+":"+key.m_right+""+key.m_strike+":"+key.m_expiry)
            #print("position where to search \n %s"% dic[key])
            #print("contract_code of the position where to search: %s"%(dic[key]['contract_code']))
            if dic[key]['contract_code'] == contract_code:
                
                #print ("**** FIND KEY")
                return dic[key]
            else:
                #print ("****DID NOT FIND KEY")
                pass
        return False
        
    def onBar(self, bar):
        """
        Calculate the SignalEvents based on market data.
        """
        print('bar Got into the Strategy')
        #print("bar: %s\n" %(bar))
        contract_code   =   self.IbBroker.buildContractRepresentation(bar['contract'])
        print(contract_code+"\n\n")
        
        self.stockBar.append(bar)
        self.stockPrice  =   np.append(self.stockPrice,self.stockBar[-1]['Close'])
        stockPrice       =  self.stockBar[-1]['Close']
        print(" Stock Price:    %s" %(stockPrice))
        
        self.i +=1
        if self.i   ==  1:
            self.initCall()
            self.initPut()
        
        #print("CALL")
        #print("%s:%s:%s:%s"%(self.callOption.m_symbol,self.callOption.m_strike,self.callOption.m_expiry,self.callOption.m_right))
        call_code  = self.IbBroker.buildContractRepresentation(self.callOption)
        # print(call_code)
        positionC   = self.getPosition(call_code,self.IbBroker.overalPosition)
        #print(positionC)
        #print(type(positionC))
        #print()
        if positionC != False:
            #print(positionC['contract_code'])
            callPrice  = float(positionC['marketPrice'])
            self.callPrice  =   np.append(self.callPrice,callPrice)
            self.callPriceCost  = float(positionC['averageCost'])
            self.callPosition   = float(positionC['position'])
            self.callPnl    = float(positionC['unrealizedPNL'])
            #print(" Call Price :    %s" %(callPrice))
            #print(" Call Price cost :    %s" %(self.callPriceCost)) 
            print(" call position:    %s" %(self.callPosition)) 
            print(" call callPnl:    %s" %(self.callPnl)) 
        else:
            print("No call option in the position - default value")
            callPrice  = 0.9
            self.callPrice  =   np.append(self.callPrice,callPrice)
            self.callPriceCost  = 0.9
            self.callPosition   = None
            self.callPnl    = None
            #print(" Call Price :    %s" %(callPrice))
            #print(" Call Price cost :    %s" %(self.callPriceCost)) 
            print(" call position:    %s" %(self.callPosition)) 
            print(" call callPnl:    %s" %(self.callPnl)) 
                    
        #print("PUT")
        put_code  = self.IbBroker.buildContractRepresentation(self.putOption)
        #print(put_code)
        #print(self.putOption.m_symbol)
        positionP   = self.getPosition(put_code,self.IbBroker.overalPosition)
        #print()
        #print(positionP)
#        print(type(position))
 #       print()
        if positionP != False:
            #print(positionP['contract_code'])
            putPrice   = float(positionP['marketPrice'])
            self.putPrice  =   np.append(self.putPrice,putPrice)
            self.putPriceCost   = float(positionP['averageCost'])
            self.putPosition    = float(positionP['position'])
            self.putPnl     = float(positionP['unrealizedPNL'])
            #print(" put Price:    %s" %(putPrice))
            #print(" put Price cost :    %s" %(self.putPriceCost ))
            print(" Put position:    %s" %(self.putPosition)) 
            print(" Put putPnl:    %s" %(self.putPnl)) 
        else:
            #print("No putt option in the position - default value")
            putPrice   = 1.12
            self.putPrice  =   np.append(self.putPrice,putPrice)
            self.putPriceCost   = 1.12
            self.putPosition    = None
            self.putPnl     = None
            #print(" put Price:    %s" %(putPrice))
            #print(" put Price cost :    %s" %(self.putPriceCost ))
            print(" Put position:    %s" %(self.putPosition)) 
            print(" Put putPnl:    %s" %(self.putPnl)) 

        #self.getOptionsPrice()
        #self.getOptionsPrice()
        self.compute(bar)
        
    def compute(self, bar):
        print('COMPUTE STRATEGY - i: %s' %(self.i))
        #position    =   self.IbBroker.overalPosition
        #print(self.IbBroker.overalPosition)
        order       =   self.IbBroker.submittedOrder
        print(order )
        
        
        
        print("*** Stock Price:    %s" %(self.stockPrice))
        print("*** Call Price :    %s" %(self.callPrice))
        print("*** Putt Price :    %s" %(self.putPrice)) 
           
        

        if self.i ==1:
            
            quantityCall    =   round(5000/(self.callPrice[-1]*100)+1)
            print("*** first loop of strategy ")
            print("*** Call quanity to buy : %s" %(quantityCall))
            self.buyCall(quantityCall)
            quantityPutt    =   round(5000/(self.putPrice[-1]*100)+1)
            print("*** Put quanity to buy : %s" %(quantityCall))
            self.buyPut(quantityPutt)
            return
        else:
            if self.putPosition >0:
                print("*** put position existing ")
                if self.putExitCondition():
                   self.sellPut(self.putPosition)
                   self.putOrderId = None
                   print("*** Exit condition succsfull Put order exit")
                   return
                else:
                        print("*** Exit condition not sucsfull")
            elif self.callPosition == 0 and self.longPut == False and self.putOrderId ==None:
                print("*** No order position - test out entry condition")
                if self.putEntryCondition():
                    print("*** put entry condition sucsffull but for now do nothing")
                else:
                    print("*** put entry condition not sucsffull do nothing")
            else:
                print("*** Put Unknown state do nothing - Position: %s -longStatus:  %s -orderid:  %s " %(self.putPosition,self.longPut,self.putOrderId))
                
                
            if self.callPosition  >0 :
                print("*** Last call order executed and filled test exit condition")
                if self.callExitCondition():
                    self.sellCall(self.callPosition)
                    self.callOrderId = None
                    print("*** Exit condition succsfull call order exit")
                    return
                else:
                    print("*** Exit condition not succsfull do nothing")
            elif self.callPosition == 0 and self.longCall == False and self.callOrderId ==None:
                print("*** No call position - test entry condition")
                if self.callEntryCondition():
                    print("*** call entry condition sucsffull but for now do nothing")
                else:
                    print("*** call entry condition not sucsfull do nothing")
                    
            else:
                print("***Call Unknown state do nothing: position %s -longstatus %s -order id %s " %(self.callPosition,self.longCall,self.callOrderId))


    def callEntryCondition(self):
        return True

    def putEntryCondition(self):
        return True

    def callExitCondition(self):
        perc= (self.callPnl/(self.callPosition*self.callPriceCost))*100
        print("### Call Exit condition perc: %s" %perc)
        if datetime.datetime.now() < datetime.time(10,30,00):
            if perc < -2 or perc >5 :
                print("### Call Exit condition True")

                return True
            else:
                print("### Call Exit condition False")

                return False
        else:
            print("### Out of Hour - Blanket Call Exit condition True")

            return True

    def putExitCondition(self):
        perc= (self.putPnl/(self.putPosition*self.putPriceCost))*100
        print("### Put Exit condition perc: %s" %perc)

        if datetime.datetime.now() < datetime.time(10,30,00):
            if perc < -2 or perc >5 :
                print("### Put Exit condition True")
                return True
            else:
                print("### Put Exit condition False")

                return False
        else:
            print("### Out of Hour - Blanket put Exit condition True")
            
            return True
        
    def buyCall(self,quantityCall):
        #self.init()
        self.callOrderId=   self.IbBroker.submitMarketOrder('BUY',self.callOption,quantityCall)
        print("Call Order ID: %s" % self.callOrderId)
        self.longCall   =   True

    def buyPut(self,quantityPutt):
        #self.init()
        self.putOrderId =   self.IbBroker.submitMarketOrder('BUY',self.putOption,quantityPutt)
        print("Put Order ID: %s" % self.putOrderId)
        self.longPut    =   True

    def sellCall(self,quantityCall):
        self.callOrderId=   self.IbBroker.submitMarketOrder('SELL',self.callOption,quantityCall)
        print("Call Order ID: %s" % self.callOrderId)
        self.longCall   =   False

    def sellPut(self,quantityCall):
        self.putOrderId=   self.IbBroker.submitMarketOrder('SELL',self.putOption,quantityCall)
        print("Call Order ID: %s" % self.putOrderId)
        self.longPut   =   False


if __name__ == "__main__":
    csv_dir = '/path/to/your/csv/file'  # CHANGE THIS!
    
    eur         =   makeForexContract(m_symbol='EUR',m_currency = 'GBP')
    aapl        =   makeStkContrcat('AAPL')
    bac         =   makeStkContrcat('BAC')
    fut         =   makeForexContract('ES','201612')
    symbol_list =   [bac]
    
    Mystrategy= LiveExecutionContainer(
        strategy_name   =   'MorningOptionStrategy',
        strategy        =   MyStrategy,
        contract_list   =   symbol_list,
        #dir_Output      =   'output3',
        debug_data_feed =   False,
        debug_broker    =   False,
         )
    
    Mystrategy.run()
    """
    print("@@@ INIT @@@")
    price        = 13
    optionExpiry = '20160617'
    c_strike     = 14#float(round(price)-1)
    p_strike     = 15#float(round(price)+1)

    #quantity     = round(5000/(150))
    
    callOption     =   makeOptContract(
                IbContract  =   bac,
                m_right     =   'C', 
                m_expiry    =   optionExpiry, 
                m_strike    =   13,)
    print("@@@ callOption @@@")
    print("@@@ %s @@@" %(buildContractRepresentation(callOption )))


    putOption     =   makeOptContract(
                    IbContract  =    bac,
                    m_right     =   'P', 
                    m_expiry    =   optionExpiry, 
                    m_strike    =   15,)
    print("@@@ putOption @@@")
    print("@@@ %s @@@" %(buildContractRepresentation(putOption )))

    
    contract_list   = [makeStkContrcat('BAC')]
    
    data_handler   =   LiveIBDataHandler(
                                contract    =   makeStkContrcat('BAC'),
                                eventQueue  =   None,
                                host        =   "localhost",
                                port        =   7496,
                                warmupBars  =   0, 
                                debug       =   True,
                                fileOutput  =   None)

   """ 
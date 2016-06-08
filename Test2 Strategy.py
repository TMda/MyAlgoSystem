# -*- coding: utf-8 -*-
"""
Created on Wed Jun 01 11:44:46 2016

@author: thoma
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-

# intraday_mr.py

from __future__ import print_function

import datetime
import numpy as np
import pandas as pd
import statsmodels.api as sm
from strategy import Strategy
from event import SignalEvent
from LiveExecutionContainer import LiveExecutionContainer
import ib.ext
from ib.ext import Contract
#from MyAlgoSystem.bar import LiveFeed
#from MyAlgoSystem.IbBroker import MyIbBroker
#from MyAlgoSystem.strategy import MyLiveStrategy
from barfeed import LiveFeed
from IbBroker import MyIbBroker
from strategy import MyLiveStrategy
from numpy import append 
import time
from lib.Contract import makeStkContrcat,makeForexContract,makeOptContract
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
        
        self.barBAC = []
        self.barAAPL= []

        self.x=np.array(1)
        self.y=np.array(1)
        self.delta=np.array(1)

        self.i=0

        self.mvx=[]
        self.mvy=[]

        self.long=False
        self.short=False

        self.IbBroker=Ibroker
        self.contract_list=contract_list




    def onBar(self, bar):
        """
        Calculate the SignalEvents based on market data.
        """
        print('bar Got into the Strategy')
        print("bar: %s\n" %(bar))
        contract_code=self.IbBroker.buildContractRepresentation(bar['contract'])
        print(contract_code+"\n\n")
        if bar['contract'].m_symbol=='AAPL':
            self.barAAPL.append(bar)
            self.y=np.append(self.x,self.barAAPL[-1]['Close'])
            print("exit because aapl info")
            return
        elif bar['contract'].m_symbol=='BAC':
            self.barBAC.append(bar)
            self.x=np.append(self.y,self.barBAC[-1]['Close'])

        else:
            return
        #print(self.x)
        #print(self.y)
        self.i +=1
        self.calculate_signals_for_pairs(bar)
        
    def calculate_signals_for_pairs(self, bar):
        print('STRATEGY - i: %s' %(self.i))
        #position    =   self.IbBroker.overalPosition
        print(self.IbBroker.overalPosition)
        order       =   self.IbBroker.submittedOrder
        print( self.IbBroker.submittedOrder)
        
        if self.i <10:
            print('EXIST i <5: %s' %(self.i))
            return
            
        self.mvx    =   pd.rolling_mean(self.x,window=5)
        self.mvy    =   pd.rolling_mean(self.x,window=10)
        price       =   self.x[-1]

        delta       =   self.mvy-self.mvx
        delt        =   delta[-1]
        delta       =   delta[~np.isnan(delta)]
        sd          =   np.std(delta) # Standard deviation between high and low
        regime      =   abs(delt) > abs(sd)
        regime      =   1>0
        sd          =  0
        #print("self.mvx: %s"%(self.mvx[-1] ))
        #print("self.mvy: %s"%(self.mvy[-1] ))
        #print("delta: %s"%(delta))
        #print("delta: %s"%(delt))
        print("sd: %s"%(sd))
        print("regime: %s"%(regime))
        #print("self.long: %s"%(self.long))
        #print("self.short: %s"%(self.short))
           
        
        if delt>0 : #low above high
            if regime:
                # the change above threshold
                optionExpiry = self.IbBroker.getOptionExpiry(2)
                m_strike     = float(round(price)+1)
                quantity     = round(self.IbBroker.getCash()/(2*150))
                print('Low above high and delta > sd - Buying 10 share - Opening position' %())
                option     =   self.IbBroker.makeOptContract(
                    IbContract  =   self.contract_list[0],
                        m_right     =   'C', 
                        m_expiry    =   optionExpiry, 
                        m_strike    =   m_strike,)

                if order['executed'] !='SUBMITTED':
                    if self.long==False and self.short==False:

                        self.IbBroker.submitMarketOrder('BUY',option,quantity)
                        self.long   =   True
                        self.short  =   False
                    elif self.long==False and self.short==True:
                        print('Low above high and delta > sd - Buying 10 share - Closing position' %())
                        self.IbBroker.submitMarketOrder('BUY',option,quantity)
                        self.long   =   True
                        self.short  =   False
       
                    elif self.long  ==  True:
                        print('Low above high but already in Long position - Do nothing' %())
                    else:
                        print('UNKNOWN STATE Low above High' %())
                        print("self.mvx: %s"%(self.mvx[-1]))
                        print("self.mvy: %s"%(self.mvy[-1] ))
                        print("delta: %s"%(delt))
                        print("sd: %s"%(sd))
                        print("regime: %s"%(regime))
                        print("self.long: %s"%(self.long))
                        print("self.short: %s"%(self.short))

                else:
                    print("Previous order not executed yet do nothing ")
                    
                    
                    
                
        else: #high above low
            if regime:
                optionExpiry = self.IbBroker.getOptionExpiry(2)
                m_strike     = float(round(price)-1)
                quantity     = round(self.IbBroker.getCash()/(2*150))
                print('Low above high and delta > sd - Buying 10 share - Opening position' %())
                option     =   self.IbBroker.makeOptContract(
                    IbContract  =   self.contract_list[0],
                        m_right     =   'P', 
                        m_expiry    =   optionExpiry, 
                        m_strike    =   m_strike,)

                if order['executed'] !='SUBMITTED':
                    

                    if self.long and self.short == False:
                        print('High above low and delta > sd - selling 10 share - Closing position' %())
                        self.IbBroker.submitMarketOrder('SELL',option,quantity)
                        self.long   =   False
                        self.short  =    True
    
                    elif self.long ==False and self.short ==False:
                        print('High above low and delta > sd - selling 10 share - Opening position' %())
                        self.IbBroker.submitMarketOrder('SELL',option,quantity)
                        self.long   =   False
                        self.short  =   True
    
                    elif self.short  ==  True:
                        print('High above low but already in Short position - Do nothing' %())
    
                    else:
                        print('UNKNOWN STATE High above Low' %())
                        print("self.mvx: %s"%(self.mvx[-1]))
                        print("self.mvy: %s"%(self.mvy[-1] ))
                        print("delta: %s"%(delta[-1]))
                        print("sd: %s"%(sd))
                        print("regime: %s"%(regime))
                        print("self.long: %s"%(self.long))
                        print("self.short: %s"%(self.short))
                else:
                    print("High above low - Previous order not executed yet do nothing ")
                    
            
        



if __name__ == "__main__":
    csv_dir = '/path/to/your/csv/file'  # CHANGE THIS!
    
    eur         =   makeForexContract(m_symbol='EUR',m_currency = 'GBP')
    aapl        =   makeStkContrcat('AAPL')
    bac         =   makeStkContrcat('BAC')
    fut         =   makeForexContract('ES','201612')
    symbol_list =   [bac,aapl]
    
    Mystrategy= LiveExecutionContainer(
        strategy_name   =   'MyStrategy',
        strategy        =   MyStrategy,
        contract_list   =   symbol_list,
        debug_data_feed =   False,
        debug_broker    =   True,
         )
    
    Mystrategy.run()

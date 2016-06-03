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

###########
def makeForexContract(m_symbol,ContractMonth,m_secType="FUT",m_currency="USD",
                      m_exchange="GLOBEX"):
    from ib.ext.Contract import Contract
    contract   =  Contract()
    contract.m_symbol   = m_symbol
    contract.m_secType  = m_secType
    contract.m_currency = m_currency
    contract.m_exchange = m_exchange
    contract.m_lastTradeDateOrContractMonth = ContractMonth
    return contract

def makeStkContrcat(m_symbol,m_secType = 'STK',m_exchange = 'SMART',m_currency = 'USD'):
    from ib.ext.Contract import Contract
   
    newContract = Contract()
    newContract.m_symbol = m_symbol
    newContract.m_secType = m_secType
    newContract.m_exchange = m_exchange
    newContract.m_currency = m_currency
    return newContract

def makeForexContract(m_symbol,m_secType = 'CASH',
                      m_exchange = 'IDEALPRO',
                      m_currency = 'USD'):
        
        
        
        
    from ib.ext.Contract import Contract
    newContract = Contract()
    newContract.m_symbol = m_symbol #contract.symbol("EUR");
    newContract.m_secType = m_secType #contract.secType("CASH");
    newContract.m_exchange = m_exchange #contract.exchange("IDEALPRO");
    newContract.m_currency = m_currency #contract.currency("GBP");
    return newContract



class IntradayOLSMRStrategy():
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
        self, Ibroker ,contract_list
    ):
        """
        Initialises the stat arb strategy.

        Parameters:
        bars - The DataHandler object that provides bar information
        events - The Event Queue object.
        """
        self.barBAC = []
        self.barAAPL= []
        self.x=np.array(1)
        self.y=np.array(1)
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
        #print("bar: %s" %(bar))

        if bar['contract'].m_symbol=='AAPL':
            self.barBAC.append(bar)
            self.x=np.append(self.x,self.barBAC[-1]['Close'])
        elif bar['contract'].m_symbol=='BAC':
            self.barAAPL.append(bar)
            self.y=np.append(self.y,self.barAAPL[-1]['Close'])

        else:
            return
        #print(self.x)
        #print(self.y)
        self.i +=1
        self.calculate_signals_for_pairs(bar)
        
    def calculate_signals_for_pairs(self, bar):
        print('STRATEGY - i: %s' %(self.i))

        if self.i <5:
            print('EXIST i <5: %s' %(self.i))
            return
        self.mvx=pd.rolling_mean(self.x,5)
        if self.long==False and self.short==False:
            print('Mean > price Buying 10 share' %())
            self.IbBroker.createMarketOrder('BUY',self.contract_list[0],10)
            self.long=True
        if self.long:
            print('Mean > price Buying 10 share' %())
            self.IbBroker.createMarketOrder('SELL',self.contract_list[0],10)
            self.long=True
            
            
        


if __name__ == "__main__":
    csv_dir = '/path/to/your/csv/file'  # CHANGE THIS!
    
    eur=makeForexContract(m_symbol='EUR',m_currency = 'GBP')
    aapl=makeStkContrcat('AAPL')
    bac=makeStkContrcat('BAC')
    fut =makeForexContract('ES','201612')
    symbol_list = [aapl,bac]
    
    Mystrategy= LiveExecutionContainer(
        strategy=IntradayOLSMRStrategy
        ,contract_list=symbol_list
       
    )
    
    Mystrategy.run()

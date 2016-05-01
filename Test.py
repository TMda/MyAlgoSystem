from __future__ import print_function
import pandas as pd
import numpy as np
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

def makeStkContrcat(m_symbol,m_secType = 'STK',m_exchange = 'SMART',m_currency = 'USD'):
    from ib.ext.Contract import Contract
    newContract = Contract()
    newContract.m_symbol = m_symbol
    newContract.m_secType = m_secType
    newContract.m_exchange = m_exchange
    newContract.m_currency = m_currency
    return newContract

def makeForexContract(m_symbol,m_secType = 'CASH',m_exchange = 'IDEALPRO',m_currency = 'USD'):
    from ib.ext.Contract import Contract
    newContract = Contract()
    newContract.m_symbol = m_symbol
    newContract.m_secType = m_secType
    newContract.m_exchange = m_exchange
    newContract.m_currency = m_currency
    return newContract

class thomas(MyLiveStrategy):
    def __init__(LiveBarFeed,broker,shortSMA):
        self.sma=0
        self.__price=None
        self._shortSMA=shortSMA
        self.__count=0

    def onBar(self,bar):
        now=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        priceBar=bar.getClose()

        print('%s[Thomas onBars]********************************'%(now))
        #bar=self._events.get().bar
        if self.__count==0:
            self.price=np.array(priceBar,dtype=float)
            self.sma=np.array(priceBar,dtype=float)
        else:
            append(self.sma,priceBar)
            append(self.price,priceBar)
        if self.__count<self._shortSMA:
 
            self.__count=+1
            return
        
        
        #f1=open(self.logfile, 'w+')

        self.i +=1
        self.j +=1
        positions=self.getBroker().Positions()
        if positions:
            for position in positions:
                if position['position'] ==0: 
                    #print('ON BAR: %d' %(self.i))
                    #print('STEP: %d' %(self.j ))
                    #print(' bar is: %s' %(priceBar))
                    print('%s[Thomas onBars]ON BAR: %d' %(now,self.i))
                    print('%s[Thomas onBars]STEP: %d' %(now,self.j ))
                    print('%s[Thomas onBars]bar is: %s' %(now,priceBar))
                    print('%s[Thomas onBars]IB cash:%s '%(now,self.getBroker().getCash()))
                    print('%s[Thomas onBars]IB shares: %s'%(now,self.getBroker().getShares()))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_symbol: %s'%(now,position['ibContract.m_symbol']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_secType: %s'%(now,position['ibContract.m_secType']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_currency: %s'%(now,position['ibContract.m_currency']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_exchange: %s'%(now,position['ibContract.m_exchange']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_multiplier: %s'%(now,position['ibContract.m_multiplier']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_expiry: %s'%(now,position['ibContract.m_expiry']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_strike: %s'%(now,position['ibContract.m_strike']))
                    print('%s[Thomas onBars]IB Broker positions ibContract.m_right: %s'%(now,position['ibContract.m_right']))
                    print('%s[Thomas onBars]IB Broker positions position: %s'%(now,position['position']))
                    print('%s[Thomas onBars]IB Broker positions marketPrice: %s'%(now,position['marketPrice']))
                    print('%s[Thomas onBars]IB Broker positions marketValue: %s'%(now,position['marketValue']))
                    print('%s[Thomas onBars]IB Broker positions averageCost: %s'%(now,position['averageCost']))
                    print('%s[Thomas onBars]IB Broker positions unrealizedPNL: %s'%(now,position['unrealizedPNL']))
                    print('%s[Thomas onBars]IB Broker positions realizedPNL: %s'%(now,position['realizedPNL']))

                    PL=position['realizedPNL']
                    Share=position['position']
                    marketPrice=position['marketPrice']
                    entryPrice=position['averageCost']
                    returnPosition=(PL/(entryPrice*Share))*100
                    print('%s[Thomas onBars]IB Broker positions return: %s'%(now,returnPosition))
                    print('%s[Thomas onBars]------------'%(now, ))

                    #Checking exit conditions for the positions
                    if  position['ibContract.m_right']=='C' and\
                        self.exitLongSignal(entryPrice,marketPrice,PL,Share,returnPosition):
                        ibContract=Contract()
                        ibContract.m_symbol     =   position['ibContract.m_symbol']
                        ibContract.m_secType    =   position['ibContract.m_secType']
                        ibContract.m_exchange   =   position['ibContract.m_exchange']
                        ibContract.m_multiplier =   position['ibContract.m_multiplier']
                        ibContract.m_expiry     =   position['ibContract.m_expiry']
                        ibContract.m_strike     =   position['ibContract.m_strike']
                        ibContract.m_right      =   position['ibContract.m_right']
                        self.createMarketOrder(ibContract,'SELL', quantity=Share)
                        print('%s[Thomas onBars]EXITING POSITION >>EXIT SIGNAL TRUE on %s' %(now,self.__instrument))
                    elif  position['ibContract.m_right']=='P' and\
                        self.exitShortSignal(entryPrice,marketPrice,PL,Share,returnPosition):
                        ibContract=Contract()
                        ibContract.m_symbol     =   position['ibContract.m_symbol']
                        ibContract.m_secType    =   position['ibContract.m_secType']
                        ibContract.m_exchange   =   position['ibContract.m_exchange']
                        ibContract.m_multiplier =   position['ibContract.m_multiplier']
                        ibContract.m_expiry     =   position['ibContract.m_expiry']
                        ibContract.m_strike     =   position['ibContract.m_strike']
                        ibContract.m_right      =   position['ibContract.m_right']
                        self.createMarketOrder(ibContract,'SELL', quantity=Share)
                        print('%s[Thomas onBars]EXITING POSITION >>EXIT SIGNAL TRUE on %s' %(now,self.__instrument))

                    else:
                        print('%s[Thomas onBars]NO EXITING POSITION >>EXIT SIGNAL False on %s' %(now,self.__instrument))
                
                
        else:
            print('%s[Thomas onBars]No active Position '%(now, ))
            if self.enterLongSignal(bar):
            
                quantity =int(self.getBroker().getCash() * 0.9 *0.5/ (200))
                #Build an option contract 3 strike price away in the money
                ibContract=Contract()
                ibContract.m_symbol     =   position['ibContract.m_symbol']
                ibContract.m_secType    =   'OPT'
                ibContract.m_exchange   =   'SMART'
                ibContract.m_multiplier =   100
                ibContract.m_expiry     =   '20160306'
                ibContract.m_strike     =   float(priceBar-(3*0.5))
                ibContract.m_right      =   'C'
                self.createMarketOrder(ibContract,'BUY', quantity)
                
                print('%s[Thomas onBars]ENTERING LONG POSITION OPTION == CALL OPTION OF: %s' %(now,self.__instrument))

            elif self.enterShortSignal(bar):
                quantity =int(self.getBroker().getCash() * 0.9 *0.5/ (200))
                #Build an option contract 3 strike price away in the money
                ibContract=Contract()
                ibContract.m_symbol     =   position['ibContract.m_symbol']
                ibContract.m_secType    =   'OPT'
                ibContract.m_exchange   =   'SMART'
                ibContract.m_multiplier =   100
                ibContract.m_expiry     =   '20160306'
                ibContract.m_strike     =   float(priceBar+(3*0.5))
                ibContract.m_right      =   'P'
                self.createMarketOrder(ibContract,'BUY', quantity)
                print('%s[Thomas onBars]ENTERING SHORT POSITION == PUT OPTION OF: %s' %(now,self.__instrument))

        self.__count=+1
        print('[Thomas onBars]EXIT ====EXIT====EXIT========================')  

        
    def enterLongSignal(self, bar):

        return bar.getPrice() < self.__entryWMA[-1] #and bar.getDateTime().time() < datetime.time(11,30,00)

    def exitLongSignal(self,entryPrice,marketPrice,PL,Share,returnPosition):
        print('[exitLongSignal]===========================================')
        crossi=self.__price[-1] < self.sma[-1]
        returnCondition=returnPosition <-0.1
        cond=(crossi or returnCondition)
        print('%s[exitLongSignal] position PNL: %s' %(now,PL ))
        print('%s[exitLongSignal] position Return: %s' %(now,returnPosition ))
        print('%s[exitLongSignal] condition Cross over condition: %s' %(now,crossi ))
        print('%s[exitLongSignal] condition Return: %s' %(now,returnCondition ))
        print('%s[exitLongSignal] Signal Condition: %s' %(now,cond))
        return cond

    def enterShortSignal(self, bar):
        return bar.getPrice() > self.__entryWMA[-1] #and bar.getDateTime().time() < datetime.time(11,30,00)

    def exitShortSignal(self,entryPrice,marketPrice,PL,Share,returnPosition):
        print('[exitShortSignal]===========================================')
        crossi=self.__price[-1] > self.sma[-1]
        returnCondition=returnPosition <-0.1
        cond=(crossi or returnCondition)
        print('%s[exitShortSignal] position PNL: %s' %(now,PL ))
        print('%s[exitShortSignal] position Return: %s' %(now,returnPosition ))
        print('%s[exitShortSignal] condition Cross over condition: %s' %(now,crossi ))
        print('%s[exitShortSignal] condition Return: %s' %(now,returnCondition ))
        print('%s[exitShortSignal] Signal Condition: %s' %(now,cond))
        return cond

#Contract to be used
bac=makeStkContrcat('BAC')
#bac.m_symbol    = 'BAC'
#bac.m_secType   = 'STK'
#bac.m_exchange  = 'SMART'
#bac.m_currency  = 'USD'
eur=makeForexContract('EUR') 
bacFeed         =   LiveFeed(contract=bac,frequency=60,debug=True)
IbBroker        =   MyIbBroker(debug=True)
thomas  =   MyLiveStrategy(LiveBarFeed=bacFeed,broker=IbBroker,debug=True)

thomas.run()

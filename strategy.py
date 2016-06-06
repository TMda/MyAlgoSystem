#!/usr/bin/python
# -*- coding: utf-8 -*-

# strategy.py

from __future__ import print_function
from IbBroker import MyIbBroker
from abc import ABCMeta, abstractmethod
import datetime
try:
    import Queue as queue
except ImportError:
    import queue

import numpy as np
import pandas as pd

from event import SignalEvent
import time



 
class Strategy(object):
    """
    Strategy is an abstract base class providing an interface for
    all subsequent (inherited) strategy handling objects.

    The goal of a (derived) Strategy object is to generate Signal
    objects for particular symbols based on the inputs of Bars 
    (OHLCV) generated by a DataHandler object.

    This is designed to work both with historic and live data as
    the Strategy object is agnostic to where the data came from,
    since it obtains the bar tuples from a queue object.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def onBar(self):
        """
        Provides the mechanisms to calculate the list of signals.
        """
        raise NotImplementedError("Should implement onBar()")

class MyLiveStrategy(Strategy):

    def __init__( self,
                  Ibroker ,contract_list,
                  strategy_name =   'MyLiveStrategy'
                  heartbeat     =   1, 
                  debug         =   False):
        self.strategy_name=strategy_name

        #Contract data stream 
        self.__bar    = LiveBarFeed

        #Building event queue
        self.__events = LiveBarFeed.getEventQueue()


        #Associatint the live Broker
        self.IbBroker=Ibroker
        self.contract_list=contract_list

        self.__heartbeat = heartbeat
        #In case there are initialisation actions to undertake
        self.__initialize()

        if debug == False:
            self.__debug = False
        else:
            self.__debug = True


    def __initialize(self):
        """
        Generates the trading instance objects from 
        their class types.
        """
        print(
            "Initialization completed"
        )

    def run(self):
        """
        Start Live Trading .
        """

        i = 0
        now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print('%s[MyLiveStrategy Super] START LIVE TRADING'%(now,))
        while True:
            i += 1
            print('%s[MyLiveStrategy Super] Entering Great Event loop'%(now,))
            print('%s[MyLiveStrategy Super] Great Event loop counter: %s'%(now,i))

            #print(i)
            # Handle the events Loop
            while True: #Starting the event Loop
                try:
                    event = self.__events.get()
                    print('%s[MyLiveStrategy Super] Removed element from event Queue'%(now,))


                    print('%s[MyLiveStrategy Super] Event type: %s'%(now,event.type))
                    print('%s[MyLiveStrategy Super] bar type %s'%(now,type(event.bar)))
                    print('%s[MyLiveStrategy Super] Event Open: %s'%(now,event.bar.getOpen()))
                    print('%s[MyLiveStrategy Super] Event Close: %s'%(now,event.bar.getClose()))
                    print('%s[MyLiveStrategy Super] Event High: %s'%(now,event.bar.getHigh()))
                    print('%s[MyLiveStrategy Super] Event Low: %s'%(now,event.bar.getLow()))
                    print('%s[MyLiveStrategy Super] Event Volume: %s'%(now,event.bar.getVolume()))
                    if event.type == 'MARKET':
                        priceBar=event.bar
                        print('%s[MyLiveStrategy Super]  %s Pass bar to the strategy'%(now,priceBar))
                        self.onBar(event.bar)
                    else:
                        print('%s[MyLiveStrategy Super] Element type: %s'%(now,event.type))
                        
                except queue.Empty:
                    print('%s[MyLiveStrategy Super] -- Event Queue is Empty'%(now,))
                    break
            time.sleep(1)
    
    def onBar(self,bar):
        """
        Provides the mechanisms to calculate the list of signals.
        """
        
    def getMarketEvent(self):
        return self.__events.get()   

    def createMarketOrder(self, contract,action, quantity, GoodTillCanceled = True,AllOrNone = True):
        self.getBroker().createMarketOrder(contract,action, quantity, GoodTillCanceled = True,AllOrNone = True)

    def createLimitOrder(self, contract, action, limitPrice, quantity,GoodTillCanceled = True,AllOrNone = True):
        self.getBroker().createLimitOrder(contract, action, limitPrice, quantity,GoodTillCanceled = True,AllOrNone = True)
        
    def createStopOrder(self, contract, action, stopPrice, quantity,GoodTillCanceled = True,AllOrNone = True):
        self.getBroker().createStopOrder(contract, action, stopPrice, quantity,GoodTillCanceled = True,AllOrNone = True)

    def createStopLimitOrder(self,contract, action,stopPrice, limitPrice, quantity):
        self.getBroker().createStopLimitOrder(contract, action,stopPrice, limitPrice, quantity)
      
    def cancelOrder(self, order):
        self.__broker.cancelOrder(order)

        

# -*- coding: utf-8 -*-
"""
Created on Thu Jun 02 09:20:05 2016

@author: thoma
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-

# backtest.py

from __future__ import print_function

import datetime

try:
    import Queue as queue
except ImportError:
    import queue
import time


class LiveExecutionContainer(object):
    """
    Enscapsulates the settings and components for carrying out
    an event-driven backtest.
    """

    def __init__(
        self,strategyName, strategy,contract_list,fileOutput=None,
        heartbeat=3
    ):
        """
        Initialises the backtest.

        Parameters:
     
        barFeed - (Class) The list of symbol strings. Handles the market data feed.
        IbBroker - (Class) Handles the orders/fills for trades and Keeps track of portfolio current and prior positions.
        strategy - (Class) Generates signals based on market data.
        """
        
        
        self.strategyName=strategyName
        self.contract_list=contract_list
        self.barFeed  = None
        self.IbBroker = None
        self.strategy = None
        self.strategy_input = strategy
        self.events = queue.Queue()
        
        self.fileOutput=fileOutput
        self.heartbeat=heartbeat
        self.signals = 0
        self.orders = 0
        self.fills = 0
        self.num_strats = 1
       
        self._generate_trading_instances()

    def _generate_trading_instances(self):
        """
        Generates the trading instance objects from 
        their class types.
        """
        from barfeed import LiveIBDataHandler
        from IbBroker import MyIbBroker_last
        print(
            "Creating DataHandler, Strategy, Portfolio and ExecutionHandler"
        )
        self.data_handler = LiveIBDataHandler(
                contract=self.contract_list,
                eventQueue=self.events,
                host="localhost",port=7496,
                warmupBars = 0, debug=False,
                fileOutput=None)
                
        
        self.strategy = self.strategy_input(
                strategyName=self.strategyName,
                Ibroker=MyIbBroker_last(strategy_name=self.strategyName,host="localhost", port=7496, debug=True, clientId = None, event=self.events ),
                contract_list=self.contract_list
        
        
        )
        
        
        
        
 
    def _run_live(self):
        """
        Executes the backtest.
        """
        i = 0
        while True:
            i += 1
            print(i)
            
            # condition to stop the live run, put a file named stop in
            # output
            try:


                fo = open("control_files\\runfile", "r+")
                print("File open")
                order=fo.read()
                fo.close()

                print ("Control Order list: %s" %(order))
                
                print("file split")
                if len(order) in [4,5]:
                    
                    print ("Control Order received : %s" %(order))
                    
                   
                    if order=='STOP':
                        self.strategy.IbBroker.stop()
                        self.data_handler.stop()
                        print ("SYSTEM STOPPED : %s" %(order))
                        break
                else:
                    print("Problem opening the file")
                   
            except Exception as e:
                print(e)
                print("Problem")
                raise
                break
                #raise("Problem")
                #pass
            
            

            # Handle the events
            while True:
                try:
                    event = self.events.get(False)
                except queue.Empty:
                    break
                else:
                    if event is not None:
                        if event.type == 'MARKET':
                            self.strategy.onBar(event.bar)
                            #self.portfolio.update_timeindex(event)

                        elif event.type == 'SIGNAL':
                            self.signals += 1                            
                            #self.portfolio.update_signal(event)

                        elif event.type == 'ORDER':
                            self.orders += 1
                            #self.execution_handler.execute_order(event)

                        elif event.type == 'FILL':
                            self.fills += 1
                            #self.portfolio.update_fill(event)

            time.sleep(self.heartbeat)
    """
    def _output_performance(self):
        
        #Outputs the strategy performance from the backtest.
        
        self.portfolio.create_equity_curve_dataframe()
        
        print("Creating summary stats...")
        stats = self.portfolio.output_summary_stats()
        
        print("Creating equity curve...")
        print(self.portfolio.equity_curve.tail(10))
        pprint.pprint(stats)

        print("Signals: %s" % self.signals)
        print("Orders: %s" % self.orders)
        print("Fills: %s" % self.fills)
    """
    def run(self):
        """
        Simulates the backtest and outputs portfolio performance.
        """
        self._run_live()
        #self._output_performance()

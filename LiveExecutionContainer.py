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
import pprint
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
        self, barfeed, IbBroker,strategy,contract_list
    ):
        """
        Initialises the backtest.

        Parameters:
     
        barFeed - (Class) The list of symbol strings. Handles the market data feed.
        IbBroker - (Class) Handles the orders/fills for trades and Keeps track of portfolio current and prior positions.
        strategy - (Class) Generates signals based on market data.
        """
        
        
       
        self.contract_list=contract_list
        self.barFeed = data_handler
        self.IbBroker = execution_handler
        self.strategy_cls = strategy
        self.events = queue.Queue()
    
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
        print(
            "Creating DataHandler, Strategy, Portfolio and ExecutionHandler"
        )
        self.data_handler = self.data_handler_cls(
                contract=self.contract_list,
                frequency=60,
                eventQueue=self.events,
                identifiers=None,
                host="localhost",port=7496,
                warmupBars = 0, debug=False,
                fileOutput=None)
        self.IbBroker_handler=self.IbBroker(
                host="localhost", port=7496, 
                debug=False, clientId = None, event=None        
        
        )
        self.strategy = self.strategy_cls(
                LiveBarFeed=self.data_handler,
                broker=self.IbBroker_handler,
                debug=True        
        
        )
 
    def _run_backtest(self):
        """
        Executes the backtest.
        """
        i = 0
        while True:
            i += 1
            print(i)
            # Update the market bars
            if self.data_handler.continue_backtest == True:
                self.data_handler.update_bars()
            else:
                break

            # Handle the events
            while True:
                try:
                    event = self.events.get(False)
                except queue.Empty:
                    break
                else:
                    if event is not None:
                        if event.type == 'MARKET':
                            self.strategy.calculate_signals(event)
                            self.portfolio.update_timeindex(event)

                        elif event.type == 'SIGNAL':
                            self.signals += 1                            
                            self.portfolio.update_signal(event)

                        elif event.type == 'ORDER':
                            self.orders += 1
                            self.execution_handler.execute_order(event)

                        elif event.type == 'FILL':
                            self.fills += 1
                            self.portfolio.update_fill(event)

            time.sleep(self.heartbeat)

    def _output_performance(self):
        """
        Outputs the strategy performance from the backtest.
        """
        self.portfolio.create_equity_curve_dataframe()
        
        print("Creating summary stats...")
        stats = self.portfolio.output_summary_stats()
        
        print("Creating equity curve...")
        print(self.portfolio.equity_curve.tail(10))
        pprint.pprint(stats)

        print("Signals: %s" % self.signals)
        print("Orders: %s" % self.orders)
        print("Fills: %s" % self.fills)

    def run(self):
        """
        Simulates the backtest and outputs portfolio performance.
        """
        self._run_backtest()
        self._output_performance()

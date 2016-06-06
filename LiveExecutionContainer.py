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

    def __init__(self,
        strategy_name,  # strategy name
        strategy,       #Strategy class
        contract_list,  #list of contract 
        dir_Output      =   None,#path to the output directory
        heartbeat       =   1 ,    #heartbeat
        debug_data_feed =   False,
        debug_broker    =   False,
    ):
        """
        Initialises the Live Execution Container.
        The container wrap a strategy a broker and a data feed for running
        a live strategy.

        Parameters:
        strategy_name   - (string)strategy name
        strategy        - (Class) Generates signals based on market data.
        contract_list   - (list) of ib contract class used by the strategy
        dir_Output      - (string) path to the output directory, where the strategy output its results
        heartbeat       - (int) heartbeat        
        debug_data_feed - (Bool) display debug message for data feed
        debug_broker    - (Bool) display message for broker 

        """
        # associate input to class variables
        self.strategy_name      =   strategy_name
        self.strategy_input     =   strategy
        self.contract_list      =   contract_list
        if dir_Output   ==  None:
            self.dir_Output      =    'output\\'
        else:
            self.dir_Output =   dir_Output
        self.heartbeat          =   heartbeat
        self.debug_data_feed    =   debug_data_feed
        self.debug_broker       =   debug_broker
        #initialize class varibale 
        self.events             =   queue.Queue() # internal queue use to pass data bar between datafeed and strategy  
        self.IbBroker           =   None # internal broker that pushes command to IB and manage execution
        self.strategy           =   None # instancied strategy class 
        self.signals            =   0    # num
       
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
        self.data_handler   =   LiveIBDataHandler(
                                    contract    =   self.contract_list,
                                    eventQueue  =   self.events,
                                    host        =   "localhost",
                                    port        =   7496,
                                    warmupBars  =   0, 
                                    debug       =   self.debug_data_feed,
                                    fileOutput  =   None)
                
        TheIbroker          =   MyIbBroker_last(
                                    strategy_name   =   self.strategy_name,
                                    host            =   "localhost", 
                                    port            =   7496, 
                                    debug           =   self.debug_broker , 
                                    clientId        =   None, 
                                    event           =   self.events )
        
        self.strategy       =   self.strategy_input(
                                    strategy_name    =  self.strategy_name,
                                    Ibroker          =  TheIbroker,
                                    contract_list    =  self.contract_list,
        )
        
        try:
            #print (type(self.strategy.IbBroker.getInitialOrders()))
            #print (self.strategy.IbBroker.getInitialOrders())
            #/function tested/
            self.strategy.IbBroker.getInitialOrders().to_csv(self.dir_Output+"InitialOrders.csv")
            self.output()
            self.strategy.IbBroker.getInitialOrders().to_sql(self.dir_Output+'myalgo',flavor='sqlite', if_exists='replace')
        except Exception as e:
            print (e)
            print ("Live Excecution Container Error output initial performances")
 
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


                fo      =   open("control_files\\runfile", "r")
                #print("File open")
                order   =   fo.read()
                fo.close()

                #print ("Control Order list: %s" %(order))
                
                if len(order) in [4,5]:
                    
                    #print ("Control Order received : %s" %(order))
                    
                   
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
            
            try:
                self.output()
            except Exception as e:
                print(e)
                print("Problem outputting strategy performances")
            

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
    def output(self):
        #self.portfolio.update_timeindex(event)
        
        
        cash    =   self.strategy.IbBroker.getCash()
        f       =   open(self.dir_Output+"cash","w")
        f.write(str(cash))
        f.close()
        
        #/ function tested/
        #print("Active Positions: ")
        #print (type(self.strategy.IbBroker.getActivePositions()))
        #print (self.strategy.IbBroker.getActivePositions())
        self.strategy.IbBroker.getActivePositions().to_csv(self.dir_Output+"ActivePositions.csv")
        self.strategy.IbBroker.getActivePositions().to_sql(self.dir_Output+'myalgo',flavor='sqlite', if_exists='replace')
        #/Function to test in production
#        print("Positions History: ")
#        print (type(self.strategy.IbBroker.getPositionsHistory()))
#        print (self.strategy.IbBroker.getPositionsHistory())
        self.strategy.IbBroker.getPositionsHistory().to_csv(self.dir_Output+"PositionsHistory.csv")
        self.strategy.IbBroker.getPositionsHistory().to_sql(self.dir_Output+'myalgo',flavor='sqlite',  if_exists='replace')
        #/Function to test in production
        #print("Active Orders: ")
        #print (type(self.strategy.IbBroker.getActiveOrders()))
        self.strategy.IbBroker.getActiveOrders().to_csv(self.dir_Output+"ActiveOrders.csv")
        self.strategy.IbBroker.getActiveOrders().to_sql(self.dir_Output+'myalgo',flavor='sqlite',  if_exists='replace')
        print("Filled Order: ")
        print (type(self.strategy.IbBroker.getFilledOrders()))
        print (self.strategy.IbBroker.getFilledOrders())
        self.strategy.IbBroker.getFilledOrders().to_csv(self.dir_Output+"FilledOrders.csv")
        self.strategy.IbBroker.getFilledOrders().to_sql(self.dir_Output+'myalgo',flavor='sqlite', if_exists='replace')
        #/Function to test in production
        #print("Order History: ")
        #print (type(self.strategy.IbBroker.getOrdersHistory()))
        #print (self.strategy.IbBroker.getOrdersHistory())
        self.strategy.IbBroker.getOrdersHistory().to_csv(self.dir_Output+"OrdersHistory.csv")
        self.strategy.IbBroker.getOrdersHistory().to_sql(self.dir_Output+'myalgo',flavor='sqlite',  if_exists='replace')


       

        

        

        
   
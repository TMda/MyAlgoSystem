#
from __future__ import print_function
from ib.ext import Contract
from ib.ext import Order
import time
from ib.opt import ibConnection, message
import random
import datetime as dat
import datetime
import datetime as dt
from math import floor
try:
    import Queue as queue
except ImportError:
    import queue

import numpy as np
import pandas as pd

from lib.ElasticSearch import loadIntoEsIndex
from event import MarketEvent
from performance import create_sharpe_ratio, create_drawdowns

#%%

class MyIbBroker_last():
    def __init__(self, host             =   "localhost", 
                       port             =   7496, 
                       debug            =   False,      #Display debug messages
                       clientId         =   None,       #Client ID for the broker
                       event            =   None,       #Event Queue
                       dir_Output       =   None,
                       strategy_name    =   'ANO'):     #Strategy Name

        self.__stop         =   False

        if debug            ==  False:
            self.__debug    =   False
        else:
            self.__debug    =   True

        if dir_Output   ==  None:
            self.dir_Output      =    'output\\'
        else:
            self.dir_Output =   dir_Output
        ###Connection to IB
        if event != None:
            self.event  =   event
        else:
            self.event  =   queue.Queue()
        # Interactive Broker Connection
        self.strategy_name      =   strategy_name
        self.connectionTime     =   None
        self.serverVersion      =   None
        self.clientId           =   clientId
        self.host               =   host
        self.port               =   port
        self.clienId            =   clientId
        self.__IbConnect() 

        # Order Management
        orderColumn =   [
            'datetime'                  ,   'status',
            'contract_code'             ,   'FilledQuantitiy',   
            'avgFillPrice'              ,   'ibContract_m_symbol',   
            'ibContract_m_secType'      ,
            'ibContract_m_currency'     ,   'ibContract_m_exchange',
            'ibContract_m_multiplier'   ,   'ibContract_m_expiry',
            'ibContract_m_strike'       ,   'ibContract_m_right',
            'ibOrder_m_orderId'         ,   'ibOrder_m_clientId',
            'ibOrder_m_permid'          ,   'ibOrder_m_action',
            'ibOrder_m_lmtPrice'        ,   'ibOrder_m_auxPrice',
            'ibOrder_m_tif'             ,   'ibOrder_m_transmit',
            'ibOrder_m_orderType'       ,   'ibOrder_m_totalQuantity',
            'ibOrder_m_parentId'        ,   'ibOrder_m_trailStopPrice',
            'ibOrder_m_trailingPercent' ,   'ibOrder_m_allOrNone',
            'remaining'                 ,   'lastFillPrice',
            'openOrderYesNo',
            ]
        self.orderColumn                =   orderColumn
        self.__initialOrders            =   pd.DataFrame(   columns    =   self.orderColumn    )
        self.__activeOrders             =   pd.DataFrame(   columns    =   self.orderColumn  ) #Order not yet fully or partially filled
        self.__ordersHistory            =   pd.DataFrame(   columns    =   self.orderColumn  )  #keep history of order life
        self.__ordersFilled             =   pd.DataFrame(   columns    =   self.orderColumn  )  #keep history of Filled order
        
                     
        #Position Management
        #2016-02-04 11:17:10[IB LiveBroker __portfolioHandler] <updatePortfolio contract=<ib.ext.Contract.Contract object at 0x00000000088E2FD0>, position=300, marketPrice=0.31, marketValue=9300.0, averageCost=31.2674, unrealizedPNL=-80.22, realizedPNL=0.0, accountName=DU213041>
        activePositionColumn=[
            'datetime'                  ,   'contract_code',
            'ibContract_m_symbol'       ,   'ibContract_m_secType',
            'ibContract_m_currency'     ,   'ibContract_m_exchange',
            'ibContract_m_multiplier'   ,   'ibContract_m_expiry' ,
            'ibContract_m_strike'       ,   'ibContract_m_right',
            'position'                  ,   'marketPrice',
            'marketValue'               ,   'averageCost',
            'unrealizedPNL'             ,   'realizedPNL',
            'accountName'               ,   'strategy_name',   
            'run_number'                ,         
            ]
        self.__activePositions      =   pd.DataFrame(   columns    =   activePositionColumn    ) #contract,position, market value
        #self.__detailedActivePositions = {}#entry price, average price etc...
        self.__positionsHistory     =   pd.DataFrame(   columns    =   activePositionColumn    )
        
        #Order Execution Management 
        execuColumn=['datetime'
                'ibExecution_m_orderId'     ,   'ibExecution_m_execId',
                'ibExecution_m_acctNumber'  ,   'ibExecution_m_clientId',
                'ibExecution_m_liquidation' ,   'ibExecution_m_permId',
                'ibExecution_m_price'       ,   'ibExecution_m_evMultiplier',
                'ibExecution_m_avgPrice'    ,   'ibExecution_m_evRule',  
                'ibExecution_m_cumQty'      ,   'ibExecution_m_shares',
                'ibOrder_m_auxPrice'        ,   'ibExecution_m_side',
                'ibExecution_m_time'        ,   'ibExecution_m_exchange' 
                ]
        self.__executionsHistory    =   pd.DataFrame(  columns   =   execuColumn   )

        #Cash Management
        self.__cash                 =   0
        
        #Next order id 
        self.__nextOrderId          =   0
        
        #order information available for the strategy to check if order has been submitted
        self.submittedOrder      =   {
                    'contract_code'  :   None,
                    'order_id'       :   None,
                    'executed'       :   None,
                    'totalQuantity'  :   None,
                    'FilledQuantitiy':   None,
                    'avgFillPrice'   :   None,
                    'lastFillPrice'  :   None,
                    'remaining'      :   None,
        
        }
        #information information available to the strategy to know what is pnl information for each contract
        self.overalPosition    =   { }
        #Get the run number that will differentiate every strategy run in ES DB
        self.run_number             =   None
        self.getRunNumber()
        
        #Request initial account balance
        self.refreshAccountBalance()
        
        # Request current open order in the system
        self.refreshOpenOrders()
        
        # Request all positions outstanding
        self.__ib.reqPositions()
        
        #give ib time to get back to us
        time.sleep(2)
    def __IbConnect(self):
        if self.clientId == None:
            clientId = random.randint(1000,10000)
            if self.__debug:
                now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                print('%s[IB LiveBroker __init__ ]Client ID: %s' % (now,clientId))
        else:
            clientId=self.clienId

        self.__ib = ibConnection(host=self.host,port=self.port,clientId=clientId)
        #register all the callback handlers
        #self.__ib.registerAll(self.__debugHandler)
        self.__ib.registerAll(self.__debugHandler)
        self.__ib.register(self.__accountHandler,       'UpdateAccountValue')
        self.__ib.register(self.__portfolioHandler,     'UpdatePortfolio')
        self.__ib.register(self.__openOrderHandler,     'OpenOrder')
        #self.__ib.register(self.__positionHandler,     'Position')
        self.__ib.register(self.__disconnectHandler,    'ConnectionClosed')
        self.__ib.register(self.__nextIdHandler,        'NextValidId')
        self.__ib.register(self.__orderStatusHandler,   'OrderStatus')
        self.__ib.register(self.__error_handler         , 'Error')
        
        self.__ib.connect()
        if self.__ib.isConnected():
            self.connectionTime=self.__ib.reqCurrentTime()
            self.serverVersion=self.__ib.serverVersion()
            if self.__debug:
                print('%s[MyIbBroker_last]********************************'%(now,))
                print('%s[MyIbBroker_last]Connection to IB established'%(now,))
                print('%s[MyIbBroker_last]IB server connection time: %s' %(now,self.connectionTime))
                print('%s[MyIbBroker_last]IB server version: %s' %(now,self.serverVersion))
                
        else:
            print('[MyIbBroker_last] Connection to IB Error')
            raise('[MyIbBroker_last] Connection to IB Error')
        ### End Connection to IB 
        return
    def getRunNumber(self):
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print('%s[MyIbBroker_last __getRunNumber]********************************'%(now,))
            print('%s[MyIbBroker_last __getRunNumber]Get run number'%(now,))

        try:
            with open("control_files\\run_number","r") as fo:
                #if self.__debug:
                #    print('%s[MyIbBroker_last __getRunNumber] File Opened: %s'%(now,fo))
                order_number=fo.read().split()
                fo.close()
                #if self.__debug:
                #    print('%s[MyIbBroker_last __getRunNumber] File containt list: %s'%(now,order_number))

                if len(order_number)==1:
                    try:
                        order=int(order_number[0])
                 #       if self.__debug:
                 #           print('%s[MyIbBroker_last __getRunNumber] Run number: %s'%(now,order))
                        
                        self.run_number=order
                        if self.__debug:
                            print('%s[MyIbBroker_last __getRunNumber] self Run number: %s'%(now,self.run_number))

                        order +=1
                #        if self.__debug:
                #            print('%s[MyIbBroker_last __getRunNumber] increased Run number: %s'%(now,order))
                        order=str(order)
                #        if self.__debug:
                #            print('%s[MyIbBroker_last __getRunNumber] type (order): %s'%(now,type(order)))

                        f=open("control_files\\run_number","w")
                #        if self.__debug:
                #            print('%s[MyIbBroker_last __getRunNumber] writing file opened'%(now,))

                        f.write(str(order))
                #        if self.__debug:
                #            print('%s[MyIbBroker_last __getRunNumber] File wrote'%(now,))
                        
                        f.close()
                        if self.__debug:
                            print('%s[MyIbBroker_last __getRunNumber] Increased number written in the file:'%(now,))
                        
                        return
                    except Exception as e:
                        #print(e)
                        raise("[MyIbBroker_last __getRunNumber] END File control_files/run_number must have an integer number in it")
        except  :
            #print(Exception)
            raise("[MyIbBroker_last __getRunNumber]File control_files/run_number must exist")
    # BEGIN FEEDBACK HANDLER
    def __error_handler(self,msg):
        """Handles the capturing of error messages"""
        
        if self.__debug: 
            print("Server Error: %s" % msg)
    def __accountHandler(self,msg):
        #FYI this is not necessarily USD - probably AUD for me as it's the base currency so if you're buying international stocks need to keep this in mind
        #self.__cash = round(balance.getUSDAvailable(), 2)
        if msg.key == 'TotalCashBalance' and msg.currency == 'USD':
            self.__cash = round(float(msg.value))
    def __disconnectHandler(self,msg):
        self.__ib.reconnect()
    def __debugHandler(self,msg):
        
        if self.__debug: 
            #print (msg)
            return
    def __nextIdHandler(self,msg):
        self.__nextOrderId = msg.orderId
        return
    def __createOrder(self,
        datetime        =   datetime.datetime.now(),
        ibContract      =   None,
        ibOrder         =   None,
        status          =   None,
        FilledQuantitiy =   None,
        avgFillPrice    =   None,
        openOrderYesNo  =   None,
        remaining       =   None,
        lastFillPrice   =   None):

        now                 =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
            print ('%s[MyIbBroker_last __createOrder] BEGIN********__createOrder *****************' % (now,))

        """
        Create an order Pandas Series  that can be inserted into the ActiveOrder or orderHistory PD dataframes
        Return - PD Series
        """
        if(ibOrder.m_orderId is None):
            print('%s[MyIbBroker_last __createOrder] Order must have ibOrder_m_orderId not null'%(now))
            if self.__debug:
                print ('%s[MyIbBroker_last __createOrder] END********__createOrder *****************' % (now,))
            return
            
        dico    =   {
          'datetime'                :   datetime,
          'status'                  :   status,
          'contract_code'           :   self.buildContractRepresentation(ibContract),
          'FilledQuantitiy'         :   FilledQuantitiy, 
          'avgFillPrice'            :   avgFillPrice,
          'ibContract_m_symbol'     :   ibContract.m_symbol, 
          'ibContract_m_secType'    :   ibContract.m_secType, 
          'ibContract_m_currency'   :   ibContract.m_currency, 
          'ibContract_m_exchange'   :   ibContract.m_exchange, 
          'ibContract_m_multiplier' :   ibContract.m_multiplier, 
          'ibContract_m_expiry'     :   ibContract.m_expiry, 
          'ibContract_m_strike'     :   ibContract.m_strike, 
          'ibContract_m_right'      :   ibContract.m_right, 
          'ibOrder_m_orderId'       :   ibOrder.m_orderId, 
          'ibOrder_m_clientId'      :   ibOrder.m_clientId, 
          'ibOrder_m_permid'        :   None, 
          'ibOrder_m_action'        :   ibOrder.m_action, 
          'ibOrder_m_lmtPrice'      :   ibOrder.m_lmtPrice, 
          'ibOrder_m_auxPrice'      :   ibOrder.m_auxPrice, 
          'ibOrder_m_tif'           :   ibOrder.m_tif, 
          'ibOrder_m_transmit'      :   ibOrder.m_transmit, 
          'ibOrder_m_orderType'     :   ibOrder.m_orderType, 
          'ibOrder_m_totalQuantity' :   ibOrder.m_totalQuantity, 
          'ibOrder_m_parentId'      :   ibOrder.m_parentId, 
          'ibOrder_m_trailStopPrice':   ibOrder.m_trailStopPrice, 
          'ibOrder_m_trailingPercent':  ibOrder.m_trailingPercent, 
          'ibOrder_m_allOrNone'     :   ibOrder.m_allOrNone, 
          'remaining'               :   remaining,
          'lastFillPrice'           :   lastFillPrice,
          'openOrderYesNo'          :   openOrderYesNo,
        }  
        if self.__debug:
            print('%s[MyIbBroker_last __createOrder]  Order created sucssfully'%(now))
            print ('%s[MyIbBroker_last __createOrder] END********__createOrder *****************' % (now,))
        return pd.Series(dico)
        
    def __registerOrder(self, order,raison='GENERATED'):
    
        now                 =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            exist=self.__activeOrders.empty
            exist= True
        except Exception as e:
            print(e)
            exist=False
        
        if self.__debug:
            print ('%s[MyIbBroker_last __registerOrder] BEGIN********__registerOrder *****************' % (now,))
        """
        if (type(order)== pd.Series) :
            if self.__debug:
                print ('%s[MyIbBroker_last __registerOrder] ERROR Order must be a pd.Series' % (now,))
                print('[%s[MyIbBroker_last __registerOrder] Order received by the function: \n %s'% (now,order))
                print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
            return
        """
        if exist == False :
            self.__activeOrders             =   pd.DataFrame(   columns    =   self.orderColumn  ) #Order not yet fully or partially filled
            if self.__debug:
                print ('%s[MyIbBroker_last __registerOrder] self.__activeOrders was null - Recreated it' % (now,))
 
            
        if order['ibOrder_m_orderId'] == None : 
            if self.__debug:
                print ('%s[MyIbBroker_last __registerOrder] ERROR Order must have ibOrder_m_orderId not null' % (now,))
                print('[%s[MyIbBroker_last __registerOrder] Order received by the function: \n %s'% (now,order))
                print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
            return

        #need to make sure order doesn't overwrite as we may lose information
        if (int(order['ibOrder_m_orderId']) in self.__activeOrders.index):
            if sel.__debug:
                print('[%s[MyIbBroker_last __registerOrder] ERROR Order ID already exist in __activeOrders table'% (now,))
                print('[%s[MyIbBroker_last __registerOrder] Order received by the function: \n %s'% (now,order))
                print('[%s[MyIbBroker_last __registerOrder] Order from ACTIVE ORDER table with same ID: \n %s'% (now,self.__activeOrders.loc[int(order['ibOrder_m_orderId'])]))
                print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
            return

        order['status']         =   raison
        order['datetime']       =   now
        order['openOrderYesNo'] =   True
        
        try:
            self.__activeOrders.loc[int(order['ibOrder_m_orderId'])] =   order
            try:
                self.__ordersHistory                                 =   self.__ordersHistory.append(order, ignore_index =   True)
                try:
                    self.__activeOrders.to_csv(self.dir_Output+"ActiveOrders.csv")
                    self.__ordersHistory.to_csv(self.dir_Output+"OrdersHistory.csv")
                    if self.__debug:
                        #print ('%s[MyIbBroker_last __registerOrder] Order received by the function:' % (now,))
                        #print ('%s[MyIbBroker_last __registerOrder] %s' % (now,order))
                        #print ('%s[MyIbBroker_last __registerOrder] ACTIVE ORDER table with added order:' % (now,))
                        #print ('%s' % (self.__activeOrders))
                        #print ('%s[MyIbBroker_last __registerOrder] HISTORY ORDER table:' % (now,))
                        #print ('%s' % (self.__ordersHistory))
                        print ('%s[MyIbBroker_last __registerOrder] Order registered sucssfuly and output Order csv'%(now,))
                        print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
                    return
                except Exception as e:    
                    if self.__debug:
                        print ('%s[MyIbBroker_last __registerOrder] >>>ERROR OUTPUT TO CSV :' % (now,))
                        print ('%s[MyIbBroker_last __registerOrder] %s' % (now,e))
                        print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
                    return

            except Exception as e:    
                if self.__debug:
                    print ('%s[MyIbBroker_last __registerOrder] >>>ERROR self.__ordersHistory.append :' % (now,))
                    print ('%s[MyIbBroker_last __registerOrder] %s' % (now,e))
                    print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
                return
        except Exception as e:    
            if self.__debug:
                print ('%s[MyIbBroker_last __registerOrder] >>>ERROR self.__activeOrders.loc[int(order[ibOrder_m_orderId])] =   order :' % (now,))
                print ('%s[MyIbBroker_last __registerOrder] %s' % (now,e))
                print ('%s[MyIbBroker_last __registerOrder] END********__registerOrder *****************' % (now,)) 
            return
    def __unregisterOrder(self, order,raison):
        #assert(type(order) is pd.Series) ,'[_unregisterOrder] Order must be a pd.Series'
        #assert(order['ibOrder_m_orderId'] in self.__activeOrders.index),'[_unregisterOrder] Order to unregister does not exist in __activeOrders table'
        #assert(order['ibOrder_m_orderId'] is not None),'[_unregisterOrder] Order must be a pd.Series'
        now                 =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
            print ('%s[MyIbBroker_last __unregisterOrder] BEGIN********__unregisterOrder *****************' % (now,))
        
        try:
            exist = self.__activeOrders.empty
            exist = True
        
        except Exception as e:
            print(e)
            exist == False
        if exist == False:
            self.__activeOrders             =   pd.DataFrame(   columns    =   self.orderColumn  ) #Order not yet fully or partially filled
            if self.__debug:
                print ('%s[MyIbBroker_last __unregisterOrder] self.__activeOrders was null - Recreated it' % (now,))
        

        try:
            order['status']         =   raison
            order['datetime']       =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            order['openOrderYesNo'] =   False
        
            self.__activeOrders =   self.__activeOrders.drop(order['ibOrder_m_orderId'],inplace=True)
            if self.__debug:
                #print ('%s[MyIbBroker_last __unregisterOrder] Order to remove from ACTIVE ORDER table:' % (now,))
                #print ('%s[MyIbBroker_last __unregisterOrder] %s' % (now,order))
                #print ('%s[MyIbBroker_last __unregisterOrder] ACTIVE ORDER table with removed order:' % (now,))
                #print ('%s' % (self.__activeOrders))
                pass
                    
            if raison   ==  'FILLED':
                self.__ordersFilled.loc[int(order['ibOrder_m_orderId'])] = order
                if self.__debug:
                    print ('%s[MyIbBroker_last __unregisterOrder] Order added to the FILLED ORDER' % (now,))
                    #print ('%s' % (self.__ordersFilled))
            try:
                self.__ordersHistory    =   self.__ordersHistory.append(pd.Series(order),ignore_index=True)
                try:
                    if exist:
                        self.__activeOrders.to_csv(self.dir_Output+"ActiveOrders.csv")
                    self.__ordersHistory.to_csv(self.dir_Output+"OrdersHistory.csv")
                    self.__ordersFilled.to_csv(self.dir_Output+"FilledOrders.csv")
                    if self.__debug:
                        #print ('%s[MyIbBroker_last __unregisterOrder] HISTORY ORDER table:' % (now,))
                        #print ('%s' % (self.__ordersHistory))
                        print ('%s[MyIbBroker_last __unregisterOrder] ORDER Unregistered sucssfully and table csv output:' % (now,))
                        print ('%s[MyIbBroker_last __unregisterOrder] END********__unregisterOrder *****************' % (now,))
                        return
                except Exception as e:
                    if self.__debug:
                        print ('%s[MyIbBroker_last __unregisterOrder] ERROR OUTPUT TO CSV:' % (now,))
                        print('[%s[MyIbBroker_last __unregisterOrder] %s'% (now,e))
                        print ('%s[MyIbBroker_last __unregisterOrder] END********__unregisterOrder *****************' % (now,)) 
                    return
                        
            except Exception as e:
                if self.__debug:
                    print ('%s[MyIbBroker_last __unregisterOrder] ERROR self.__ordersHistory.append(pd.Series(order):' % (now,))
                    print('[%s[MyIbBroker_last __unregisterOrder] %s'% (now,e))
                    print ('%s[MyIbBroker_last __unregisterOrder] END********__unregisterOrder *****************' % (now,)) 
                return
 
        except Exception as e:
            if self.__debug:
                print ('%s[MyIbBroker_last __unregisterOrder] ERROR unregistering Order :' % (now,))
                print('[%s[MyIbBroker_last __unregisterOrder] %s'% (now,e))
                print ('%s[MyIbBroker_last __unregisterOrder] END********__unregisterOrder *****************' % (now,)) 
            return
        
    def __updateActiveOrder(self,order):
        """
        Input Pd Series Order
        """
        now                 =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
            print ('%s[MyIbBroker_last __updateActiveOrder] BEGIN********__updateActiveOrder *****************' % (now,))
        """
        if (type(order) == pd.Series) :
            if self.__debug:
                print ('%s[MyIbBroker_last __updateActiveOrder] ERROR Order must be a pd.Series' % (now,))
                print('[%s[MyIbBroker_last __updateActiveOrder] Order received by the function: \n %s'% (now,order))
                print ('%s[MyIbBroker_last __updateActiveOrder] END********__updateActiveOrder *****************' % (now,)) 
            return
        """
        if self.__activeOrders == None:
            self.__activeOrders             =   pd.DataFrame(   columns    =   self.orderColumn  ) #Order not yet fully or partially filled
            if self.__debug:
                print ('%s[MyIbBroker_last __updateActiveOrder] self.__activeOrders was null - Recreated it' % (now,))

        if (order['ibOrder_m_orderId'] is None) : 
            if self.__debug:
                print ('%s[MyIbBroker_last __updateActiveOrder] ERROR Order must have ibOrder_m_orderId can not be null' % (now,))
                print('[%s[MyIbBroker_last __updateActiveOrder] Order received by the function: \n %s'% (now,order))
                print ('%s[MyIbBroker_last __updateActiveOrder] END********__updateActiveOrder *****************' % (now,)) 
            return

        #need to make sure order doesn't overwrite as we may lose information
        if (order['ibOrder_m_orderId'] not in self.__activeOrders.index):
            if self.__debug:
                print('[%s[MyIbBroker_last __updateActiveOrder] ERROR Order ID must be in __activeOrders table'% (now,))
                print('[%s[MyIbBroker_last __updateActiveOrder] Order received by the function: \n %s'% (now,order))
                print('[%s[MyIbBroker_last __updateActiveOrder] ACTIVE ORDER table:\n %s'% (now,self.__activeOrders))
                print ('%s[MyIbBroker_last __updateActiveOrder] END********__updateActiveOrder *****************' % (now,)) 
            return
        try:
            order['datetime']                                        =   now
            self.__activeOrders.loc[int(order['ibOrder_m_orderId'])] =   order
            self.__ordersHistory                                     =   self.__ordersHistory.append(order,ignore_index=True)
            
            self.__activeOrders.to_csv(self.dir_Output+"ActiveOrders.csv")
            self.__ordersHistory.to_csv(self.dir_Output+"OrdersHistory.csv")
            

            if self.__debug:
                #print ('%s[MyIbBroker_last __updateActiveOrder] Order to update in ACTIVE ORDER table:' % (now,))
                #print ('%s[MyIbBroker_last __updateActiveOrder] %s' % (now,order))
                #print ('%s[MyIbBroker_last __updateActiveOrder] ACTIVE ORDER table with updated order:' % (now,))
                #print ('%s' % (self.__activeOrders))
                #print('[%s[MyIbBroker_last __updateActiveOrder] HISTORY ORDER table with added order:' % (now,))
                #print ('%s' % (self.__ordersHistory))
                print ('%s[MyIbBroker_last __unregisterOrder] ORDER updated and table csv output:' % (now,))
                print ('%s[MyIbBroker_last __updateActiveOrder] END********__updateActiveOrder *****************' % (now,)) 
            return
        except Exception as e:
            if self.__debug:
                print ('%s[MyIbBroker_last __updateActiveOrder] ERROR __updateActiveOrder Order :' % (now,))
                print('[%s[MyIbBroker_last __updateActiveOrder] %s'% (now,e))
                print ('%s[MyIbBroker_last __updateActiveOrder] END********__updateActiveOrder *****************' % (now,)) 
            return
    def __getActiveOrder(self,orderId):
        """
        return a pd Series, that can be used as a dictionary
        """
        now                 =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
            #print ('%s[MyIbBroker_last __getActiveOrder] BEGIN********__getActiveOrder *****************' % (now,))
            #print ('%s[MyIbBroker_last __getActiveOrder] Number to check :%s' %(now,orderId) )
            #print ('%s[MyIbBroker_last __getActiveOrder] Index :%s' %(now,self.__activeOrders.index) )
            #print ('%s[MyIbBroker_last __getActiveOrder] END*******__getActiveOrder *****************' % (now,))
            pass
        
        return self.__activeOrders.loc[int(orderId)] 

    def __createExecution(self,msg):
        """
        Return an Execution details pandas Series that can be inserted in __executionsHistory DataFrame
        """
        #msg.orderId,msg.avgFillPrice, abs(msg.filled), 0, datetime.datetime.now()

        ibContract=msg.contract
        ibExecution=msg.execution
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rxDict={
                'datetime':now,
                'ibOrder_m_orderId': ibExecution.m_orderId,
                'ibExecution_m_execId':ibExecution.m_execId,
                'ibExecution_m_acctNumber':ibExecution.m_acctNumber,
                'ibExecution_m_clientId'  : ibExecution.m_clientId,
                'ibExecution_m_liquidation':ibExecution.m_liquidation,
                'ibExecution_m_permId': ibExecution.m_permId,
                'ibExecution_m_price' : ibExecution.m_price,
                'ibExecution_m_evMultiplier' : ibExecution.m_evMultiplier,
                'ibExecution_m_avgPrice' : ibExecution.m_avgPrice,
                'ibExecution_m_evRule' :  ibExecution.m_evRule,
                'ibExecution_m_cumQty' :  ibExecution.m_cumQty,
                'ibExecution_m_shares' : ibExecution.m_shares,
                'ibExecution_m_side':ibExecution.m_side,
                'ibExecution_m_time':ibExecution.m_time,
                'ibExecution_m_exchange':ibExecution.m_exchange

                }
        return pd.Series(rxDict)
    def __orderStatusHandler(self,msg):
        """
        Feedback handler managing OrderStatus Messages
        """
        # <orderStatus orderId=5, status=PreSubmitted, 
        #filled=0, remaining=10, avgFillPrice=0.0, permId=745610442,
        #parentId=0, lastFillPrice=0.0, clientId=2457, whyHeld=locate>
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print ('%s[MyIbBroker_last __orderStatusHandler] BEGIN********__orderStatusHandler *****************' % (now,))
            print ('%s[MyIbBroker_last __orderStatusHandler] Message received from Server:' % (now,))
            print ('%s[MyIbBroker_last __orderStatusHandler]................................................'%(now,))
            print ('%s[MyIbBroker_last __orderStatusHandler] %s' %(now,msg))
            print ('%s[MyIbBroker_last __orderStatusHandler]................................................'%(now,))
        try:   
            order = self.__getActiveOrder(int(msg.orderId))
        except Exception as e:

            if self.__debug:
                print ('%s[MyIbBroker_last __orderStatusHandler] ERROR GETTING ORDER FROM ACTIVE ORDER TABLE:' % (now,))
                print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,e))
                print ('%s[MyIbBroker_last __orderStatusHandler]................................................'%(now,))
                print ('%s[MyIbBroker_last __orderStatusHandler] There was no active Order retrieved from __activeOrder table or table empty :' % (now,))
                print ('%s[MyIbBroker_last __orderStatusHandler] Open Order Not in Active Order, probably Already Filled or open order from previous session,Cancell it if not necessary anymore'%(now,))
                #print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,order))
                #print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,self.__activeOrders))
                print ('%s[MyIbBroker_last __orderStatusHandler] This is not a response from an active order submitted during this session - Open order should handle it'%(now,))
                print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
                return 
        
       
        if msg.status == 'Filled' and order['status'] != 'FILLED':
            order['status']         =   'FILLED'
            order['avgFillPrice']   =   msg.avgFillPrice
            order['FilledQuantitiy']=   abs(msg.filled)
            order['remaining']      =   abs(msg.remaining)
            order['lastFillPrice']  =   msg.lastFillPrice
            order['openOrderYesNo'] =   False
            if msg.orderId not in self.__ordersFilled.index:
                if self.submittedOrder['order_id']  == order['ibOrder_m_orderId']:
                #This is to ensure that self.submitted order is capturing information from the same order it was submitted for
                    self.submittedOrder      =   {
                        'contract_code'  :   order['contract_code'],
                        'order_id'       :   order['ibOrder_m_orderId'],
                        'executed'       :   'TOTAL',
                        'totalQuantity'  :   order['ibOrder_m_totalQuantity'],
                        'FilledQuantitiy':   abs(msg.filled),
                        'avgFillPrice'   :   float(msg.avgFillPrice),
                        'lastFillPrice'  :   float(msg.lastFillPrice),
                        'remaining'      :   abs(msg.remaining),
                
                }

                self.__unregisterOrder(order,raison='FILLED')
                if self.__debug:
                    print ('%s[MyIbBroker_last __orderStatusHandler] @@@@FILLED Order removed from  __activeOrder table :@@@@@' % (now,))
                    print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,self.submittedOrder))
                    print ('%s' % (self.__activeOrders))
                    print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
            else:
                if self.__debug:
                    print ('%s[MyIbBroker_last __orderStatusHandler] Duplicate Order already removed from  __activeOrder table and in Filled Table:' % (now,))
                    print ('%s[MyIbBroker_last __orderStatusHandler]\n %s' % (now,order))
                    print ('%s' % (self.__activeOrders))
                    print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
            
            return
            
            #order.setState(broker.Order.State.FILLED)
        elif msg.status == 'Submitted' and msg.filled > 0:
            order['status']         =   'PARTIALLY_FILLED'
            order['avgFillPrice']   =   msg.avgFillPrice
            order['FilledQuantitiy']=   abs(msg.filled)
            order['remaining']      =   abs(msg.remaining)
            order['lastFillPrice']  =   msg.lastFillPrice
            order['openOrderYesNo'] =   True
            self.__updateActiveOrder(order)

            if self.submittedOrder['order_id']  == order['ibOrder_m_orderId']:
                self.submittedOrder      =   {
                    'contract_code'  :   order['contract_code'],
                    'order_id'       :   order['ibOrder_m_orderId'],
                    'executed'       :   'PARTIAL',
                    'totalQuantity'  :   order['ibOrder_m_totalQuantity'],
                    'FilledQuantitiy':   abs(msg.filled),
                    'avgFillPrice'   :   float(msg.avgFillPrice),
                    'lastFillPrice'  :   float(msg.lastFillPrice),
                    'remaining'      :   abs(msg.remaining),
                    
            
            }
            
            if self.__debug:
                print ('%s[MyIbBroker_last __orderStatusHandler] PARTIALLY FILLED Order - Order updated in  __activeOrders table :' % (now,))
                print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,order))
                print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,self.__activeOrders))
                print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
            return

            #may already be partially filled
            #if order.getState() != broker.Order.State.PARTIALLY_FILLED:
            #    order.setState(broker.Order.State.PARTIALLY_FILLED)
        elif msg.status == 'Cancelled' and order['status'] != 'CANCELED':
            order['status']         =   'CANCELED'
            order['avgFillPrice']   =   msg.avgFillPrice
            order['FilledQuantitiy']=   abs(msg.filled)
            order['remaining']      =   abs(msg.remaining)
            order['lastFillPrice']  =   msg.lastFillPrice
            order['openOrderYesNo'] =   False
            if self.submittedOrder['order_id']  == order['ibOrder_m_orderId']:
                self.submittedOrder      =   {
                    'contract_code'  :   order['contract_code'],
                    'order_id'       :   order['ibOrder_m_orderId'],
                    'executed'       :   'CANCELED',
                    'totalQuantity'  :   order['ibOrder_m_totalQuantity'],
                    'FilledQuantitiy':   abs(msg.filled),
                    'avgFillPrice'   :   float(msg.avgFillPrice),
                    'lastFillPrice'  :   float(msg.lastFillPrice),
                    'remaining'      :   abs(msg.remaining),
         
            }
           
            #order.setState(broker.Order.State.CANCELED)
            self.__unregisterOrder(order,raison='CANCELLED')
            if self.__debug:
                print ('%s[MyIbBroker_last __orderStatusHandler] CANCELED ORDER - ORDER removed from __activeOrder table :' % (now,))
                print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,order))
                print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,self.__activeOrders))
                print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
            return
          
        else:
            if msg.status=='PreSubmitted' and order['status']=='PRESUBMITTED':
                order['status']         =   'SUBMITTED'
                order['avgFillPrice']   =   msg.avgFillPrice
                order['FilledQuantitiy']=   abs(msg.filled)
                order['remaining']      =   abs(msg.remaining)
                order['lastFillPrice']  =   msg.lastFillPrice
                order['openOrderYesNo'] =   True
                """
                To see if open order from previous session should not be cancelled automatically
                instead of being recorded and let to be executed
                """
                self.__updateActiveOrder(order)
                if self.__debug:
                    print ('%s[MyIbBroker_last __orderStatusHandler] ORDER in PRESUBMITTED STATE changed to submitted - it was an out of trading hour order submitted at market opening' % (now,))
                    #print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,order))
                    #print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,self.__activeOrders))
                    print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
                return
        
            else:
                if self.__debug:
                    print ('%s[MyIbBroker_last __orderStatusHandler] duplicate PRESUBMITTED ORDER do nothing' % (now,))
                    print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,order))
                    #print ('%s[MyIbBroker_last __orderStatusHandler] %s' % (now,self.__activeOrders))
                    print ('%s[MyIbBroker_last __orderStatusHandler] END********__orderStatusHandler *****************' % (now,))
                return
    def getContractPositionLine(self,ibContract):
        now             =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        contract_exist  =   False
        contract_line   =   None
        contract_code   =   None
        
        if self.__debug:
            print ('%s[MyIbBroker_last getContractPosition] BEGIN*********getContractPosition*******************' %(now,))

        for pos in range(self.__activePositions.shape[0]):
            position    =   self.__activePositions.loc[pos]
            if self.__debug:
                #print(type(position))
                print(position['contract_code'])
                #print ('%s[MyIbBroker_last getContractPosition] iter Position from ACTIVE POSITION table: %s ' %(now,position))


            if (type(position) is pd.Series):
                if position['ibContract_m_symbol']      ==  ibContract.m_symbol and\
                    position['ibContract_m_secType']    ==  ibContract.m_secType and\
                    position['ibContract_m_currency']   ==  ibContract.m_currency and\
                    position['ibContract_m_multiplier'] ==  ibContract.m_multiplier and\
                    position['ibContract_m_expiry']     ==  ibContract.m_expiry and\
                    position['ibContract_m_strike']     ==  ibContract.m_strike :

                    contract_exist  =   True
                    contract_code   =   position['contract_code']
                    contract_line   =   pos

                    if self.__debug:
                        print ('%s[MyIbBroker_last getContractPosition] Contract Received from IB existing in this Positon, PNL information updated:  ' %(now,))
                    return (contract_exist,contract_line,contract_code)
                    
                else:
                    if self.__debug:
                        #print ('%s[MyIbBroker_last getContractPosition] Contract Received not in this position, Checking next iter position in Active position table' %(now,))
                        pass  
            else:
                if self.__debug:
                    print("%s[MyIbBroker_last getContractPosition] ERROR in ACTIVE POSITION table Position must be a pd.Series"%(now))
                    print ('%s[MyIbBroker_last getContractPosition] END********getContractPosition *****************' % (now,))
                return (False,0,0)
    
        if self.__debug:
            print ('%s[MyIbBroker_last getContractPosition] Contract NOT IN ACTIVE POSITION TABLE ' %(now,))
            print ('%s[MyIbBroker_last getContractPosition] END********getContractPosition *****************' % (now,))


        return (False,0,0)
    def addNonExistingPosition(self,portDict,contract_code,msg,ibContract):
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
            print ('%s[MyIbBroker_last addNonExistingPosition] BEGIN********addNonExistingPosition *****************' % (now,))

        self.__activePositions  =   self.__activePositions.append(pd.Series(portDict),ignore_index=True)
        self.overalPosition[ibContract]           = {
                        'contract_code' :   contract_code,
                        'position'      :   msg.position,
                        'marketPrice'   :   msg.marketPrice,
                        'marketValue'   :   msg.marketValue,
                        'averageCost'   :   msg.averageCost,
                        'unrealizedPNL' :   msg.unrealizedPNL,
                        'realizedPNL'   :   msg.realizedPNL
            }
        self.__activePositions.to_csv(self.dir_Output+"ActivePositions.csv")
        self.__positionsHistory.to_csv(self.dir_Output+"PositionsHistory.csv")

        if self.__debug:
            print ('%s[MyIbBroker_last addNonExistingPosition] Active Positon table empty :added to Active Position:  ' %(now,))
            #print ('%s[MyIbBroker_last addNonExistingPosition]................................................'%(now,))
            #print ('%s[MyIbBroker_last addNonExistingPosition] %s  ' %(now,self.__activePositions))
            print ('%s[MyIbBroker_last addNonExistingPosition] ActivePositions and PositionsHistory outputed as csv  ' %(now,))
            #print ('%s[MyIbBroker_last addNonExistingPosition] %s  ' %(now,self.__activePositions))
            print ('%s[MyIbBroker_last addNonExistingPosition] END********addNonExistingPosition *****************' % (now,))
        return
    def updateExistingPosition(self,portDict,contract_line,contract_code,ibContract,msg):
        now =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
            print ('%s[MyIbBroker_last updateExistingPosition] BEGIN********updateExistingPosition *****************' % (now,))

        if self.__activePositions.loc[contract_line,'contract_code'] == contract_code :
                """
                self.__activePositions.loc[contract_line,'ibContract_m_right']      ==  ibContract.m_right:
                self.__activePositions.loc[contract_line,'position']        =   msg.position,
                self.__activePositions.loc[contract_line,'marketPrice']     =   msg.marketPrice,
                self.__activePositions.loc[contract_line,'marketValue']     =   msg.marketValue,
                self.__activePositions.loc[contract_line,'averageCost']     =   msg.averageCost,
                self.__activePositions.loc[contract_line,'unrealizedPNL']   =   msg.unrealizedPNL,
                self.__activePositions.loc[contract_line,'realizedPNL']     =   msg.realizedPNL,
                """

                self.__activePositions.loc[contract_line] = pd.Series(portDict)
                
                def replace_value_with_definition(key_to_find, definition):
                    for key in self.overalPosition.keys():
                        if key == key_to_find:
                            print ("**** FIND KEY")
                            self.overalPosition[key] = definition
                        else:
                            print ("****DID NOT FIND KEY")
                        
                s   = {
                            'contract_code' :   contract_code,
                            'position'      :   portDict['position'] ,
                            'marketPrice'   :   portDict['marketPrice'],
                            'marketValue'   :   portDict['marketValue'],
                            'averageCost'   :   portDict['averageCost'],
                            'unrealizedPNL' :   portDict['unrealizedPNL'],
                            'realizedPNL'   :   portDict['realizedPNL'],
                        }
                print(s)
                replace_value_with_definition(ibContract, s)
                
                self.__activePositions.to_csv(self.dir_Output+"ActivePositions.csv")
                self.__positionsHistory.to_csv(self.dir_Output+"PositionsHistory.csv")
                if self.__debug:
                    print ('%s[MyIbBroker_last updateExistingPosition] ActivePositions and PositionsHistory outputed as csv  ' %(now,))
                    print ('%s  ' %(self.__activePositions))
                    print ('%s[MyIbBroker_last updateExistingPosition] END********updateExistingPosition *****************' % (now,))   
                return
        else:
            if self.__debug:
                print ('%s[MyIbBroker_last updateExistingPosition] ERROR  ' %(now,))
                print ('__activePositions: %s  ' %(self.__activePositions))
                print ('ibContract.m_symbol: %s  ' %(ibContract.m_symbol))
                print ('contract_line: %s  ' %(contract_line))
                print ('contract_code: %s  ' %(contract_code))
                print ('msg: %s  ' %(msg))
                print ('%s[MyIbBroker_last updateExistingPosition] END********updateExistingPosition *****************' % (now,))   
            return
    def __portfolioHandler(self,msg):
        """
        get portfolio messages - stock, price, purchase price etc

        """
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #<updatePortfolio contract=<ib.ext.Contract.Contract object at 0x000000000BB83048>, position=-5, 
        #marketPrice=1.13680005, marketValue=-5.68, averageCost=0.91886, unrealizedPNL=-1.09, 
        #realizedPNL=0.0, accountName=DU213041>
        if self.__debug:
            print ('%s[MyIbBroker_last __portfolioHandler] BEGIN********__portfolioHandler *****************' % (now,))
            print ('%s[MyIbBroker_last __portfolioHandler] Message received from Server:' % (now,))
            print ('%s[MyIbBroker_last __portfolioHandler]................................................'%(now,))
            print ('%s[MyIbBroker_last __portfolioHandler] %s' %(now,msg))
            print ('%s[MyIbBroker_last __portfolioHandler]................................................'%(now,))

        
        ibContract      =   msg.contract
        contract_code   =   self.buildContractRepresentation(ibContract)

        
        
        
        portDict={
        'datetime'                  :   datetime.datetime.now(),
        'ibContract_m_symbol'       :   ibContract.m_symbol,
        'ibContract_m_secType'      :   ibContract.m_secType,
        'ibContract_m_currency'     :   ibContract.m_currency,
        'ibContract_m_exchange'     :   ibContract.m_exchange,
        'ibContract_m_multiplier'   :   ibContract.m_multiplier,
        'ibContract_m_expiry'       :   ibContract.m_expiry ,
        'ibContract_m_strike'       :   ibContract.m_strike,
        'ibContract_m_right'        :   ibContract.m_right,
        'position'      :   msg.position,
        'marketPrice'   :   msg.marketPrice,
        'marketValue'   :   msg.marketValue,
        'averageCost'   :   msg.averageCost,
        'unrealizedPNL' :   msg.unrealizedPNL,
        'realizedPNL'   :   msg.realizedPNL,
        'accountName'   :   msg.accountName,
        'strategy_name' :   self.strategy_name,
        'run_number'    :   self.run_number,
        'contract_code' :   contract_code,
     
        }
        if self.__debug:
            print ('%s[MyIbBroker_last __portfolioHandler] Contract Code:  %s' %(now,contract_code))        
            #print ('%s[MyIbBroker_last __portfolioHandler] Existing Portfolio Position Received from IB: ' %(now,))
            #print ('%s[MyIbBroker_last __portfolioHandler] %s  ' %(now,portDict))
            
        self.__positionsHistory =   self.__positionsHistory.append(pd.Series(portDict),ignore_index=True)
        if self.__debug:
            print ('%s[MyIbBroker_last __portfolioHandler] Position Received from IB added POSITION HISTORY:  ' %(now,))
           # print ('%s[MyIbBroker_last __portfolioHandler]................................................'%(now,))
            #print ('%s  ' %(self.__positionsHistory))
            #print ('%s[MyIbBroker_last __portfolioHandler]................................................'%(now,))


        try:
            loadIntoEsIndex(portDict)            
            if self.__debug:
                print ('%s[MyIbBroker_last __portfolioHandler] Position Received from IB added into ELASTIC SEARCH:  ' %(now,))
        except Exception as e:
            if self.__debug:
                print ('%s[MyIbBroker_last __portfolioHandler] Error loading to ELASTIC SEARCH:  ' %(now,e))
                #print (e)
                #raise("ERROR")

        
        #Checking if the Contract of the position is already in the Active Position table
        #1 step checking if the contract exist in the active position table
        
        if self.__activePositions.empty: #Active position table is empty no position in it

            if self.__debug:
                print ('%s[MyIbBroker_last __portfolioHandler] ACTIVE POSITION TABLE empty position added'%(now,))

            self.addNonExistingPosition(portDict,contract_code,msg,ibContract)
            #self.__activeOrders.to_csv(self.dir_Output+"ActiveOrders.csv")
            #self.__ordersHistory.to_csv(self.dir_Output+"OrdersHistory.csv")
            if self.__debug:
                #print ('%s[MyIbBroker_last __portfolioHandler] output Order csv'%(now,))
                print ('%s[MyIbBroker_last __portfolioHandler] END*********__portfolioHandler*******************'%(now,))
            return

        else: #Active position table is not empty
            contractInfo    =   self.getContractPositionLine(ibContract)
            if self.__debug:
                print ('%s[MyIbBroker_last __portfolioHandler] Retrieved Contract Info: %s'%(now,contractInfo))

            contract_exist  =   contractInfo[0]
            contract_line   =   contractInfo[1]
            #contract_code   =   contractInfo[2]
            if contract_exist   == True:
                if self.__debug:
                    print ('%s[MyIbBroker_last __portfolioHandler] Updating ACTIVE POSITION TABLE'%(now,))

                self.updateExistingPosition(portDict,contract_line,contract_code,ibContract,msg)
                #self.__activeOrders.to_csv(self.dir_Output+"ActiveOrders.csv")
                #self.__ordersHistory.to_csv(self.dir_Output+"OrdersHistory.csv")
                if self.__debug:
                    #print ('%s[MyIbBroker_last __portfolioHandler] output Order csv'%(now,))
                    print ('%s[MyIbBroker_last __portfolioHandler] END*********__portfolioHandler*******************'%(now,))
                return
            elif contract_exist == False:

                if self.__debug:
                        print ('%s[MyIbBroker_last __portfolioHandler] Adding new position in ACTIVE POSITION TABLE '%(now,))

                self.addNonExistingPosition(portDict,contract_code,msg,ibContract)
                #self.__activeOrders.to_csv(self.dir_Output+"ActiveOrders.csv")
                #self.__ordersHistory.to_csv(self.dir_Output+"OrdersHistory.csv")
                if self.__debug:
                    #print ('%s[MyIbBroker_last __portfolioHandler] output Order csv'%(now,))
                    print ('%s[MyIbBroker_last __portfolioHandler] END*********__portfolioHandler*******************'%(now,))

                return
            else:
                if self.__debug:
                    print ('%s[MyIbBroker_last __portfolioHandler] UNKNOWN ERROR to INVESTIGATE'%(now,))
                    print ('%s[MyIbBroker_last __portfolioHandler] self.getContractPositionLine: %s' %(now,contractInfo))
                    print ('%s[MyIbBroker_last __portfolioHandler] END*********__portfolioHandler*******************'%(now,))
                    return
                    
            return
    def __openOrderHandler(self,msg):
        '''
        #build position array from ib object (NOTE: This isn't a pyalgotrade position it's an array with enough details hopefully to build one)
        def build_position_from_open_position(self,msg):
            #return pyalgotrade.strategy.position.LongPosition(self., instrument, stopPrice, None, quantity, goodTillCanceled, allOrNone)
            return {
                'stock': 'STW',
                'shortLong': 'long',
                'quantity': 500,
                'price': 31.63
            }
            pass

        #creates positions and hopefully tells the strategy on startup
        #great for error recovery
        def __positionHandler(self,msg):
            self.__initialPositions.append(self.build_position_from_open_position(msg))
            print "GOT POSITIONS"

        def getInitialPositions(self):
            return self.__initialPositions

        '''
    #listen for orders to be fulfilled or cancelled

        #Do nothing now but might want to use this to pick up open orders at start (eg in case of shutdown or crash)
        #note if you want to test this make sure you actually have an open order otherwise it's never called
        #Remember this is called once per open order so if you have 3 open orders it's called 3 times
        
        #self._registerOrder(build_order_from_open_order(msg, self.getInstrumentTraits(msg.contract.m_symbol)))
        #Do nothing now but might want to use this to pick up open orders at start (eg in case of shutdown or crash)
        #note if you want to test this make sure you actually have an open order otherwise it's never called
        #Remember this is called once per open order so if you have 3 open orders it's called 3 times

        now             =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
        ibContract      =   msg.contract
        ibOrder         =   msg.order
        orderId         =   int(ibOrder.m_orderId) 
        #ibOrderState    =   msg.orderState
        
        try:
            exist   =   self.__activeOrders.empty 
            exist   =   True
            test    =   (orderId in self.__activeOrders.index)  or (orderId in self.__ordersFilled.index)

        except Exception as e:
            print(e)
            exist   =   False
            test    =   (orderId in self.__ordersFilled.index)
            

        if self.__debug:
            print ('%s[MyIbBroker_last __openOrderHandler] BEGIN*********__openOrderHandler*******************'%(now,))
            print ('%s[MyIbBroker_last __openOrderHandler] Message received from Server:' %(now,))
            print ('%s[MyIbBroker_last __openOrderHandler]  %s' %(now,msg))
            print ('%s[MyIbBroker_last __openOrderHandler]................................................'%(now,))
            print ('%s[MyIbBroker_last __openOrderHandler] Order ID %s:'%(now,orderId))
            if exist == True:
                print ('%s[MyIbBroker_last __openOrderHandler] __activeOrders:%s'%(now, self.__activeOrders.index))
            else:
                print ('%s[MyIbBroker_last __openOrderHandler] __activeOrders has been dropped and does not exist '%(now,))
            
            print ('%s[MyIbBroker_last __openOrderHandler] __ordersFilled:%s'%(now,  self.__ordersFilled.index))
            
        
            #ibOderFromActiveTable = self.__getActiveOrder(ibOrder.m_orderId)
            
        
            
        if test:
                
            if self.__debug:
                print ('%s[MyIbBroker_last __openOrderHandler] Open Order existing in Active or FILLED ORDER  TABLE'%(now,))
                """
                    
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_orderId: %s' %(now,ibOderFromActiveTable.m_orderId)) 
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_clientId  : %s' %(now,ibOderFromActiveTable.m_clientId  )) 
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_action : %s' %(now,ibOderFromActiveTable.m_action )) 
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_lmtPrice : %s' %(now,ibOderFromActiveTable.m_lmtPrice )) 
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_auxPrice: %s' %(now,ibOderFromActiveTable.m_auxPrice)) 
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_tif  %s' %(now,ibOderFromActiveTable.m_tif ))
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_transmit  %s' %(now,ibOderFromActiveTable.m_transmit ))
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_orderType   %s' %(now,ibOderFromActiveTable.m_orderType  ))
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_totalQuantity   %s' %(now,ibOderFromActiveTable.m_totalQuantity ))
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_allOrNone  %s' %(now,ibOderFromActiveTable.m_allOrNone ))
                    print ('%s[MyIbBroker_last __openOrderHandler] ibOrder.m_tif   %s' %(now,(ibOderFromActiveTable.m_tif )))
                    
                """
                print ('%s[MyIbBroker_last __openOrderHandler] END*********__openOrderHandler*******************'%(now,))
                return
                     
        else:
            print ('%s[MyIbBroker_last __openOrderHandler] Order not in Active Table - Adding it' %(now, ))
            order   =   self.__createOrder(
                    datetime        =   now,
                    status          =   "PRESUBMITTED",
                    ibContract      =   ibContract,
                    ibOrder         =   ibOrder,
                    openOrderYesNo  =   True,
                    #contract_code    =   self.buildContractRepresentation(ibContract)  ,
                        )
            try:
                self.__registerOrder(   order,  raison  =   "PRESUBMITTED" )
                self.__initialOrders.loc[int(order['ibOrder_m_orderId'])] = order
                
                
                if self.__debug:
                    print ('%s[MyIbBroker_last __openOrderHandler] Open Order Not Active or Filled Order, Order registered in active order, Cancell it if not necessary anymore'%(now,))
                    #print ('%s[MyIbBroker_last __openOrderHandler] %s' % (now,order))
                    #print ('%s[MyIbBroker_last __openOrderHandler] %s' % (now,self.__activeOrders))
                    print ('%s[MyIbBroker_last __openOrderHandler] END********__openOrderHandler *****************' % (now,))
                    return
            except Exception as e:
                if self.__debug:
                    print ('%s[MyIbBroker_last __openOrderHandler] Problem Order: %s'%(now,e))
                    print ('%s[MyIbBroker_last __openOrderHandler] END*********__openOrderHandler*******************'%(now,))
                    return
    def __startTradeMonitor(self):
        return
    def getOrderNumber(self):
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print('%s[MyIbBroker_last getOrderNumber]********************************'%(now,))
            print('%s[MyIbBroker_last getOrderNumber]Get order number'%(now,))

        try:
            with open("control_files\\order_number","r+") as fo:
                #if self.__debug:
                #    print('%s[MyIbBroker_last getOrderNumber] File Opened: %s'%(now,fo))
                order_number=fo.read().split()
                fo.close()
                #if self.__debug:
                #    print('%s[MyIbBroker_last getOrderNumber] File containt list: %s'%(now,order_number))

                if len(order_number)==1:
                    try:
                        order=int(order_number[0])
                 #       if self.__debug:
                 #           print('%s[MyIbBroker_last getOrderNumber] ORder number: %s'%(now,order))
                        
                        orderPlus=order+1
                        if self.__debug:
                            print('%s[MyIbBroker_last getOrderNumber] self order number: %s'%(now,order))

                        
                #        if self.__debug:
                #            print('%s[MyIbBroker_last getOrderNumber] increased Run number: %s'%(now,order))
                        order=str(order)
                #        if self.__debug:
                #            print('%s[MyIbBroker_last getOrderNumber] type (order): %s'%(now,type(order)))

                        f=open("control_files\\order_number","w")
                #        if self.__debug:
                #            print('%s[MyIbBroker_last getOrderNumber] writing file opened'%(now,))

                        f.write(str(orderPlus))
                #        if self.__debug:
                #            print('%s[MyIbBroker_last getOrderNumber] File wrote'%(now,))
                        
                        f.close()
                        
                        if self.__debug:
                            print('%s[MyIbBroker_last getOrderNumber] Increased number written in the file:'%(now,))
                        
                        return order
                    except Exception as e:
                        #print(e)
                        raise("[MyIbBroker_last getOrderNumber] END File control_files/run_number must have an integer number in it")
        except  :
            #print(Exception)
            raise("[MyIbBroker_last getOrderNumber]File control_files/order_number must exist")
    def refreshAccountBalance(self):
        """
        subscribes for regular account balances which are sent to portfolio and account handlers
        """
        self.__ib.reqAccountUpdates(1,'')
    def refreshOpenOrders(self):
        self.__ib.reqAllOpenOrders()

        # END FEEDBACK HANDLER

    # BEGIN observer.Subject interface
    def start(self):
        return
    def stop(self):
        print("@@@@@@@@@@@@@@@@@@@@")
        self.__stop = True
        self.__ib.disconnect()
        print("@@@@@@@@@@@@@@@@@@@@")
        print("@@@ @ @@@@@@@@@@@@@@")
        print("@@  @@ @@@@@@@@@@@@@@")
        print("@@   @@@ @@@@@@@@@@@@@@")
        print("@@@@@@@@@@@@@@@@@@@@")
    def join(self):
        pass
    def eof(self):
        return self.__stop
    def dispatch(self):
        """
        # Switch orders from SUBMITTED to ACCEPTED.
        ordersToProcess = self.__activeOrderss.values()
        for order in ordersToProcess:
            if order.isSubmitted():
                order.switchState(broker.Order.State.ACCEPTED)
                self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.ACCEPTED, None))
        """
        return
    def peekDateTime(self):
        # Return None since this is a realtime subject.
        return None
    # END observer.Subject interface

    # BEGIN broker.Broker interface
    def getInstrumentTraits(self):   #HISTORICAL
        return  self.__activePositions
    def getShares(self, instrument): #HISTORICAL
        return self.__activePositions
    def getPositions(self):          #HISTORICAL
        return self.__activePositions
    def getDetailedPositions(self):  #HISTORICAL
        return self.__activePositions

    def getCash(self, includeShort=True):
        return self.__cash
    def getInitialOrders(self):
        return self.__initialOrders
    def getActivePositions(self):          
        return self.__activePositions
    def getPositionsHistory(self):
        return self.__positionsHistory
    def getActiveOrders(self, instrument=None):
        return self.__activeOrders
    def getFilledOrders(self):
        return self.__ordersFilled
    def getOrdersHistory(self, instrument=None):
        return self.__ordersHistory

    # BEGIN broker ORDER MAKING AND SUBMISSION 
    def buildContractRepresentation(self,ibContract):
    
        return ("%s:%s:%s:%s:%s" %(ibContract.m_symbol,ibContract.m_secType,ibContract.m_right,ibContract.m_strike,ibContract.m_expiry )).strip()
    def makeStkContrcat(self,m_symbol,m_secType = 'STK',m_exchange = 'SMART',m_currency = 'USD'):
        from ib.ext.Contract import Contract
        newContract = Contract()
        newContract.m_symbol = m_symbol
        newContract.m_secType = m_secType
        newContract.m_exchange = m_exchange
        newContract.m_currency = m_currency
        return newContract
    def makeOptContract(self,
            IbContract  =   None,
            m_right     =   None, 
            m_expiry    =   None, 
            m_strike    =   None,

            m_symbol    =   None, 
            m_secType = 'OPT',
            m_exchange = 'SMART',
            m_currency = 'USD'):
        '''
        makeOptContract('BAC', '20160304', 'C', 15)
        sym: Ticker instrument
        exp: expiry date format YYYYYMMDD
        right: C or P 
        strike price: float
        '''
        from ib.ext.Contract import Contract

        if isinstance(IbContract,Contract):
            newOptContract = IbContract
            
        else:
            newOptContract = Contract()
            newOptContract.m_symbol = m_symbol
        
        
        
        newOptContract.m_secType = m_secType
        newOptContract.m_right = m_right
        newOptContract.m_expiry = m_expiry
        newOptContract.m_strike = float(m_strike)
        newOptContract.m_exchange = m_exchange
        newOptContract.m_currency = m_currency
        #newOptContract.m_localSymbol = ''
        #newOptContract.m_primaryExch = ''
        return newOptContract
    def makeForexContract(self,m_symbol,m_secType = 'CASH',m_exchange = 'IDEALPRO',m_currency = 'USD'):
        from ib.ext.Contract import Contract
        newContract = Contract()
        newContract.m_symbol = m_symbol
        newContract.m_secType = m_secType
        newContract.m_exchange = m_exchange
        newContract.m_currency = m_currency
        return newContract
    def makeOrder(self,
                 
                 m_action ,
                 m_orderType,
                 m_totalQuantity,
                 m_orderId          = None,
                 m_lmtPrice         = 0,
                 m_auxPrice         = 0,
                 m_tif              = 'DAY',
                 m_trailStopPrice   = None,
                 m_trailingPercent  = None ,
                 m_transmit = True):
        '''
        optOrder = makeOptOrder( 'BUY', orderID, 'DAY', 'MKT')
        action: 'BUY' or 'SELL'
        orderID: float that identifies the order
        tif: time in force 'DAY', 'GTC'
        orderType:'MKT','STP','STP LMT'
        totalQunatity: int number of share  
        '''
        assert (m_action in ['BUY','SELL']),'[makeOrder] m_action not either BUY or SELL'
        assert (m_tif in ['DAY','GTC']),'[makeOrder] m_tif not either DAY or GTC'
        assert (m_orderType in ['MKT','LMT','STP','STP LMT']),'[makeOrder] orderType not either MKT,STP,STP LMT'
        assert (int(m_totalQuantity)  is int),'[makeOrder] m_totalQuantity is not int'
        
        from ib.ext.Order import Order
        newOptOrder = Order()
        newOptOrder.m_orderId           =   m_orderId  #int m_orderId	The id for this order.
        #newOptOrder.m_clientId          =   m_clientId #int m_clientId	The id of the client that placed this order.
        #newOptOrder.m_permid            =   m_permid #int m_permid	The TWS id used to identify orders, remains the same over TWS sessions.
        #Main Order Fields
        newOptOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        newOptOrder.m_lmtPrice          =   m_lmtPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.
        newOptOrder.m_auxPrice          =   m_auxPrice #double m_auxPrice This is the STOP price for stop-limit orders, and the offset amount for relative orders. In all other cases, specify zero.
        newOptOrder.m_orderType         =   m_orderType #String m_orderType
        newOptOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.
        #newOptOrder.m_parentId          =   None  #int m_parentId	The order ID of the parent order, used for bracket and auto trailing stop orders.
        newOptOrder.m_trailStopPrice    =   m_trailStopPrice  #m_trailStopPrice	For TRAILLIMIT orders only
        newOptOrder.m_trailingPercent   =   m_trailingPercent  # double m_trailingPercent	

        #Extended Order Fields
        newOptOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        newOptOrder.m_transmit      =   m_transmit #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        newOptOrder.m_allOrNone     = 0 #  boolean m_allOrNone	0 = no, 1 = yes

        return newOptOrder
    def submitOrder(self, ibContract, ibOrder):
        #from ib.ext.Contract import Contract
        #assert(ibContract is Contract)
        #assert(ibOrder is Order)
        contract_code       =   self.buildContractRepresentation(ibContract)
        order_id            =   int(self.getOrderNumber())
        ibOrder.m_orderId   =   int(order_id)
        now                 =   dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S' )

        try:
            order   =   self.__createOrder(
                            datetime        =    now,
                            FilledQuantitiy =   0,
                            avgFillPrice    =   0,
                            openOrderYesNo  =   True,
                            ibContract      =   ibContract,
                            ibOrder         =   ibOrder)


            try:
                self.__registerOrder(   order,  raison  =   'SUBMITTED' )               
                try:
                    self.__ib.placeOrder(   order_id,   ibContract,     ibOrder)
                    self.submittedOrder      =   {
                                'contract_code'  :   contract_code,
                                'order_id'       :   order_id,
                                'executed'       :   'SUBMITTED',
                                'totalQuantity'  :   ibOrder.m_totalQuantity,
                                'FilledQuantitiy':   0,
                                'avgFillPrice'   :   0,
                                'lastFillPrice'  :   0,
                        }
    
                except Exception as c:
                    if self.__debug:
                        print ('%s[MyIbBroker_last submitOrder] ERROR place Order - active order table out of synch:\n ' % (now,c))
                        print ('%s[MyIbBroker_last submitOrder] END********submitOrder *****************' % (now,))
                        return
            except Exception as b:
                if self.__debug:
                    print ('%s[MyIbBroker_last submitOrder] ERROR __registerOrder, active ordewr table out of synch\n %s' % (now,b))
                    print ('%s[MyIbBroker_last submitOrder] END********submitOrder *****************' % (now,))
                    return
        except Exception as a:
            if self.__debug:
                print ('%s[MyIbBroker_last submitOrder] ERROR IB __createOrder:\n %s' % (now,a))
                print ('%s[MyIbBroker_last submitOrder] END********submitOrder *****************' % (now,))
                return
        
            
        if self.__debug:
                print ('%s[MyIbBroker_last submitOrder] Order submitted and registered in ACTIVE ORDER table:'%(now,))
                print ('%s[MyIbBroker_last submitOrder] Order:\n %s' % (now,order))
                print ('%s[MyIbBroker_last submitOrder] ACTIVE ORDER TABLE:\n %s' % (now,self.__activeOrders))
                print ('%s[MyIbBroker_last submitOrder] END********submitOrder *****************' % (now,))
                
    def submitMarketOrder(self, m_action, ibContract, m_totalQuantity, onClose=True):
        assert (m_action in ['BUY','SELL']),'[createMarketOrder] m_action not either BUY or SELL'
        if onClose==False :
            m_tif='GTC'
        else:
            m_tif='DAY'
            
        
        from ib.ext.Order import Order
        ibOrder = Order()
        ibOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        ibOrder.m_orderType         =   'MKT'
        ibOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.

        #Extended Order Fields
        ibOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        ibOrder.m_transmit      =   1 #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        ibOrder.m_allOrNone     =   0 #  boolean m_allOrNone	0 = no, 1 = yes

        self.submitOrder(ibContract, ibOrder)

        return 
    def submitLimitOrder(self, m_action, ibContract, m_lmtPrice, m_totalQuantity,onClose=True):
        assert (m_action in ['BUY','SELL']),'[createMarketOrder] m_action not either BUY or SELL'
        if onClose==False :
            m_tif='GTC'
        else:
            m_tif='DAY'
            
        
        from ib.ext.Order import Order
        ibOrder = Order()
        ibOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        ibOrder.m_orderType         =   'LMT'
        ibOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.
        ibOrder.m_lmtPrice          =   m_lmtPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.

        #Extended Order Fields
        ibOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        ibOrder.m_transmit      =   1 #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        ibOrder.m_allOrNone     =   0 #  boolean m_allOrNone	0 = no, 1 = yes

        self.submitOrder(ibContract, ibOrder)

        return  
    def submitStopOrder(self, m_action, ibContract, stopPrice, m_totalQuantity,onClose=True):
        assert (m_action in ['BUY','SELL']),'[createMarketOrder] m_action not either BUY or SELL'
        if onClose==False :
            m_tif='GTC'
        else:
            m_tif='DAY'
        m_auxPrice=stopPrice
        from ib.ext.Order import Order
        ibOrder = Order()
        ibOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        ibOrder.m_orderType         =   'STP'
        ibOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.
        ibOrder.m_auxPrice          =   m_auxPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.

        #Extended Order Fields
        ibOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        ibOrder.m_transmit      =   1 #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        ibOrder.m_allOrNone     =   0 #  boolean m_allOrNone	0 = no, 1 = yes

        self.submitOrder(ibContract, ibOrder)


        return  
    def submitStopLimitOrder(self, m_action, ibContract, stopPrice, m_lmtPrice, m_totalQuantity,onClose=True):
        if onClose==False :
            m_tif='GTC'
        else:
            m_tif='DAY'
        m_auxPrice=stopPrice
        
        from ib.ext.Order import Order
        ibOrder = Order()
        ibOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        ibOrder.m_orderType         =   'STP LMT'
        ibOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.
        ibOrder.m_auxPrice          =   m_auxPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.
        ibOrder.m_lmtPrice          =   m_lmtPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.

        #Extended Order Fields
        ibOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        ibOrder.m_transmit      =   1 #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        ibOrder.m_allOrNone     =   0 #  boolean m_allOrNone	0 = no, 1 = yes

        self.submitOrder(ibContract, ibOrder)
    def submittrailingLimitStop(self,m_action,ibContract,limitPrice,trailingAmount,trailStopPrice,quantity,onClose=True):
        
        if onClose==False :
            m_tif='GTC'
        else:
            m_tif='DAY'

        
        m_totalQuantity  =  quantity
        m_auxPrice       =  trailingAmount
        m_lmtPrice       =  limitPrice
        m_trailStopPrice =  trailStopPrice
        
        
        from ib.ext.Order import Order
        ibOrder = Order( )
        ibOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        ibOrder.m_orderType         =   'TRAIL LIMIT'
        ibOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.
        ibOrder.m_auxPrice          =   m_auxPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.
        ibOrder.m_lmtPrice          =   m_lmtPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.
        ibOrder.m_trailStopPrice     =   m_trailStopPrice
        ibOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        ibOrder.m_transmit      =   1 #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        ibOrder.m_allOrNone     =   0 #  boolean m_allOrNone	0 = no, 1 = yes

        self.submitOrder(ibContract, ibOrder)
    def cancelOrder(self, order):
        assert(type(order) is pd.Series) ,'[cancelOrder] Order must be a pd.Series'
        assert(order['ibOrder_m_orderId'] in self.__activeOrders.index),'[cancelOrder] Order to unregister does not exist in __activeOrders table'
        assert(order['ibOrder_m_orderId'] is not None),'[cancelOrder] Order must be a pd.Series'
        assert(order['ibOrder_m_orderId'] not in self.__ordersFilled.index),'[cancelOrder] Can not cancel order that has already been filled'

        self.__ib.cancelOrder(order['ibOrder_m_orderId'])
        order['status']='CANCELATION REQUESTED'
        order['datetime']= dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
        order['openOrderYesNo']=False
        self.__updateActiveOrder(order)


        #DO NOT DO THE BELOW:
        '''
        self._unregisterOrder(order)
        order.switchState(broker.Order.State.CANCELED)

        # Update cash and shares. - might not be needed
        self.refreshAccountBalance()

        # Notify that the order was canceled.
        self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.CANCELED, "User requested cancellation"))
        '''
    # END broker.Broker interface
    def getOptionExpiry(self,month):
        dic=['20160617','20160715']
        return dic[0]
        
        
        

class MyIbBroker():
    def __init__(self, host="localhost", port=7496, 
                debug=False, clientId = None, event=None):

        if debug == False:
            self.__debug = False
        else:
            self.__debug = True

 
        ###Connection to IB
        if event !=None:
            self.event = event
        else:
            self.event = queue.Queue()
        
        self.connectionTime=None
        self.serverVersion=None
        self.host=host
        self.port=port
        self.clienId=clientId
        self.__IbConnect() 

        ##dictionary of tuples(orderId,contract object order id, order status )
        orderColumn=[
            'datetime',
            'status',
            'partialFilledQuantitiy',
            'ibContract_m_symbol','ibContract_m_secType',
            'ibContract_m_currency','ibContract_m_exchange',
            'ibContract_m_multiplier','ibContract_m_expiry',
            'ibContract_m_strike','ibContract_m_right',
            'ibOrder_m_orderId','ibOrder_m_clientId',
            'ibOrder_m_permid','ibOrder_m_action',
            'ibOrder_m_lmtPrice','ibOrder_m_auxPrice',
            'ibOrder_m_tif','ibOrder_m_transmit',
            'ibOrder_m_orderType','ibOrder_m_totalQuantity',
            'ibOrder_m_parentId','ibOrder_m_trailStopPrice',
            'ibOrder_m_trailingPercent',
            'ibOrder_m_allOrNone','ibOrder_m_tif','openOrderYesNo',]
        activePositionColumn=[
            'datetime',
            'ibContract_m_symbol','ibContract_m_secType',
            'ibContract_m_currency','ibContract_m_exchange',
            'ibContract_m_multiplier','ibContract_m_expiry' ,
            'ibContract_m_strike','ibContract_m_right',
            'position','marketPrice'
            'marketValue','averageCost','unrealizedPNL','realizedPNL','accountName']
        #2016-02-04 11:17:10[IB LiveBroker __portfolioHandler] <updatePortfolio contract=<ib.ext.Contract.Contract object at 0x00000000088E2FD0>, position=300, marketPrice=0.31, marketValue=9300.0, averageCost=31.2674, unrealizedPNL=-80.22, realizedPNL=0.0, accountName=DU213041>
        self.__activeOrder=[] #Order not yet fully or partially filled
        self.__completelyFilledOrder=[] #Fully filled order
        self.__ordersHistory=pd.DataFrame(columns=orderColumn) #keep history of order life
        #Cash Management
        self.__cash = 0
        #Position Management
        self.__activePositions = pd.DataFrame(columns=activePositionColumn)
   #contract, share
        #self.__detailedActivePositions = {}#entry price, average price etc...
        self.__detailedActivePositionsHistory=pd.DataFrame(columns=activePositionColumn)
        #from InitialLive Broker get portfolio status from the broker
        #equivalent to self.__activePositions = [] , self.__detailedActivePositions
        self.__shares = {}

        self.__nextOrderId = 0
        self.__initialPositions = []
        execuColumn=['datetime'
                'ibExecution_m_orderId','ibExecution_m_execId','ibExecution_m_acctNumber',
                'ibExecution_m_clientId','ibExecution_m_liquidation','ibExecution_m_permId',
                'ibExecution_m_price','ibExecution_m_evMultiplier''ibExecution_m_avgPrice' ,'ibExecution_m_evRule',  
                'ibExecution_m_cumQty','ibExecution_m_shares','ibOrder_m_auxPrice','ibExecution_m_side',
                'ibExecution_m_time','ibExecution_m_exchange' ]
        self.__executionsHistory=pd.DataFrame(columns=execuColumn )
        self.__detailedShares = {}
        #Request initial account balance
        self.refreshAccountBalance()
        # Request current open order in the system
        self.refreshOpenOrders()
        # Request all positions outstanding
        self.__ib.reqPositions()
        #give ib time to get back to us
        time.sleep(5)
            
    def __IbConnect(self):
        if self.clientId == None:
            clientId = random.randint(1000,10000)
            if self.__debug:
                now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                print('%s[IB LiveBroker __init__ ]Client ID: %s' % (now,clientId))
        else:
            clientId=self.clienId

        self.__ib = ibConnection(host=self.host,port=self.port,clientId=clientId)
        #register all the callback handlers
        #self.__ib.registerAll(self.__debugHandler)
        self.__ib.register(self.__accountHandler,'UpdateAccountValue')
        self.__ib.register(self.__portfolioHandler,'UpdatePortfolio')
        self.__ib.register(self.__openOrderHandler, 'OpenOrder')
        
        

        self.__ib.register(self.__positionHandler, 'position account')
        self.__ib.register(self.__disconnectHandler,'ConnectionClosed')
        #self.__ib.register(self.__nextIdHandler,'NextValidId')
        #self.__ib.register(self.__orderStatusHandler,'OrderStatus')
        self.__ib.register(self.__execDetailsHandler,'execDetails')
        self.__ib.connect()
        if self.__ib.isConnected():
            self.connectionTime=self.__ib.reqCurrentTime()
            self.serverVersion=self.__ib.serverVersion()
            if self.__debug:
                print('%s[IB LiveBroker]********************************'%(now,))
                print('%s[IB LiveBroker]Connection to IB established'%(now,))
                print('%s[IB LiveBroker]IB server connection time: %s' %(now,self.connectionTime))
                print('%s[IB LiveBroker]IB server version: %s' %(now,self.serverVersion))
                
        else:
            print('[LiveBroker] Connection to IB Error')
        ### End Connection to IB
    def refreshAccountBalance(self):
        self.__ib.reqAccountUpdates(1,'')
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print ('%s[IB LiveBroker refreshAccountBalance] *****************************'%(now,))
            print ('%s[IB LiveBroker refreshAccountBalance]subscribes for regular account balances which are sent to portfolio and account handlers'%(now,) )
            print ('%s[IB LiveBroker refreshAccountBalance]------------------------------'%(now,))
        


    def refreshOpenOrders(self):
        self.__ib.reqAllOpenOrders()
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print ('%s[IB LiveBroker refreshOpenOrders] *****************************'%(now,))
            print ('%s[IB LiveBroker refreshOpenOrders]------------------------------'%(now,))

    def __debugHandler(self,msg): 
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker __debugHandler] *****************************'%(now,))
            print ('%s[IB LiveBroker __debugHandler] DEBUG HANDLER'%(now,))
            print ('%s[IB LiveBroker __debugHandler] Message received from Server:' % (now,))
            print ('%s[IB LiveBroker __debugHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __debugHandler] %s' %(now,msg))
            print ('%s[IB LiveBroker __debugHandler]................................................'%(now,))
           

        if msg.execution and msg.contract:#:=='execDetails':
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker __debugHandler __execDetailsHandler] *****************************'%(now,))
            print ('%s[IB LiveBroker __debugHandler __execDetailsHandler] Position msg handler'%(now,))
            print ('%s[IB LiveBroker __debugHandler __execDetailsHandler] Message received from Server:' % (now,))
            print ('%s[IB LiveBroker __debugHandler __execDetailsHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __debugHandler __execDetailsHandler] %s' %(now,msg))
            print ('%s[IB LiveBroker __debugHandler __execDetailsHandler]................................................'%(now,))
            print ('%s[IBLiveBroker __debugHandler execDetailsHandler]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC')
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract contract' %(now,)) 
            ibContract=msg.contract
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract.m_symbol: %s' %(now,ibContract.m_symbol)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract.m_secType: %s' %(now,ibContract.m_secType)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract.m_currency: %s' %(now,ibContract.m_currency)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract.m_exchange: %s' %(now,ibContract.m_exchange)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibContract.m_expiry: %s' %(now,ibContract.m_expiry)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]ibContract.m_strike %s' %(now,ibContract.m_strike))
            ibExecution=msg.execution
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]'%(now))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'%(now))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution ' %(now)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibOrder.m_orderId: %s' %(now,ibExecution.m_orderId)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution.m_execId  : %s' %(now,ibExecution.m_execId  )) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution.m_price : %s' %(now,ibExecution.m_price )) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution.m_shares : %s' %(now,ibExecution.m_shares)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]  ibOrder.m_auxPrice: %s' %(now,ibOrder.m_auxPrice)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution.m_side  %s' %(now,ibExecution.m_side))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution.m_time  %s' %(now,ibExecution.m_time ))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibExecution.m_exchange  %s' %(now,ibExecution.m_exchange  ))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
             
            ibOrder = self.__activeOrders.get(msg.orderId)
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO'%(now))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibOder ' %(now)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibOrder.m_orderId: %s' %(now,ibOrder.m_orderId)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibOrder.m_clientId  : %s' %(now,ibOrder.m_clientId  )) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibOrder.m_action : %s' %(now,ibOrder.m_action )) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler] ibOrder.m_lmtPrice : %s' %(now,ibOrder.m_lmtPrice )) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]  ibOrder.m_auxPrice: %s' %(now,ibOrder.m_auxPrice)) 
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]ibOrder.m_tif  %s' %(now,ibOrder.m_tif ))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]ibOrder.m_transmit  %s' %(now,ibOrder.m_transmit ))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]ibOrder.m_orderType   %s' %(now,ibOrder.m_orderType  ))
            print ('%s[IBLiveBroker __debugHandler __execDetailsHandler]ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_allOrNone  %s' %(now,ibOrder.m_allOrNone ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_tif   %s' %(now,ibOrder.m_tif ))
 


        if msg.keys=='error':
            if msg.errorCode==103:
                print ('%s[IB LiveBroker __debugHandler] error id=0, errorCode=103, errorMsg=Duplicate order id'%(now,))
                #print ('%s[IB LiveBroker __debugHandler] EXIT EXIT EXIT ============================'%(now,))
        if self.__debug:        
             print ('%s[IB LiveBroker __debugHandler] EXIT EXIT EXIT ============================'%(now,))
    def __execDetailsHandler(self,msg):
        ibContract=msg.contract
        ibExecution=msg.execution
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__debug:
                print ('%s[IB LiveBroker __execDetailsHandler] ===START============================'%(now,))

        #Check duplicate execution order
        if ibExecution.m_execId in self.__executionsHistory['ibExecution_m_execId']:
            if self.__debug:
                print ('%s[IB LiveBroker __execDetailsHandler] This is a Duplicate execution order'%(now,))
                self.__printDebug()
            
            return
        #building execution row to add in executionHistory
        rxDict={
                    'datetime':now,
                    'ibOrder_m_orderId': ibExecution.m_orderId,
                    'ibExecution_m_execId':ibExecution.m_execId,
                    'ibExecution_m_acctNumber':ibExecution.m_acctNumber,
                    'ibExecution_m_clientId'  : ibExecution.m_clientId,
                    'ibExecution_m_liquidation':ibExecution.m_liquidation,
                    'ibExecution_m_permId': ibExecution.m_permId,
                    'ibExecution_m_price' : ibExecution.m_price,
                    'ibExecution_m_evMultiplier' : ibExecution.m_evMultiplier,
                    'ibExecution_m_avgPrice' : ibExecution.m_avgPrice,
                    'ibExecution_m_evRule' :  ibExecution.m_evRule,
                    'ibExecution_m_cumQty' :  ibExecution.m_cumQty,
                    'ibExecution_m_shares' : ibExecution.m_shares,
                    'ibExecution_m_side':ibExecution.m_side,
                    'ibExecution_m_time':ibExecution.m_time,
                    'ibExecution_m_exchange':ibExecution.m_exchange

            }
        #adding the new execution in execution history    
        self.__executionsHistory.append(rxDict,ignore_index=True)

        if self.__debug:
            print ('%s[IB LiveBroker __execDetailsHandler] *****************************'%(now,))
            print ('%s[IB LiveBroker __execDetailsHandler] Position msg handler'%(now,))
            print ('%s[IB LiveBroker __execDetailsHandler] Message received from Server:' % (now,))
            print ('%s[IB LiveBroker __execDetailsHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __execDetailsHandler] %s' %(now,msg))
            print ('%s[IB LiveBroker __execDetailsHandler]................................................'%(now,))
            print ('%s[IBLiveBroker  __execDetailsHandler]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'%(now))
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract contract details:' %(now)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_symbol: %s' %(now,ibContract.m_symbol)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_secType: %s' %(now,ibContract.m_secType)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_currency: %s' %(now,ibContract.m_currency)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_exchange: %s' %(now,ibContract.m_exchange)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_expiry: %s' %(now,ibContract.m_expiry)) 
            print ('%s[IBLiveBroker  __execDetailsHandler] ibContract.m_strike %s' %(now,ibContract.m_strike))
            print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_right %s' %(now,ibContract.m_right))
            
            print ('%s[IBLiveBroker __execDetailsHandler]'%(now))
            print ('%s[IBLiveBroker __execDetailsHandler] EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'%(now))
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution details: ' %(now)) 
            print ('%s[IBLiveBroker __execDetailsHandler] ibOrder.m_orderId: %s' %(now,ibExecution.m_orderId))#int m_orderId The order id. Note:  TWS orders have a fixed order id of "0."
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_execId  : %s' %(now,ibExecution.m_execId  ))#String m_execId Unique order execution id.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_acctNumber  : %s' %(now,ibExecution.m_acctNumber  )) # String m_acctNumber the customer account number.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_clientId  : %s' %(now,ibExecution.m_clientId  )) #int m_clientId The id of the client that placed the order. Note: TWS orders have a fixed client id of "0."
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_liquidation : %s' %(now,ibExecution.m_liquidation )) #int m_liquidation Identifies the position as one to be liquidated last should the need arise.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_permId : %s' %(now,ibExecution.m_permId )) #int m_permId The TWS id used to identify orders, remains the same over TWS sessions.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_price : %s' %(now,ibExecution.m_price ))#The order execution price, not including commissions. 
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_evMultiplier : %s' %(now,ibExecution.m_evMultiplier ))#double m_evMultiplier	Tells you approximately how much the market value of a contract would change if the price were to change by 1. It cannot be used to get market value by multiplying the price by the approximate multiplier            
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_avgPrice : %s' %(now,ibExecution.m_avgPrice )) #double m_avgPrice Average price. Used in regular trades, combo trades and legs of the combo. Does not include commissions.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_evRule : %s' %(now,ibExecution.m_evRule )) #String m_evRule	Contains the Economic Value Rule name and the respective optional argument. The two values should be separated by a colon. For example, aussieBond:YearsToExpiration=3. When the optional argument is not present, the first value will be followed by a colon.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_cumQty : %s' %(now,ibExecution.m_cumQty ))#int m_cumQty Cumulative quantity. Used in regular trades, combo trades and legs of the combo.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_shares : %s' %(now,ibExecution.m_shares)) #int m_shares The number of shares filled.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_side  %s' %(now,ibExecution.m_side))#String m_side Specifies if the transaction was a sale or a purchase. Valid values are BOT SLD
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_time  %s' %(now,ibExecution.m_time ))#String m_time The order execution time.
            print ('%s[IBLiveBroker __execDetailsHandler] ibExecution.m_exchange  %s' %(now,ibExecution.m_exchange  ))#String m_exchange Exchange that executed the order.
        #Retrieving the active Order associated to the execution
        ibContrcatA,ibOderA = getActiveOrder(ibOrder.m_orderId)
        assert(ibContrcatA is Contract),'[IB LiveBroker __execDetailsHandler] Error contract not in active Order Table'
        assert(ibOderA is Order),'[IB LiveBroker __execDetailsHandler] Error Order not in active Order Table'

        if self.__debug:
            print ('%s[IBLiveBroker __execDetailsHandler]Retrieving Order from Active Order Table'%(now))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_totalQuantity   %s' %(now,ibOrderA.m_totalQuantity ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOder ' %()) 
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_orderId: %s' %(now,ibOrderA.m_orderId)) 
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_clientId  : %s' %(now,ibOrderA.m_clientId  )) 
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_action : %s' %(now,ibOrderA.m_action )) 
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_lmtPrice : %s' %(now,ibOrderA.m_lmtPrice )) 
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_auxPrice: %s' %( ibOrderA.m_auxPrice)) 
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_tif  %s' %(now,ibOrderA.m_tif ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_transmit  %s' %(now,ibOrderA.m_transmit ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_orderType   %s' %(now,ibOrderA.m_orderType  ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_totalQuantity   %s' %(now,ibOrderA.m_totalQuantity ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_allOrNone  %s' %(now,ibOrderA.m_allOrNone ))
            print ('%s[IBLiveBroker __execDetailsHandler]ibOrder.m_tif   %s' %(now,ibOrderA.m_tif ))
            print ('%s[IBLiveBroker __execDetailsHandler]Consistency Check OK: order and contract from IB same as the one recorded in Active Order Table')


        #Iborder consistency check between value from execution and Active Order table
        if ibOrderA.m_orderId!=ibExecution.m_orderId :
            if self.__debug:
                print('%s[IBLiveBroker __execDetailsHandler] Order Consistency Check Order NO OK')
                raise('%s[IBLiveBroker __execDetailsHandler] Order Consistency Check Oredr NO OK')
            
        else:
            if self.__debug:
                print('%s[IBLiveBroker __execDetailsHandler] Order Consistency Check ORDER OK')
        
            
        if ibContract.m_symbol==ibContractA.m_symbol and \
            ibContract.m_secType==ibContractA.m_secType and \
            ibContract.m_currency==ibContractA.m_currency and \
            ibContract.m_exchange==ibContractA.m_exchange and \
            ibContract.m_multiplier==ibContractA.m_multiplier and \
            ibContract.m_expiry==ibContractA.m_expiry and \
            ibContract.m_strike==ibContractA.m_strike and\
            ibContract.m_right==ibContractA.m_right:
            if self.__debug:
                print('%s[IBLiveBroker __execDetailsHandler] contract Consistency Check OK'%(now))
        else:
            if self.__debug:
                print ('%s[IBLiveBroker __execDetailsHandler] Consistency Check NO OK'%(now))
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract from Active Order Table contract'%(now)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_symbol: %s' %(now,ibContractA.m_symbol)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_secType: %s' %(now,ibContractA.m_secType)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_currency: %s' %(now,ibContractA.m_currency)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_exchange: %s' %(now,ibContractA.m_exchange)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_multiplier: %s' %(now,ibContractA.m_multiplier)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_expiry: %s' %(now,ibContractA.m_expiry)) 
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_strike %s' %(now,ibContractA.m_strike))
                print ('%s[IBLiveBroker __execDetailsHandler] ibContract.m_right %s' %(now,ibContractA.m_right))
                      
           
                self.__printDebug()
            raise('[IB LiveBroker __execDetailsHandler] Contract Consistency Check NO OK')

        if self.__debug:
            print ('%s[IBLiveBroker __execDetailsHandler] Check if order Executed Completely or Partially')

        if ibOrder.m_totalQuantity==ibExecution.m_shares:
            status='FILLED'
            self.__setOrderStatus(contract=contract,order=order,status=status, datetime=datetime.datetime.now())
            self.__registerOrder(contract=contract,order=order,status=status,datetime=datetime.datetime.now())

        elif ibOrder.m_totalQuantity>ibExecution.m_shares:
            status='PARTIALLY FILLED'
            self.__setOrderStatus(contract=contract,order=order,status=status,partialFilledQuantitiy=ibExecution.m_shares, datetime=datetime.datetime.now())
            self.__registerOrder(contract=contract,order=order,status=status,partialFilledQuantitiy=ibExecution.m_shares,datetime=datetime.datetime.now())
        else:
            self.__printDebug()
            raise('Execution order > or order not executed submitted')
                #building execution row to add in executionHistory
        rxDict={
                    'datetime':now,
                    'ibOrder_m_orderId': ibExecution.m_orderId,
                    'ibExecution_m_execId':ibExecution.m_execId,
                    'ibExecution_m_acctNumber':ibExecution.m_acctNumber,
                    'ibExecution_m_clientId'  : ibExecution.m_clientId,
                    'ibExecution_m_liquidation':ibExecution.m_liquidation,
                    'ibExecution_m_permId': ibExecution.m_permId,
                    'ibExecution_m_price' : ibExecution.m_price,
                    'ibExecution_m_evMultiplier' : ibExecution.m_evMultiplier,
                    'ibExecution_m_avgPrice' : ibExecution.m_avgPrice,
                    'ibExecution_m_evRule' :  ibExecution.m_evRule,
                    'ibExecution_m_cumQty' :  ibExecution.m_cumQty,
                    'ibExecution_m_shares' : ibExecution.m_shares,
                    'ibExecution_m_side':ibExecution.m_side,
                    'ibExecution_m_time':ibExecution.m_time,
                    'ibExecution_m_exchange':ibExecution.m_exchange

            }
        #adding the new execution in execution history    
        self.__executionsHistory.append(rxDict,ignore_index=True)
    def __accountHandler(self,msg):
        import datetime as dat
        #FYI this is not necessarily USD - probably AUD for me as it's the base currency so if you're buying international stocks need to keep this in mind
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #if self.__debug:
            #print ('%s[IB LiveBroker __accountHandler] *****************************'% (now,))
            #print ('%s[IB LiveBroker __accountHandler] get account messages like cash value etc'% (now,))
            #print ('%s[IB LiveBroker __accountHandler] Message received from Server:' % (now,))
            #print ('%s[IB LiveBroker __accountHandler]................................................'% (now,))
            #print ('%s[IB LiveBroker __accountHandler]  %s' % (now,msg))
            #print ('%s[IB LiveBroker __accountHandler]................................................'% (now,))

        if msg.key == 'TotalCashBalance' and msg.currency == 'USD':
            self.__cash = round(float(msg.value))
        #if self.__debug: 
            #print ('%s[IB LiveBroker __accountHandler] Account cash set: %s ' %(now,self.__cash ))
            #print ('%s[IB LiveBroker __accountHandler] -EXIT EXIT EXIT-----------------------------'% (now,))

    def __portfolioHandler(self,msg):
        #contract=<ib.ext.Contract.Contract object at 0x00000000084E3278>, position=-5, marketPrice=1.11680995, marketValue=-5.58, 
        #averageCost=0.91886, unrealizedPNL=-0.99, realizedPNL=0.0, accountName=DU213041
        import datetime as dat
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ibContract=msg.contract
        portDict={
        'datetime': now,
        'ibContract_m_symbol':ibContract.m_symbol,
        'ibContract_m_secType':ibContract.m_secType,
        'ibContract_m_currency':ibContract.m_currency,
        'ibContract_m_exchange':ibContract.m_exchange,
        'ibContract_m_multiplier':ibContract.m_multiplier,
        'ibContract_m_expiry':ibContract.m_expiry ,
        'ibContract_m_strike':ibContract.m_strike,
        'ibContract_m_right':ibContract.m_right,
        'position' :msg.position,
        'marketPrice' : msg.marketPrice,
        'marketValue' : msg.marketValue,
        'averageCost' :  msg.averageCost,
        'unrealizedPNL': msg.unrealizedPNL,
        'realizedPNL'  : msg.realizedPNL,
        'accountName'  : msg.accountName,}
        if self.__debug:
            print ('%s[IB LiveBroker __portfolioHandler] Message received from Server:' % (now,))
            print ('%s[IB LiveBroker __portfolioHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __portfolioHandler] %s' %(now,msg))
            print ('%s[IB LiveBroker __portfolioHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __portfolioHandler]Existing Position Received from IB: ' %(now,))
            print ('%s[IB LiveBroker __portfolioHandler] %s  ' %(now,portDict))
        
        self.__detailedActivePositionsHistory=self.__detailedActivePositionsHistory.append(portDict,ignore_index=True)
        if self.__debug:
            print ('%s[IB LiveBroker __portfolioHandler] Position Received from IB added to Position history:  ' %(now,))
            print ('%s[IB LiveBroker __portfolioHandler]  %s  ' %(now,self.__detailedActivePositionsHistory))
        
        contractExist=False
        for position in self.__activePositions:
            if position['ibContract_m_symbol'] ==ibContract.m_symbol and \
                position['ibContract_m_secType']==ibContract.m_secType and\
                position['ibContract_m_currency']==ibContract.m_currency and\
                position['ibContract_m_exchange']==ibContract.m_exchange and\
                position['ibContract_m_multiplier']==ibContract.m_multiplier and\
                position['ibContract_m_expiry']==ibContract.m_expiry and\
                position['ibContract_m_strike']==ibContract.m_strike and\
                position['ibContract_m_right']==ibContract.m_right:
                    position['position'] =msg.position,
                    position['marketPrice'] = msg.marketPrice,
                    position['marketValue'] = msg.marketValue,
                    position['averageCost'] =  msg.averageCost,
                    position['unrealizedPNL'] =msg.unrealizedPNL,
                    position['realizedPNL']  = msg.realizedPNL,
                    contractExist=True    
                    if self.__debug:
                        print ('%s[IB LiveBroker __portfolioHandler]Position Received from IB existing in Active Positon table:  ' %(now,))
                        print ('%s[IB LiveBroker __portfolioHandler]  %s  ' %(now,self.__activePositions))

        if contractExist==False:
            self.__activePositions.append(portDict)
            if self.__debug:
                print ('%s[IB LiveBroker __portfolioHandler]Position Received from IB Not existing in Active Positon table:added to Active Position:  ' %(now,))
                print ('%s[IB LiveBroker __portfolioHandler]  %s  ' %(now,self.__activePositions))

        #history code kept to be compatible with previous code this code only 
        #handle only stock
        self.__shares[msg.contract.m_symbol] = msg.position
        self.__detailedShares[msg.contract.m_symbol] = {    'shares': msg.position,             #number of units
                                                            'marketPrice': msg.marketPrice,     #current price on market
                                                            'entryPrice': msg.averageCost,      #cost per unit at acquistion (unfortunately minus commissions)
                                                            'PL': msg.unrealizedPNL             #unrealised profit and loss
                                                        }
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print ('%s[IB LiveBroker __portfolioHandler] *HISTORICAL PART****************************'%(now,))
            #print ('%s[IB LiveBroker __portfolioHandler] get portfolio messages - stock, price, purchase price etc'%(now,))
            #print ('%s[IB LiveBroker __portfolioHandler] Symbol %s  ' %(now,msg.contract.m_symbol))
            print ('%s[IB LiveBroker __portfolioHandler] Updated position number of share : %s, %s' %(now,msg.contract.m_symbol, msg.position))

            print('%s[IB LiveBroker __portfolioHandler] self_.detailedShare: %s '%(now,self.__detailedShares))
            print ('%s[IB LiveBroker __portfolioHandler] Seld detailed position for share %s' % (now,self.__detailedShares))
            print ('%s[IB LiveBroker __portfolioHandler] --EXIT EXIT EXIT----------------------------'%(now,))
    def __orderStatus(self,msg):
        if msg.status == "Filled" and \
            self.fill_dict[msg.orderId]["filled"] == False:
            self.create_fill(msg)
        print("Server Response: %s, %s\n" % (msg.typeName, msg))        
        
        
    def __openOrderHandler(self,msg):
        #Do nothing now but might want to use this to pick up open orders at start (eg in case of shutdown or crash)
        #note if you want to test this make sure you actually have an open order otherwise it's never called
        #Remember this is called once per open order so if you have 3 open orders it's called 3 times

        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
        ibContract=msg.contract
        ibOrder =msg.order

        if self.__debug:
            print ('%s[IB LiveBroker __openOrderHandler] *****************************'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] Do nothing now but might want to use this to pick up open orders at start (eg in case of shutdown or crash)'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] note if you want to test this make sure you actually have an open order otherwise it is never called'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] Remember this is called once per open order so if you have 3 open orders it is called 3 times'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] Message received from Server:' %(now,))
            print ('%s[IB LiveBroker __openOrderHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler]  %s' %(now,msg))
            print ('%s[IB LiveBroker __openOrderHandler]................................................'%(now,))
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker __openOrderHandler] *****************************'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] Position msg handler'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] Message received from Server:' % (now,))
            print ('%s[IB LiveBroker __openOrderHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] %s' %(now,msg))
            print ('%s[IB LiveBroker __openOrderHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __openOrderHandler]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC')
            print ('%s[IB LiveBroker __openOrderHandler] ibContract contract' %(now,)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibContract.m_symbol: %s' %s(now,ibContract.msymbol)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibContract.m_secType: %s' %s(now,ibContract.msecType)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibContract.m_currency: %s' %s(now,ibContract.mcurrency)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibContract.m_exchange: %s' %s(now,ibContract.mexchange)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibContract.m_multiplier: %s' %s(now,ibContract.mmultiplier)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibContract.m_expiry: %s' %s(now,ibContract.mexpiry)) 
            print ('%s[IB LiveBroker __openOrderHandler]ibContract.m_strike %s' %s(now,ibContract.mstrike))
            print ('%s[IB LiveBroker __openOrderHandler]O from IB  '%(now,))
            print ('%s[IB LiveBroker __openOrderHandler] ibOder ' %(now,)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_orderId: %s' %(now,ibOrder.m_orderId)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_clientId  : %s' %(now,ibOrder.m_clientId  )) 
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_action : %s' %(now,ibOrder.m_action )) 
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_lmtPrice : %s' %(now,ibOrder.m_lmtPrice )) 
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_auxPrice: %s' %(now,ibOrder.m_auxPrice)) 
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_tif  %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_transmit  %s' %(now,ibOrder.m_transmit ))
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_orderType   %s' %(now,ibOrder.m_orderType  ))
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_allOrNone  %s' %(now,ibOrder.m_allOrNone ))
            print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_tif   %s' %(now,(ibOrder.m_tif )))

        ibOderFromActiveTable = self.getActiveOrder(msg.order.orderId)
        if isinstance(ibOderFromActiveTable,Order):
            if self.__debug:
                print ('%s[IB LiveBroker __openOrderHandler] Open Order in Active Order'%(now,))
                print ('%s[IB veBroker __openOrderHandler] ibOder ' %(now,)) 
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_orderId: %s' %(now,ibOderFromActiveTable.m_orderId)) 
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_clientId  : %s' %(now,ibOderFromActiveTable.m_clientId  )) 
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_action : %s' %(now,ibOderFromActiveTable.m_action )) 
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_lmtPrice : %s' %(now,ibOderFromActiveTable.m_lmtPrice )) 
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_auxPrice: %s' %(now,ibOderFromActiveTable.m_auxPrice)) 
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_tif  %s' %(now,ibOderFromActiveTable.m_tif ))
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_transmit  %s' %(now,ibOderFromActiveTable.m_transmit ))
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_orderType   %s' %(now,ibOderFromActiveTable.m_orderType  ))
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_totalQuantity   %s' %(now,ibOderFromActiveTable.m_totalQuantity ))
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_allOrNone  %s' %(now,ibOderFromActiveTable.m_allOrNone ))
                print ('%s[IB LiveBroker __openOrderHandler] ibOrder.m_tif   %s' %(now,(ibOderFromActiveTable.m_tif )))
        else:
            if self.__debug:
                print ('%s[IB LiveBroker __openOrderHandler] Open Order Not in Active Order, These Order should be Recorded or Cancelled'%(now,))
            
    def __disconnectHandler(self,msg):
        self.__ib.reconnect()
    def __positionHandler(self,msg):
        if self.__debug:
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker __positionHandler] *****************************'%(now,))
            print ('%s[IB LiveBroker __positionHandler] Position msg handler'%(now,))
            print ('%s[IB LiveBroker __positionHandler] Message received from Server:' % (now,))
            print ('%s[IB LiveBroker __positionHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __positionHandler] %s' %(now,msg))
            print ('%s[IB LiveBroker __positionHandler]................................................'%(now,))
            print ('%s[IB LiveBroker __positionHandler] Symbol %s  ' %(now,msg.contract.m_symbol))
            print ('%s[IB LiveBroker __positionHandler] Updated position number of share : %s, %s' %(now,msg.contract.m_symbol, msg.position))
            print ('%s[IB LiveBroker __positionHandler] self_.detailedShare: %s '%(now,self.__detailedShares))
            print ('%s[IB LiveBroker __positionHandler] Seld detailed position for share %s' % (now,self.__detailedShares))
            print ('%s[IB LiveBroker __positionHandler] --EXIT EXIT EXIT----------------------------'%(now,))
            
    def __getUniqueOrderId(self):
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.__ordersHistory.empty:
            self.__nextOrderId=0
            #return self.__nextOrderId
        else:
            self.__nextOrderId=int(self.__ordersHistory['ibOrder_m_orderId'].max())+1
            #return self.__nextOrderId
        if self.__nextOrderId in self.__ordersHistory['ibOrder_m_orderId']:
            raise('getUniqueOrderId created a duplicate order ID %s' %(self.__nextOrderId))
        else:
            if self.__debug:
               now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
               print('%s[IB LiveBroker getUniqueOrderId]INCREASE ORDER ID: %s' %(now,self.__nextOrderId))

            return self.__nextOrderId

    def __setOrderStatus(self,contract,order,status, datetime,partialFilledQuantitiy=None,openOrderYesNo=False):
        if status not in ['GENERATED','SUBMITTED','PRESUBMITTED','FILLED','PARTIALLY_FILLED','CANCELLED_BY_USER','CANCELLED_BY_API']:
            raise('Status can only be either: SUBMITTED,FILLED,PARTIALLY FILLED,CANCELLED BY USER,CANCELLED BY API')
            
        elif status in ('GENERATED'):
            dico={
                    'ibOrder_m_orderId':ibOrder.m_orderId,
                    'status':'SUBMITTED',
                    'ibOrder_m_permid':ibOrder.m_permid,
                    'ibContract_m_symbol':ibContract.m_symbol,
                    'ibContract_m_secType':ibContract.m_secType,
                    'ibContract_m_currency':ibContract.m_currency,
                    'ibContract_m_exchange':ibContract.m_exchange,
                    'ibContract_m_expiry':ibContract.m_expiry ,
                    'ibContract_m_strike':ibContract.m_strike,
                    'ibOrder_m_action':ibOrder.m_action,
                    'ibOrder_m_lmtPrice':ibOrder.m_lmtPrice,
                    'ibOrder_m_auxPrice':ibOrder.m_auxPrice,
                    'ibOrder_m_tif':ibOrder.m_tif,
                    'ibOrder_m_transmit':ibOrder.m_transmit,
                    'ibOrder_m_orderType':ibOrder.m_orderType,
                    'ibOrder_m_totalQuantity':ibOrder.m_totalQuantity,
                }
            self.__activeOrders.append(dico,ignore_index=True)

        elif status in ('FILLED',):
            #Remove from active Order
            i=0
            position=0
            for Order in self.__activeOrder:
                if(Order['ibOrder_m_orderId']==ibOrder.m_orderId):
                    position=i
                    i+=1
            if i !=1:
                raise('Order ID %s not unique'%(ibOrder.m_orderId))
            elif i==0:                
                raise('Order ID %s does not exist in active order'%(ibOrder.m_orderId))
            elif i==1:
                #delete the order from active order
                del self.__activeOrder[position]
                self.__completelyFilledOrder.append(ibOrder.m_orderId)
                
                
        elif (status in ('PARTIALLY FILLED')) and (partialFilledQuantitiy !=None):
            i=0
            position=0
            for Order in self.__activeOrder:
                if(Order['ibOrder_m_orderId']==ibOrder.m_orderId):
                    position=i
                    i+=1
                if i !=1:
                    raise('Order ID %s not unique'%(ibOrder.m_orderId))
                elif i==0:                
                    raise('Order ID %s does not exist in active order'%(ibOrder.m_orderId))
                elif i==1:
                    #delete the order from active order
                    self.__activeOrder[position]['ibOrder_m_totalQuantity']=int(self.__activeOrder[position]['ibOrder_m_totalQuantity'])-int(partialFilledQuantitiy)
               
        elif status in ('CANCELLED BY USER','CANCELLED BY API'):
            #Remove from active Order
            i=0
            position=0
            for Order in self.__activeOrder:
                if(Order['ibOrder_m_orderId']==ibOrder.m_orderId):
                    position=i
                    i+=1
            if i !=1:
                raise('Order ID %s not unique'%(ibOrder.m_orderId))
            elif i==0:                
                raise('Order ID %s does not exist in active order'%(ibOrder.m_orderId))
            elif i==1:
                #delete the order from active order
                del self.__activeOrder[position]

    def __registerOrder(self,status,contract,order,datetime,partialFilledQuantitiy=None):
            now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ibContract=contract
            ibOrder=order
            orderDict={
            'datetime'              :   datetime,
            'status'                :   status,
            'ibOrder_m_orderId'     :   ibOrder.m_orderId,
            'ibOrder_m_permid'      :   ibOrder.m_permid,
            'partialFilledQuantitiy':   partialFilledQuantitiy,
            'ibContract_m_symbol'   :   ibContract.m_symbol,
            'ibContract_m_secType'  :   ibContract.m_secType,
            'ibContract_m_currency' :   ibContract.m_currency,
            'ibContract_m_exchange' :   ibContract.m_exchange,
            'ibContract_m_multiplier':  ibContract.m_multiplier,
            'ibContract_m_expiry'   :   ibContract.m_expiry ,
            'ibContract_m_strike'   :   ibContract.m_strike,
            'ibOrder_m_action'      :   ibOrder.m_action,
            'ibOrder_m_lmtPrice'    :   ibOrder.m_lmtPrice,
            'ibOrder_m_auxPrice'    :   ibOrder.m_auxPrice,
            'ibOrder_m_tif'         :   ibOrder.m_tif,
            'ibOrder_m_transmit'    :   ibOrder.m_transmit,
            'ibOrder_m_orderType'   :   ibOrder.m_orderType,
            'ibOrder_m_totalQuantity':  ibOrder.m_totalQuantity,
            'ibOrder_m_parentId'    :   ibOrder.m_parentId,          #int m_parentId	The order ID of the parent order, used for bracket and auto trailing stop orders.
            'ibOrder_m_trailStopPrice': ibOrder.m_trailStopPrice,    #m_trailStopPrice	For TRAILLIMIT orders only
            'ibOrder_m_trailingPercent':ibOrder.m_trailingPercent,   # double m_trailingPercent	
            'ibOrder_m_allOrNone'   :   ibOrder.m_allOrNone,
            'ibOrder_m_tif'         :   ibOrder.m_tif,
            'openOrderYesNo'        :   openOrderYesNo,
            'ibOrder_m_clientId'    :   ibOrder.m_clientId,
            }
            #2016-02-04 11:17:10[IB LiveBroker __portfolioHandler] <updatePortfolio contract=<ib.ext.Contract.Contract object at 0x00000000088E2FD0>, position=300, marketPrice=0.31, marketValue=9300.0, averageCost=31.2674, unrealizedPNL=-80.22, realizedPNL=0.0, accountName=DU213041>
            self.__ordersHistory=self.__ordersHistory.append(orderDict,ignore_index=True)
            
           
    def __printDebug(self):
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print ('self.__activeOrder:')
 
        print (self.__activeOrder)
        print ('self.__completelyFilledOrder')

        print (self.__completelyFilledOrder)
        print ('self.__ordersHistory')
        print (self.__ordersHistory)

        print ('self.__cash')
        print (self.__cash)

        print ('self.__activePositions')
        print (self.__activePositions)

        #print ('self.__detailedActivePositions')
        #print (self.__detailedActivePositions)

        print ('self.__detailedActivePositionsHistory')
        print (self.__detailedActivePositionsHistory)

        print ('self.__nextOrderId')
        print (self.__nextOrderId)

        print ('self.__initialPositions')
        print (self.__initialPositions)

        print ('self.__executionsHistory')
        print (self.__executionsHistory)
        
         

        
    def getCash(self, includeShort=True):
        return self.__cash


    def getShares(self, instrument=None):
        '''
        Modified function to allow return of share dictionaries
        '''
        if instrument!=None:
            return self.__shares.get(instrument, 0)
        else:
            return self.__shares

    def getPositions(self):
    
        return self.__activePositions
        
    def getActiveOrder(self,orderId):
        i=0
        pos=0
        for Order in self.__activeOrder:
            if orderId==Order.ibOrder.m_orderId:
                i+=1
                pos=i       
        if i !=1:
            raise('Order ID %s not unique in Active Order Table'%(ibOrder.m_orderId))
        elif i==0:                
            raise('Order ID %s does not exist in active order'%(ibOrder.m_orderId))
        elif i==1:

            ibContract=Contract() 
            ibContract.m_symbol     =   self.__activeOrder[pos]['ibContract_m_symbol']
            ibContract.m_secType    =   self.__activeOrder[pos]['ibContract_m_secType']
            ibContract.m_currency   =   self.__activeOrder[pos]['ibContract_m_currency']
            ibContract.m_exchange   =   self.__activeOrder[pos]['ibContract_m_exchange']
            ibContract.m_multiplier =   self.__activeOrder[pos]['ibContract_m_multiplier']
            ibContract.m_expiry     =   self.__activeOrder[pos]['ibContract_m_expiry']
            ibContract.m_strike     =   self.__activeOrder[pos]['ibContract_m_strike']
            ibOrder=Order()

            ibOrder.m_action       =    self.__activeOrder[pos]['ibOrder_m_action']
            ibOrder.m_lmtPrice     =    self.__activeOrder[pos]['ibOrder_m_lmtPrice']
            ibOrder.m_auxPrice     =    self.__activeOrder[pos]['ibOrder_m_auxPrice']
            ibOrder.m_tif          =    self.__activeOrder[pos]['ibOrder_m_tif']
            ibOrder.m_transmit   =      self.__activeOrder[pos]['ibOrder_m_transmit']
            ibOrder.m_orderType   =     self.__activeOrder[pos]['ibOrder_m_orderType']
            ibOrder.m_totalQuantity=    self.__activeOrder[pos]['ibOrder_m_totalQuantity']
            return ibContract, ibOrder
    def makeStkContrcat(self,m_symbol,m_secType = 'STK',m_exchange = 'SMART',m_currency = 'USD'):
        from ib.ext.Contract import Contract
        newContract = Contract()
        newContract.m_symbol = m_symbol
        newContract.m_secType = m_secType
        newContract.m_exchange = m_exchange
        newContract.m_currency = m_currency
        return newContract
    def makeOptContract(self,m_symbol, m_right, m_expiry, m_strike,m_secType = 'OPT',m_exchange = 'SMART',m_currency = 'USD'):
        '''
        makeOptContract('BAC', '20160304', 'C', 15)
        sym: Ticker instrument
        exp: expiry date format YYYYYMMDD
        right: C or P 
        strike price: float
        '''
        from ib.ext.Contract import Contract
        newOptContract = Contract()
        newOptContract.m_symbol = m_symbol
        newOptContract.m_secType = m_secType
        newOptContract.m_right = m_right
        newOptContract.m_expiry = m_expiry
        newOptContract.m_strike = float(m_strike)
        newOptContract.m_exchange = m_exchange
        newOptContract.m_currency = m_currency
        #newOptContract.m_localSymbol = ''
        #newOptContract.m_primaryExch = ''
        return newOptContract
    def makeForexContract(self,m_symbol,m_secType = 'CASH',m_exchange = 'IDEALPRO',m_currency = 'USD'):
        from ib.ext.Contract import Contract
        newContract = Contract()
        newContract.m_symbol = m_symbol
        newContract.m_secType = m_secType
        newContract.m_exchange = m_exchange
        newContract.m_currency = m_currency
        return newContract
    def makeOrder(self,m_orderId, m_action,m_tif ,
                 m_orderType,m_totalQuantity,
                 m_clientId = 0,m_permid = 0,m_lmtPrice = 0,m_auxPrice = 0,m_transmit = True):
        '''
        optOrder = makeOptOrder( 'BUY', orderID, 'DAY', 'MKT')
        action: 'BUY' or 'SELL'
        orderID: float that identifies the order
        tif: time in force 'DAY', 'GTC'
        orderType:'MKT','STP','STP LMT'
        totalQunatity: int number of share  
        '''
        from ib.ext.Order import Order
        newOptOrder = Order()
        newOptOrder.m_orderId           =   m_orderId  #int m_orderId	The id for this order.
        newOptOrder.m_clientId          =   m_clientId #int m_clientId	The id of the client that placed this order.
        newOptOrder.m_permid            =   m_permid #int m_permid	The TWS id used to identify orders, remains the same over TWS sessions.
        #Main Order Fields
        newOptOrder.m_action            =   m_action #String m_action	Identifies the side. Valid values are: BUY, SELL, SSHORT
        newOptOrder.m_lmtPrice          =   m_lmtPrice #double m_lmtPrice This is the LIMIT price, used for limit, stop-limit and relative orders. In all other cases specify zero. For relative orders with no limit price, also specify zero.
        newOptOrder.m_auxPrice          =   m_auxPrice #double m_auxPrice This is the STOP price for stop-limit orders, and the offset amount for relative orders. In all other cases, specify zero.
        newOptOrder.m_orderType         =   m_orderType #String m_orderType
        newOptOrder.m_totalQuantity     =   int(m_totalQuantity) #long m_totalQuantity	The order quantity.
        newOptOrder.m_parentId          =   None  #int m_parentId	The order ID of the parent order, used for bracket and auto trailing stop orders.
        newOptOrder.m_trailStopPrice    =   None  #m_trailStopPrice	For TRAILLIMIT orders only
        newOptOrder.m_trailingPercent   =   None  # double m_trailingPercent	

        #Extended Order Fields
        newOptOrder.m_tif           =   m_tif #String m_tif	The time in force. Valid values are: DAY, GTC, IOC, GTD.
        newOptOrder.m_transmit      =   m_transmit #  bool m_transmit	Specifies whether the order will be transmitted by TWS. If set to false, the order will be created at TWS but will not be sent.
        newOptOrder.m_allOrNone     = 0 #  boolean m_allOrNone	0 = no, 1 = yes

        return newOptOrder
    def checkOrderStatus(self,order):
        ibOrder=order
        i=0
        position=0
        for Order in self.__activeOrder:
            if(Order['ibOrder_m_orderId']==ibOrder.m_orderId):
                position=i
                i+=1
        if i !=1:
            return('Order ID %s not unique'%(ibOrder.m_orderId))
        elif i==0:                
            return('Order ID %s does not exist in active order'%(ibOrder.m_orderId))
        elif i==1:
            return self.__activeOrder[position]['status']
    def submitOrder(self,contract,order):
            ''' 
            Process contract and order then submit to IB
            '''
 
            if checkOrderStatus(order) =='GENERATED':# Order must be in Generated status in the Active Order Table
                
                ibContract=contract
                ibOrder=order
                if self.__debug:
                    now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                    print ('%s[IB LiveBroker submitOrder] CONTRACT RECEIVED INFORMATION') 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_symbol    : %s' %(now,ibContract.m_symbol)) 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_secType   : %s' %(now,ibContract.m_secType)) 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_currency  : %s' %(now,ibContract.m_currency)) 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_exchange  : %s' %(now,ibContract.m_exchange)) 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_expiry    : %s' %(now,ibContract.m_expiry)) 
                    print ('%s[IB LiveBroker submitOrder] ibContract.m_strike    : %s' %(now,ibContract.m_strike))
                    print   ('%s[IB LiveBroker submitOrder]')
                    print ('%s[IB LiveBroker submitOrder] ORDER RECEIVED INFORMATION') 
                    print ('%s[IB LiveBroker submitOrder] m_clientId         : %s' %(now,ibOrder.m_clientId))
                    print ('%s[IB LiveBroker submitOrder] m_orderId          : %s' %(now,ibOrder.m_orderId))
                    print ('%s[IB LiveBroker submitOrder] m_parentId          : %s' %(now,ibOrder.m_parentId))
                    print ('%s[IB LiveBroker submitOrder] m_action           : %s' %(now,ibOrder.m_action))
                    print ('%s[IB LiveBroker submitOrder] m_transmit         : %s' %(now,ibOrder.m_transmit))
                    print ('%s[IB LiveBroker submitOrder] m_orderType        : %s' %(now,ibOrder.m_orderType))
                    print ('%s[IB LiveBroker submitOrder] m_totalQuantity    : %s' %(now,ibOrder.m_totalQuantity)) 
                    print ('%s[IB LiveBroker submitOrder] m_lmtPrice         : %s' %(now,ibOrder.m_lmtPrice)) 
                    print ('%s[IB LiveBroker submitOrder] m_auxPrice STOP    : %s' %(now,ibOrder.m_auxPrice)) 
                    print ('%s[IB LiveBroker submitOrder] m_trailStopPrice   : %s' %(now,ibOrder.m_trailStopPrice)) 
                    print ('%s[IB LiveBroker submitOrder] m_trailingPercent  : %s' %(now,ibOrder.m_trailingPercent)) 
                    print ('%s[IB LiveBroker submitOrder] m_allOrNone        : %s' %(now,ibOrder.m_allOrNone)) 
                    print ('%s[IB LiveBroker submitOrder] m_tif              : %s' %(now,ibOrder.m_tif)) 

                self.__ib.placeOrder(ibOrder.m_orderId,ibContract, ibOrder)
                if self.__debug:
                    print('%s[IB LiveBroker submitOrder] ORDER SUBMITTED TO IB' %(now))
            
                self.__setOrderStatus(contract=contract,order=order,status='SUBMITTED', datetime=datetime.datetime.now())
                self.__registerOrder(contract=contract,order=order,status='SUBMITTED',datetime=datetime.datetime.now())
                self.__nextOrderId += 1
                if self.__debug:
                    print('%s[submitOrder] INCREASE ORDER ID: %s' %(now,self.__nextOrderId))

            else:
                if self.__debug:
                    raise('Order %s not in GEnerated Status ' %(order.m_orderId))
                    print('[submitOrder] =====EXIT===============EXIT=====EXIT' %())
                    raise Exception("The order was already processed")
    def createMarketOrder(self, contract,action, quantity, GoodTillCanceled = True,AllOrNone = True):
        ibContract=contract
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createMarketOrder] CONTRACT RECEIVED INFORMATION') 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_symbol    : %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_secType   : %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_currency  : %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_exchange  : %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_expiry    : %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_strike    : %s' %(now,ibContract.m_strike))
            
        ibOrder=Order()
        ibOrder.m_orderId       = self.__getUniqueOrderId()
        ibOrder.m_totalQuantity = quantity
        
        if action == 'BUY':
            ibOrder.m_action    = 'BUY'
        elif action == 'SELL':
            ibOrder.m_action = 'SELL'
 
        ibOrder.m_orderType = 'MKT'
 
        if AllOrNone == AllOrNone:
            ibOrder.m_allOrNone = 1
        else:
            ibOrder.m_allOrNone = 0

        if GoodTillCanceled == True:
            ibOrder.m_tif = 'GTC'
        else:
            ibOrder.m_tif = 'DAY'
            
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createMarketOrder]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'%(now))
            print ('%s[IB LiveBroker createMarketOrder] ibContract contract' %(now)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_symbol: %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_secType: %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_currency: %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_exchange: %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createMarketOrder] ibContract.m_expiry: %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createMarketOrder]ibContract.m_strike %s' %(now,ibContract.m_strike))

            print ('%s[IB LiveBroker createMarketOrder]'%(now))
            print ('%s[IB LiveBroker createMarketOrder] OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO'%(now))
            print ('%s[IB LiveBroker createMarketOrder] ibOder ' %(now)) 
            print ('%s[IB LiveBroker createMarketOrder] ibOrder.m_orderId: %s' %(now,ibOrder.m_orderId)) 
            print ('%s[IB LiveBroker createMarketOrder] ibOrder.m_clientId  : %s' %(now,ibOrder.m_clientId  )) 
            #print ('%s[IB LiveBroker createMarketOrder] ibOrder.m_permid: %s' %(now,ibOrder.m_permid)) 
            print ('%s[IB LiveBroker createMarketOrder] ibOrder.m_action : %s' %(now,ibOrder.m_action )) 
            print ('%s[IB LiveBroker createMarketOrder] ibOrder.m_lmtPrice : %s' %(now,ibOrder.m_lmtPrice )) 
            print ('%s[IB LiveBroker createMarketOrder]  ibOrder.m_auxPrice: %s' %( ibOrder.m_auxPrice)) 
            print ('%s[IB LiveBroker createMarketOrder]ibOrder.m_tif  %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createMarketOrder]ibOrder.m_transmit  %s' %(now,ibOrder.m_transmit ))
            print ('%s[IB LiveBroker createMarketOrder]ibOrder.m_orderType   %s' %(now,ibOrder.m_orderType  ))
            print ('%s[IB LiveBroker createMarketOrder]ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
            print ('%s[IB LiveBroker createMarketOrder]ibOrder.m_allOrNone  %s' %(now,ibOrder.m_allOrNone ))
            print ('%s[IB LiveBroker createMarketOrder]ibOrder.m_tif   %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createMarketOrder]>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'%(now))

        self.__setOrderStatus(contract=contract,order=order,status='GENERATED', datetime=datetime.datetime.now())
        self.__registerOrder(contract=contract,order=order,status='GENERATED',datetime=datetime.datetime.now())
        if self.__debug:
            print('%s[IB LiveBroker createMarketOrder]INCREASE ORDER ID: %s' %(now,self.__nextOrderId))
    def createLimitOrder(self, contract, action, limitPrice, quantity,GoodTillCanceled = True,AllOrNone = True):
        ibContract=contract
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createLimitOrder] CONTRACT RECEIVED INFORMATION') 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_symbol    : %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_secType   : %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_currency  : %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_exchange  : %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_expiry    : %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_strike    : %s' %(now,ibContract.m_strike))
            
        ibOrder=Order()
        ibOrder.m_orderId       = self.__getUniqueOrderId()
        ibOrder.m_totalQuantity = quantity
        
        if action == 'BUY':
            ibOrder.m_action    = 'BUY'
        elif action == 'SELL':
            ibOrder.m_action = 'SELL'
 
        ibOrder.m_orderType = 'LMT'
        ibOrder.m_lmtPrice = limitPrice
 
        if AllOrNone == AllOrNone:
            ibOrder.m_allOrNone = 1
        else:
            ibOrder.m_allOrNone = 0

        if GoodTillCanceled == True:
            ibOrder.m_tif = 'GTC'
        else:
            ibOrder.m_tif = 'DAY'
            
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createLimitOrder]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'%(now))
            print ('%s[IB LiveBroker createLimitOrder] ibContract contract' %(now)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_symbol: %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_secType: %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_currency: %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_exchange: %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createLimitOrder] ibContract.m_expiry: %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createLimitOrder]ibContract.m_strike %s' %(now,ibContract.m_strike))

            print ('%s[IB LiveBroker createLimitOrder]'%(now))
            print ('%s[IB LiveBroker createLimitOrder] OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO'%(now))
            print ('%s[IB LiveBroker createLimitOrder] ibOder ' %(now)) 
            print ('%s[IB LiveBroker createLimitOrder] ibOrder.m_orderId: %s' %(now,ibOrder.m_orderId)) 
            print ('%s[IB LiveBroker createLimitOrder] ibOrder.m_clientId  : %s' %(now,ibOrder.m_clientId  )) 
            #print ('%s[IB LiveBroker createLimitOrder] ibOrder.m_permid: %s' %(now,ibOrder.m_permid)) 
            print ('%s[IB LiveBroker createLimitOrder] ibOrder.m_action : %s' %(now,ibOrder.m_action )) 
            print ('%s[IB LiveBroker createLimitOrder] ibOrder.m_lmtPrice : %s' %(now,ibOrder.m_lmtPrice )) 
            print ('%s[IB LiveBroker createLimitOrder]  ibOrder.m_auxPrice: %s' %( ibOrder.m_auxPrice)) 
            print ('%s[IB LiveBroker createLimitOrder]ibOrder.m_tif  %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createLimitOrder]ibOrder.m_transmit  %s' %(now,ibOrder.m_transmit ))
            print ('%s[IB LiveBroker createLimitOrder]ibOrder.m_orderType   %s' %(now,ibOrder.m_orderType  ))
            print ('%s[IB LiveBroker createLimitOrder]ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
            print ('%s[IB LiveBroker createLimitOrder]ibOrder.m_allOrNone  %s' %(now,ibOrder.m_allOrNone ))
            print ('%s[IB LiveBroker createLimitOrder]ibOrder.m_tif   %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createLimitOrder]>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'%(now))

        self.__setOrderStatus(contract=contract,order=order,status='GENERATED', datetime=datetime.datetime.now())
        self.__registerOrder(contract=contract,order=order,status='GENERATED',datetime=datetime.datetime.now())
        if self.__debug:
            print('%s[IB LiveBroker createLimitOrder]INCREASE ORDER ID: %s' %(now,self.__nextOrderId))
    def createStopOrder(self, contract, action, stopPrice, quantity,GoodTillCanceled = True,AllOrNone = True):
        ibContract=contract
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createStopOrder] CONTRACT RECEIVED INFORMATION') 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_symbol    : %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_secType   : %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_currency  : %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_exchange  : %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_expiry    : %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_strike    : %s' %(now,ibContract.m_strike))
            
        ibOrder=Order()
        ibOrder.m_orderId       = self.__getUniqueOrderId()
        ibOrder.m_totalQuantity = quantity
        
        if action == 'BUY':
            ibOrder.m_action    = 'BUY'
        elif action == 'SELL':
            ibOrder.m_action = 'SELL'
 
        ibOrder.m_orderType = 'STP'
        ibOrder.m_auxPrice = stopPrice

        if AllOrNone == AllOrNone:
            ibOrder.m_allOrNone = 1
        else:
            ibOrder.m_allOrNone = 0

        if GoodTillCanceled == True:
            ibOrder.m_tif = 'GTC'
        else:
            ibOrder.m_tif = 'DAY'
            
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createStopOrder]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'%(now))
            print ('%s[IB LiveBroker createStopOrder] ibContract contract' %(now)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_symbol: %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_secType: %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_currency: %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_exchange: %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createStopOrder] ibContract.m_expiry: %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createStopOrder]ibContract.m_strike %s' %(now,ibContract.m_strike))

            print ('%s[IB LiveBroker createStopOrder]'%(now))
            print ('%s[IB LiveBroker createStopOrder] OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO'%(now))
            print ('%s[IB LiveBroker createStopOrder] ibOder ' %(now)) 
            print ('%s[IB LiveBroker createStopOrder] ibOrder.m_orderId: %s' %(now,ibOrder.m_orderId)) 
            print ('%s[IB LiveBroker createStopOrder] ibOrder.m_clientId  : %s' %(now,ibOrder.m_clientId  )) 
            #print ('%s[IB LiveBroker createStopOrder] ibOrder.m_permid: %s' %(now,ibOrder.m_permid)) 
            print ('%s[IB LiveBroker createStopOrder] ibOrder.m_action : %s' %(now,ibOrder.m_action )) 
            print ('%s[IB LiveBroker createStopOrder] ibOrder.m_lmtPrice : %s' %(now,ibOrder.m_lmtPrice )) 
            print ('%s[IB LiveBroker createStopOrder]  ibOrder.m_auxPrice: %s' %( ibOrder.m_auxPrice)) 
            print ('%s[IB LiveBroker createStopOrder]ibOrder.m_tif  %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createStopOrder]ibOrder.m_transmit  %s' %(now,ibOrder.m_transmit ))
            print ('%s[IB LiveBroker createStopOrder]ibOrder.m_orderType   %s' %(now,ibOrder.m_orderType  ))
            print ('%s[IB LiveBroker createStopOrder]ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
            print ('%s[IB LiveBroker createStopOrder]ibOrder.m_allOrNone  %s' %(now,ibOrder.m_allOrNone ))
            print ('%s[IB LiveBroker createStopOrder]ibOrder.m_tif   %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createStopOrder]>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'%(now))

        self.__setOrderStatus(contract=contract,order=order,status='GENERATED', datetime=datetime.datetime.now())
        self.__registerOrder(contract=contract,order=order,status='GENERATED',datetime=datetime.datetime.now())
        if self.__debug:
            print('%s[IB LiveBroker createStopOrder]INCREASE ORDER ID: %s' %(now,self.__nextOrderId))
    def createStopLimitOrder(self,contract, action,stopPrice, limitPrice, quantity):
        ibContract=contract
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createStopLimitOrder] CONTRACT RECEIVED INFORMATION') 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_symbol    : %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_secType   : %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_currency  : %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_exchange  : %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_expiry    : %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_strike    : %s' %(now,ibContract.m_strike))
            
        ibOrder=Order()
        ibOrder.m_orderId       = self.__getUniqueOrderId()
        ibOrder.m_totalQuantity = quantity
        
        if action == 'BUY':
            ibOrder.m_action    = 'BUY'
        elif action == 'SELL':
            ibOrder.m_action = 'SELL'
 
        ibOrder.m_orderType = 'STP LMT'
        ibOrder.m_lmtPrice = limitPrice
        ibOrder.m_auxPrice = stopPrice

        if AllOrNone == AllOrNone:
            ibOrder.m_allOrNone = 1
        else:
            ibOrder.m_allOrNone = 0

        if GoodTillCanceled == True:
            ibOrder.m_tif = 'GTC'
        else:
            ibOrder.m_tif = 'DAY'
            
        if self.__debug:
            now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            print ('%s[IB LiveBroker createStopLimitOrder]CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'%(now))
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract contract' %(now)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_symbol: %s' %(now,ibContract.m_symbol)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_secType: %s' %(now,ibContract.m_secType)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_currency: %s' %(now,ibContract.m_currency)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_exchange: %s' %(now,ibContract.m_exchange)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_multiplier: %s' %(now,ibContract.m_multiplier)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibContract.m_expiry: %s' %(now,ibContract.m_expiry)) 
            print ('%s[IB LiveBroker createStopLimitOrder]ibContract.m_strike %s' %(now,ibContract.m_strike))

            print ('%s[IB LiveBroker createStopLimitOrder]'%(now))
            print ('%s[IB LiveBroker createStopLimitOrder] OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO'%(now))
            print ('%s[IB LiveBroker createStopLimitOrder] ibOder ' %(now)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibOrder.m_orderId: %s' %(now,ibOrder.m_orderId)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibOrder.m_clientId  : %s' %(now,ibOrder.m_clientId  )) 
            #print ('%s[IB LiveBroker createStopLimitOrder] ibOrder.m_permid: %s' %(now,ibOrder.m_permid)) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibOrder.m_action : %s' %(now,ibOrder.m_action )) 
            print ('%s[IB LiveBroker createStopLimitOrder] ibOrder.m_lmtPrice : %s' %(now,ibOrder.m_lmtPrice )) 
            print ('%s[IB LiveBroker createStopLimitOrder]  ibOrder.m_auxPrice: %s' %( ibOrder.m_auxPrice)) 
            print ('%s[IB LiveBroker createStopLimitOrder]ibOrder.m_tif  %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createStopLimitOrder]ibOrder.m_transmit  %s' %(now,ibOrder.m_transmit ))
            print ('%s[IB LiveBroker createStopLimitOrder]ibOrder.m_orderType   %s' %(now,ibOrder.m_orderType  ))
            print ('%s[IB LiveBroker createStopLimitOrder]ibOrder.m_totalQuantity   %s' %(now,ibOrder.m_totalQuantity ))
            print ('%s[IB LiveBroker createStopLimitOrder]ibOrder.m_allOrNone  %s' %(now,ibOrder.m_allOrNone ))
            print ('%s[IB LiveBroker createStopLimitOrder]ibOrder.m_tif   %s' %(now,ibOrder.m_tif ))
            print ('%s[IB LiveBroker createStopLimitOrder]>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'%(now))

        self.__setOrderStatus(contract=contract,order=order,status='GENERATED', datetime=datetime.datetime.now())
        self.__registerOrder(contract=contract,order=order,status='GENERATED',datetime=datetime.datetime.now())
        if self.__debug:
            print('%s[IB LiveBroker createStopLimitOrder]INCREASE ORDER ID: %s' %(now,self.__nextOrderId))
    def cancelOrder(self, order):
        '''
        activeOrder = self.__activeOrders.get(order.getId())
        if activeOrder is None:
            raise Exception("The order is not active anymore")
        if activeOrder.isFilled():
            raise Exception("Can't cancel order that has already been filled")
        '''
        self.__ib.cancelOrder(order.m_orderId)
            

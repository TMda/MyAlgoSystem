#
from __future__ import print_function
import pandas as pd
from pyalgotrade.barfeed import csvfeed
from pyalgotrade import strategy
from pyalgotrade import bar
from pyalgotrade.technical import ma
from ib.ext import Contract
from ib.ext import Order
import time
from ib.opt import ibConnection, message
import numpy as np
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

from event import MarketEvent
from performance import create_sharpe_ratio, create_drawdowns


class MyIbBroker():
    def __init__(self, host="localhost", port=7496, 
                debug=False, clientId = None, event=None):

        if debug == False:
            self.__debug = False
        else:
            self.__debug = True

 
        ###Connection to IB
        self.event=event
        self.connectionTime=None
        self.serverVersion=None
        if clientId == None:
            clientId = random.randint(1000,10000)
            if self.__debug:
                now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                print('%s[IB LiveBroker __init__ ]Client ID: %s' % (now,clientId))
        

        self.__ib = ibConnection(host=host,port=port,clientId=clientId)
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

        ##dictionary of tuples(orderId,contract object order id, order status )
        orderColumn=[
            'datetime',
            'status',
            'partialFilledQuantitiy',
            'ibContract.m_symbol','ibContract.m_secType',
            'ibContract.m_currency','ibContract.m_exchange',
            'ibContract.m_multiplier','ibContract.m_expiry',
            'ibContract.m_strike','ibContract.m_right',
            'ibOrder.m_orderId','ibOrder.m_clientId',
            'ibOrder.m_permid','ibOrder.m_action',
            'ibOrder.m_lmtPrice','ibOrder.m_auxPrice',
            'ibOrder.m_tif','ibOrder.m_transmit',
            'ibOrder.m_orderType','ibOrder.m_totalQuantity',
            'ibOrder.m_parentId','ibOrder.m_trailStopPrice',
            'ibOrder.m_trailingPercent',
            'ibOrder.m_allOrNone','ibOrder.m_tif','openOrderYesNo',]
        activePositionColumn=[
            'datetime',
            'ibContract.m_symbol','ibContract.m_secType',
            'ibContract.m_currency','ibContract.m_exchange',
            'ibContract.m_multiplier','ibContract.m_expiry' ,
            'ibContract.m_strike','ibContract.m_right',
            'position','marketPrice'
            'marketValue','averageCost','unrealizedPNL','realizedPNL','accountName']
        #2016-02-04 11:17:10[IB LiveBroker __portfolioHandler] <updatePortfolio contract=<ib.ext.Contract.Contract object at 0x00000000088E2FD0>, position=300, marketPrice=0.31, marketValue=9300.0, averageCost=31.2674, unrealizedPNL=-80.22, realizedPNL=0.0, accountName=DU213041>
        self.__activeOrder=[]
        self.__completelyFilledOrder=[]
        self.__orderHistory=pd.DataFrame(columns=orderColumn)
        #Cash Management
        self.__cash = 0
        #Position Management
        self.__activePositions = [] #contract, share
        #self.__detailedActivePositions = {}#entry price, average price etc...
        self.__detailedActivePositionsHistory=pd.DataFrame(columns=activePositionColumn)
        #from InitialLive Broker get portfolio status from the broker
        #equivalent to self.__activePositions = [] , self.__detailedActivePositions
        self.__shares = {}

        self.__nextOrderId = 0
        self.__initialPositions = []
        execuColumn=['datetime'
                'ibExecution.m_orderId','ibExecution.m_execId','ibExecution.m_acctNumber',
                'ibExecution.m_clientId','ibExecution.m_liquidation','ibExecution.m_permId',
                'ibExecution.m_price','ibExecution.m_evMultiplier''ibExecution.m_avgPrice' ,'ibExecution.m_evRule',  
                'ibExecution.m_cumQty','ibExecution.m_shares','ibOrder.m_auxPrice','ibExecution.m_side',
                'ibExecution.m_time','ibExecution.m_exchange' ]
        self.__executionHistory=pd.DataFrame(columns=execuColumn )
        self.__detailedShares = {}
        #Request initial account balance
        self.refreshAccountBalance()
        # Request current open order in the system
        self.refreshOpenOrders()
        # Request all positions outstanding
        self.__ib.reqPositions()
        #give ib time to get back to us
        time.sleep(5)
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
             
            ibOder = self.__activeOrders.get(msg.orderId)
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
        if ibExecution.m_execId in self.__executionHistory['ibExecution.m_execId']:
            if self.__debug:
                print ('%s[IB LiveBroker __execDetailsHandler] This is a Duplicate execution order'%(now,))
                self.__printDebug()
            
            return
        #building execution row to add in executionHistory
        rxDict={
                    'datetime':now,
                    'ibOrder.m_orderId': ibExecution.m_orderId,
                    'ibExecution.m_execId':ibExecution.m_execId,
                    'ibExecution.m_acctNumber':ibExecution.m_acctNumber,
                    'ibExecution.m_clientId'  : ibExecution.m_clientId,
                    'ibExecution.m_liquidation':ibExecution.m_liquidation,
                    'ibExecution.m_permId': ibExecution.m_permId,
                    'ibExecution.m_price' : ibExecution.m_price,
                    'ibExecution.m_evMultiplier' : ibExecution.m_evMultiplier,
                    'ibExecution.m_avgPrice' : ibExecution.m_avgPrice,
                    'ibExecution.m_evRule' :  ibExecution.m_evRule,
                    'ibExecution.m_cumQty' :  ibExecution.m_cumQty,
                    'ibExecution.m_shares' : ibExecution.m_shares,
                    'ibExecution.m_side':ibExecution.m_side,
                    'ibExecution.m_time':ibExecution.m_time,
                    'ibExecution.m_exchange':ibExecution.m_exchange

            }
        #adding the new execution in execution history    
        self.__executionHistory.append(rxDict,ignore_index=True)

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
        assert(ibContrcatA,Contract),'[IB LiveBroker __execDetailsHandler] Error contract not in active Order Table'
        assert(ibOderA,Order),'[IB LiveBroker __execDetailsHandler] Error Order not in active Order Table'

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
                    'ibOrder.m_orderId': ibExecution.m_orderId,
                    'ibExecution.m_execId':ibExecution.m_execId,
                    'ibExecution.m_acctNumber':ibExecution.m_acctNumber,
                    'ibExecution.m_clientId'  : ibExecution.m_clientId,
                    'ibExecution.m_liquidation':ibExecution.m_liquidation,
                    'ibExecution.m_permId': ibExecution.m_permId,
                    'ibExecution.m_price' : ibExecution.m_price,
                    'ibExecution.m_evMultiplier' : ibExecution.m_evMultiplier,
                    'ibExecution.m_avgPrice' : ibExecution.m_avgPrice,
                    'ibExecution.m_evRule' :  ibExecution.m_evRule,
                    'ibExecution.m_cumQty' :  ibExecution.m_cumQty,
                    'ibExecution.m_shares' : ibExecution.m_shares,
                    'ibExecution.m_side':ibExecution.m_side,
                    'ibExecution.m_time':ibExecution.m_time,
                    'ibExecution.m_exchange':ibExecution.m_exchange

            }
        #adding the new execution in execution history    
        self.__executionHistory.append(rxDict,ignore_index=True)
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
        'ibContract.m_symbol':ibContract.m_symbol,
        'ibContract.m_secType':ibContract.m_secType,
        'ibContract.m_currency':ibContract.m_currency,
        'ibContract.m_exchange':ibContract.m_exchange,
        'ibContract.m_multiplier':ibContract.m_multiplier,
        'ibContract.m_expiry':ibContract.m_expiry ,
        'ibContract.m_strike':ibContract.m_strike,
        'ibContract.m_right':ibContract.m_right,
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
            if position['ibContract.m_symbol'] ==ibContract.m_symbol and \
                position['ibContract.m_secType']==ibContract.m_secType and\
                position['ibContract.m_currency']==ibContract.m_currency and\
                position['ibContract.m_exchange']==ibContract.m_exchange and\
                position['ibContract.m_multiplier']==ibContract.m_multiplier and\
                position['ibContract.m_expiry']==ibContract.m_expiry and\
                position['ibContract.m_strike']==ibContract.m_strike and\
                position['ibContract.m_right']==ibContract.m_right:
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
        if self.__orderHistory.empty:
            self.__nextOrderId=0
            #return self.__nextOrderId
        else:
            self.__nextOrderId=int(self.__orderHistory['ibOrder.m_orderId'].max())+1
            #return self.__nextOrderId
        if self.__nextOrderId in self.__orderHistory['ibOrder.m_orderId']:
            raise('getUniqueOrderId created a duplicate order ID %s' %(self.__nextOrderId))
        else:
            if self.__debug:
               now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
               print('%s[IB LiveBroker getUniqueOrderId]INCREASE ORDER ID: %s' %(now,self.__nextOrderId))

            return self.__nextOrderId

    def __setOrderStatus(self,contract,order,status, datetime,partialFilledQuantitiy=None,openOrderYesNo=False):
        if status not in ['GENERATED','SUBMITTED','FILLED','PARTIALLY FILLED','CANCELLED BY USER','CANCELLED BY API']:
            raise('Status can only be either: SUBMITTED,FILLED,PARTIALLY FILLED,CANCELLED BY USER,CANCELLED BY API')
            
        elif status in ('GENERATED'):
            dict={
                    'ibOrder.m_orderId':ibOrder.m_orderId,
                    'status':'SUBMITTED',
                    'ibOrder.m_permid':ibOrder.m_permid,
                    'ibContract.m_symbol':ibContract.m_symbol,
                    'ibContract.m_secType':ibContract.m_secType,
                    'ibContract.m_currency':ibContract.m_currency,
                    'ibContract.m_exchange':ibContract.m_exchange,
                    'ibContract.m_expiry':ibContract.m_expiry ,
                    'ibContract.m_strike':ibContract.m_strike,
                    'ibOrder.m_action':ibOrder.m_action,
                    'ibOrder.m_lmtPrice':ibOrder.m_lmtPrice,
                    'ibOrder.m_auxPrice':ibOrder.m_auxPrice,
                    'ibOrder.m_tif':ibOrder.m_tif,
                    'ibOrder.m_transmit':ibOrder.m_transmit,
                    'ibOrder.m_orderType':ibOrder.m_orderType,
                    'ibOrder.m_totalQuantity':ibOrder.m_totalQuantity,
                }
            self.__activeOrder.append(dict)

        elif status in ('FILLED',):
            #Remove from active Order
            i=0
            position=0
            for Order in self.__activeOrder:
                if(Order['ibOrder.m_orderId']==ibOrder.m_orderId):
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
                if(Order['ibOrder.m_orderId']==ibOrder.m_orderId):
                    position=i
                    i+=1
                if i !=1:
                    raise('Order ID %s not unique'%(ibOrder.m_orderId))
                elif i==0:                
                    raise('Order ID %s does not exist in active order'%(ibOrder.m_orderId))
                elif i==1:
                    #delete the order from active order
                    self.__activeOrder[position]['ibOrder.m_totalQuantity']=int(self.__activeOrder[position]['ibOrder.m_totalQuantity'])-int(partialFilledQuantitiy)
               
        elif status in ('CANCELLED BY USER','CANCELLED BY API'):
            #Remove from active Order
            i=0
            position=0
            for Order in self.__activeOrder:
                if(Order['ibOrder.m_orderId']==ibOrder.m_orderId):
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
            'datetime':datetime,
            'status':status,
            'ibOrder.m_orderId':ibOrder.m_orderId,
            'ibOrder.m_permid':ibOrder.m_permid,
            'partialFilledQuantitiy':partialFilledQuantitiy,
            'ibContract.m_symbol':ibContract.m_symbol,
            'ibContract.m_secType':ibContract.m_secType,
            'ibContract.m_currency':ibContract.m_currency,
            'ibContract.m_exchange':ibContract.m_exchange,
            'ibContract.m_multiplier':ibContract.m_multiplier,
            'ibContract.m_expiry':ibContract.m_expiry ,
            'ibContract.m_strike':ibContract.m_strike,
            'ibOrder.m_action':ibOrder.m_action,
            'ibOrder.m_lmtPrice':ibOrder.m_lmtPrice,
            'ibOrder.m_auxPrice':ibOrder.m_auxPrice,
            'ibOrder.m_tif':ibOrder.m_tif,
            'ibOrder.m_transmit':ibOrder.m_transmit,
            'ibOrder.m_orderType':ibOrder.m_orderType,
            'ibOrder.m_totalQuantity':ibOrder.m_totalQuantity,
            'ibOrder.m_parentId':ibOrder.m_parentId,          #int m_parentId	The order ID of the parent order, used for bracket and auto trailing stop orders.
            'ibOrder.m_trailStopPrice':ibOrder.m_trailStopPrice,    #m_trailStopPrice	For TRAILLIMIT orders only
            'ibOrder.m_trailingPercent':ibOrder.m_trailingPercent,   # double m_trailingPercent	
            'ibOrder.m_allOrNone':ibOrder.m_allOrNone,
            'ibOrder.m_tif':ibOrder.m_tif,
            'openOrderYesNo':openOrderYesNo,
            'ibOrder.m_clientId':ibOrder.m_clientId,
            }
            #2016-02-04 11:17:10[IB LiveBroker __portfolioHandler] <updatePortfolio contract=<ib.ext.Contract.Contract object at 0x00000000088E2FD0>, position=300, marketPrice=0.31, marketValue=9300.0, averageCost=31.2674, unrealizedPNL=-80.22, realizedPNL=0.0, accountName=DU213041>
            self.__orderHistory=self.__orderHistory.append(orderDict,ignore_index=True)
            
           
    def __printDebug(self):
        now=dat.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print ('self.__activeOrder:')
 
        print (self.__activeOrder)
        print ('self.__completelyFilledOrder')

        print (self.__completelyFilledOrder)
        print ('self.__orderHistory')
        print (self.__orderHistory)

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

        print ('self.__executionHistory')
        print (self.__executionHistory)
        
         

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
            ibContract.m_symbol     =   self.__activeOrder[pos]['ibContract.m_symbol']
            ibContract.m_secType    =   self.__activeOrder[pos]['ibContract.m_secType']
            ibContract.m_currency   =   self.__activeOrder[pos]['ibContract.m_currency']
            ibContract.m_exchange   =   self.__activeOrder[pos]['ibContract.m_exchange']
            ibContract.m_multiplier =   self.__activeOrder[pos]['ibContract.m_multiplier']
            ibContract.m_expiry     =   self.__activeOrder[pos]['ibContract.m_expiry']
            ibContract.m_strike     =   self.__activeOrder[pos]['ibContract.m_strike']
            ibOrder=Order()

            ibOrder.m_action       =    self.__activeOrder[pos]['ibOrder.m_action']
            ibOrder.m_lmtPrice     =    self.__activeOrder[pos]['ibOrder.m_lmtPrice']
            ibOrder.m_auxPrice     =    self.__activeOrder[pos]['ibOrder.m_auxPrice']
            ibOrder.m_tif          =    self.__activeOrder[pos]['ibOrder.m_tif']
            ibOrder.m_transmit   =      self.__activeOrder[pos]['ibOrder.m_transmit']
            ibOrder.m_orderType   =     self.__activeOrder[pos]['ibOrder.m_orderType']
            ibOrder.m_totalQuantity=    self.__activeOrder[pos]['ibOrder.m_totalQuantity']
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
            if(Order['ibOrder.m_orderId']==ibOrder.m_orderId):
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
            

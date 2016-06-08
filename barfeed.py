"""
Interactive brokers live feed module

Requires:
- ibPy - https://github.com/blampe/IbPy
- trader work station or IB Gateway - https://www.interactivebrokers.com/en/?f=%2Fen%2Fsoftware%2Fibapi.php&ns=T

PyAlgoTrade
ib live broker

TMMMMM
"""
from __future__ import print_function

import time
import datetime
import threading
import Queue
import random
import sys
import pytz

import bar
from event import MarketEvent
from pyalgotrade import barfeed
from pyalgotrade import dataseries
from pyalgotrade import resamplebase
import pyalgotrade.logger
from pyalgotrade.utils import dt
from pyalgotrade.utils.dt import localize
from ib.ext.Contract import Contract
from ib.ext.Order import Order
from ib.opt import ibConnection, message
import datetime as dt
import pandas as pd
try:
    import Queue as queue
except ImportError:
    import queue



def utcnow():
    return datetime.as_utc(datetime.datetime.utcnow())


def makeContract(contractTuple):
    newContract = Contract()
    newContract.m_symbol = contractTuple[0]
    newContract.m_secType = contractTuple[1]
    newContract.m_exchange = contractTuple[2]
    newContract.m_currency = contractTuple[3]
    newContract.m_expiry = contractTuple[4]
    newContract.m_strike = contractTuple[5]
    newContract.m_right = contractTuple[6]
    if len(contractTuple) > 7:
        if contractTuple[1] == "OPT":
            newContract.m_multiplier = contractTuple[7]
    return newContract

class BarEvent():
    ON_BARS = 1

# PyAlgoTrade
#
# Copyright 2011-2015 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
.. moduleauthor:: Gabriel Martin Becedillas Ruiz <gabriel.becedillas@gmail.com>
"""

import abc

import bar
from pyalgotrade import dataseries
from pyalgotrade.dataseries import bards
from pyalgotrade import feed


# This is only for backward compatibility since Frequency used to be defined here and not in bar.py.
Frequency = bar.Frequency
import abc


class Event(object):
    def __init__(self):
        self.__handlers = []
        self.__toSubscribe = []
        self.__toUnsubscribe = []
        self.__emitting = False

    def __applyChanges(self):
        if len(self.__toSubscribe):
            for handler in self.__toSubscribe:
                if handler not in self.__handlers:
                    self.__handlers.append(handler)
            self.__toSubscribe = []

        if len(self.__toUnsubscribe):
            for handler in self.__toUnsubscribe:
                self.__handlers.remove(handler)
            self.__toUnsubscribe = []

    def subscribe(self, handler):
        if self.__emitting:
            self.__toSubscribe.append(handler)
        elif handler not in self.__handlers:
            self.__handlers.append(handler)

    def unsubscribe(self, handler):
        if self.__emitting:
            self.__toUnsubscribe.append(handler)
        else:
            self.__handlers.remove(handler)

    def emit(self, *args, **kwargs):
        try:
            self.__emitting = True
            for handler in self.__handlers:
                handler(*args, **kwargs)
        finally:
            self.__emitting = False
            self.__applyChanges()


class Subject(object):
    __metaclass__ = abc.ABCMeta

    # This may raise.
    @abc.abstractmethod
    def start(self):
        raise NotImplementedError()

    # This should not raise.
    @abc.abstractmethod
    def stop(self):
        raise NotImplementedError()

    # This should not raise.
    @abc.abstractmethod
    def join(self):
        raise NotImplementedError()

    # Return True if there are not more events to dispatch.
    @abc.abstractmethod
    def eof(self):
        raise NotImplementedError()

    # Dispatch events. If True is returned, it means that at least one event was dispatched.
    @abc.abstractmethod
    def dispatch(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def peekDateTime(self):
        # Return the datetime for the next event.
        # This is needed to properly synchronize non-realtime subjects.
        # Return None since this is a realtime subject.
        raise NotImplementedError()

    def getDispatchPriority(self):
        # Returns a number (or None) used to sort subjects within the dispatch queue.
        # The return value should never change.
        return None

def feed_iterator(feed):
    feed.start()
    try:
        while not feed.eof():
            yield feed.getNextValuesAndUpdateDS()
    finally:
        feed.stop()
        feed.join()


class BaseFeed(object):
    """Base class for feeds.

    :param maxLen: The maximum number of values that each :class:`pyalgotrade.dataseries.DataSeries` will hold.
        Once a bounded length is full, when new items are added, a corresponding number of items are discarded
        from the opposite end.
    :type maxLen: int.

    .. note::
        This is a base class and should not be used directly.
    """

    def __init__(self, maxLen):
        if not maxLen > 0:
            raise Exception("Invalid maximum length")
        self.__ds = {}
        self.__event = observer.Event()
        self.__maxLen = maxLen

    def reset(self):
        keys = self.__ds.keys()
        self.__ds = {}
        for key in keys:
            self.registerDataSeries(key)

    # Subclasses should implement this and return the appropriate dataseries for the given key.
    @abc.abstractmethod
    def createDataSeries(self, key, maxLen):
        raise NotImplementedError()

    # Subclasses should implement this and return a tuple with two elements:
    # 1: datetime.datetime.
    # 2: dictionary or dict-like object.
    @abc.abstractmethod
    def getNextValues(self):
        raise NotImplementedError()

    def registerDataSeries(self, key):
        if key not in self.__ds:
            self.__ds[key] = self.createDataSeries(key, self.__maxLen)

    def getNextValuesAndUpdateDS(self):
        dateTime, values = self.getNextValues()
        if dateTime is not None:
            for key, value in values.items():
                # Get or create the datseries for each key.
                try:
                    ds = self.__ds[key]
                except KeyError:
                    ds = self.createDataSeries(key, self.__maxLen)
                    self.__ds[key] = ds
                ds.appendWithDateTime(dateTime, value)
        return (dateTime, values)

    def __iter__(self):
        return feed_iterator(self)

    def getNewValuesEvent(self):
        """Returns the event that will be emitted when new values are available.
        To subscribe you need to pass in a callable object that receives two parameters:

         1. A :class:`datetime.datetime` instance.
         2. The new value.
        """
        return self.__event

    def dispatch(self):
        dateTime, values = self.getNextValuesAndUpdateDS()
        if dateTime is not None:
            self.__event.emit(dateTime, values)
        return dateTime is not None

    def getKeys(self):
        return self.__ds.keys()

    def __getitem__(self, key):
        """Returns the :class:`pyalgotrade.dataseries.DataSeries` for a given key."""
        return self.__ds[key]

    def __contains__(self, key):
        """Returns True if a :class:`pyalgotrade.dataseries.DataSeries` for the given key is available."""
        return key in self.__ds


class BaseBarFeed(BaseFeed):
    """Base class for :class:`pyalgotrade.bar.Bar` providing feeds.

    :param frequency: The bars frequency. Valid values defined in :class:`pyalgotrade.bar.Frequency`.
    :param maxLen: The maximum number of values that the :class:`pyalgotrade.dataseries.bards.BarDataSeries` will hold.
        Once a bounded length is full, when new items are added, a corresponding number of items are discarded
        from the opposite end.
    :type maxLen: int.

    .. note::
        This is a base class and should not be used directly.
    """

    def __init__(self, frequency, maxLen=dataseries.DEFAULT_MAX_LEN):
        feed.BaseFeed.__init__(self, maxLen)
        self.__frequency = frequency
        self.__useAdjustedValues = False
        self.__defaultInstrument = None
        self.__currentBars = None
        self.__lastBars = {}

    def reset(self):
        self.__currentBars = None
        self.__lastBars = {}
        feed.BaseFeed.reset(self)

    def setUseAdjustedValues(self, useAdjusted):
        if useAdjusted and not self.barsHaveAdjClose():
            raise Exception("The barfeed doesn't support adjusted close values")
        # This is to affect future dataseries when they get created.
        self.__useAdjustedValues = useAdjusted
        # Update existing dataseries
        for instrument in self.getRegisteredInstruments():
            self[instrument].setUseAdjustedValues(useAdjusted)

    # Return the datetime for the current bars.
    @abc.abstractmethod
    def getCurrentDateTime(self):
        raise NotImplementedError()

    # Return True if bars provided have adjusted close values.
    @abc.abstractmethod
    def barsHaveAdjClose(self):
        raise NotImplementedError()

    # Subclasses should implement this and return a pyalgotrade.bar.Bars or None if there are no bars.
    @abc.abstractmethod
    def getNextBars(self):
        """Override to return the next :class:`pyalgotrade.bar.Bars` in the feed or None if there are no bars.

        .. note::
            This is for BaseBarFeed subclasses and it should not be called directly.
        """
        raise NotImplementedError()

    def createDataSeries(self, key, maxLen):
        ret = bards.BarDataSeries(maxLen)
        ret.setUseAdjustedValues(self.__useAdjustedValues)
        return ret

    def getNextValues(self):
        dateTime = None
        bars = self.getNextBars()
        if bars is not None:
            dateTime = bars.getDateTime()

            # Check that current bar datetimes are greater than the previous one.
            if self.__currentBars is not None and self.__currentBars.getDateTime() >= dateTime:
                raise Exception(
                    "Bar date times are not in order. Previous datetime was %s and current datetime is %s" % (
                        self.__currentBars.getDateTime(),
                        dateTime
                    )
                )

            # Update self.__currentBars and self.__lastBars
            self.__currentBars = bars
            for instrument in bars.getInstruments():
                self.__lastBars[instrument] = bars[instrument]
        return (dateTime, bars)

    def getFrequency(self):
        return self.__frequency

    def isIntraday(self):
        return self.__frequency < bar.Frequency.DAY

    def getCurrentBars(self):
        """Returns the current :class:`pyalgotrade.bar.Bars`."""
        return self.__currentBars

    def getLastBar(self, instrument):
        """Returns the last :class:`pyalgotrade.bar.Bar` for a given instrument, or None."""
        return self.__lastBars.get(instrument, None)

    def getDefaultInstrument(self):
        """Returns the default instrument."""
        return self.__defaultInstrument

    def getRegisteredInstruments(self):
        """Returns a list of registered intstrument names."""
        return self.getKeys()

    def registerInstrument(self, instrument):
        self.__defaultInstrument = instrument
        self.registerDataSeries(instrument)

    def getDataSeries(self, instrument=None):
        """Returns the :class:`pyalgotrade.dataseries.bards.BarDataSeries` for a given instrument.

        :param instrument: Instrument identifier. If None, the default instrument is returned.
        :type instrument: string.
        :rtype: :class:`pyalgotrade.dataseries.bards.BarDataSeries`.
        """
        if instrument is None:
            instrument = self.__defaultInstrument
        return self[instrument]


# This class is used by the optimizer module. The barfeed is already built on the server side,
# and the bars are sent back to workers.
class OptimizerBarFeed(BaseBarFeed):
    def __init__(self, frequency, instruments, bars, maxLen=dataseries.DEFAULT_MAX_LEN):
        BaseBarFeed.__init__(self, frequency, maxLen)
        for instrument in instruments:
            self.registerInstrument(instrument)
        self.__bars = bars
        self.__nextPos = 0
        self.__currDateTime = None

        try:
            self.__barsHaveAdjClose = self.__bars[0][instruments[0]].getAdjClose() is not None
        except Exception:
            self.__barsHaveAdjClose = False

    def getCurrentDateTime(self):
        return self.__currDateTime

    def barsHaveAdjClose(self):
        return self.__barsHaveAdjClose

    def start(self):
        pass

    def stop(self):
        pass

    def join(self):
        pass

    def peekDateTime(self):
        ret = None
        if self.__nextPos < len(self.__bars):
            ret = self.__bars[self.__nextPos].getDateTime()
        return ret

    def getNextBars(self):
        ret = None
        if self.__nextPos < len(self.__bars):
            ret = self.__bars[self.__nextPos]
            self.__currDateTime = ret.getDateTime()
            self.__nextPos += 1
        return ret

    def eof(self):
        return self.__nextPos >= len(self.__bars)


class LiveFeed(barfeed.BaseBarFeed):
    """ real-time BarFeed that builds bars using IB API
    :param host: hostname of IB API (localhost)
    :param port: port the IB API listens on 
    :param identifiers: A list with the fully qualified identifier for the securities including the exchange suffix.
    :type identifiers: list.
    :param frequency: The frequency of the bars.
        Must be greater than or equal to **bar.Frequency.MINUTE** and less than or equal to **bar.Frequency.DAY**.


    :param maxLen: The maximum number of values that the :class:`pyalgotrade.dataseries.bards.BarDataSeries` will hold.
        Once a bounded length is full, when new items are added, a corresponding number of items are discarded from the opposite end.
    :type maxLen: int.
    :param marketOptions: What asset type, currency and routing method to use for Interactive Brokers. Eg assetType:'STK', currency:'USD', routing:'SMART'
    :type marketOptions: dictionary

    :param warmupBars: How many historical bars to start with
    type warmupBars: int

    :param debug: print all output of IB API calls
    :type debug: bool.
    :param file: file to output the history

    """

    QUEUE_TIMEOUT = 0.01


    def __init__(self,contract,frequency=60,eventQueue=None,
                 identifiers=None, 
                host="localhost",port=7496,       
                warmupBars = 0, debug=False,fileOutput=None):
        # Contract is either a ib contract or a list of ib contract 
        #barfeed.BaseBarFeed.__init__(self, frequency, maxLen)
        #if not isinstance(identifiers, list):
        #    raise Exception("identifiers must be a list")
        
        #Check if a queue is provided if not create one
        #Queue are used to communicate with outside program that 
        #share the same queue
        if eventQueue !=None:
            self.__queue = eventQueue
        else:
            self.__queue = queue.Queue()
        
        #Create a disctionary for bar
        self.__currentBar = {}
        
        #Check if a contract has been provided or a list and 
        #adapt accordingly because the following code expect a list
        #of contract
        if isinstance(contract,list):
            self.__contracts=contract
        elif isinstance(contract,Contract):
            self.__contracts=[contract]
        else:
            raise('Contract should be either a contract or a list of contract')

        #This version is kept for historical raison
        self.__instruments = self.buildInstrumentList()# I use contract that is for historical compatibility

        #keep track of latest timestamp on any bars for requesting next set
        self.__lastBarStamp = 0
        self.__currentBarStamp = 0
        
      

        self.__timer = None
        
        # File where historical values are outputed
        self.__fileOutput=fileOutput
        
        # BAr frequency       
        self.__frequency = frequency
        '''
        valid frequencies are (and we are really limited by IB here but it's a good range). If the values don't suit then look at taking a higher 
        frequency and using http://gbeced.github.io/pyalgotrade/docs/v0.16/html/strategy.html#pyalgotrade.strategy.BaseStrategy.resampleBarFeed to get the desired frequency
            - 1 minute - 60 - bar.Frequency.MINUTE 
            - 2 minutes - 120 - (bar.Frequency.MINUTE * 2)
            - 5 minutes - 300 - (bar.Frequency.MINUTE * 5)
            - 15 minutes - 900 - (bar.Frequency.MINUTE * 15)
            - 30 minutes - 1800 - (bar.Frequency.MINUTE * 30)
            - 1 hour - 3600 - bar.Frequency.HOUR
            - 1 day - 86400 - bar.Frequency.DAY

            Note: That instrument numbers and frequency affect pacing rules. Keep it to 3 instruments with a 1 minute bar to avoid pacing. Daily hits could include as many as 60 instruments as the limit is 60 calls within a ten minute period. We make one request per instrument for the warmup bars and then one per instrument every frequency seconds. See here for more info on pacing - https://www.interactivebrokers.com/en/software/api/apiguide/tables/historical_data_limitations.htm

        '''
        if self.__frequency not in [60,120,300,900,1800,3600,86400]:
            raise Exception("Please use a frequency of 1,2,5,15,30,60 minutes or 1 day")

        #builds up a list of quotes
        self.__synchronised = False #have we synced to IB's bar pace yet?

        if debug == False:
            self.__debug = False
        else:
            self.__debug = True

 
        #Ib connection parameters
        self.__ib = ibConnection(host=host,port=port,clientId=random.randint(1,10000))
        self.__ib.register(self.__historicalBarsHandler, message.historicalData)
        self.__ib.register(self.__errorHandler, message.error)
        self.__ib.register(self.__disconnectHandler, 'ConnectionClosed')
        #self.__ib.registerAll(self.__debugHandler)
        self.__ib.connect()
        if self.__ib.isConnected():
            self.connectionTime=self.__ib.reqCurrentTime()
            self.serverVersion=self.__ib.serverVersion()
            if self.__debug:
                print('********************************')
                print('%s LiveFeed - DATA FEED Connection to IB established' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                print('%s LiveFeed- IB server connection time: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.connectionTime))
                print('%s LiveFeed- IB server version: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'), self.serverVersion))
                
        else:
            print('LiveFeed Connection to IB Error')
        
        #warming up?
        self.__numWarmupBars = 0       #number of warmup bars to use
        self.__warmupBars = dict((el,[]) for el in self.__instruments)        #the warmup bars arrays indexed by stock code
        self.__inWarmup = False        #are we still in the warmup phase - when finished warming up this is set to false
        self.__stockFinishedWarmup = dict((el,False) for el in self.__instruments)  #has this stock finished warming up? create dict keyed by stock and set to false
        if warmupBars > 0:
            if warmupBars > 200:
                raise Exception("Max number of warmup bars is 200")

            self.__numWarmupBars = warmupBars
            self.__inWarmup = True
            self.__requestWarmupBars()
        else:
            #start the clock
            self.__requestBars()
     
    def buildInstrumentList(self):
        a=[]
        for i in range(len(self.__contracts)):
            if self.__contracts[i].m_secType =='OPT':
                instrument ='%s-%s-%s-%s-%s-%s-%s' %(self.__contracts[i].m_symbol,self.__contracts[i].m_secType,self.__contracts[i].m_right,self.__contracts[i].m_strike,self.__contracts[i].m_expiry)
                a.append(instrument)
            else:
                instrument ='%s' %(self.__contracts[i].m_symbol)
                a.append(instrument)
        return a
    
    def __build_bar(self,barMsg, identifier,frequency,currency):
        # "StartDate": "3/19/2014"
        # "StartTime": "9:55:00 AM"
        # "EndDate": "3/19/2014"
        # "EndTime": "10:00:00 AM"
        # "UTCOffset": 0
        # "Open": 31.71
        # "High": 31.71
        # "Low": 31.68
        # "Close": 31.69
        # "Volume": 2966
        # "Trades": 19
        # "TWAP": 31.6929
        # "VWAP": 31.693

        #Note date/time is local time not market time
        #Also for some weird reason IB is sending bars with finished in the date so why not just ignore
        now=datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')
        if self.__debug:
            
            print ('%s[LiveFeed __build_bar] **********************************' %(now))
            print ('%s[LiveFeed __build_bar] starting try catch sentence'%(now))
        ts = 0

        try:
            (offset, tz) = self.__marketCloseTime(currency)
            if self.__debug:
                print ('%s[LiveFeed __build_bar] Offset: %s and tz: %s ' %(now,offset,tz))

            if len(barMsg.date) == 8:   #it's not a unix timestamp it's something like 20150812 (YYYYMMDD) which means this was a daily bar
                if self.__debug:
                    print ('%s[LiveFeed __build_bar] msg.date==8 it is not a unix timestamp it is something like 20150812 (YYYYMMDD) which means this was a daily bar' %(now,))

                date = datetime.datetime.strptime(barMsg.date,'%Y%m%d')
                if self.__debug:
                    print ('%s[LiveFeed __build_bar] date:  %s ' %(now,date))

                
                date = date + offset
                if self.__debug:
                    print ('%s[LiveFeed __build_bar] date+offset: %s  ' %(now,date))

                date = tz.localize(date)
                if self.__debug:
                    print ('%s[LiveFeed __build_bar] date+offset+localize: %s  ' %(now,date))

                ts = int((date - datetime.datetime(1970,1,1,tzinfo=pytz.utc)).total_seconds()) #probably going to have timezone issues
                if self.__debug:
                    print ('%s[LiveFeed __build_bar]timestamp date: %s ' %(now,ts))

            else:
                if self.__debug:
                    print ('%s[LiveFeed __build_bar] msg.date!=8' %(now,))

                ts = int(barMsg.date)
                if self.__debug:
                    print ('%s[LiveFeed __build_bar] timestamp date: %s ' %(now,ts))

            startDateTime = localize(datetime.datetime.fromtimestamp(ts,tz),tz)
            if self.__debug:
                print ('%s[LiveFeed __build_bar] strtDateTime: %s' %(now,startDateTime))

            self.__currentBarStamp = ts
            if self.__debug:
                print ('%s[LiveFeed __build_bar] time: %s, Open: %d ,High: %d, Low: %d, Close: %d, Volume: %d, frequency: %s' %(now,startDateTime, float(barMsg.open), float(barMsg.high), float(barMsg.low), float(barMsg.close), int(barMsg.volume), frequency))
    
            return bar.BasicBar(startDateTime, float(barMsg.open), float(barMsg.high), float(barMsg.low), float(barMsg.close), int(barMsg.volume), None, frequency)
        except Exception as e:
            if self.__debug:
                print ('%s[LiveFeed __build_bar] Exception error:  %s ' %(now,e))
                print ('%s[LiveFeed __build_bar] ====EXIT====EXIT=====EXIT========================== ' %(now,))
            return None

    def __requestWarmupBars(self):
        #work out what duration and barSize to use
        if self.__debug:
            print ('[LiveFeed __requestWarmupBars] **********************************' %())
            print('%s [LiveFeed __requestWarmupBars] work out what duration and barSize to use' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
            print('%s [LiveFeed __requestWarmupBars] frequency (self.__frequency):  %s ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__frequency))
 
        if self.__frequency < bar.Frequency.DAY:
            barSize = "%d min" % (self.__frequency / bar.Frequency.MINUTE)
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency < bar.Frequency.DAY ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] barsize: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),barSize))


            #make it mins for anything greater than a minute
            if self.__frequency > bar.Frequency.MINUTE:
                barSize += "s"
                if self.__debug:
                    print('%s [LiveFeed __requestWarmupBars] make it mins for anything greater than a minute' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                    print('%s [LiveFeed __requestWarmupBars] self.__frequency > bar.Frequency.MINUTE ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),))

        else:
            barSize = "1 day"
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency > bar.Frequency.DAY ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] barsize: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),barSize))

        #duration

        if self.__frequency == bar.Frequency.DAY:
            lookbackDuration = "%d D" % self.__numWarmupBars
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency == bar.Frequency.DAY ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] lookbackDuration: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),lookbackDuration))

        else:
            lookbackDuration = "%d S" % (self.__numWarmupBars * self.__frequency)
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency != bar.Frequency.DAY ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] lookbackDuration: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),lookbackDuration))

        #for tickId in range(len(self.__contracts)):
        for tickId in range(len(self.__contracts)):
            self.__ib.reqHistoricalData(tickerId=tickId,
                                          contract= self.__contracts[tickId],
                                          endDateTime='',
                                          durationStr=lookbackDuration,       #how far back to go
                                          barSizeSetting=barSize,      #bar size
                                          whatToShow='TRADES',
                                          useRTH=1,
                                          formatDate=2)
            if self.__debug:
            
                print('%s [LiveFeed __requestWarmupBars] tickid:, symbol: %s, security: %s, right: %s, expiry: %s, strike: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,self.__contracts[tickId].m_symbol,self.__contracts[tickId].m_secType,self.__contracts[tickId].m_expiry,self.__contracts[tickId].m_strike))
                print('** [LiveFeed __requestWarmupBars] ')
 
            #if self.__debug:
               #(tickerId=tickerId, contract=stkContract, endDateTime='20160128 16:30:00', durationStr='10 D', barSizeSetting='5 secs', whatToShow='TRADES', useRTH=0, formatDate=1)
                #print('%s [LiveFeed __requestWarmupBars] reqHistoricalData: tickerId=%s,durationStr=&s,barSizeSetting=%s,whatToShow=TRADES,useRTH=1,formatDate=2' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,lookbackDuration,barSize))
        
        if self.__debug:
            print('** [LiveFeed __requestWarmupBars] ******************************')
            print('** [LiveFeed __requestWarmupBars] ==EXIT ====EXIT=========================')
    #adds whatever bars we have to queue and requests new ones so bars can go missing here
    def __requestBars(self):

        #push old bars into queue if any remaining - this might cause problems - commenting out to determine if this is the cause
        '''
        if len(self.__currentBar) > 0:
            bars = bar.Bars(self.__currentBar)
            self.__queue.put(bars)
        '''
        self.__currentBar = {}
        if self.__debug:
            print('** [LiveFeed __requestBars] ******************************')


        #what are our duration and frequency settings
        if self.__frequency < bar.Frequency.DAY:
            barSize = "%d min" % (self.__frequency / bar.Frequency.MINUTE)
            #make it mins for anything greater than a minute
            if self.__frequency > bar.Frequency.MINUTE:
                barSize += "s"
        else:
            barSize = "1 day"

        #duration

        if self.__frequency == bar.Frequency.DAY:
            lookbackDuration = "1 D"
        else:
            lookbackDuration = "%d S" % (self.__frequency)                

        for tickId in range(len(self.__contracts)):
            #seems no matter what we do we might end up with a couple of bars of data whether we set an end date/time or not
            #need to handle this by ignoring first bars
            
            if self.__lastBarStamp == 0:
                endDate = ''
            else:
                #%z
                #endDate = time.strftime("%Y%m%d %H:%M:%S GMT", time.gmtime(self.__lastBarStamp + (self.__frequency * 2)-1))   
                endDate = time.strftime("%Y%m%d %H:%M:%S GMT", time.gmtime(self.__lastBarStamp + self.__frequency))   
            
            
            #prevent race condition here with threading
            lastBarTS = self.__lastBarStamp 

            self.__ib.reqHistoricalData(tickId,
                                          self.__contracts[tickId],
                                          '',
                                          lookbackDuration,       #how far back to go
                                          barSize,      #bar size
                                          'TRADES',
                                          1,
                                          2)
        if self.__debug:
            print('%s [LiveFeed __requestBars] tickid:, symbol: %s, security: %s, right: %s, expiry: %s, strike: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,self.__contracts[tickId].m_symbol,self.__contracts[tickId].m_secType,self.__contracts[tickId].m_expiry,self.__contracts[tickId].m_strike))
            print('** [LiveFeed __requestBars] ')
            
        #start the timer and do it all over again 
        if not self.__synchronised:
            delay = self.__calculateSyncDelay(self.__lastBarStamp)
            self.__synchronised = True
        else:
            delay = self.__frequency

        if self.__debug:
            print('%s [LiveFeed __requestBars]- Sleeping for %d seconds for next bar' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),delay))

        #print "Sleeping for %d seconds for next bar" % delay
        self.__timer = threading.Timer(delay,self.__requestBars)
        self.__timer.daemon = True
        self.__timer.start()
        if self.__debug:
            print('[LiveFeed __requestBars]==EXIT=======EXIT============================================')
    def __disconnectHandler(self,msg):
        self.__ib.reconnect()
    def __debugHandler(self,msg):
        if self.__debug:
            print ("")
            print ("[LiveFeed __debugHandler] ")
            print (msg)
    def __errorHandler(self,msg):
        if self.__debug:
            if msg.id !=-1:
                print ("")
                print ("[LiveFeed __requestBars] ERRROR BAR HANDLER")
                print (msg)
    def __historicalBarsHandler(self,msg):
        '''
        deal with warmup bars first then switch to requesting real time bars. Make sure you deal with end of bars 
        properly and cross fingers there's no loss of data
        '''

        #we get one stock per message here so we need to build a set of bars and only add to queue when all quotes 
        #received for all stocks if we ever miss one this thing is going to completely out of whack and either not 
        #return anything or go out of order so we also need to be able to say either send the bar off if we start 
        #getting new ones before its complete or drop the bar completely - seems easier at this point to drop
        #print "stock: %s - time %s open %.2f hi %.2f, low %.2f close %.2f volume %.2f" % 
        #   (self.__instruments[msg.reqId],msg.time, msg.open, msg.high,msg.low,msg.close,msg.volume)
        if self.__debug:
            print('%s [LiveFeed __historicalBarsHandler] ******************************' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
            print ('%s[LiveFeed __historicalBarsHandler] Message received from Server: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),msg))
  
        barDict = {}
        if self.__contracts[msg.reqId].m_secType=='OPT':
            instrument ='%s-%s-%s-%s-%s-%s-%s' %(self.__contracts[msg.reqId].m_symbol,self.__contracts[msg.reqId].m_secType,self.__contracts[msg.reqId].m_right,self.__contracts[msg.reqId].m_strike,self.__contracts[msg.reqId].m_expiry)
            if self.__debug:
                print('%s [LiveFeed __historicalBarsHandler] instrument: %s ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),instrument))

        else:
            instrument =self.__contracts[msg.reqId].m_symbol
            if self.__debug:
                print('%s [LiveFeed __historicalBarsHandler] instrument: %s ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),instrument))

        stockBar = self.__build_bar(msg, instrument,self.__frequency,self.__contracts[msg.reqId].m_currency)
        if stockBar==None:
            return
            
        print("!!!!@@@@@@ %s @@@@@@@" %(stockBar))
        
        if self.__debug:
              print ('%s[LiveFeed  __historicalBarsHandler]>>><<< instrument: %s, stockbar Closing price: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),instrument,stockBar.getClose()))
              print ('%s[LiveFeed  __historicalBarsHandler]>>><<< stockbar : %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),stockBar))

        if self.__inWarmup:
            if self.__debug:
                print('%s [LiveFeed __historicalBarsHandler] self.__inWarmup: %s ' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__inWarmup))

            #non bar means feed has finished or worst case data error but haven't seen one of these yet
            if stockBar == None:
                self.__stockFinishedWarmup[instrument] = True
            else:
                self.__warmupBars[instrument].append(stockBar)
                #prevents duplicate bar error when moving to live mode
                if stockBar != None and int(msg.date) > self.__lastBarStamp:
                    self.__lastBarStamp = int(msg.date)
            
            finishedWarmup = True
            for stock in self.__stockFinishedWarmup:
                if self.__stockFinishedWarmup[stock] == False:
                    finishedWarmup = False

            #all stocks have returned all warmup bars - now we take the n most recent warmup bars and return them in order
            if finishedWarmup:

                #truncate the list to recent
                for stock in self.__warmupBars:
                    self.__warmupBars[stock] = self.__warmupBars[stock][-self.__numWarmupBars:]


                for i in range(0,self.__numWarmupBars):
                    currentBars = {}
                    for stock in self.__instruments:
                        currentBars[stock] = self.__warmupBars[stock][i]


                    #push bars onto queue
                    bars = bar.Bars(currentBars)
                    barEvent=bars.getBar()
                    self.__queue.put(MarketEvent(barEvent))
                    if self.__debug:
                        print('%s[LiveFeed  __historicalBarsHandler] Putting BAR in event queue ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                        print('%s[LiveFeed  __historicalBarsHandler] barEvent: Close:%s ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),barEvent.getClose()))

                #mark the warmup as finished and go to normal bar request mode
                #TODO - potentially we may need to use the last bar to work out the end date for the bars - last bar date + frequency 
                self.__inWarmup = False

                #sync ourselves to the server's pace
                #and ensure we're requesting the bars as soon as they are available (10 second lag added on purpose to allow IB to catchup) rather than any lag caused by startup timing
                
                '''
                if stockBar != None and int(msg.date) > self.__lastBarStamp:
                    lastBarStamp = int(msg.date) 
                else:
                    lastBarStamp = self.__lastBarStamp
                '''

                delay = self.__calculateSyncDelay(self.__currentBarStamp)
                self.__synchronised = True

                print ("[LiveFeed  __historicalBarsHandler] Sleeping for %d seconds for next bar" % delay)
                self.__timer = threading.Timer(delay,self.__requestBars)
                self.__timer.daemon = True
                self.__timer.start()
                if self.__debug:
                    print('** %s [LiveFeed  __historicalBarsHandler] ===EXIT==============EXIT' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))

                #no idea what to do if we missed the end message on the warmup - will never get past here
        else:
            #print("@@@@@@ NO WARMUP @@@@@@@")
            print ('%s[@@@@@] Message received from Server: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),msg))
            Event=MarketEvent(stockBar)
            print ("@@@@@  %s"%(Event.type))
            print ("@@@@@  %s"%(Event.bar.getDateTime()))
            print ("@@@@@  %s"%(Event.bar.getOpen()))
            print ("@@@@@  %s"%(Event.bar.getClose()))
            print ("@@@@@  %s"%(Event.bar.getHigh()))
            print ("@@@@@  %s"%(Event.bar.getLow()))
            print ("@@@@@  %s"%(Event.bar.getVolume()))

            if self.__debug:
                  print ('%s[LiveFeed  __historicalBarsHandler] live bar code no Warmup' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                  print ('%s[LiveFeed  __historicalBarsHandler] ignore bars with a date past the last bar stamp' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
             
                  print ('%s[LiveFeed  __historicalBarsHandler] @int(msg.date): %s ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),int(msg.date)))
                  print ('%s[LiveFeed  __historicalBarsHandler] @self.__lastBarStamp: %s ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__lastBarStamp))

                #normal operating mode 
                #below is the live bar code - ignore bars with a date past the last bar stamp

            if stockBar != None and int(msg.date) > self.__lastBarStamp:
                print("@@@@@@stockBar != None and int(msg.date) > self.__lastBarStamp correct")
 
                self.__currentBar[self.__instruments[msg.reqId]] = stockBar
                self.__queue.put(Event)
                self.__lastBarStamp = int(msg.date) 
                print ("@@@@@ BAR PUT ON THE QUEUE")
                if self.__debug:
                    print('%s[LiveFeed  __historicalBarsHandler] BAR put in event queue ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                    print ('%s[LiveFeed  __historicalBarsHandler] setting current bar to stockbar' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                    print ('%s[LiveFeed  __historicalBarsHandler] self.__currentBar: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__currentBar))
            else:
                  print("@@@@@stockBar != None and int(msg.date) > self.__lastBarStamp not correct")
                  print ("@@@@@ BAR NOT PUT ON THE QUEUE")
                  print ('%s[LiveFeed  __historicalBarsHandler] int(msg.date): %s ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),int(msg.date)))
                  print ('%s[LiveFeed  __historicalBarsHandler] self.__lastBarStamp: %s ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__lastBarStamp))
                
            if self.__debug:
                print ('%s[LiveFeed  __historicalBarsHandler] stockbar Close: %s, Open: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),stockBar.getClose(),stockBar.getOpen()))
                print ('%s[LiveFeed  __historicalBarsHandler] self.__currentBar: %s, len:' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__currentBar,len(self.__currentBar)))
                print ('%s[LiveFeed  __historicalBarsHandler] self.__instruments: %s, len: ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__instruments,len(self.__instruments)))
            
            
            #got all bars?
            print ("@@@@@ len(self.__currentBar): %s"%(len(self.__currentBar)))
            print ("@@@@@ len(self.__instruments) %s"%(len(self.__instruments)))
           
            """
            if len(self.__currentBar) == len(self.__instruments):
                print ("@@@@@ len(self.__currentBar) == len(self.__instruments)")
                bars = bar.Bars(self.__currentBar)
                barEvent=self.__currentBar
                self.__queue.put(MarketEvent(barEvent))
                print ("@@@@@ BAR PUT ON THE QUEUE")
                self.__currentBar = {}
                if self.__debug:
                    print('%s[LiveFeed  __historicalBarsHandler] BAR put in event queue ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                    print('%s[LiveFeed  __historicalBarsHandler] Type barEvent: %s, barEvent: %s ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),type(barEvent),barEvent))

                #keep lastBarStamp at latest unix timestamp so we can use it for the enddate of requesthistoricalbars call
                if stockBar != None and int(msg.date) > self.__lastBarStamp:
                    self.__lastBarStamp = int(msg.date)                
            else:
                if self.__debug:
                    print('%s[LiveFeed  __historicalBarsHandler] BAR NOT PUT in event queue ' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
            """
            if self.__debug:
                print('** [LiveFeed  __historicalBarsHandler] ===EXIT==============EXIT')
    # observer.Subject interface
    def getEventQueue(self):
        return self.__queue
    def __calculateSyncDelay(self,lastBarTS):
        now = int(time.time())
        delay=0
        if lastBarTS > 0:    
            delay = ((lastBarTS + self.__frequency) - now) + 10
        else:
            delay = self.__frequency

        return delay
    #needed for daily bars so we can pick up at the next day's close returns timedelta and timezone
    #time delta is how long after close to next open so 24hrs - opening hours - eg ASX is open 10 - 4 - 8 hours so 24 - 8 is 16
    def __marketCloseTime(self,currency):
        if currency == 'AUD':
            return [datetime.timedelta(hours=16),pytz.timezone('Australia/Sydney')]
        if currency == 'USD':
            return [datetime.timedelta(hours=15,minutes=30),pytz.timezone('America/New_York')]
        if currency == 'GBP':
            return [datetime.timedelta(hours=14,minutes=30),pytz.timezone('Europe/London')]                        


    def start(self):
        pass

    def stop(self):
        pass

    def join(self):
        pass

    def eof(self):
        #TODO might need logic to work out if API has dropped connection here
        return False
        #return self.__thread.stopped()

    def peekDateTime(self):
        return None

    ######################################################################
    # barfeed.BaseBarFeed interface

    def getCurrentDateTime(self):
        return utcnow()

    def barsHaveAdjClose(self):
        return False


    def getNextBars(self):
        ret = None
        try:
            eventData = self.__queue.get(True, LiveFeed.QUEUE_TIMEOUT)
            ret = eventData            
        except Queue.Empty:
            pass
        return ret
#=================
#=================
#!/usr/bin/python
# -*- coding: utf-8 -*-

# data.py

from abc import ABCMeta, abstractmethod
import datetime
import os, os.path

import numpy as np
import pandas as pd

from event import MarketEvent


class DataHandler(object):
    """
    DataHandler is an abstract base class providing an interface for
    all subsequent (inherited) data handlers (both live and historic).

    The goal of a (derived) DataHandler object is to output a generated
    set of bars (OHLCVI) for each symbol requested. 

    This will replicate how a live strategy would function as current
    market data would be sent "down the pipe". Thus a historic and live
    system will be treated identically by the rest of the backtesting suite.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_latest_bar(self, symbol):
        """
        Returns the last bar updated.
        """
        raise NotImplementedError("Should implement get_latest_bar()")

    @abstractmethod
    def get_latest_bars(self, symbol, N=1):
        """
        Returns the last N bars updated.
        """
        raise NotImplementedError("Should implement get_latest_bars()")

    @abstractmethod
    def get_latest_bar_datetime(self, symbol):
        """
        Returns a Python datetime object for the last bar.
        """
        raise NotImplementedError("Should implement get_latest_bar_datetime()")

    @abstractmethod
    def get_latest_bar_value(self, symbol, val_type):
        """
        Returns one of the Open, High, Low, Close, Volume or OI
        from the last bar.
        """
        raise NotImplementedError("Should implement get_latest_bar_value()")

    @abstractmethod
    def get_latest_bars_values(self, symbol, val_type, N=1):
        """
        Returns the last N bar values from the 
        latest_symbol list, or N-k if less available.
        """
        raise NotImplementedError("Should implement get_latest_bars_values()")

    @abstractmethod
    def update_bars(self):
        """
        Pushes the latest bars to the bars_queue for each symbol
        in a tuple OHLCVI format: (datetime, open, high, low, 
        close, volume, open interest).
        """
        raise NotImplementedError("Should implement update_bars()")


class HistoricCSVDataHandler(DataHandler):
    """
    HistoricCSVDataHandler is designed to read CSV files for
    each requested symbol from disk and provide an interface
    to obtain the "latest" bar in a manner identical to a live
    trading interface. 
    """

    def __init__(self, events, csv_dir, symbol_list):
        """
        Initialises the historic data handler by requesting
        the location of the CSV files and a list of symbols.

        It will be assumed that all files are of the form
        'symbol.csv', where symbol is a string in the list.

        Parameters:
        events - The Event Queue.
        csv_dir - Absolute directory path to the CSV files.
        symbol_list - A list of symbol strings.
        """
        self.events = events
        self.csv_dir = csv_dir
        self.symbol_list = symbol_list

        self.symbol_data = {}
        self.latest_symbol_data = {}
        self.continue_backtest = True       
        self.bar_index = 0

        self._open_convert_csv_files()

    def _open_convert_csv_files(self):
        """
        Opens the CSV files from the data directory, converting
        them into pandas DataFrames within a symbol dictionary.

        For this handler it will be assumed that the data is
        taken from Yahoo. Thus its format will be respected.
        """
        comb_index = None
        for s in self.symbol_list:
            # Load the CSV file with no header information, indexed on date
            self.symbol_data[s] = pd.io.parsers.read_csv(
                os.path.join(self.csv_dir, '%s.csv' % s),
                header=0, index_col=0, parse_dates=True,
                names=[
                    'datetime', 'open', 'high', 
                    'low', 'close', 'volume', 'adj_close'
                ]
            ).sort()

            # Combine the index to pad forward values
            if comb_index is None:
                comb_index = self.symbol_data[s].index
            else:
                comb_index.union(self.symbol_data[s].index)

            # Set the latest symbol_data to None
            self.latest_symbol_data[s] = []

        for s in self.symbol_list:
            self.symbol_data[s] = self.symbol_data[s].reindex(
                index=comb_index, method='pad'
            )
            self.symbol_data[s]["returns"] = self.symbol_data[s]["adj_close"].pct_change()
            self.symbol_data[s] = self.symbol_data[s].iterrows()

    def _get_new_bar(self, symbol):
        """
        Returns the latest bar from the data feed.
        """
        for b in self.symbol_data[symbol]:
            yield b

    def get_latest_bar(self, symbol):
        """
        Returns the last bar from the latest_symbol list.
        """
        try:
            bars_list = self.latest_symbol_data[symbol]
        except KeyError:
            print("That symbol is not available in the historical data set.")
            raise
        else:
            return bars_list[-1]

    def get_latest_bars(self, symbol, N=1):
        """
        Returns the last N bars from the latest_symbol list,
        or N-k if less available.
        """
        try:
            bars_list = self.latest_symbol_data[symbol]
        except KeyError:
            print("That symbol is not available in the historical data set.")
            raise
        else:
            return bars_list[-N:]

    def get_latest_bar_datetime(self, symbol):
        """
        Returns a Python datetime object for the last bar.
        """
        try:
            bars_list = self.latest_symbol_data[symbol]
        except KeyError:
            print("That symbol is not available in the historical data set.")
            raise
        else:
            return bars_list[-1][0]

    def get_latest_bar_value(self, symbol, val_type):
        """
        Returns one of the Open, High, Low, Close, Volume or OI
        values from the pandas Bar series object.
        """
        try:
            bars_list = self.latest_symbol_data[symbol]
        except KeyError:
            print("That symbol is not available in the historical data set.")
            raise
        else:
            return getattr(bars_list[-1][1], val_type)

    def get_latest_bars_values(self, symbol, val_type, N=1):
        """
        Returns the last N bar values from the 
        latest_symbol list, or N-k if less available.
        """
        try:
            bars_list = self.get_latest_bars(symbol, N)
        except KeyError:
            print("That symbol is not available in the historical data set.")
            raise
        else:
            return np.array([getattr(b[1], val_type) for b in bars_list])

    def update_bars(self):
        """
        Pushes the latest bar to the latest_symbol_data structure
        for all symbols in the symbol list.
        """
        for s in self.symbol_list:
            try:
                bar = next(self._get_new_bar(s))
            except StopIteration:
                self.continue_backtest = False
            else:
                if bar is not None:
                    self.latest_symbol_data[s].append(bar)
        self.events.put(MarketEvent())

class LiveIBDataHandler():
    """
    IB Live Data Handler
    """

    def __init__(self, contract,
                frequency=60,
                eventQueue=None,
                host="localhost",port=7496,       
                warmupBars = 0, debug=False,fileOutput=None    
    
    
        ):
        """
        Initialises IB data feed for a list of contract.

        Parameters:
        eventQueue - The Event Queue.
        symbol_list - A list of IB contracts.
        Identifier  - Name of the feed data
        hots, port - IB gateway or Desktop connecting 
        warmupBars - In case historical data are needed to initialize strategy
        debug - If debug info must be shown
        fileOutput  - Where the data feed data will persist its data
        """
        self.__stop = False
        self.port=port
        self.host=host
        #Check if a queue is provided if not create one
        #Queue are used to communicate with outside program that 
        #share the same queue
        if eventQueue !=None:
            self.__queue = eventQueue
        else:
            self.__queue = queue.Queue()
        
        #Create a disctionary for bar
        self.__currentBar = {}
        
        #Check if a contract has been provided or a list and 
        #adapt accordingly because the following code expect a list
        #of contract
        if isinstance(contract,list):
            self.__contracts=contract
        elif isinstance(contract,Contract):
            self.__contracts=[contract]
        else:
            raise('Contract should be either a contract or a list of contract')

        #keep track of latest timestamp on any bars for requesting next set
        self.__lastBarStamp = 0
        self.__currentBarStamp = 0
        
      

        self.__timer = None
        
        # File where historical values are outputed
        self.__fileOutput=fileOutput
        
        # BAr frequency       
        self.__frequency = frequency
        '''
        valid frequencies are (and we are really limited by IB here but it's a good range). If the values don't suit then look at taking a higher 
        frequency and using http://gbeced.github.io/pyalgotrade/docs/v0.16/html/strategy.html#pyalgotrade.strategy.BaseStrategy.resampleBarFeed to get the desired frequency
            - 1 minute - 60 - bar.Frequency.MINUTE 
            - 2 minutes - 120 - (bar.Frequency.MINUTE * 2)
            - 5 minutes - 300 - (bar.Frequency.MINUTE * 5)
            - 15 minutes - 900 - (bar.Frequency.MINUTE * 15)
            - 30 minutes - 1800 - (bar.Frequency.MINUTE * 30)
            - 1 hour - 3600 - bar.Frequency.HOUR
            - 1 day - 86400 - bar.Frequency.DAY

            Note: That instrument numbers and frequency affect pacing rules. Keep it to 3 instruments with a 1 minute bar to avoid pacing. Daily hits could include as many as 60 instruments as the limit is 60 calls within a ten minute period. We make one request per instrument for the warmup bars and then one per instrument every frequency seconds. See here for more info on pacing - https://www.interactivebrokers.com/en/software/api/apiguide/tables/historical_data_limitations.htm

        '''
        if self.__frequency not in [60,120,300,900,1800,3600,86400]:
            raise Exception("Please use a frequency of 1,2,5,15,30,60 minutes or 1 day")

        #builds up a list of quotes
        self.__synchronised = False #have we synced to IB's bar pace yet?

        if debug == False:
            self.__debug = False
        else:
            self.__debug = True
        
        self.__ib           = None
        self.connectionTime = None
        self.serverVersion  = None
        self.IbConnect() 
        #### historical code from Data feed      
        #self.symbol_list = symbol_list
        self.symbol_data = {}
        self.latest_symbol_data = {}
        self.bar_index = 0
        ###
        
        #warming up?
        self.__numWarmupBars = warmupBars
        self.__warmupBars = dict((el,[]) for el in self.__contracts)        #the warmup bars arrays indexed by stock code
        #are we still in the warmup phase - when finished warming up this is set to false
        self.__stockFinishedWarmup = dict((el,False) for el in self.__contracts)  #has this stock finished warming up? create dict keyed by stock and set to false

        if self.__numWarmupBars ==0:
            self.__inWarmup = False 
            self.__requestBars()
            
        else:
            if warmupBars > 0:
                if warmupBars > 200:
                    raise Exception("Max number of warmup bars is 200")
                self.__inWarmup = True
                self.__requestWarmupBars()
            else:
                raise Exception("warmup number must be between 0 and 200")
                
         
    def IbConnect(self):
        #Ib connection parameters
        self.__ib = ibConnection(host       =   self.host,
                                 port       =   self.port,
                                 clientId   =   random.randint(1,10000)
                                 )
        self.__ib.register(self._get_new_bar, message.realtimeBar)
        #self.__ib.register(self.__errorHandler, message.error)
        #self.__ib.register(self.__disconnectHandler, 'ConnectionClosed')
        #self.__ib.registerAll(self.__debugHandler)
        self.__ib.connect()
        if self.__ib.isConnected():
            self.connectionTime=self.__ib.reqCurrentTime()
            self.serverVersion=self.__ib.serverVersion()
            if self.__debug:
                print('********************************')
                print('%s LiveIBDataHandler - DATA FEED Connection to IB established' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                print('%s LiveIBDataHandler- IB server connection time: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.connectionTime))
                print('%s LiveIBDataHandler- IB server version: %s' % (datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'), self.serverVersion))
                
        else:
            print('LiveIBDataHandler Connection to IB Error')

    def __requestBars(self):

        self.__currentBar = {}
        if self.__debug:
            print('** [LiveIBDataHandler __requestBars] ******************************')
        #what are our duration and frequency settings
        for tickId in range(len(self.__contracts)):
            #self.__ib.reqMktData(ticker_id, self.__contracts[tickId], generic_tick_keys, False)
           
            self.__ib.reqRealTimeBars(
                            tickerId=tickId,
                             contract= self.__contracts[tickId],
                              barSize=5,
                              whatToShow='TRADES',
                              useRTH=0
            )
            #sleep(1)

        if self.__debug:
            print('%s [LiveIBDataHandler __requestBars] tickid:, symbol: %s, security: %s, right: %s, expiry: %s, strike: %s' %(datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,self.__contracts[tickId].m_symbol,self.__contracts[tickId].m_secType,self.__contracts[tickId].m_expiry,self.__contracts[tickId].m_strike))
            print('[LiveIBDataHandler __requestBars]==EXIT=======EXIT============================================')

    def _get_new_bar(self,msg):
        import datetime
        import pytz
        now             =   datetime.datetime.now()
        barMsg          =   msg
        frequency       =   5
        tz              =   pytz.timezone('America/New_York')
        startDateTime   =   localize(datetime.datetime.fromtimestamp(int(msg.time),tz),tz)

        if self.__debug:
            print ('%s[LiveFeed __build_bar] time: %s, symb: %s, Open: %d ,High: %d, Low: %d, Close: %d, Volume: %d, frequency: %s' %(now,startDateTime,self.__contracts[msg.reqId].m_symbol, float(barMsg.open), float(barMsg.high), float(barMsg.low), float(barMsg.close), int(barMsg.volume), frequency))
    
        #bar= bar.BasicBar(startDateTime, float(barMsg.open), float(barMsg.high), float(barMsg.low), float(barMsg.close), int(barMsg.volume), None, frequency)

        
        barEvent={
                'datetime'  :   msg.time,
                'contract'  :   self.__contracts[msg.reqId],          
                'Open'      :   msg.open,
                'Close'     :   msg.close,
                'High'      :   msg.high,
                'Low'       :   msg.low,
                'wap'       :   msg.wap,
                'Volume'    :   msg.volume
                }
             
        
        self.__queue.put(MarketEvent(barEvent,self.__contracts[msg.reqId]))
        if self.__debug:
            print ("@@@@@ BAR PUT ON THE QUEUE")
    def stop(self):
        print("@@@@@@@@@@@@@@@@@@@@")
        self.__stop = True
        self.__ib.disconnect()
        print("@@@@@@@@@@@@@@@@@@@@")
        print("@@@ @ @@@@@@@@@@@@@@")
        print("@@  @@ @@@@@@@@@@@@@@")
        print("@@   @@@ @@@@@@@@@@@@@@")
        print("@@@@@@@@@@@@@@@@@@@@")
        
            
"""
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

bac=makeStkContrcat('BAC')
aapl=makeStkContrcat('AAPL')

eur=makeForexContract('AUD') 
Live        =   LiveIBDataHandler([bac,aapl],debug=True)
"""
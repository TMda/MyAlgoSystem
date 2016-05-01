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
    return dt.as_utc(datetime.datetime.utcnow())


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


    def __init__(self,contract,frequency=60,eventQueue=None,identifiers=None, 
                host="localhost",port=7496,       
                warmupBars = 0, debug=False,fileOutput=None):
        #barfeed.BaseBarFeed.__init__(self, frequency, maxLen)
        #if not isinstance(identifiers, list):
        #    raise Exception("identifiers must be a list")
        if eventQueue !=None:
            self.__queue = eventQueue
        else:
            self.__queue = queue.Queue()
        self.__currentBar = {}
        if isinstance(contract,list):
            self.__contracts=contract
        elif isinstance(contract,Contract):
            self.__contracts=[contract]
        else:
            raise('Contract should be either a contract or a list of contract')
        self.__instruments = self.buildInstrumentList()# I use contract that is for historical compatibility
        #keep track of latest timestamp on any bars for requesting next set
        self.__lastBarStamp = 0
        self.__currentBarStamp = 0
             
        self.__frequency = frequency
        self.__timer = None
        self.__fileOutput=fileOutput

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
                print('%s LiveFeed - DATA FEED Connection to IB established' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                print('%s LiveFeed- IB server connection time: %s' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.connectionTime))
                print('%s LiveFeed- IB server version: %s' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'), self.serverVersion))
                
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
        if self.__debug:
            now=dt.datetime.now().strftime('%Y%m%d %H:%M:%S')
            print ('%s[LiveFeed __build_bar] **********************************' %(now))
            print('%s[LiveFeed __build_bar] starting try catch sentence'%(now))
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
            print('%s [LiveFeed __requestWarmupBars] work out what duration and barSize to use' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
            print('%s [LiveFeed __requestWarmupBars] frequency (self.__frequency):  %s ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__frequency))
 
        if self.__frequency < bar.Frequency.DAY:
            barSize = "%d min" % (self.__frequency / bar.Frequency.MINUTE)
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency < bar.Frequency.DAY ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] barsize: %s' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),barSize))


            #make it mins for anything greater than a minute
            if self.__frequency > bar.Frequency.MINUTE:
                barSize += "s"
                if self.__debug:
                    print('%s [LiveFeed __requestWarmupBars] make it mins for anything greater than a minute' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                    print('%s [LiveFeed __requestWarmupBars] self.__frequency > bar.Frequency.MINUTE ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))

        else:
            barSize = "1 day"
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency > bar.Frequency.DAY ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] barsize: %s' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),barSize))

        #duration

        if self.__frequency == bar.Frequency.DAY:
            lookbackDuration = "%d D" % self.__numWarmupBars
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency == bar.Frequency.DAY ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] lookbackDuration: %s' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),lookbackDuration))

        else:
            lookbackDuration = "%d S" % (self.__numWarmupBars * self.__frequency)
            if self.__debug:
                print('%s [LiveFeed __requestWarmupBars] self.__frequency != bar.Frequency.DAY ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
                print('%s [LiveFeed __requestWarmupBars] lookbackDuration: %s' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),lookbackDuration))

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
            
                print('%s [LiveFeed __requestWarmupBars] tickid:, symbol: %s, security: %s, right: %s, expiry: %s, strike: %s' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,self.__contracts[tickId].m_symbol,self.__contracts[tickId].m_secType,self.__contracts[tickId].m_expiry,self.__contracts[tickId].m_strike))
                print('** [LiveFeed __requestWarmupBars] ')
 
            #if self.__debug:
               #(tickerId=tickerId, contract=stkContract, endDateTime='20160128 16:30:00', durationStr='10 D', barSizeSetting='5 secs', whatToShow='TRADES', useRTH=0, formatDate=1)
                #print('%s [LiveFeed __requestWarmupBars] reqHistoricalData: tickerId=%s,durationStr=&s,barSizeSetting=%s,whatToShow=TRADES,useRTH=1,formatDate=2' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,lookbackDuration,barSize))
        
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
            print('%s [LiveFeed __requestBars] tickid:, symbol: %s, security: %s, right: %s, expiry: %s, strike: %s' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),tickId,self.__contracts[tickId].m_symbol,self.__contracts[tickId].m_secType,self.__contracts[tickId].m_expiry,self.__contracts[tickId].m_strike))
            print('** [LiveFeed __requestBars] ')
            
        #start the timer and do it all over again 
        if not self.__synchronised:
            delay = self.__calculateSyncDelay(self.__lastBarStamp)
            self.__synchronised = True
        else:
            delay = self.__frequency

        if self.__debug:
            print('%s [LiveFeed __requestBars]- Sleeping for %d seconds for next bar' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),delay))

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
            print('%s [LiveFeed __historicalBarsHandler] ******************************' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
            print ('%s[LiveFeed __historicalBarsHandler] Message received from Server: %s' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),msg))
  
        barDict = {}
        if self.__contracts[msg.reqId].m_secType=='OPT':
            instrument ='%s-%s-%s-%s-%s-%s-%s' %(self.__contracts[msg.reqId].m_symbol,self.__contracts[msg.reqId].m_secType,self.__contracts[msg.reqId].m_right,self.__contracts[msg.reqId].m_strike,self.__contracts[msg.reqId].m_expiry)
            if self.__debug:
                print('%s [LiveFeed __historicalBarsHandler] instrument: %s ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),instrument))

        else:
            instrument =self.__contracts[msg.reqId].m_symbol
            if self.__debug:
                print('%s [LiveFeed __historicalBarsHandler] instrument: %s ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),instrument))

        stockBar = self.__build_bar(msg, instrument,self.__frequency,self.__contracts[msg.reqId].m_currency)
        if self.__debug:
              print ('%s[LiveFeed  __historicalBarsHandler] instrument: %s, stockbar Closing price: %s' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),instrument,stockBar.getClose()))

        if self.__inWarmup:
            if self.__debug:
                print('%s [LiveFeed __historicalBarsHandler] self.__inWarmup: %s ' % (dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__inWarmup))

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
                        print('%s[LiveFeed  __historicalBarsHandler] Putting BAR in event queue ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                        print('%s[LiveFeed  __historicalBarsHandler] barEvent: Close:%s ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),barEvent.getClose()))

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
                    print('** %s [LiveFeed  __historicalBarsHandler] ===EXIT==============EXIT' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))

                #no idea what to do if we missed the end message on the warmup - will never get past here
        else:
            if self.__debug:
                  print ('%s[LiveFeed  __historicalBarsHandler] live bar code no Warmup' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))

            #normal operating mode 
            #below is the live bar code - ignore bars with a date past the last bar stamp
            if self.__debug:
                  print ('%s[LiveFeed  __historicalBarsHandler] ignore bars with a date past the last bar stamp' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))

            if stockBar != None and int(msg.date) > self.__lastBarStamp:
                self.__currentBar[self.__instruments[msg.reqId]] = stockBar
                self.__queue.put(MarketEvent(barEvent))
                if self.__debug:
                    print('%s[LiveFeed  __historicalBarsHandler] BAR put in event queue ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                    print ('%s[LiveFeed  __historicalBarsHandler] setting current bar to stockbar' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                    print ('%s[LiveFeed  __historicalBarsHandler] self.__currentBar: %s' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__currentBar))
       
            if self.__debug:
                print ('%s[LiveFeed  __historicalBarsHandler] stockbar Close: %s, Open: %s' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),stockBar.getClose(),stockBar.getOpen()))
                print ('%s[LiveFeed  __historicalBarsHandler] self.__currentBar: %s, len:' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__currentBar,len(self.__currentBar)))
                print ('%s[LiveFeed  __historicalBarsHandler] self.__instruments: %s, len: ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__instruments,len(self.__instruments)))
                print ('%s[LiveFeed  __historicalBarsHandler] STARTING PUT STOCKBAR IN EVENT QUEUE' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
            
            print ('%s[LiveFeed  __historicalBarsHandler] self.__instruments: %s, len: ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),self.__instruments,len(self.__instruments)))
            print ('%s[LiveFeed  __historicalBarsHandler] IF GOT ALL BAR STARTING PUT STOCKBAR IN EVENT QUEUE' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),))
            
            #got all bars?
            if len(self.__currentBar) == len(self.__instruments):
                bars = bar.Bars(self.__currentBar)
                barEvent=self.__currentBar
                self.__queue.put(MarketEvent(barEvent))
                self.__currentBar = {}
                if self.__debug:
                    print('%s[LiveFeed  __historicalBarsHandler] BAR put in event queue ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))
                    print('%s[LiveFeed  __historicalBarsHandler] Type barEvent: %s, barEvent: %s ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S'),type(barEvent),barEvent))

                #keep lastBarStamp at latest unix timestamp so we can use it for the enddate of requesthistoricalbars call
                if stockBar != None and int(msg.date) > self.__lastBarStamp:
                    self.__lastBarStamp = int(msg.date)                
            else:
                if self.__debug:
                    print('%s[LiveFeed  __historicalBarsHandler] BAR NOT PUT in event queue ' %(dt.datetime.now().strftime('%Y%m%d %H:%M:%S')))

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

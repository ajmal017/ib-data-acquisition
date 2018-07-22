#!/usr/bin/env python
"""This is an end of day algorithmic trading system based on the ideas of Shawn Keller.
Author: Jim Strieter
Date:   06/01/2018
Where:  Scottsdale, AZ
Copyright 2017 James J. Strieter"""


ENABLE_REDUNDANCY_PREVENTION = False
REDUNDANCY_PREVENTION_TERMS = ['ticker', 'epoch']   # Either None or a dictionary to prevent adding the same record twice

import numpy as np
import sys
import argparse
from datetime import datetime
import inspect # Use this to get traceback. Give it a try some time!
import logging
import time
from ibapi import wrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.common import *
from ibapi.order_condition import *
from ibapi.contract import *
from ibapi.order import *
from ibapi.order_state import *
from ibapi.execution import Execution
from ibapi.ticktype import *
from ibapi.account_summary_tags import *
from historicalFetcher import durationDay
from historicalFetcher import sizeDay
from tradingEngine import states
from barTools import human2epoch
from barTools import epoch2human
from techInd import trendDecision
import copy as cp
from contractDump import *
from contracts_jim_uses import spy
from rtWrapper import CustomWrapper
from cmdLineParser import cmdLineParseObj
from threading import Thread
from decisionFunctions import makeTrend
from decisionFunctions import kLite
from decisionFunctions import dLite


from pymongo import MongoClient
import datetime
# client = MongoClient('localhost', 27017)
# db = client.test_database

# def makeBar(ticker, secType, exchange, o, c, h, l, epoch, barLen, parent=None, conId=None)
#     y = {}
#     y['ticker'] = ticker
#     y['secType'] = secType
#     y['open'] = o
#     y['close'] = c
#     y['high'] = h
#     y['low'] = l
#     y['volume'] = -1
#     y['parent'] = parent
#     y['children'] = []
#     y['barLength'] = barLen # Bar length in seconds
#     y['epoch'] = epoch # Epoch time of bar
#     y['dateStr'] = str(epoch2human(epoch))
#     y['numTicks'] = 0 # 0 means no ticks during bar period, 3 = a lot
#     y['exchange'] = exchange
#     y['conId'] = None
#     y['predecessor'] = None         # 1 bar earlier
#     y['successor'] = None           # 1 bar later
#     y['measuredVolatility']
#     return y
#
#
# def makeOptionBar(ticker, exchange, o, c, h, l, epoch, barLen, parent=None):
#     y = barEntry(ticker, "OPT", exchange, o, c, h, l, epoch, barLen, parent)
#     y['numPredecessors']  = 0   # Could be useful if I want to use smoothing
#     y['numSuccessors']    = 0
#     y['calculationStyle'] = ''  # If a bar has 10+ successors/predecessors, can use smoothing. Otherwise not.
#     y['delta']      = None
#     y['gamma']      = None
#     y['speed']      = None
#     y['vega']       = None
#     y['theta']      = None
#     y['rho']        = None
#     y['lambda']     = None      # lambda = omega = (% change in option) / (% change in underlying). aka gearing
#     y['epsilon']    = None      # (% change in option) / (% change in dividend)
#     y['zomma']      = None      # dGamma/dVol
#     y['ultima']     = None
#     y['impliedVolatility'] = None
#
#     return y
#
#
# def makeStochastic():
#     y = {}
#     y['epoch'] = 0
#     y['barLength'] = 0
#     y['parent'] = None
#     y['predecessor'] = None
#     y['successor'] = None


# def dateFilter(dateStr, dateFilt):
#     substr = dateStr[:len(dateFilt)]
#     return substr == dateFilt


class newDailyOnly(CustomWrapper):
    def __init__(self, parseObj=None):
        super().__init__()

        self.dataIds = []

        # Keyed by reqId:
        self.dailyBars = {}
        self.dailyHighs = {}
        self.dailyLows = {}
        self.dailyCloses = {}
        self.dailyOpens = {}
        self.dailyDates = {}
        self.dailyEpochs = {}
        self.ma10 = {}
        self.ma20 = {}
        self.ma10Times = {}
        self.ma20Times = {}
        self.tickers = {}
        self.requestedAlready = {}
        self.historicalDone = {}
        self.kVec = {}
        self.dVec = {}
        self.kTimes = {}
        self.dTimes = {}
        self.entryVec = {}
        self.entryNum = {}
        self.entryTimes = {}
        self.underlyingContract = {}

        # Keyed by ticker:
        self.tick2req = {}

        # Initialize all the dictionaries:
        self.chooseStocks()

        # For interacting w/ Mongo:
        client = MongoClient('localhost', 27017)
        db = client.test_database
        self.posts = db.posts


    def chooseStocks(self):
        self.chooseStocksHelper("SPY", spy())
        self.chooseStocksHelper('AAPL', usStock_aapl())
        self.chooseStocksHelper('ABX', usStock_abx())
        self.chooseStocksHelper('AMD', usStock_amd())
        self.chooseStocksHelper('AXP', usStock_axp())
        self.chooseStocksHelper('BA', usStock_ba())
        self.chooseStocksHelper('BABA', usStock_baba())
        self.chooseStocksHelper('BAC', usStock_bac())
        self.chooseStocksHelper('BB', usStock_bb())
        self.chooseStocksHelper('CAT', usStock_cat())
        self.chooseStocksHelper('CHK', usStock_chk())
        self.chooseStocksHelper('CSCO', usStock_csco())
        self.chooseStocksHelper('CVX', usStock_cvx())
        self.chooseStocksHelper('DIS', usStock_dis())
        self.chooseStocksHelper('DWDP', usStock_dwdp())
        self.chooseStocksHelper('FB', usStock_fb())
        self.chooseStocksHelper('JNJ', usStock_jnj())
        self.chooseStocksHelper('MU', usStock_mu())
        self.chooseStocksHelper('NFLX', usStock_nflx())
        self.chooseStocksHelper('NKE', usStock_nke())
        self.chooseStocksHelper('NVDA', usStock_nvda())
        self.chooseStocksHelper('PFE', usStock_pfe())
        self.chooseStocksHelper('PG', usStock_pg())
        self.chooseStocksHelper('FCX', usStock_fcx())
        self.chooseStocksHelper('GE', usStock_ge())
        self.chooseStocksHelper('GLW', usStock_glw())
        self.chooseStocksHelper('GS', usStock_gs())
        self.chooseStocksHelper('HD', usStock_hd())
        self.chooseStocksHelper('HPQ', usStock_hpq())
        self.chooseStocksHelper('IBM', usStock_ibm())
        self.chooseStocksHelper('INTC', usStock_intc())
        self.chooseStocksHelper('JPM', usStock_jpm())
        self.chooseStocksHelper('KO', usStock_ko())
        self.chooseStocksHelper('LOW', usStock_low())
        self.chooseStocksHelper('MCD', usStock_mcd())
        self.chooseStocksHelper('MMM', usStock_mmm())
        self.chooseStocksHelper('MRK', usStock_mrk())
        self.chooseStocksHelper('MSFT', usStock_msft())
        self.chooseStocksHelper('SBUX', usStock_sbux())
        self.chooseStocksHelper('SLB', usStock_slb())
        self.chooseStocksHelper('SNAP', usStock_snap())
        self.chooseStocksHelper('TSLA', usStock_tsla())
        self.chooseStocksHelper('TWTR', usStock_twtr())
        self.chooseStocksHelper('TXN', usStock_txn())
        self.chooseStocksHelper('UNH', usStock_unh())
        self.chooseStocksHelper('UTX', usStock_utx())
        self.chooseStocksHelper('V', usStock_v())
        self.chooseStocksHelper('VZ', usStock_vz())
        self.chooseStocksHelper('WMT', usStock_wmt())
        self.chooseStocksHelper('XOM', usStock_xom())


    def chooseStocksHelper(self, t, undContract):
        reqId = self.newReqId()
        self.tick2req[t]            = reqId
        self.dailyBars[reqId]       = []
        self.dailyHighs[reqId]      = []
        self.dailyLows[reqId]       = []
        self.dailyCloses[reqId]     = []
        self.dailyOpens[reqId]      = []
        self.dailyDates[reqId]      = []
        self.dailyEpochs[reqId]     = []
        self.tickers[reqId]         = t
        self.requestedAlready[reqId] = False
        self.historicalDone[reqId]  = False
        self.kVec[reqId]            = []
        self.dVec[reqId]            = []
        self.kTimes[reqId]          = []
        self.dTimes[reqId]          = []
        self.ma10[reqId]            = []
        self.ma20[reqId]            = []
        self.ma10Times[reqId]       = []
        self.ma20Times[reqId]       = []
        self.entryVec[reqId]        = []
        self.entryNum[reqId]        = []
        self.entryTimes[reqId]      = []
        self.underlyingContract[reqId] = undContract


    def newReqId(self):
        if len(self.dataIds) == 0:
            self.dataIds.append(3001)
        else:
            self.dataIds.append(self.dataIds[-1] + 1)
        return self.dataIds[-1]


    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.start()


    def start(self):
        """Try moving this to rtWrapper.py"""
        print("*****************************************************************************************************")
        print("******************************************* Running start *******************************************")
        print("*****************************************************************************************************")
        print("self.started: ", self.started)

        if self.started:
            return

        # Normal stuff goes here:
        self.started = True

        if self.globalCancelOnly:
            print("Executing GlobalCancel only")
            self.reqGlobalCancel()
        else:
            print("Executing requests")
            self.requestNextTicker()
            print("Executing requests ... finished")


    def requestNextTicker(self, numDays=364):
        """Scan through the data Ids and request the first thing that isn't finished yet."""
        for m in self.dataIds:
            if not self.historicalDone[m]:
                print("Requesting daily data for ", self.tickers[m], ", reqId: ", m)
                self.reqHistoricalData(m, self.underlyingContract[m], "", durationDay(numDays), sizeDay(), "MIDPOINT", 1, 1, False, [])
                return # leave this here


    def historicalData(self, reqId:int, bar: BarData):
        """Q: Does tEng[] want a bar class or a bar dict?
           A: When he goes to the bar, he's looking for dict. Get it?!? HAHAHAHAHAHAHA"""
        eTime = human2epoch(bar.date)
        setattr(bar, 'epochTime', eTime)
        self.dailyEpochs[reqId].append(eTime)
        self.dailyDates[reqId].append(bar.date)
        self.dailyBars[reqId].append(bar)
        self.dailyHighs[reqId].append(bar.high)
        self.dailyLows[reqId].append(bar.low)
        self.dailyCloses[reqId].append(bar.close)
        self.dailyOpens[reqId].append(bar.open)

        dateObj = epoch2human(eTime)
        dateStr = str(dateObj)

        oneBar = {
            "thingType" :   "bar",
            "secType"   :   "STK",
            "open"      :   bar.open,
            "close"     :   bar.close,
            "high"      :   bar.high,
            "low"       :   bar.low,
            "epoch"     :   eTime,
            "dateStr"   :   dateStr[:8],
            "year"      :   dateObj.year,
            "month"     :   dateObj.month,
            "day"       :   dateObj.day,
            "hour"      :   dateObj.hour,
            "minute"    :   dateObj.minute,
            "second"    :   dateObj.second,
            "trigNow"   :   False,
            "ticker"    :   self.tickers[reqId],
            "barLen"    :   "1 day"
        }

        if len(self.dailyCloses[reqId]) > 10:
            # Calculate 10 day MA
            self.ma10[reqId].append(makeTrend(self.dailyHighs[reqId][-9:], self.dailyLows[reqId][-9:]))
            self.ma10Times[reqId].append(eTime)

        if len(self.dailyCloses[reqId]) > 21:
            # Calculate 20 day MA
            self.ma20[reqId].append(makeTrend(self.dailyHighs[reqId][-21:], self.dailyLows[reqId][-21:], tol=0.02))
            self.ma20Times[reqId].append(eTime)

        if len(self.dailyCloses[reqId]) > 20:
            # Calculate %K:
            self.kVec[reqId].append(kLite(self.dailyHighs[reqId][-20:], self.dailyLows[reqId][-20:], bar.close))
            self.kTimes[reqId].append(eTime)

        if len(self.kVec[reqId]) > 3:
            # Calculate %D:
            self.dVec[reqId].append(dLite(self.kVec[reqId][-3:]))
            self.dTimes[reqId].append(eTime)

        self.entrySig(reqId, eTime)

        if len(self.entryTimes[reqId]) > 0 and self.entryTimes[reqId][-1] == eTime:
            oneBar['trigNow'] = True
            oneBar["trigDirection"] = self.entryVec[reqId][-1]

        # Send to Mongo:
        if ENABLE_REDUNDANCY_PREVENTION:
            if len(REDUNDANCY_PREVENTION_TERMS) > 0:
                redunPreventionDic = {}
                if 'ticker' in REDUNDANCY_PREVENTION_TERMS:
                    redunPreventionDic["ticker"] = self.tickers[reqId]
                if "epoch" in REDUNDANCY_PREVENTION_TERMS:
                    redunPreventionDic["epoch"] = eTime
                # Insert other if statements here.
                if self.posts.find(redunPreventionDic).count() == 0:
                    self.posts.insert_one(oneBar)
                else:
                    # If results are returned, do not add this bar again.
                    pass
            else:
                self.posts.insert_one(oneBar)
        else:
            self.posts.insert_one(oneBar)


    def entrySig(self, reqId, eTime, tol=0.01):
        assert(tol >= 0)
        if len(self.dVec[reqId]) < 5:
            return
        if len(self.ma20[reqId]) < 25:
            return
        if len(self.ma10[reqId]) < 15:
            return
        if self.ma20[reqId][-1] == "up" and self.ma10[reqId][-1] == "down":
            if self.dVec[reqId][-2] > self.kVec[reqId][-2] + tol:
                if self.kVec[reqId][-1] > self.dVec[reqId][-1] + tol:
                    self.entryVec[reqId].append("call")
                    self.entryNum[reqId].append(3)
                    self.entryTimes[reqId].append(eTime)
                    return
                return
            return
        if self.ma10[reqId][-1] == "up" and self.ma20[reqId][-1] == "down":
            if self.kVec[reqId][-2] > self.dVec[reqId][-2] + tol:
                if self.dVec[reqId][-1] > self.kVec[reqId][-1] + tol:
                    self.entryVec[reqId].append("put")
                    self.entryNum[reqId].append(1)
                    self.entryTimes[reqId].append(eTime)
                    return
                return
            return
        return


    def historicalDataEnd(self, reqId: int, start: str, end: str):
        self.historicalDone[reqId] = True
        self.requestNextTicker()
        if self.allDailyHistoricalDone():
            #self.generateReport()
            self.done = True


    def allDailyHistoricalDone(self):
        y = True
        for m in self.dataIds:
            y = y and self.historicalDone[m]
        return y


def rightJustify(s, w):
    """right justifies a string s to be column width w"""
    numSpace = w - len(str(s))
    if numSpace < 1:
        numSpace = 1
    return " "*numSpace + str(s)


def floatField(x, w, p):
    """Returns number x formatted to be p digits with field width w."""
    x = float(x)
    return f"{x:{w}.{p}}"


def makePriceRow(h, l, o, c, w=12, p=6):
    """Column order:
        Open   Close    High    Low"""
    return floatField(float(o), w, p) + floatField(float(c), w, p) + floatField(float(h), w, p) + floatField(float(l), w, p)


def main():
    cmdLineParser = cmdLineParseObj()
    args = cmdLineParser.parse_args()
    print("Using args", args)
    from ibapi import utils
    from ibapi.order import Order
    Order.__setattr__ = utils.setattr_log
    from ibapi.contract import Contract, UnderComp
    Contract.__setattr__ = utils.setattr_log
    UnderComp.__setattr__ = utils.setattr_log
    from ibapi.tag_value import TagValue
    TagValue.__setattr__ = utils.setattr_log
    TimeCondition.__setattr__ = utils.setattr_log
    ExecutionCondition.__setattr__ = utils.setattr_log
    MarginCondition.__setattr__ = utils.setattr_log
    PriceCondition.__setattr__ = utils.setattr_log
    PercentChangeCondition.__setattr__ = utils.setattr_log
    VolumeCondition.__setattr__ = utils.setattr_log

    try:
        #app = MyTradingApp(cmdLineParser.parse_args())
        app = newDailyOnly(cmdLineParser.parse_args())
        if args.global_cancel:
            app.globalCancelOnly = True
        # ! [connect]
        app.connect("127.0.0.1", args.port, clientId=0)
        print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                      app.twsConnectionTime()))
        # ! [connect]

        app.run()
        app.nextValidId(1) # nextValidId

    except:
        raise
    finally:
        app.dumpTestCoverageSituation()
        app.dumpReqAnsErrSituation()


if __name__ == "__main__":
    main()


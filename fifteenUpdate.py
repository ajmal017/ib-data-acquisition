#!/usr/bin/env python
"""This is an end of day algorithmic trading system based on the ideas of Shawn Keller.
Author: Jim Strieter
Date:   06/01/2018
Where:  Scottsdale, AZ
Copyright 2017 James J. Strieter"""

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
from historicalFetcher import sizeMin
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
from pymongo import MongoClient
import datetime


class newDailyOnly(CustomWrapper):
    def __init__(self, parseObj=None):
        super().__init__()

        self.dataIds = []

        # Keyed by reqId:
        self.latestEpoch = {}
        self.tickers = {}
        self.requestedAlready = {}
        self.historicalDone = {}
        self.underlyingContract = {}

        # Keyed by ticker:
        self.tick2req = {}

        # Initialize all the dictionaries:
        self.chooseStocks()

        # For interacting w/ Mongo:
        client = MongoClient('localhost', 27017)
        db = client.test_database
        self.posts = db.posts
        self.searchMongo()


    def chooseStocksHelper(self, t, undContract):
        reqId = self.newReqId()
        self.tick2req[t]                = reqId
        self.tickers[reqId]             = t
        self.requestedAlready[reqId]    = False
        self.historicalDone[reqId]      = False
        self.underlyingContract[reqId]  = undContract
        self.latestEpoch[reqId]         = -1 # Do NOT initialize to None


    def searchMongo(self):
        """Initializes self.latestEpoch"""
        for reqId in self.dataIds:
            ticker = self.tickers[reqId]
            # barList = self.posts.find({"ticker":ticker, "barLen":"1 day", "secType":"STK"})
            for bar in self.posts.find({"ticker":ticker, "barLen":"15 min", "secType":"STK"}): #, "close":{"$exists":"1"}, "strike":{"$exists":"0"}}):
                if bar["epoch"] > self.latestEpoch[reqId]:
                    self.latestEpoch[reqId] = bar["epoch"]
                    # print(ticker, "    ", bar["epoch"])

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


    def requestNextTicker(self, numDays=10):
        """Scan through the data Ids and request the first thing that isn't finished yet."""
        for m in self.dataIds:
            if not self.historicalDone[m]:
                print("Requesting daily data for ", self.tickers[m], ", reqId: ", m)
                self.reqHistoricalData(m, self.underlyingContract[m], "", durationDay(numDays), sizeMin(15), "MIDPOINT", 1, 1, False, [])
                return # leave this here


    def historicalData(self, reqId:int, bar: BarData):
        """Q: Does tEng[] want a bar class or a bar dict?
           A: When he goes to the bar, he's looking for dict. Get it?!? HAHAHAHAHAHAHA"""
        eTime = human2epoch(bar.date)
        if eTime > self.latestEpoch[reqId]:
            self.latestEpoch[reqId] = eTime
            setattr(bar, 'epochTime', eTime)
            dateObj = epoch2human(eTime)
            dateStr = str(dateObj)
            print("Adding to mongo: ", self.tickers[reqId], "     ", dateStr)

            oneBar = {
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
                "ticker"    :   self.tickers[reqId],
                "barLen"    :   "15 min"
            }

            # Send to mongo:
            self.posts.insert_one(oneBar)


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


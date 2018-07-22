#!/usr/bin/env python
"""Collects 5 second RT bars from IB and sends to mongo.
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
from makeContract import dict2Contract

client = MongoClient('localhost', 27017)
db = client.test_database


# def dic2cont(someDic):
#     """Converts a contract dic to an object contract"""
#     cont = Contract()
#     cont.lastTradeDateOrContractMonth = someDic["expiration"]
#     cont.symbol = someDic["ticker"]
#     cont.exchange = "SMART",
#     cont.right = "CALL",
#     cont.strike = someDic["strike"]
#     cont.currency = "USD"
#     return cont


class newFifteenOnly(CustomWrapper):
    def __init__(self, parseObj=None):
        super().__init__()

        self.dataIds = []

        # Keyed by reqId:
        self.tickers = {}
        self.historicalDone = {}
        self.rights = {}

        # Keyed by ticker:
        self.tick2req = {}

        # Initialize all the dictionaries:
        self.chooseStocks()

        # For interacting w/ Mongo:
        self.posts = db.posts

        self.optContracts = {} # Keyed by ticker
        for m in self.posts.find({"right" : {"$exists" : 1}}):
            self.optContracts[m["ticker"]] = m
            # print(m["ticker"], "     ", m["strike"])


    def chooseStocks(self):
        # self.chooseStocksHelper("SPY", spy())
        # self.chooseStocksHelper('AAPL', usStock_aapl())
        self.chooseStocksHelper('ABX', usStock_abx())
        self.chooseStocksHelper('AMD', usStock_amd())
        self.chooseStocksHelper('AXP', usStock_axp())
        self.chooseStocksHelper('BA', usStock_ba())
        # self.chooseStocksHelper('BABA', usStock_baba())
        # self.chooseStocksHelper('BAC', usStock_bac())
        # self.chooseStocksHelper('BB', usStock_bb())
        # self.chooseStocksHelper('CAT', usStock_cat())
        # self.chooseStocksHelper('CHK', usStock_chk())
        # self.chooseStocksHelper('CSCO', usStock_csco())
        # self.chooseStocksHelper('CVX', usStock_cvx())
        # self.chooseStocksHelper('DIS', usStock_dis())
        # self.chooseStocksHelper('DWDP', usStock_dwdp())
        # self.chooseStocksHelper('FB', usStock_fb())
        # self.chooseStocksHelper('JNJ', usStock_jnj())
        # self.chooseStocksHelper('MU', usStock_mu())
        # self.chooseStocksHelper('NFLX', usStock_nflx())
        # self.chooseStocksHelper('NKE', usStock_nke())
        # self.chooseStocksHelper('NVDA', usStock_nvda())
        # self.chooseStocksHelper('PFE', usStock_pfe())
        # self.chooseStocksHelper('PG', usStock_pg())
        # self.chooseStocksHelper('FCX', usStock_fcx())
        # self.chooseStocksHelper('GE', usStock_ge())
        # self.chooseStocksHelper('GLW', usStock_glw())
        # self.chooseStocksHelper('GS', usStock_gs())
        # self.chooseStocksHelper('HD', usStock_hd())
        # self.chooseStocksHelper('HPQ', usStock_hpq())
        # self.chooseStocksHelper('IBM', usStock_ibm())
        # self.chooseStocksHelper('INTC', usStock_intc())
        # self.chooseStocksHelper('JPM', usStock_jpm())
        # self.chooseStocksHelper('KO', usStock_ko())
        # self.chooseStocksHelper('LOW', usStock_low())
        # self.chooseStocksHelper('MCD', usStock_mcd())
        # self.chooseStocksHelper('MMM', usStock_mmm())
        # self.chooseStocksHelper('MRK', usStock_mrk())
        # self.chooseStocksHelper('MSFT', usStock_msft())
        # self.chooseStocksHelper('SBUX', usStock_sbux())
        # self.chooseStocksHelper('SLB', usStock_slb())
        # self.chooseStocksHelper('SNAP', usStock_snap())
        # self.chooseStocksHelper('TSLA', usStock_tsla())
        # self.chooseStocksHelper('TWTR', usStock_twtr())
        # self.chooseStocksHelper('TXN', usStock_txn())
        # self.chooseStocksHelper('UNH', usStock_unh())
        # self.chooseStocksHelper('UTX', usStock_utx())
        # self.chooseStocksHelper('V', usStock_v())
        # self.chooseStocksHelper('VZ', usStock_vz())
        # self.chooseStocksHelper('WMT', usStock_wmt())
        # self.chooseStocksHelper('XOM', usStock_xom())


    def chooseStocksHelper(self, t, undContract):
        """undContract is not used in this file. It is only an input so that chooseStocks()
        can be copied & pasted from other files.

        Since reqIds start at 3001, odd reqIds are calls and even reqIds are puts.

        Since self.tick2req[someTicker] is a scalar, not a list, it is only populated
        for calls. If you want the reqId for a put, use this:
            self.tick2req[someTicker]+1                                                 """

        # Handle Calls:
        reqId = self.newReqId()
        self.tick2req[t]                = reqId
        self.tickers[reqId]             = t
        self.historicalDone[reqId]      = False
        self.rights[reqId]              = "CALL"

        # Handle Puts:
        reqId = self.newReqId()
        self.tickers[reqId]             = t
        self.historicalDone[reqId]      = False
        self.rights[reqId]              = "PUT"


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
            self.realTimeBars_req()
            print("Executing requests ... finished")


    def realTimeBars_req(self):
        """Iterates through all the reqId's we created earlier and sends the contract associated with each
        to TWS."""
        print(self.dataIds)

        for reqId in self.dataIds:
            ticker = self.tickers[reqId]
            print("Requesting Data Id: ", reqId, "     ", ticker)
            cont = dict2Contract(ticker, self.optContracts[ticker]["strike"], self.rights[reqId], self.optContracts[ticker], acct=None)
            cont.lastTradeDateOrContractMonth = "20180720"
            self.reqRealTimeBars(reqId, cont, 5, "MIDPOINT", False, [] )


    def realtimeBar(self, reqId: TickerId, eTime: int, open: float, high: float, low: float, close: float, volume: int,
                    wap: float, count: int, testMode=False):
        super().realtimeBar(reqId, time, open, high, low, close, volume, wap, count)
        ticker = self.tickers[reqId]
        print("RT Data: ", ticker, "    ", close, "     ", self.rights[reqId])
        dateObj = epoch2human(eTime)
        dateStr = str(dateObj)

        oneBar = {
            "secType": "OPT",
            "open": open,
            "close": close,
            "high": high,
            "low": low,
            "epoch": eTime,
            "dateStr": dateStr[:8],
            "year": dateObj.year,
            "month": dateObj.month,
            "day": dateObj.day,
            "hour": dateObj.hour,
            "minute": dateObj.minute,
            "second": dateObj.second,
            "barLen": "15 mins",
            "ticker": ticker,
            "strike": self.optContracts[ticker]["strike"],
            "expiration": self.optContracts[ticker]["expiration"],
            "right": self.rights[reqId],
            "exchange": self.optContracts[ticker]["exchange"]
        }

        self.posts.insert_one(oneBar)


    def historicalData(self, reqId:int, bar: BarData):
        """Q: Does tEng[] want a bar class or a bar dict?
           A: When he goes to the bar, he's looking for dict. Get it?!? HAHAHAHAHAHAHA"""
        ticker = self.tickers[reqId]
        print("Historical Data: ", ticker, "    ", bar.close)
        eTime = human2epoch(bar.date)
        dateObj = epoch2human(eTime)
        dateStr = str(dateObj)

        oneBar = {
            "secType"   :   "OPT",
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
            "barLen"    :   "15 mins",
            "ticker"    :   ticker,
            "strike"    :   self.optContracts[ticker]["strike"],
            "expiration":   self.optContracts[ticker]["expiration"],
            "right"     :   self.optContracts[ticker]["right"],
            "exchange"  :   self.optContracts[ticker]["exchange"]
        }

        self.posts.insert_one(oneBar)


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
        app = newFifteenOnly(cmdLineParser.parse_args())
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


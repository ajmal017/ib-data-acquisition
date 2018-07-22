#!/usr/bin/env python
"""Acquires option contract data and dumps it to mongo.
Author: Jim Strieter
Date:   06/10/2018
Where:  Scottsdale, AZ
Copyright 2018 James J. Strieter

ACTION: Flesh out this file.
    - Make a version that ONLY does options
    - Make a version that ONLY does underlying
        - This version should mine conId's and generate contractDump.py.
    - They both dump data to mongo
    - Modify to cancel data request after receiving enough stuff
    - Use default params, and start modifying if returned data is too small,
      doesn't cover all cancelConditions, etc.
"""

defaultParams = {
    "expiration"        :       "20180720"
}

MAX_ATTEMPTS = 3

# Do this for all possible keys:
# if "numExchanges" in cancelConditions.keys():
#     numExchanges = getExchanges()
#     if numExchanges >= cancelConditions["numExchanges"]:
#         cancelRequest()


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
from dailyDataAnalysis import connect2Mongo
from getLatestClose import getLatestClose
from pymongo import MongoClient
import datetime
from dailyDataAnalysis import connect2Mongo
from dailyDataAnalysis import sortListOfDictionaries
from daily2mongo import rightJustify


class contractMiner(CustomWrapper):
    def __init__(self, parseObj=None, maxAttempts=MAX_ATTEMPTS):
        super().__init__()

        # Store all our reqIds in 1 place:
        self.dataIds = []

        # Keyed by reqId:
        self.tickers            = {}
        self.contracts          = {}
        self.requestedContracts = {}    # Can be underlying or derivative
        self.receivedContracts  = {}    # Handy for calculating Greeks later.
        self.closes             = {}
        self.epochs             = {}
        self.tickerDone         = {}
        self.startingStrike     = {}
        self.strikeDeviationMag = {}
        self.strikeDeviationSgn = {}
        self.numAttempts        = {}

        # Keyed by ticker:
        self.tick2req = {}

        # Initialize all the dictionaries:
        self.chooseStocks()

        # For interacting w/ Mongo:
        self.posts = connect2Mongo().posts

        # Terminate stuff that is going poorly:
        self.maxAttempts = maxAttempts
        self.reqMgrCount = 0
        self.getClosingPrices()


    def getClosingPrices(self):
        """Retrieves closing prices from mongo and maps the latest one to reqId."""
        x = self.posts.find({"barLen":"close only"})
        for m in x:
            print(m)
            reqId = self.tick2req[m['ticker']]
            if m['epoch'] is not None and m['epoch'] > self.epochs[reqId]:
                self.epochs[reqId] = m['epoch']
                self.closes[reqId] = m['close']
                self.requestedContracts[reqId].strike = np.floor(m['close'])
                self.startingStrike[reqId] = np.floor(m['close'])
        for m in self.tick2req.keys():
            reqId = self.tick2req[m]
            print(m, "    ", self.closes[reqId], "    ", self.epochs[reqId])


    def chooseStocksHelper(self, t, contract, conId=None):
        reqId = self.newReqId()
        self.tick2req[t]                = reqId
        self.tickers[reqId]             = t
        self.contracts[reqId]           = contract
        self.closes[reqId]              = None
        self.epochs[reqId]              = -1 # DO NOT initialize to None!!!
        self.successfulStrikes          = []
        self.tickerDone[reqId]          = False
        c = Contract()
        c.symbol                        = t
        c.secType                       = "OPT"
        c.exchange                      = "SMART"
        c.lastTradeDateOrContractMonth  = defaultParams["expiration"]
        c.right                         = "CALL"
        c.currency                      = "USD"
        c.strike                        = None
        self.requestedContracts[reqId]  = c
        self.receivedContracts[reqId]   = []
        self.startingStrike[reqId]      = None
        self.strikeDeviationMag[reqId]  = None
        self.strikeDeviationSgn[reqId]  = 1
        self.numAttempts[reqId]         = 0


    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        super().error(reqId, errorCode, errorString)
        if "No security definition" in errorString:
            # PICK UP HERE: try another strike
            self.requestedContracts[reqId].strike += 1
            self.reqContractDetails(reqId, self.requestedContracts[reqId])


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
        print("Got to Next Valid Id")
        self.start()


    def start(self):
        """Try moving this to rtWrapper.py"""
        print("*****************************************************************************************************")
        print("******************************************* Running start #44 *******************************************")
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
            #self.requestMgr()
            for m in self.dataIds:
                self.reqContractDetails(m, self.requestedContracts[m])
            print("Executing requests ... finished")


    def allTickersDone(self):
        for m in self.tickerDone.keys():
            if not self.tickerDone[m]:
                return False
        return True


    def getNextTicker(self):
        for m in self.tickerDone.keys():
            if not self.tickerDone[m]:
                return m
        return None


    def requestMgr(self, reqId=None):
        """This is the logical hub of the whole program"""
        return
        # print("Request Manager", self.reqMgrCount)
        # self.reqMgrCount += 1
        # if self.allTickersDone():
        #     self.done = True
        #     return
        #
        # if reqId is not None:
        #     if self.numAttempts[reqId] >= self.maxAttempts:
        #         self.done = True
        #         return
        #
        # nextTicker = self.getNextTicker()
        # if nextTicker in self.tick2req.keys():
        #     reqId = self.tick2req[nextTicker]
        #     if reqId in self.requestedContracts.keys():
        #         self.reqContractDetails(reqId, self.requestedContracts[reqId])


    def tryAnotherStrike(self, reqId):
        self.requestedContracts[reqId].strike = str()
        return


    def contractDetails(self, reqId:int, contractDetails:ContractDetails):
        oneContr = {
            "ticker"        :   self.tickers[reqId],
            "expiration"    :   contractDetails.summary.lastTradeDateOrContractMonth,
            "strike"        :   contractDetails.summary.strike,
            "right"         :   "CALL",
            "exchange"      :   contractDetails.summary.exchange,
            "validExchanges":   contractDetails.validExchanges,
            "underConId"    :   contractDetails.underConId,
            "underSymbol"   :   contractDetails.underSymbol,
            "underSecType"  :   contractDetails.underSecType,
            "contractMonth" :   contractDetails.contractMonth,
            "tradingHours"  :   contractDetails.tradingHours,
            "liquidHours"   :   contractDetails.liquidHours,
            "currency"      :   contractDetails.summary.currency,
            "epochAdded"    :   '',
            "dateAdded"     :   '',
            "notes"         :   contractDetails.notes
        }
        self.posts.insert_one(oneContr)
        # print("Contract Details: ", contractDetails)
        # with open("./contract-details.txt", 'a+') as f:
        #     f.write(str(contractDetails)+"\n")


    def contractDetailsEnd(self, reqId:int):
        print("Finished with: ", reqId)
        self.tickerDone[reqId] = True
        if self.allTickersDone():
            for m in self.posts.find({"right":"CALL"}):
                print(m)
            self.done = True

        #self.requestMgr(reqId)


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
        app = contractMiner(cmdLineParser.parse_args())
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

        # Print Trades to Screen:
        print("\n"*20)


if __name__ == "__main__":
    main()


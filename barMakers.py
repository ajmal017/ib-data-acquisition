def safe2divide(o, c, h, l, minDenominator):
    """Assesses whether it is safe to use the difference between 2 values in a bar
    as a denominator, for instance 1/(h-l), and also verifies the underlying assumptions
    such as open <= high, etc."""
    assert(minDenominator >= 0)
    # Work in a little margin for comparing open and close:
    h0 = h + minDenominator
    l0 = l - minDenominator
    #           Primary Concern      |              Underlying Assumptions
    #      -------------------------------------------------------------------------------
    return (h - l > minDenominator) and (o <= h0) and (c <= h0) and (o >= l0) and (c >= l0)

def makeBar(ticker, secType, exchange, o, c, h, l,
            epoch, barLen, measuredVol=None, parent=None, conId=None, minDenominator=1E-6):
    y = {}
    y['ticker']         = ticker
    y['secType']        = secType
    y['open']           = o
    y['close']          = c
    y['high']           = h
    y['low']            = l
    y['safe2divide']    = safe2divide(o, c, h, l, minDenominator)
    y['volume']         = -1
    y['parent']         = parent
    y['children']       = []
    y['barLength']      = barLen        # Bar length in seconds
    y['epoch']          = epoch         # Epoch time of bar
    y['dateStr']        = str(epoch2human(epoch))
    y['numTicks']       = 0             # 0 means no ticks during bar period, 3 = a lot
    y['exchange']       = exchange
    y['conId']          = None
    y['predecessor']    = None          # 1 bar earlier
    y['successor']      = None          # 1 bar later
    y['measuredVolatility'] = measuredVol
    return y


def makeOptionBar(existingDic, delta, gamma, theta, iv, speed=None, vega=None, rho=None,
                  lambd=None, epsilon=None, zomma=None, ultima=None,
                  predSmoothing=None, sucSmoothing=None):
    existingDic['delta']        = delta
    existingDic['gamma']        = gamma
    existingDic['theta']        = theta
    existingDic['iv']           = iv
    existingDic['speed']        = speed
    existingDic['vega']         = vega
    existingDic['rho']          = rho
    existingDic['lambda']       = lambd     # lambda = omega = (% change in option) / (% change in underlying). aka gearing
    existingDic['epsilon']      = epsilon   # (% change in option) / (% change in dividend)
    existingDic['zomma']        = zomma,    # dGamma/dVol
    existingDic['ultima']       = ultima,
    existingDic['predecessorSmoothing'] = predSmoothing     # Number of predecessors (past bars) that went into Greek smoothing
    existingDic['successorSmoothing'] = sucSmoothing        # Number of successors (future bars) that went into Greek smoothing
    return y


def makeStochastic(eTime, k, d, kLength, dLength, barLength, parent=None, predecessor=None):
    """Takes an existing dictionary and adds option fields to it."""
    y                   = {}
    y['epoch']          = eTime
    y['barLength']      = barLength         # bar length in seconds
    y['parent']         = parent
    y['predecessor']    = predecessor
    y['successor']      = None
    y['kLength']        = kLength
    y['dLength']        = dLength
    y['k']              = k
    y['d']              = d
    return y
def buildContractRepresentation(ibContract):
    return ("%s:%s:%s:%s:%s" %(ibContract.m_symbol,ibContract.m_secType,ibContract.m_right,ibContract.m_strike,ibContract.m_expiry )).strip()

def makeFutureContract(
    m_symbol,
    ContractMonth,
    m_secType="FUT",
    m_currency="USD",
    m_exchange="GLOBEX"):
            
    

    from ib.ext.Contract import Contract
    contract   =  Contract()
    contract.m_symbol   = m_symbol
    contract.m_secType  = m_secType
    contract.m_currency = m_currency
    contract.m_exchange = m_exchange
    contract.m_lastTradeDateOrContractMonth = ContractMonth
    return contract



def makeStkContrcat(
    m_symbol,
    m_secType = 'STK',
    m_exchange = 'SMART',
    m_currency = 'USD'):

    from ib.ext.Contract import Contract
    newContract = Contract()
    newContract.m_symbol = m_symbol
    newContract.m_secType = m_secType
    newContract.m_exchange = m_exchange
    newContract.m_currency = m_currency
    return newContract
        
def makeOptContract(
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
        
def makeForexContract(
    
    m_symbol,
    m_secType  = 'CASH',
    m_exchange = 'IDEALPRO',
    m_currency = 'USD'):
        
    from ib.ext.Contract import Contract
    newContract = Contract()
    newContract.m_symbol = m_symbol
    newContract.m_secType = m_secType
    newContract.m_exchange = m_exchange
    newContract.m_currency = m_currency
    return newContract
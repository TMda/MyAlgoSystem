import sqlite3

conn = sqlite3.connect('myalgo.db')
print "Opened database successfully";
    request_body = "
                CREATE TABLE portfolio 
   
                    "strategy_name"            CHAR(250),
                    "run_number"                INT ,
                    "contract_code"             CHAR(250,
                    "datetime"                 CHAR(250),
                    "ibContract_m_symbol"       CHAR(250),
                    "ibContract_m_secType"      CHAR(250),
                    "ibContract_m_currency"     CHAR(250),
                    "ibContract_m_exchange"     CHAR(250),
                    "ibContract_m_multiplier"   CHAR(250),
                    "ibContract_m_expiry"       CHAR(250),
                    "ibContract_m_strike"       REAL,
                    "ibContract_m_right"        CHAR(250),
                    "position"                  INT ,
                    "marketPrice"               REAL,
                    "marketValue"               REAL,
                    "averageCost"               REAL,
                    "unrealizedPNL"             REAL,
                    "realizedPNL"               REAL,
                    "accountName"               CHAR(250)
"
    #
conn.execute(request_body)
print "Table created successfully";

conn.close()
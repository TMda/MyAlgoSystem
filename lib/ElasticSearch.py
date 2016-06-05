from __future__ import absolute_import, division,print_function, unicode_literals
import cython
import datetime
BROWSER_USER_AGENT='Mozilla/5.0 (Linux; U; Android 2.3.5; AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
ES_HOST = {"host" : "localhost", "port" : 9200}
INDEX_NAME = 'myalgo'
TYPE_NAME  ='portfolio'
ES_LOADING_BULK=60

#%%
def createEsIndex(type_name=TYPE_NAME,delete=False):
    #%%
    #ES_HOST = {"host" : "localhost", "port" : 9200}
    #INDEX_NAME = 'eestore'
    #type_name='news_en'
    delete=False
    #%%
    TYPE_NAME =type_name
    #%%
    #
    from elasticsearch import Elasticsearch
    print ('createEsIndex starts: %s'% (unicode(datetime.datetime.now())))

    # create ES client, create index
    es = Elasticsearch(hosts = [ES_HOST])
    #
    if delete:
        if es.indices.exists(INDEX_NAME):
            print("deleting '%s' index..." % (INDEX_NAME))
            res = es.indices.delete(index = INDEX_NAME)
            print(" response: '%s'" % (res))
        else:
            print("index '%s' does not exist." % (INDEX_NAME))
    #  
    # since we are running locally, use one shard and no replicas
    request_body = {
        "settings" : {
            "number_of_shards": 5,
            "number_of_replicas": 0
            },

        "mappings": {
            "portfolio": {
                #"include_in_all": false,
                #"_id": {
                #    "path": "doc_id"
                #    },
                #"_source": {
                #    "enabled": false
                #},
                

                "properties": {
                    "strategy_name"             :   {"type": "string",  "index": "not_analyzed",     "analyzer": "english"},
                    "run_number"                :   {"type": "integer", "index": "not_analyzed" },
                    "contract_code"             :   {"type": "string",  "index": "not_analyzed",     "analyzer": "english" },
                    "datetime"                  :   {"type": "date",    "index": "not_analyzed" },
                    "ibContract_m_symbol"       :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "ibContract_m_secType"      :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "ibContract_m_currency"     :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "ibContract_m_exchange"     :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "ibContract_m_multiplier"   :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "ibContract_m_expiry"       :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "ibContract_m_strike"       :   {"type": "float",   "index": "not_analyzed" },
                    "ibContract_m_right"        :   {"type": "string",  "index": "not_analyzed",    "analyzer": "english" },
                    "position"                  :   {"type": "integer", "index": "not_analyzed" },
                    "marketPrice"               :   {"type": "float",   "index": "not_analyzed" },
                    "marketValue"               :   {"type": "float",   "index": "not_analyzed" },
                    "averageCost"               :   {"type": "float",   "index": "not_analyzed" },
                    "unrealizedPNL"             :   {"type": "float",   "index": "not_analyzed" },
                    "realizedPNL"               :   {"type": "float",   "index": "not_analyzed" },
                    "accountName"               :   {"type": "string",  "index": "not_analyzed" },



                    
                }
            }
        }
    }   
    
    #
    print("creating '%s' index..." % (INDEX_NAME))
    res = es.indices.create(index = INDEX_NAME, body = request_body)
    print(" response: '%s'" % (res))
#%%
def loadIntoEsIndex(portfolio_dic,type_name=TYPE_NAME,index_name = INDEX_NAME,id=None):
    #%%
    ES_HOST = {"host" : "localhost", "port" : 9200}
    INDEX_NAME = index_name
    TYPE_NAME = type_name
    if portfolio_dic == None:
        return

    #

    from elasticsearch import Elasticsearch
    import datetime
    es = Elasticsearch(hosts = [ES_HOST])
    print()
    print ('loadIntoEsIndex starts: %s'% (unicode(datetime.datetime.now())))
    print()
    print ('Portfolio dic received : %s' %(portfolio_dic))
    print()
    try:
        res = es.index(index=INDEX_NAME, doc_type=TYPE_NAME, body=portfolio_dic)
        print("Portfolio position loaded into ES: "%(res['created']))
    except Exception as e:
        print(e)
    
#%%


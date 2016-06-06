# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 14:11:35 2016

@author: thoma
"""
import pyximport; pyximport.install(pyimport = False)
from libdata import loadIntoEsIndex
import datetime
#%%
g1='https://www.google.com/search?hl=en&gl=us&tbm=nws&authuser=0&q=humanitarian+crisis&oq=humanit&gs_l=news-cc.3.6.43j0l10j43i53.412458.420303.0.425823.12.10.2.0.0.0.247.873.9j0j1.10.0...0.0...1ac.1.bKP9cStDlcI'

abc='http://www.abc.net.au/news/world/asia-pacific/'
irin_conflict='http://www.irinnews.org/conflict'
thomson_reuters='http://news.trust.org/'
un_org='http://www.un.org/news/'
al_jazeera='http://www.aljazeera.com/'
reuter="http://www.reuters.com/"
ret="http://www.reuters.com/news/world"
f="http://www.bbc.com/news/world/europe"
g="http://www.bbc.com/news/world/middle_east"
allafrica='http://allafrica.com/'
voa='http://www.voanews.com/section/africa/2204.html'
xina='http://www.xinhuanet.com/english/asiapacific/index.htm'
arabya='http://english.alarabiya.net/'
rfi_en='http://en.rfi.fr/asia-pacific/'
#url = 'http://edition.cnn.com/2012/02/22/world/europe/uk-occupy-london/index.html?hpt=ieu_c2'
#%%

#url=[
#url=[xina,abc,rfi_en,
url=[irin_conflict,un_org,al_jazeera,thomson_reuters,reuter,f,allafrica,voa,]
 

#%%
for u in url:
    try:
        print unicode(datetime.datetime.now())
        print (u)
        loadIntoEsIndex([u])
        print unicode(datetime.datetime.now())
    except Exception as e:
        print(e)
#%%
"""
    ES_HOST = {"host" : "localhost", "port" : 9200}
    INDEX_NAME = 'eestore'
    type_name='news_en'
    TYPE_NAME = type_name
    #
    from elasticsearch import Elasticsearch
    import datetime
    # create ES client, create index
    es = Elasticsearch(hosts = [ES_HOST])
    print unicode(datetime.datetime.now())
    articles=extractWebsiteNews(url)
    print unicode(datetime.datetime.now())
    #
    bulk_data = [] 
"""
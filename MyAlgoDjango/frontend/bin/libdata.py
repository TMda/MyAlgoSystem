# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
from __future__ import absolute_import, division,print_function, unicode_literals
import cython
import gc
#%%
MEMOIZE_WEB_ARTICLE=True
NUMBER_OF_THREAD=15
MINIMUM_VALID_ARTICLE_LENGHT=3 #articlesExtraction minimum number of word for the title of an article to be considered
FETCH_IMAGES=False
BROWSER_USER_AGENT='Mozilla/5.0 (Linux; U; Android 2.3.5; AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
ES_HOST = {"host" : "localhost", "port" : 9200}
INDEX_NAME = 'eestore'
ES_LOADING_BULK=60

DB_PATH='' #SQLITE DB 
print('Libdata xx.PY')
#%%%%

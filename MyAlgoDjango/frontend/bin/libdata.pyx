# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
from __future__ import absolute_import, division,print_function, unicode_literals
import cython
#%%
DEF MEMOIZE_WEB_ARTICLE=False
DEF NUMBER_OF_THREAD=10
DEF MINIMUM_VALID_ARTICLE_LENGHT=3 #articlesExtraction minimum number of word for the title of an article to be considered
DEF FETCH_IMAGES=False
DEF BROWSER_USER_AGENT='Mozilla/5.0 (Linux; U; Android 2.3.5; AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
ES_HOST = {"host" : "localhost", "port" : 9200}
DEF INDEX_NAME = 'eestore'

DB_PATH='' #SQLITE DB 
print('libdata.PYX')
#%%%%
def generateArticleDico(article,news=True):
    #%%
    import requests
    import lxml
    from lxml.html.clean import Cleaner
    from lxml.html.clean import clean_html
    from bs4 import BeautifulSoup
    cleaner = Cleaner()
    cleaner = Cleaner(
    page_structure=True, links=True, javascript = True,style = True,
    kill_tags=['img','noscript','aside','figure','footer','header'],
    remove_tags=['div','i','a','b','nav','hr','br','strong','article','body',
    'p','h1','h2','h3','h4','h5','h6','ul','li','span','label','time','section'],safe_attrs_only=True
    )
    #cleaner.javascript = True # This is True because we want to activate the javascript filter
    #cleaner.style = True      # This is True because we want to activate the styles & stylesheet filter
    #url='http://www.jeuneafrique.com/318633/politique/francois-hollande-arrive-liban-tournee-moyen-orient/'
    #url='https://www.washingtonpost.com/world/pope-francis-arrives-on-lesbos-in-visit-intended-to-prick-europes-conscience/2016/04/16/b0a66c08-fd09-11e5-813a-90ab563f0dde_story.html'

  
    #print(clean_html(url))
    #%%cleaner.kill_tags['img','noscript','a']


    dic_article={
    'publish_date':article.publish_date

    ,'title':article.title
    ,'description':article.meta_description
    
    ,'keyword':article.meta_keywords
    
    ,'meta_lang':article.meta_lang
    
    ,'top_image':    article.top_image
     ,'movies':   article.movies

   
  
    }
    if news==True:
        #Article extracted using News python Library
        
        
        #
        dic_article['url']= article.url
        dic_article['authors']= article.authors
        dic_article['html']=unicode(article.html)
       
        dic_article['text']=unicode(article.text)
        dic_article['nlp_keywords']=article.keywords
        dic_article['summary']=unicode(article.summary)

        soup = BeautifulSoup(article.html,'lxml')
        [s.extract() for s in soup('script')]
        dic_article['pure_html']=unicode(soup)

        clenead=cleaner.clean_html(article.html)
        c=" ".join(clenead.split())    
        dic_article['pure_text']=unicode(c)

        #%
        '''
        ar=BeautifulSoup(article.html ,'lxml')
        meta1= ar.find_all(attrs={"property":"article:published_time"})[0]['content']
        if metat1 not null:
            dic_article['extrapolated_date']=meta1
        else:
            meta1= ar.find_all(attrs={"property":"article:published"})[0]['content']
            if metat1 not null:
                dic_article['extrapolated_date']=meta1
            else:
                meta1= ar.find_all(attrs={"name":"REVISION_DATE"})[0]['content']
                dic_article['extrapolated_date']=meta1
        
        '''
        #dic_article['meta_date']=
        #
        #n='http://www.nytimes.com/2016/04/13/world/americas/canada-vancouver-chinese-immigrant-wealth.html?hp&action=click&pgtype=Homepage&clickSource=story-heading&module=photo-spot-region&region=top-news&WT.nav=top-news&_r=0'
        #n='https://www.irinnews.org/news/2016/03/07/mongolian-livestock-succumb-en-masse-freezing-dzud'
        #ar=BeautifulSoup(requests.get(n).text,'lxml')
        #
        #type(ar)
        #
        #meta= ar.find_all(attrs={"property":"article:published_time"})
        #
        #print(meta[0]['content'])
        ##
    else:#article extarcted with Goose library
        dic_article['text']=unicode(article.cleaned_text)
        dic_article['html']=unicode(article.raw_html)

        clenead=cleaner.clean_html(article.raw_html)
        c=" ".join(clenead.split())    
        dic_article['pure_text']=unicode(c)
        
        soup = BeautifulSoup(article.raw_html,'lxml')
        [s.extract() for s in soup('script')]
        dic_article['pure_html']=unicode(soup)
        
    
    return dic_article

#%%
def articlesExtraction(papers,thread=True):
    import datetime
    
    
    category=[unicode(str(catego).split("/")[-1])
                 for catego 
                     in papers.category_urls()]
    
    #print(category)      #
    #print(len(papers.articles))
            #
    articles= [article 
                   for article 
                       in papers.articles
                           if len(article.title.split())>MINIMUM_VALID_ARTICLE_LENGHT]
    #print(len(articles))
    #print (articles[0].title)
            #articles=[news_article 
             #   for news_article in articles 
              #      if len(news_article.title.split())>3]
            #print(len(articles))  
    if thread==False:
        #article.download()
        [news_article.download() for news_article in articles ]
            #
            #print(downloaded)
            #
    [news_article.parse() for news_article in articles]
            #print(parsed)
            #
    [news_article.nlp() for news_article in articles]
            #
    articles=[generateArticleDico(news_article) 
                   for news_article 
                         in articles]
           #
    
            #
    
    #print(articles[0]['publish_date'])
    #print(articles[0]['authors'])
    #print(articles[0]['title'])
    #print(articles[0]['summary'])
    #print(articles[0]['description'])

    for art in articles:
        if isinstance(art,dict):
            art['category_link']=category
            art['website_brand']=papers.brand
            art['website_description']=papers.description
            art['website_url']=papers.url
            art['timestamp']= datetime.datetime.now()

        else:
            pass
            #print(art)
            #
    #print(art.keys())
    print('Processed Article: %s'%(len(articles)))
    return articles
       
#%%##################
def extractWebsiteNews(url,debug=False):
    import newspaper as ns
    from newspaper import news_pool, Config
    string=False
    listUrl=False
    
    if (isinstance(url,str)):
        string=True
    elif (isinstance(url,list)):
        a=[l for l in url if isinstance(l,str)]
        if len(a)==len(url):
            listUrl=True
        else:
            return 'Error: PLease provide a list of URL [1]'
    else:
        return 'Error: PLease provide one URL or a list of URL [2]'
    
    config = Config()
        
    config.memoize_articles=MEMOIZE_WEB_ARTICLE
    config.browser_user_agent =BROWSER_USER_AGENT
    config.fetch_images=FETCH_IMAGES

    if string:
        papers=ns.build(url,config)
        if debug:
            print('Only One URL provided')
        return articlesExtraction(papers,thread=False)
        
        
    if listUrl:
       #
        article_news=[]
        site=url
        #site=['http://www.un.org/news/','http://www.aljazeera.com/']#'http://www.irinnews.org/conflict','http://news.trust.org/','http://www.un.org/news/','http://www.aljazeera.com/']
        print(site)
        #
        newsite_papers=[ns.build(news_paper,memoize_articles=MEMOIZE_WEB_ARTICLE,fetch_images=FETCH_IMAGES,browser_user_agent=BROWSER_USER_AGENT,request_timeout=9) 
                            for news_paper 
                                in site]
        #print('newspaper Built')
        #
        news_pool.set(newsite_papers, threads_per_source=NUMBER_OF_THREAD) # (3*2) = 6 threads total
        news_pool.join() 
        #
        for papers in newsite_papers:
            print(papers.brand)
            #print(papers.category_urls())
            #print(papers.articles)
            articles=articlesExtraction(papers)
            article_news.extend(articles)
        return article_news

#%%
def createEsIndex(type_name='news_en',delete=False):
    ES_HOST = {"host" : "localhost", "port" : 9200}
    #INDEX_NAME = 'eestore'
    #type_name='news_en'
    TYPE_NAME =type_name
    #
    from elasticsearch import Elasticsearch
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
            "news_en": {
                #"include_in_all": false,
                #"_id": {
                #    "path": "doc_id"
                #    },
                #"_source": {
                #    "enabled": false
                #},
                "properties": {
                    "title":            {"type":"string","index":"analyzed","analyzer": "english"},
                     "authors":         {"type":"string","index":"analyzed","analyzer": "english" },
                    "nlp_keywords":     {"type":"string","index":"not_analyzed"      ,"analyzer": "english" },
                    "publish_date":     {"type":"string", "index": "analyzed","analyzer": "english" },
                    "meta_lang":        {"type":"string","index":"not_analyzed","analyzer": "english" },
 
                    "website_brand":    {"type": "string","index":"analyzed"   ,"analyzer": "english" },
                    "website_description":    {"type":"string","index": "analyzed"   ,"analyzer": "english" },
    
                    "description":      {"type": "string","index": "analyzed"   ,"analyzer": "english" },
                    "keyword":          {"type": "string","index": "not_analyzed","analyzer": "english" },
                    "summary":          {"type": "string","index": "analyzed"   ,"analyzer": "english" },
                    "url":              {"type": "string","index": "not_analyzed"         ,"analyzer": "english" },
                    "category_link":    {"type": "string","index": "not_analyzed","analyzer": "english" },
                    "text":             {"type": "string","index": "analyzed"   ,"analyzer": "english" },
                    "timestamp":        {"type": "date", "index": "not_analyzed"           },
                    "pure_text":        {"type": "string","index": "analyzed"   ,"analyzer": "english" },



                    "movies":           {"type": "string","index": "no"         ,"analyzer": "english","include_in_all": 0},
                    "html":             {"type": "string","index": "analyzed","analyzer": "english","include_in_all": 0},
                    "top_image":        {"type": "string","index": "no",        "analyzer": "english", "include_in_all": 0},
                    "pure_html":        {"type": "binary","index": "no" ,        "include_in_all": 0},
                 
                }
            }
        }
    }   
    
    #
    print("creating '%s' index..." % (INDEX_NAME))
    res = es.indices.create(index = INDEX_NAME, body = request_body)
    print(" response: '%s'" % (res))

#%%
def loadIntoEsIndex(url,type_name='news_en'):
    #%%
    ES_HOST = {"host" : "localhost", "port" : 9200}
    #INDEX_NAME = 'eestore'
    #type_name='news_en'
    TYPE_NAME = type_name
    #
    from elasticsearch import Elasticsearch
    import datetime
    # create ES client, create index
    es = Elasticsearch(hosts = [ES_HOST])
    print (unicode(datetime.datetime.now()))
    articles=extractWebsiteNews(url)
    print ('Articles extracted : %s' %(len(articles)))
    #
    bulk_data = [] 
    #%%
    ## Read document ID
    for news in articles:# for every article
        
        op_dict = {
        "index": {
            "_index": INDEX_NAME, 
            "_type": TYPE_NAME, 
           # "_id": data_dict[ID_FIELD]
        } #Meta data dictionary for the row, only the id varrying wih each row
    }
        bulk_data.append(op_dict)
        bulk_data.append(news)
    #%%
    count=len(bulk_data)
    print ('formatted record for ES x 2 %s' %(count))
    #%%
    if len(bulk_data) >500:
        #
        #i=(count/500)+1
        rema=count%500
        i=((count-rema)/500)+1
        bulk=[]
        #
        print(i)
        print(len(bulk_data))
        print(rema)
        #
        a=0
        b=500
        for h in range(int(i)):
            #print(h)
            
            if h!=i:
                #print ('%s:%s' % (a,b))
                bulk.append(bulk_data[a:b])
                #print(bulk_data[h])
                #print(len(bulk_data[a:b]))
                a=b
                b=b+500
            else:
                #print ('%s:%s' % (b,b+rema))
                bulk.append(bulk_data[b:b+rema])
                #print(len(bulk_data[b:b+rema]))
    else:
        bulk=[bulk_data]
        rema=0
        #%%
#
    print(len(bulk))
    print("bulk indexing...")
    print(INDEX_NAME)
    
    res = es.search(index = INDEX_NAME, size=1, body={"query": {"match_all": {}}})
    print("%d initial documents number before Indexing" % res['hits']['total']) 
    ai=res['hits']['total']
    #print(len(bulk))
    print(rema)
    #%%
    print(len(bulk))
    
    for lot in bulk:
        res = es.bulk(index = INDEX_NAME, body = lot, refresh = True)
        #print(res)
        #Sanity check
        res = es.search(index = INDEX_NAME, size=1, body={"query": {"match_all": {}}})
        #print(" response: '%s'" % (res))
        bi=res['hits']['total']
        print("%s Loaded documents " % str(bi-ai)) 
        print("%s Total documents found" % (bi)) 
        ai=bi
#%%
def format_results(results):
    """Print results nicely:
    doc_id) content
    """
    data = [doc for doc in results['hits']['hits']]
    for doc in data:
        print("%s) %s" % (doc['_id'], doc['_source']['content']))
#%%
def validate_date(date_text):
    import datetime
    try:
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
        return True
    except ValueError:
        #raise ValueError("Incorrect data format, should be YYYY-MM-DD")
        return False


#%%
def searchEs(term=None,date_start=None,date_end=None,type_name='news_en',search_size=100):
    from datetime import date, timedelta
    from elasticsearch import Elasticsearch
    import requests
    #import json
    
    TYPE_NAME = type_name
    #
    if  date_start != None and date_end != None:
        if validate_date(date_start) and validate_date(date_end) :
            pass
        else:
            return "Error date must be in the format 'Y-M-D' ex: 2016-04-02"
    elif date_start == None and date_end == None:
        today=date.today()
        yesterday =today  - timedelta(1)
        date_start=yesterday
        date_end=today
    elif date_start != None:
        if validate_date(date_start):
            date_end=date.today() + timedelta(1)
        else:
            return "Error start date must be in the format 'Y-M-D' ex: 2016-04-02"
    elif date_end != None:
        if validate_date(date_end):
            date_start=date.today()- timedelta(100)
        else:
            return "Error end date must be in the format 'Y-M-D' ex: 2016-04-02"
    else:
        return "Error date range must be in the format 'Y-M-D' ex: 2016-04-02"
    #connect to our cluster
    es = Elasticsearch(hosts = [ES_HOST])
    #res = requests.get('http://localhost:9200')
    print(es)
    #
    """Simple Elasticsearch Query
    today=date.today()
    yesterday =today  - timedelta(1)
    term='tajikistan'
 
    date_start=yesterday
    date_end=today
    """
    #
    if term==None :
           #     
        query={
                "from" : 0, "size" : search_size,
                "query": {
                    "match_all": {}
                }
            }
    else:
        #
        query = {
            "from" : 0, "size" : search_size,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "and": [
                            {
                                "range" : {
                                    "timestamp" : { "from" : date_start,"to" : date_end }
                                },
                            },
                            {
                                "term": {
                                    "text": term
                                }
                            }
                        ]
                    }
                }
            }
        }    
#
    """
    queryLazzy={
        "query": {
            "fuzzy_like_this_field" : { 
                "text" : {
                    "like_text": term, "max_query_terms":100
                        }
                        }
                }
        }
    """
       #
    #print(query)
    #es.search(index=TYPE_NAME, body={"query": {"match": {'name':'Darth Vader'}}})
    results=es.search(index=INDEX_NAME, body=query )
    
    #response = requests.get(ES_HOST, data=req_all)
    #results = json.loads(response.text)
    print("%d documents found" % results['hits']['total'])
    #for doc in results['hits']['hits']:
#        print("- %s" % (doc['_source']['title']).encode('utf8'))
    #
    return [res for res in results['hits']['hits']]
#%%%

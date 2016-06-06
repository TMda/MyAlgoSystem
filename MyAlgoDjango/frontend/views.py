from django.shortcuts import render
from django.http import HttpResponse
import datetime as dt
from django.contrib import messages
from django.shortcuts import render
#%% Create your views here.
from django.http import HttpResponse,HttpRequest, HttpResponseRedirect
from django.views.generic import View,ListView,CreateView,UpdateView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
#%% Create your views here.
from django.core.urlresolvers import reverse
import frontend.bin.libdata 
import pandas as pd
#%% Create your views here.

def processLogin(request):
    username = request.POST['username']
    password = request.POST['password']
    try:
        user = authenticate(username=username, password=password)
        request.session['logged']=True
    except Exception as e:
        messages.add_message(request, messages.INFO, "Login Incorrect mauvaise combinaison user name/password, reessayz ou contacter service client")
        return HttpResponseRedirect('login')

    if user is not None:
        if user.is_active:
            login(request, user)
            return HttpResponseRedirect('index')
            # Redirect to a success page.
        else:
            messages.add_message(request, messages.INFO, "Votre accompte est dessactiver contacter service Client")
            return  HttpResponseRedirect('login')
        
        
 
    else:
        messages.add_message(request, messages.INFO, "Login Incorrect mauvaise combinaison user name/password, reessayz ou contacter service client")
        return HttpResponseRedirect('login')


        
def logout_view(request):
    logout(request)
    return HttpResponseRedirect('index')
# Redirect to a success page.


def index(request):
    dir_Output='C:\\Users\\thoma\\OneDrive\\Git repo\\MyAlgoSystem\\output\\'
    #Getting Active order and turning it into a list
     
    f               =   open(dir_Output+"cash","r")
    cash            =   f.read()
    f.close()
    active_positions     =   pd.DataFrame.from_csv(dir_Output+"ActivePositions.csv").to_dict('records')
    positions_history    =   pd.DataFrame.from_csv(dir_Output+"PositionsHistory.csv").to_dict('records')
    active_orders        =   pd.DataFrame.from_csv(dir_Output+"ActiveOrders.csv").to_dict('records')
    filled_orders        =   pd.DataFrame.from_csv(dir_Output+"FilledOrders.csv").to_dict('records')
    order_history       =    pd.DataFrame.from_csv(dir_Output+"OrdersHistory.csv").to_dict('records')
    initial_orders      =    pd.DataFrame.from_csv(dir_Output+"InitialOrders.csv").to_dict('records')
    
    context = {'title'             : 'MyAlgo Front End',
                'active_positions'  :   active_positions,
                'cash'              :   cash,
                'positions_history' :   positions_history,
                'active_orders'     :   active_orders,
                'filled_orders'     :   filled_orders,
                'order_history'     :   order_history,
                'initial_orders'    :   initial_orders,
                
               'message':''}
               
      
    return render(request, 'frontend/index.html', context)   
    

def user_list(request):
    return HttpResponse("Hello, world. You're at user_list.")
    
def info_frontend(request):
    context = {'title': 'Info info_frontend',
               'message':''}
    return render(request, 'frontend/info_frontend.html', context)
    
def contact(request):
    context = {'title': 'Nous Contacter',
               'message':''}
    return render(request, 'frontend/contact.html', context)  

def tariff(request): 

    context = {'title': 'Tariff et Services',
               'message':''}
    return render(request, 'frontend/tariff.html', context)  

def opscen(request):
    context = {'title': 'OPSCEN',
               'message':''}
    return render(request, 'frontend/opscen.html', context)

def horizon_scanning(request):
    context = {'title': 'Horizon Scanning',
               'message':''}
    return render(request, 'frontend/horizon_scanning.html', context)

def search(request):
    #%%
    def dico(news):
        dic={
        'title':news['_source']['title'],
        'description':news['_source']['description'],
        'summary':news['_source']['summary'],
        'website_brand':news['_source']['website_brand'],
        'timestamp':news['_source']['timestamp'],
        'url':news['_source']['url'],
        #'highlight':news['highlight']
        #'website_description':news['_source']['website_description'],
        }
        return dic
    #%%
    try:
        print ("IM in SEARCH")
        if 'search_text' in request.GET:
            term=request.GET['search_text']
            #print(term,'1')
            if term =='':
                term=None
        else:
            term=None
        print('Search Term: %s' %(term))
        
        if 'date_start' in request.GET:
            date_start=request.GET['date_start']
            
        else:
            date_start=None
            
        print('Date start: %s' %(date_start))
        
        if 'date_end' in request.GET:
            date_end=request.GET['date_end']
            #print(date_end,'3')
        else:
            date_end=None
        print('Date end: %s' %(date_end))
        
            #%%
        type_name='news_en' 
        print ("Fetching data in ES")
        result=searchEs(term)
    #%%
        print ("Data collected from ES")
        article_search_results=[dico(news) for news in result]
        print('article search reported: %s' %(len(article_search_results)))
        
        messages.add_message(request, messages.INFO, "%s results found..." %(len(article_search_results)))
        #print("Message added")   
        context = {'title': 'OPSCEN','article_search_results':article_search_results,
               'message':''}
              
        #print("Launching rendering request")    
        return render(request, 'frontend/opscen.html', context)
       
    except UnicodeEncodeError as e:
        print (e)
        messages.add_message(request, messages.INFO, "%s results found..." %(len(article_search_results)))
            
        context = {'title': 'OPSCEN','article_search_results':article_search_results,
               'message':''}
        #print("Launching rendering request")    
        return render(request, 'frontend/opscen.html', context)
  
        
    except Exception as e:
        print (e)
        #print ("IM in SEARCh Exception: %s" % (type(e)))
        # Redisplay the question voting form.
        messages.add_message(request, messages.INFO, "empty search string...")
        return HttpResponseRedirect('opscen')
        

      
        

    #%%
def horizon_process(request):
    #%%
    try:
        #print ("IM in SEARCh")
        if 'search_text' in request.GET:
            term=request.GET['search_text']
            #print(term,'1')
            if term =='':
                term=None
        else:
            term=None
        #print(' IF date_start')
        
        if 'date_start' in request.GET:
            date_start=request.GET['date_start']
            
        else:
            date_start=None
        #print(' IF date_end')   
        if 'date_end' in request.GET:
            date_end=request.GET['date_end']
            #print(date_end,'3')
        else:
            date_end=None
        
            #%%
        type_name='news_en' 
        #print ("Fetching data in ES")
        result=horizon_scan(term)
    #%% TO DO    
    #%%###########################################################
        #print ("Data collected from ES")
        article_search_results=[dico(news) for news in result]
        #print('article search reported: %s' %(len(article_search_results)))
        
        messages.add_message(request, messages.INFO, "%s results found..." %(len(article_search_results)))
        #print("Message added")   
        context = {'title': 'horizon_scanning','article_search_results':article_search_results,
               'message':''}
              
        #print("Launching rendering request")    
        return render(request, 'frontend/horizon_scanning.html', context)
       
    except UnicodeEncodeError as e:
        #print (e)
        messages.add_message(request, messages.INFO, "%s results found..." %(len(article_search_results)))
            
        context = {'title': 'horizon_scanning','article_search_results':article_search_results,
               'message':''}
        #print("Launching rendering request")    
        return render(request, 'frontend/horizon_scanning.html', context)
  
        
    except Exception as e:
        #print (e)
        #print ("IM in SEARCh Exception: %s" % (type(e)))
        # Redisplay the question voting form.
        messages.add_message(request, messages.INFO, "empty search string...")
        return HttpResponseRedirect('horizon_scanning')
    #%%
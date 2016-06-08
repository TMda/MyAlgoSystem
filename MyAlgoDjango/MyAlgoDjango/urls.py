"""eengineDjango URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from frontend import views
from frontend.forms import BootstrapAuthenticationForm
import datetime
urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', views.index, name='index'),    
    url(r'^opscen', views.opscen, name='opscen'), 
    url(r'^user_list', views.user_list, name='user_list'), 

    url(r'^contact', views.contact, name='contact'), 
    url(r'^logout', views.logout, name='logout'), 
    url(r'^search', views.search, name='search'), 
    
    url(r'^cancel_order'    ,   views.cancel_order,     name='cancel_order'), 
    url(r'^close_position'  ,   views.close_position,   name='close_position'), 
    url(r'^get_trading_data',   views.get_trading_data, name='get_trading_data'), 

    url(r'^horizon_scanning', views.horizon_scanning, name='horizon_scanning'), 
    url(r'^processLogin', views.processLogin, name='processLogin'),  
    url(r'^login',
        'django.contrib.auth.views.login',
        {
            'template_name': 'frontend/login.html',
            'authentication_form': BootstrapAuthenticationForm,
            'extra_context':
            {
                'title':'Log in',
                'year':datetime.datetime.now().year,
            }
        },
    name='login'),     
]

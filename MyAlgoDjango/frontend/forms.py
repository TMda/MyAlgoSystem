# -*- coding: utf-8 -*-
"""
Created on Sun Feb 22 07:45:18 2015

@author: TM
"""

from django import forms
from django.core.exceptions import ValidationError
 
"""
Definition of forms.
"""

from django import forms
from django.forms import ModelForm, Form
 
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import ugettext_lazy as _


class BootstrapAuthenticationForm(AuthenticationForm):
    """Authentication form which uses boostrap CSS."""
    username = forms.CharField(max_length=254,
                               widget=forms.TextInput({
                                   'class': 'form-control',
                                   'placeholder': 'User name'}))
    password = forms.CharField(label=_("Password"),
                               widget=forms.PasswordInput({
                                   'class': 'form-control',
                                   'placeholder':'Password'}))
    
    

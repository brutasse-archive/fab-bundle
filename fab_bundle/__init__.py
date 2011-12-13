# -*- coding: utf-8 -*-
__title__ = u'fab_bundle'
__version__ = u'0.1'
__author__ = u'Bruno Renié'


from fabric.api import env, task
from .bundle import deploy, destroy
from .provisioning import bootstrap
from .utils import ssh

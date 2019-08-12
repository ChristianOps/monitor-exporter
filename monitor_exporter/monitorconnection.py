# -*- coding: utf-8 -*-
"""
    Copyright (C) 2019  Opsdis AB

    This file is part of monitor-exporter.

    monitor-exporter is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    monitor-exporter is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with monitor-exporter.  If not, see <http://www.gnu.org/licenses/>.

"""

import requests
import json
from requests.auth import HTTPBasicAuth
import monitor_exporter.log as log


class Singleton(type):
    """
    Provide singleton pattern to MonitorConfig. A new instance is only created if:
     - instance do not exists
     - config is provide in constructor call, __init__
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances or args:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class MonitorConfig(object, metaclass=Singleton):

    def __init__(self, config=None):
        """
        The constructor takes on single argument that is a config dict
        :param config:
        """
        self.user = ''
        self.passwd = ''
        self.host = ''
        self.headers = {'content-type': 'application/json'}
        self.verify = False
        self.retries = 5
        self.prefix = ''
        self.labels = []
        self.url_query_service_perfdata = ''

        if config:
            self.user = config['op5monitor']['user']
            self.passwd = config['op5monitor']['passwd']
            self.host = config['op5monitor']['host']
            self.prefix = config['op5monitor']['metric_prefix'] + '_'
            self.labels = config['op5monitor']['custom_vars']
            self.url_query_service_perfdata = 'https://' + self.host + \
                                              '/api/filter/query?query=[services]%20host.name="{}' \
                                              '"&columns=host.name,description,perf_data,check_command'
            self.url_get_host_custom_vars = 'https://' + self.host + \
                                            '/api/filter/query?query=[hosts]%20display_name="{}' \
                                            '"&columns=custom_variables'

    def get_user(self):
        return self.user

    def get_passwd(self):
        return self.passwd

    def get_header(self):
        return self.headers

    def get_verify(self):
        return self.verify

    def get_host(self):
        return self.host

    def number_of_retries(self):
        return self.retries

    def get_prefix(self):
        return self.prefix

    def get_labels(self):
        labeldict = {}

        for label in self.labels:
            for custom_var, value in label.items():
                for key, prom_label in value.items():
                    labeldict.update({custom_var: prom_label})
        return labeldict

    def get_perfdata(self, hostname):
        # Get performance data from Monitor and return in json format
        data_from_monitor, data_json = self.get(self.url_query_service_perfdata.format(hostname))

        if len(data_from_monitor.content) < 3:
            log.warn('Received no perfdata from Monitor')

        return data_json

    def get_custom_vars(self, hostname):
        # Build new URL and get custom_vars from Monitor

        data_from_monitor, custom_vars_json = self.get(self.url_get_host_custom_vars.format(hostname))

        custom_vars = {}
        for var in custom_vars_json:
            custom_vars = var['custom_variables']

        return custom_vars

    def get(self, url):
        data_from_monitor = requests.get(url, auth=HTTPBasicAuth(self.user, self.passwd),
                                         verify=False, headers={'Content-Type': 'application/json'})
        data_json = json.loads(data_from_monitor.content)
        log.debug('API call: ' + data_from_monitor.url)
        if data_from_monitor.status_code != 200:
            log.info("Response", {'status': data_from_monitor.status_code, 'error': data_json['error'],
                                  'full_error': data_json['full_error']})
        else:

            log.info("call api {}".format(url), {'status': data_from_monitor.status_code,
                                                 'response_time': data_from_monitor.elapsed.total_seconds()})

        return data_from_monitor, data_json

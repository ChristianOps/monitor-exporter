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
import aiohttp
import requests
import json
import redis
import time
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
    config_entry = 'op5monitor'
    # high number so all services is fetched
    default_limit = '10000'

    def __init__(self, config=None):
        """
        The constructor takes on single argument that is a config dict
        :param config:
        """
        self.is_cache = False if config.get('cache') is None else True
        if self.is_cache:
            self.redis_host = 'localhost' if config.get('cache').get('redis').get('host') is None else config.get(
                'cache').get('redis').get('host')
            self.redis_port = '6379' if config.get('cache').get('redis').get('port') is None else config.get(
                'cache').get('redis').get('port')
            self.redis_db = '0' if config.get('cache').get('redis').get('db') is None else config.get(
                'cache').get('redis').get('db')
            self.redis_auth = None if config.get('cache').get('redis').get('auth') is None else config.get(
                'cache').get('redis').get('auth')

        self.user = ''
        self.passwd = ''
        self.host = ''
        self.headers = {'content-type': 'application/json'}
        self.verify = False
        self.retries = 5
        self.timeout = 5
        self.prefix = ''
        self.labels = []
        self.url_query_service_perfdata = ''
        self.perfname_to_label = []

        if config:
            self.user = config[MonitorConfig.config_entry]['user']
            self.passwd = config[MonitorConfig.config_entry]['passwd']
            self.host = config[MonitorConfig.config_entry]['url']
            if 'metric_prefix' in config[MonitorConfig.config_entry]:
                self.prefix = config['op5monitor']['metric_prefix'] + '_'
            if 'host_custom_vars' in config[MonitorConfig.config_entry]:
                self.labels = config['op5monitor']['host_custom_vars']
            if 'perfnametolabel' in config[MonitorConfig.config_entry]:
                self.perfname_to_label = config[MonitorConfig.config_entry]['perfnametolabel']
            if 'timeout' in config[MonitorConfig.config_entry]:
                self.timeout = int(config[MonitorConfig.config_entry]['timeout'])

            self.url_query_service_perfdata = self.host + \
                                              '/api/filter/query?query=[services]%20host.name="{}' \
                                              '"&columns=host.name,description,perf_data,check_command' \
                                              '&limit=' + self.default_limit
            self.url_get_host_custom_vars = self.host + \
                                            '/api/filter/query?query=[hosts]%20display_name="{}' \
                                            '"&columns=custom_variables'

            self.url_query_all_service_perfdata = self.host + \
                                                  '/api/filter/{}?query=[services]%20all' \
                                                  '&columns=host.name,description,perf_data,check_command'

            self.url_query_all_host_custom_vars = self.host + \
                                                  '/api/filter/{}?query=[hosts]%20all' \
                                                  '&columns=name,custom_variables'

    def get_user(self):
        return self.user

    def get_passwd(self):
        return self.passwd

    def get_header(self):
        return self.headers

    def get_verify(self):
        return self.verify

    def get_url(self):
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

    def get_perfname_to_label(self):
        return self.perfname_to_label

    async def get_perfdata(self, hostname):
        # Get performance data from Monitor and return in dict format
        if self.is_cache:
            data_json = await self.get_cache_service_perfdata(hostname)
        else:
            data_json = await self.get(self.url_query_service_perfdata.format(hostname))

        if not data_json:
            log.warn('Received no perfdata from Monitor')

        return data_json

    async def get_custom_vars(self, hostname):
        # Build new URL and get custom_vars from Monitor
        if self.is_cache:
            custom_vars_json = await self.get_cache_host_custom_vars(hostname)
        else:
            custom_vars_json = await self.get(
                self.url_get_host_custom_vars.format(hostname))  # self.get_host_custom_vars(hostname)

        custom_vars = {}
        for var in custom_vars_json:
            custom_vars = var['custom_variables']

        return custom_vars

    #    async def get_host_custom_vars(self, hostname):
    #        custom_vars_json = await self.get(self.url_get_host_custom_vars.format(hostname))
    #        return custom_vars_json

    def get_old(self, url):
        data_json = {}

        try:
            data_from_monitor = requests.get(url, auth=HTTPBasicAuth(self.user, self.passwd),
                                             verify=False, headers={'Content-Type': 'application/json'},
                                             timeout=self.timeout)
            data_from_monitor.raise_for_status()

            log.debug('API call: ' + data_from_monitor.url)
            if data_from_monitor.status_code != 200:
                log.info("Response", {'status': data_from_monitor.status_code, 'error': data_json['error'],
                                      'full_error': data_json['full_error']})
            else:
                data_json = json.loads(data_from_monitor.content)
                log.info("call api {}".format(url), {'status': data_from_monitor.status_code,
                                                     'response_time': data_from_monitor.elapsed.total_seconds()})
        except requests.exceptions.RequestException as err:
            log.error("{}".format(str(err)))

        return data_json

    async def get(self, url):

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=aiohttp.BasicAuth(self.user, self.passwd),
                                       verify_ssl=False,
                                       headers={'Content-Type': 'application/json'}) as response:
                    re = await response.text()
                    return json.loads(re)
        finally:
            pass

    async def get_cache_service_perfdata(self, hostname):
        r = self.get_cache_connection()

        data = r.get(hostname + ':services')
        if data:
            return json.loads(data)
        else:
            return []

    async def get_cache_host_custom_vars(self, hostname):
        r = self.get_cache_connection()

        data = r.get(hostname + ':customvars')
        if data:
            return [json.loads(data)]
        else:
            return [{'custom_variables': {}}]

    def collect_cache(self, ttl: int):

        count_services = self.get_old(self.url_query_all_service_perfdata.format('count'))
        start_time = time.time()
        count = 0
        hosts_to_services = {}
        if 'count' in count_services:
            count = count_services['count']
            services_flat = self.get_old(self.url_query_all_service_perfdata.format('query') + '&limit=' + str(count))
            for service_item in services_flat:
                if service_item['host']['name'] not in hosts_to_services:
                    hosts_to_services[service_item['host']['name']] = []
                host_name = service_item['host']['name']
                # del service_item['host']
                hosts_to_services[host_name].append(service_item)

        count_hosts = self.get_old(self.url_query_all_host_custom_vars.format('count'))
        if 'count' in count_hosts:
            count = count_hosts['count']
            hosts = self.get_old(self.url_query_all_host_custom_vars.format('query') + '&limit=' + str(count))

        start_redis_time = time.time()
        r = self.get_cache_connection()
        p = r.pipeline()
        for host in hosts:
            host_name = host['name']
            del host['name']
            p.set(host_name + ":customvars", json.dumps(host))  # host['custom_variables']))
            p.expire(host_name + ":customvars", ttl)
        p.execute()

        p = r.pipeline()
        for host, service in hosts_to_services.items():
            p.set(host + ':services', json.dumps(service))
            p.expire(host + ':services', ttl)
        p.execute()
        end_time = time.time()
        log.info(
            f"Monitor collector exec time total {(end_time - start_time)} redis write {len(services_flat) + len(hosts)} objects in {end_time - start_redis_time}")

    def get_cache_connection(self):
        return redis.Redis(host=self.redis_host,port=self.redis_port, db=self.redis_db, password=self.redis_auth)

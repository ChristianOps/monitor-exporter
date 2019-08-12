monitor-exporter
-----------------------

# Overview 

The monitor-exporter utilize OP5 Monitors API to fetch service based performance data and publish it in a way that lets prometheus scrape the 
performance data as metrics.

Benefits:

- Enable advanced queries and aggregation on timeseries
- Promethues based alerting rules 
- Grafana graphing
- Utilize investments with OP5 Monitor of collecting metrics 

This solution is a perfect gateway for any OP5 Monitor users that likes to start using Prometheus and Grafana.

# Metrics naming
## Metric names
Metrics that is scraped with the monitor-exporter will have the following name structure:
 
    monitor_<check_command>_<perfname>_<unit>

> Unit is only added if it exists on perfromance data

Example from check command `check_ping` will result in two metrics: 
    
    monitor_check_ping_rta_seconds
    monitor_check_ping_pl_ratio
## Metric labels
The monitor-exporter adds a number of labels to each metrics: 

- host - is the `host_name` in Monitor
- service - is the `service_description` in Monitor

Optional mointor-exporter can be configured to add specific custom variables configured on the host. 

> Labels created from custom variables are all transformed to lowercase. 


# Configuration
## monitor-exporter
All configuration is made in the config.yml file.

Example:
```yaml

# Port can be overridden by using -p if running development flask
# This is the default port assigned at https://github.com/prometheus/prometheus/wiki/Default-port-allocations
#port: 9628

op5monitor:
  # The url to the Monitor server
  url: https://monitor.aw.oc-testbench.xyz
  user: monitor
  passwd: monitor
  metric_prefix: monitor
  # Example of custom vars that should be added as labels and how to be translated
  custom_vars:
    # Specify which custom_vars to extract from Monitor
    - env:
        # Name of the label in Prometheus
        label_name: environment
    - site:
        label_name: dc

logger:
  # Path and name for the log file. If not set send to stdout
  logfile: /var/tmp/monitor-exporter.log
  # Log level
  level: INFO

```

> When running with gunicorn the port is selected by gunicorn

# Logging
The log stream is configure in the above config. If `logfile` is not set the logs will go to stdout.

Logs are formatted as json so its easy to store logs in log servers like Loki and Elasticsearch. 

# Prometheus configuration
Prometheus can be used with static configuration or with dynamic file discovery using the project [monitor-promdiscovery](https://bitbucket.org/opsdis/monitor-promdiscovery)

Please add the the job to the scrape_configs in prometheus.yml.

> The target is the `host_name` configured in Monitor.

## Static config
```yaml

scrape_configs:
  - job_name: 'op5monitor'
    metrics_path: /metrics
    static_configs:
      - targets:
        - monitor
        - google.se
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9628

```

## File discovery config for usage with `monitor-promdiscovery`

```yaml

scrape_configs:
  - job_name: 'op5monitor'
    scrape_interval: 1m
    metrics_path: /metrics
    file_sd_configs:
    - files:
      - 'sd/monitor_sd.yml'
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9628

```


# Running
## Development with flask built in webserver 

    python -m  monitor_exporter -f config.yml

The switch -p enable setting of the port.
    
## Production with gunicorn 
Running with default config.yml. The default location is current directory

    gunicorn --access-logfile /dev/null -w 4 "wsgi:create_app()"
    
Set the path to the configuration file.

    gunicorn --access-logfile /dev/null -w 4 "wsgi:create_app('/etc/monitor-exporter/config.yml')" 

> Port for gunicorn is default 8000, but can be set with -b, e.g. `-b localhost:9628`

## Test the connection 

Check if exporter is working. 

    curl -s http://localhost:9628/health

Get metrics for a host where target is a host, `host_name` that exists in Monitor

    curl -s http://localhost:9628/metrics?target=google.se

# System requierments
Python 3

For required packages please review `requierments.txt` 

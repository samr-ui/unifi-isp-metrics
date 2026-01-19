1. git clone git@github.com:samr-ui/unifi-isp-metrics.git
2. cd unifi-isp-metrics/
3. python3 -m venv .venv
4. source .venv/bin/activate
5. pip install -r requirements.txt
6. python3 unifi_isp_metrics.py --api-key API_KEY --metric-type 1h --hours-back 720
7. python3 generate_charts.py --metrics isp_metrics.json --sites sites.json
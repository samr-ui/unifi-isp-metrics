git clone git@github.com:samr-ui/unifi-isp-metrics.git
cd unifi-isp-metrics/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 unifi_isp_metrics.py --api-key API_KEY --metric-type 1h --hours-back 720
python3 generate_charts.py --metrics isp_metrics.json --sites sites.json
#!/usr/bin/env python3
"""
UniFi ISP Metrics - HTML Chart Generator

This script reads the ISP metrics JSON file and generates an interactive
HTML dashboard with charts for visualization.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path


def generate_html_dashboard(metrics_file: str, sites_file: str, output_file: str, verbose: bool = False) -> None:
    """
    Generate an HTML dashboard with charts from ISP metrics data
    
    Args:
        metrics_file: Path to the ISP metrics JSON file
        sites_file: Path to the sites JSON file
        output_file: Path to output HTML file
        verbose: Enable verbose debug output
    """
    # Load metrics data
    with open(metrics_file, 'r') as f:
        metrics_data = json.load(f)
    
    if verbose:
        print(f"Loaded metrics file: {metrics_file}")
        print(f"Top-level keys: {list(metrics_data.keys())}")
    
    # Load sites data
    sites_data = {}
    if Path(sites_file).exists():
        with open(sites_file, 'r') as f:
            sites_json = json.load(f)
            # Create a lookup dict of site_id -> site_name
            for site in sites_json.get('sites', []):
                site_id = site.get('siteId')
                site_name = site.get('meta', {}).get('name', 'Unknown')
                if site_id:
                    sites_data[site_id] = site_name
        if verbose:
            print(f"Loaded {len(sites_data)} site names from {sites_file}")
    else:
        print(f"Warning: Sites file not found: {sites_file}")
    
    # Extract metrics info
    response = metrics_data.get('response', {})
    data = response.get('data', {})
    metrics = data.get('metrics', [])
    
    if verbose:
        print(f"Found {len(metrics)} sites with metrics")
    
    if not metrics:
        print("ERROR: No metrics found in JSON file!")
        print("Please run inspect_metrics.py to diagnose the issue.")
        return
    
    # Prepare data for charts
    chart_data = prepare_chart_data(metrics, sites_data, verbose)
    
    if verbose:
        print(f"\nChart data summary:")
        print(f"  Sites: {chart_data['sites']}")
        print(f"  Timestamps: {len(chart_data['timestamps'])}")
        for site in chart_data['sites']:
            print(f"  {site}:")
            print(f"    Latency values: {len(chart_data['latency'][site])} (sample: {chart_data['latency'][site][:3]})")
            print(f"    Download values: {len(chart_data['download'][site])} (sample: {chart_data['download'][site][:3]})")
    
    # Generate HTML
    html_content = generate_html_template(chart_data, metrics_data)
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"HTML dashboard generated: {output_file}")


def prepare_chart_data(metrics: list, sites_data: dict, verbose: bool = False) -> dict:
    """Prepare data structure for charts"""
    
    chart_data = {
        'sites': [],
        'timestamps': [],
        'latency': {},
        'download': {},
        'upload': {},
        'packet_loss': {},
        'uptime': {}
    }
    
    # Debug: print first metric to see structure
    if verbose and metrics:
        print(f"\nDEBUG: Processing {len(metrics)} site metrics")
        print(f"  First metric structure:")
        print(f"  Keys: {list(metrics[0].keys())}")
        if 'periods' in metrics[0] and metrics[0]['periods']:
            print(f"  First period keys: {list(metrics[0]['periods'][0].keys())}")
            if 'data' in metrics[0]['periods'][0]:
                print(f"  Data structure: {metrics[0]['periods'][0]['data'].keys()}")
    
    # First pass: collect all unique timestamps and sites
    all_timestamps = set()
    site_id_to_name = {}  # Track the mapping
    name_counts = {}  # Track duplicate names
    
    if verbose:
        print(f"\nDEBUG: First pass - collecting sites and timestamps")
        print(f"  sites_data lookup has {len(sites_data)} entries")
    
    for idx, site_metric in enumerate(metrics):
        site_id = site_metric.get('siteId', 'Unknown')
        site_name = sites_data.get(site_id, None)
        
        # If name not found in sites_data, use a truncated site_id as the name
        if site_name is None:
            site_name = f"Site-{site_id[:8]}"
        
        # Handle duplicate names by appending site_id suffix
        if site_name in name_counts:
            name_counts[site_name] += 1
            unique_name = f"{site_name} ({site_id[:8]})"
        else:
            name_counts[site_name] = 1
            unique_name = site_name
        
        # Use site_id as the unique key, store the unique name
        site_id_to_name[site_id] = unique_name
        chart_data['sites'].append(unique_name)
        
        if verbose:
            print(f"  Metric {idx + 1}: siteId={site_id[:30]}... -> name='{site_name}' -> unique='{unique_name}'")
            print(f"    Added to sites list (total now: {len(chart_data['sites'])})")
        
        periods = site_metric.get('periods', [])
        for period in periods:
            timestamp = period.get('metricTime', '')
            if timestamp:
                all_timestamps.add(timestamp)
    
    # Sort timestamps chronologically
    chart_data['timestamps'] = sorted(list(all_timestamps))
    
    if verbose:
        print(f"\nDEBUG: Found {len(chart_data['sites'])} sites and {len(chart_data['timestamps'])} unique timestamps")
    
    # Second pass: build data arrays for each site
    for site_metric in metrics:
        site_id = site_metric.get('siteId', 'Unknown')
        site_name = site_id_to_name.get(site_id)
        
        if site_name is None:
            site_name = f"Site-{site_id[:8]}"
        
        # Initialize arrays for this site
        chart_data['latency'][site_name] = []
        chart_data['download'][site_name] = []
        chart_data['upload'][site_name] = []
        chart_data['packet_loss'][site_name] = []
        chart_data['uptime'][site_name] = []
        
        # Create a mapping of timestamp to data for this site
        timestamp_data = {}
        
        periods = site_metric.get('periods', [])
        if verbose:
            print(f"DEBUG: Site {site_name} has {len(periods)} periods")
        
        for period in periods:
            timestamp = period.get('metricTime', '')
            
            # The data structure might be different - check for wan data
            wan_data = {}
            if 'data' in period:
                data_obj = period['data']
                # Could be directly in data, or nested under 'wan'
                if 'wan' in data_obj:
                    wan_data = data_obj['wan']
                else:
                    # Data might be at the top level
                    wan_data = data_obj
            
            if timestamp:
                timestamp_data[timestamp] = wan_data
        
        # Debug first site
        if verbose and chart_data['sites'][0] == site_name and timestamp_data:
            first_ts = list(timestamp_data.keys())[0]
            first_wan = timestamp_data[first_ts]
            print(f"DEBUG: First timestamp data for {site_name}:")
            print(f"  Timestamp: {first_ts}")
            print(f"  WAN data keys: {list(first_wan.keys()) if first_wan else 'EMPTY'}")
            if first_wan:
                print(f"  Sample values:")
                print(f"    avgLatency: {first_wan.get('avgLatency')}")
                print(f"    download_kbps: {first_wan.get('download_kbps')}")
                print(f"    upload_kbps: {first_wan.get('upload_kbps')}")
                print(f"    packetLoss: {first_wan.get('packetLoss')}")
                print(f"    uptime: {first_wan.get('uptime')}")
        
        # Fill in data for each timestamp
        for idx, timestamp in enumerate(chart_data['timestamps']):
            wan_data = timestamp_data.get(timestamp, {})
            
            # Store metrics - handle None values
            latency = wan_data.get('avgLatency') if wan_data.get('avgLatency') is not None else 0
            chart_data['latency'][site_name].append(latency)
            
            download_kbps = wan_data.get('download_kbps', 0)
            download_mbps = (download_kbps / 1000) if download_kbps else 0
            chart_data['download'][site_name].append(download_mbps)
            
            upload_kbps = wan_data.get('upload_kbps', 0)
            upload_mbps = (upload_kbps / 1000) if upload_kbps else 0
            chart_data['upload'][site_name].append(upload_mbps)
            
            packet_loss = wan_data.get('packetLoss') if wan_data.get('packetLoss') is not None else 0
            chart_data['packet_loss'][site_name].append(packet_loss)
            
            uptime = wan_data.get('uptime') if wan_data.get('uptime') is not None else 0
            chart_data['uptime'][site_name].append(uptime)
            
            # Debug first few values
            if verbose and site_name == chart_data['sites'][0] and idx < 3:
                print(f"  Processing timestamp {idx+1}:")
                print(f"    download_kbps={download_kbps} -> {download_mbps} Mbps")
                print(f"    upload_kbps={upload_kbps} -> {upload_mbps} Mbps")
                print(f"    latency={latency} ms")
    
    if verbose:
        print(f"\nDEBUG: Final chart data:")
        for site in chart_data['sites']:
            latency_vals = chart_data['latency'][site]
            download_vals = chart_data['download'][site]
            print(f"  {site}: {len(latency_vals)} data points")
            print(f"    Latency range: {min(latency_vals):.1f} - {max(latency_vals):.1f}")
            print(f"    Download range: {min(download_vals):.1f} - {max(download_vals):.1f} Mbps")
            print(f"    Sample: {latency_vals[:3]}")
    
    return chart_data


def generate_html_template(chart_data: dict, metrics_data: dict) -> str:
    """Generate the complete HTML template with embedded data"""
    
    # Convert data to JSON for embedding
    chart_data_json = json.dumps(chart_data, indent=2)
    
    # Extract query metadata
    query_time = metrics_data.get('query_timestamp', 'Unknown')
    metric_type = metrics_data.get('metric_type', '5m')
    begin_time = metrics_data.get('begin_timestamp', 'Unknown')
    end_time = metrics_data.get('end_timestamp', 'Unknown')
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UniFi ISP Metrics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@700;800&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        :root {{
            --bg-primary: #0a0e14;
            --bg-secondary: #111720;
            --bg-tertiary: #1a2332;
            --accent-primary: #00f5d4;
            --accent-secondary: #fee440;
            --accent-tertiary: #f15bb5;
            --text-primary: #e8eef2;
            --text-secondary: #9ba7b5;
            --border: rgba(0, 245, 212, 0.2);
            --glow: rgba(0, 245, 212, 0.4);
        }}
        
        body {{
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
            position: relative;
        }}
        
        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 30%, rgba(0, 245, 212, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 80% 70%, rgba(254, 228, 64, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(241, 91, 181, 0.02) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 3rem 2rem;
            position: relative;
            z-index: 1;
        }}
        
        header {{
            margin-bottom: 4rem;
            border-bottom: 2px solid var(--border);
            padding-bottom: 2rem;
            animation: slideDown 0.8s ease-out;
        }}
        
        h1 {{
            font-family: 'Syne', sans-serif;
            font-size: 4rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 50%, var(--accent-tertiary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 1rem;
            letter-spacing: -0.02em;
            text-transform: uppercase;
        }}
        
        .subtitle {{
            font-size: 1.1rem;
            color: var(--text-secondary);
            font-weight: 400;
            letter-spacing: 0.05em;
        }}
        
        .metadata {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
            animation: fadeIn 1s ease-out 0.3s both;
        }}
        
        .metadata-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }}
        
        .metadata-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, var(--accent-primary), var(--accent-tertiary));
            transition: width 0.3s ease;
        }}
        
        .metadata-card:hover {{
            border-color: var(--accent-primary);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 245, 212, 0.1);
        }}
        
        .metadata-card:hover::before {{
            width: 8px;
        }}
        
        .metadata-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        
        .metadata-value {{
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--accent-primary);
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 2rem;
            margin-bottom: 3rem;
        }}
        
        .chart-container {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
            position: relative;
            overflow: hidden;
            animation: fadeInUp 0.8s ease-out both;
            transition: all 0.3s ease;
        }}
        
        .chart-container:nth-child(1) {{ animation-delay: 0.1s; }}
        .chart-container:nth-child(2) {{ animation-delay: 0.2s; }}
        .chart-container:nth-child(3) {{ animation-delay: 0.3s; }}
        .chart-container:nth-child(4) {{ animation-delay: 0.4s; }}
        .chart-container:nth-child(5) {{ animation-delay: 0.5s; }}
        
        .chart-container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary), var(--accent-tertiary));
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .chart-container:hover {{
            border-color: var(--accent-primary);
            box-shadow: 0 12px 32px rgba(0, 245, 212, 0.15);
        }}
        
        .chart-container:hover::before {{
            opacity: 1;
        }}
        
        .chart-title {{
            font-family: 'Syne', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: var(--text-primary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .chart-wrapper {{
            position: relative;
            height: 350px;
        }}
        
        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
            border-top: 1px solid var(--border);
            margin-top: 4rem;
            animation: fadeIn 1s ease-out 0.8s both;
        }}
        
        @keyframes slideDown {{
            from {{
                opacity: 0;
                transform: translateY(-30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        @keyframes fadeIn {{
            from {{
                opacity: 0;
            }}
            to {{
                opacity: 1;
            }}
        }}
        
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        @media (max-width: 1200px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 768px) {{
            h1 {{
                font-size: 2.5rem;
            }}
            
            .container {{
                padding: 2rem 1rem;
            }}
            
            .chart-wrapper {{
                height: 300px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>ISP Metrics</h1>
            <p class="subtitle">Real-time Network Performance Dashboard</p>
        </header>
        
        <div class="metadata">
            <div class="metadata-card">
                <div class="metadata-label">Query Time</div>
                <div class="metadata-value">{query_time}</div>
            </div>
            <div class="metadata-card">
                <div class="metadata-label">Metric Type</div>
                <div class="metadata-value">{metric_type.upper()} Intervals</div>
            </div>
            <div class="metadata-card">
                <div class="metadata-label">Time Range</div>
                <div class="metadata-value">{begin_time[:10]}</div>
            </div>
            <div class="metadata-card">
                <div class="metadata-label">Sites Monitored</div>
                <div class="metadata-value">{len(chart_data['sites'])} Sites</div>
            </div>
        </div>
        
        <!-- DEBUG INFO -->
        <div style="background: #1a2332; border: 1px solid #00f5d4; border-radius: 8px; padding: 1rem; margin-bottom: 2rem; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
            <div style="color: #00f5d4; font-weight: bold; margin-bottom: 0.5rem;">🔍 DEBUG INFO (Open browser console for more details)</div>
            <div style="color: #e8eef2;">Sites loaded: {len(chart_data['sites'])}</div>
            <div style="color: #e8eef2;">Site names: {', '.join(chart_data['sites'])}</div>
            <div style="color: #e8eef2;">Timestamps: {len(chart_data['timestamps'])}</div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-container">
                <h2 class="chart-title">Average Latency</h2>
                <div class="chart-wrapper">
                    <canvas id="latencyChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <h2 class="chart-title">Download Speed</h2>
                <div class="chart-wrapper">
                    <canvas id="downloadChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <h2 class="chart-title">Upload Speed</h2>
                <div class="chart-wrapper">
                    <canvas id="uploadChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <h2 class="chart-title">Packet Loss</h2>
                <div class="chart-wrapper">
                    <canvas id="packetLossChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <h2 class="chart-title">Network Uptime</h2>
                <div class="chart-wrapper">
                    <canvas id="uptimeChart"></canvas>
                </div>
            </div>
        </div>
        
        <footer>
            Generated from UniFi Site Manager ISP Metrics
        </footer>
    </div>
    
    <script>
        // Embedded chart data
        const chartData = {chart_data_json};
        
        // DEBUG: Log chart data to console
        console.log('=== CHART DATA DEBUG ===');
        console.log('Total sites:', chartData.sites ? chartData.sites.length : 0);
        console.log('Sites array:', chartData.sites);
        console.log('Total timestamps:', chartData.timestamps ? chartData.timestamps.length : 0);
        
        if (chartData.sites) {{
            chartData.sites.forEach((site, idx) => {{
                console.log(`Site ${{idx + 1}}: ${{site}}`);
                console.log(`  Latency points: ${{chartData.latency[site] ? chartData.latency[site].length : 0}}`);
                console.log(`  Download points: ${{chartData.download[site] ? chartData.download[site].length : 0}}`);
                if (chartData.latency[site]) {{
                    console.log(`  Sample latency: ${{chartData.latency[site].slice(0, 3)}}`);
                }}
            }});
        }}
        console.log('========================');
        
        // Color palette
        const colors = [
            '#00f5d4',  // Cyan
            '#fee440',  // Yellow
            '#f15bb5',  // Magenta
            '#9b5de5',  // Purple
            '#00bbf9',  // Blue
            '#ff6b6b',  // Red
            '#51cf66',  // Green
            '#ff922b',  // Orange
        ];
        
        // Chart configuration
        const commonOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{
                mode: 'index',
                intersect: false,
            }},
            plugins: {{
                legend: {{
                    display: true,
                    position: 'top',
                    labels: {{
                        color: '#9ba7b5',
                        font: {{
                            family: 'JetBrains Mono',
                            size: 11
                        }},
                        padding: 15,
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }}
                }},
                tooltip: {{
                    backgroundColor: 'rgba(17, 23, 32, 0.95)',
                    titleColor: '#00f5d4',
                    bodyColor: '#e8eef2',
                    borderColor: 'rgba(0, 245, 212, 0.2)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    titleFont: {{
                        family: 'JetBrains Mono',
                        size: 13,
                        weight: 'bold'
                    }},
                    bodyFont: {{
                        family: 'JetBrains Mono',
                        size: 12
                    }}
                }}
            }},
            scales: {{
                x: {{
                    grid: {{
                        color: 'rgba(0, 245, 212, 0.05)',
                        drawBorder: false
                    }},
                    ticks: {{
                        color: '#9ba7b5',
                        font: {{
                            family: 'JetBrains Mono',
                            size: 10
                        }},
                        maxRotation: 45,
                        minRotation: 45
                    }}
                }},
                y: {{
                    grid: {{
                        color: 'rgba(0, 245, 212, 0.05)',
                        drawBorder: false
                    }},
                    ticks: {{
                        color: '#9ba7b5',
                        font: {{
                            family: 'JetBrains Mono',
                            size: 10
                        }}
                    }}
                }}
            }}
        }};
        
        // Format timestamps for display
        const formatTimestamp = (timestamp) => {{
            const date = new Date(timestamp);
            return date.toLocaleString('en-US', {{ 
                month: 'short', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit' 
            }});
        }};
        
        const labels = chartData.timestamps.map(formatTimestamp);
        
        // Create datasets for each chart
        const createDatasets = (metricKey) => {{
            console.log(`Creating datasets for ${{metricKey}}...`);
            const datasets = chartData.sites.map((site, index) => {{
                const dataset = {{
                    label: site,
                    data: chartData[metricKey][site],
                    borderColor: colors[index % colors.length],
                    backgroundColor: colors[index % colors.length] + '20',
                    borderWidth: 2,
                    tension: 0.4,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    pointBackgroundColor: colors[index % colors.length],
                    pointBorderColor: '#0a0e14',
                    pointBorderWidth: 2,
                    fill: true
                }};
                console.log(`  Dataset ${{index}}: ${{site}} - ${{dataset.data ? dataset.data.length : 0}} points`);
                return dataset;
            }});
            console.log(`  Total datasets created: ${{datasets.length}}`);
            return datasets;
        }};
        
        // Latency Chart
        new Chart(document.getElementById('latencyChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: createDatasets('latency')
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{
                            display: true,
                            text: 'Latency (ms)',
                            color: '#9ba7b5',
                            font: {{
                                family: 'JetBrains Mono',
                                size: 11
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Download Speed Chart
        new Chart(document.getElementById('downloadChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: createDatasets('download')
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{
                            display: true,
                            text: 'Speed (Mbps)',
                            color: '#9ba7b5',
                            font: {{
                                family: 'JetBrains Mono',
                                size: 11
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Upload Speed Chart
        new Chart(document.getElementById('uploadChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: createDatasets('upload')
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{
                            display: true,
                            text: 'Speed (Mbps)',
                            color: '#9ba7b5',
                            font: {{
                                family: 'JetBrains Mono',
                                size: 11
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Packet Loss Chart
        new Chart(document.getElementById('packetLossChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: createDatasets('packet_loss')
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{
                            display: true,
                            text: 'Packet Loss (%)',
                            color: '#9ba7b5',
                            font: {{
                                family: 'JetBrains Mono',
                                size: 11
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Uptime Chart
        new Chart(document.getElementById('uptimeChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: createDatasets('uptime')
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        min: 0,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Uptime (%)',
                            color: '#9ba7b5',
                            font: {{
                                family: 'JetBrains Mono',
                                size: 11
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''
    
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML dashboard from UniFi ISP metrics JSON"
    )
    parser.add_argument(
        "--metrics",
        required=True,
        help="Path to ISP metrics JSON file"
    )
    parser.add_argument(
        "--sites",
        default="sites.json",
        help="Path to sites JSON file (default: sites.json)"
    )
    parser.add_argument(
        "--output",
        default="isp_metrics_dashboard.html",
        help="Output HTML file (default: isp_metrics_dashboard.html)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug output"
    )
    
    args = parser.parse_args()
    
    generate_html_dashboard(args.metrics, args.sites, args.output, args.verbose)


if __name__ == "__main__":
    main()

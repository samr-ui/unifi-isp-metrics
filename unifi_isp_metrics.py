#!/usr/bin/env python3
"""
UniFi Site Manager API - ISP Metrics Collector

This script:
1. Retrieves all sites from the UniFi Site Manager API
2. Saves the site list to a JSON file
3. Queries ISP metrics for each site
4. Saves the ISP metrics to a separate JSON file
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse


class UniFiAPIClient:
    """Client for interacting with the UniFi Site Manager API"""
    
    BASE_URL = "https://api.ui.com"
    
    def __init__(self, api_key: str):
        """
        Initialize the API client
        
        Args:
            api_key: Your UniFi API key from unifi.ui.com
        """
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def get_all_sites(self, page_size: int = 100) -> List[Dict]:
        """
        Retrieve all sites associated with the API key
        
        Args:
            page_size: Number of sites to retrieve per page (default: 100)
            
        Returns:
            List of site dictionaries
        """
        all_sites = []
        next_token = None
        
        print("Fetching sites from UniFi Site Manager API...")
        
        while True:
            # Build URL with pagination
            url = f"{self.BASE_URL}/v1/sites?pageSize={page_size}"
            if next_token:
                url += f"&nextToken={next_token}"
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                
                # Add sites from this page
                if "data" in data:
                    sites = data["data"]
                    all_sites.extend(sites)
                    print(f"Retrieved {len(sites)} sites (total: {len(all_sites)})")
                
                # Check for next page
                if "nextToken" in data and data["nextToken"]:
                    next_token = data["nextToken"]
                else:
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"Error fetching sites: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response: {e.response.text}")
                raise
        
        print(f"Successfully retrieved {len(all_sites)} total sites")
        return all_sites
    
    def query_isp_metrics(
        self,
        metric_type: str,
        sites: List[Dict],
        begin_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        relative_time: Optional[str] = None
    ) -> Dict:
        """
        Query ISP metrics for specific sites
        
        Args:
            metric_type: Either "5m" or "1h" for 5-minute or 1-hour intervals
            sites: List of site query objects with siteId, hostId, beginTimestamp, endTimestamp
            begin_timestamp: ISO 8601 timestamp for start of range (optional)
            end_timestamp: ISO 8601 timestamp for end of range (optional)
            relative_time: Relative time range like "24h", "7d", or "30d" (optional)
            
        Returns:
            Dictionary containing ISP metrics data
        """
        url = f"{self.BASE_URL}/ea/isp-metrics/{metric_type}/query"
        
        # Build the request payload
        payload = {
            "sites": sites
        }
        
        print(f"\nQuerying ISP metrics ({metric_type} intervals) for {len(sites)} sites...")
        print(f"Sites in request:")
        for i, site in enumerate(sites, 1):
            print(f"  {i}. siteId: {site.get('siteId', 'N/A')[:20]}... hostId: {site.get('hostId', 'N/A')[:30]}...")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for partial success
            if data.get("data", {}).get("status") == "partialSuccess":
                print(f"Warning: {data['data'].get('message', 'Partial success')}")
            
            # Show how many sites returned data
            metrics_returned = len(data.get("data", {}).get("metrics", []))
            print(f"Successfully retrieved ISP metrics for {metrics_returned}/{len(sites)} sites")
            
            if metrics_returned < len(sites):
                print(f"⚠️  Warning: Only {metrics_returned} of {len(sites)} sites returned data")
                print(f"   This could mean some sites don't have metrics available for this time period")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Error querying ISP metrics: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def build_site_queries(
        self,
        sites: List[Dict],
        begin_timestamp: str,
        end_timestamp: str
    ) -> List[Dict]:
        """
        Build site query objects from site list
        
        Args:
            sites: List of site dictionaries from get_all_sites()
            begin_timestamp: ISO 8601 timestamp for start
            end_timestamp: ISO 8601 timestamp for end
            
        Returns:
            List of site query objects for the ISP metrics API
        """
        site_queries = []
        
        print(f"\nBuilding queries for {len(sites)} sites...")
        
        for i, site in enumerate(sites, 1):
            site_query = {
                "siteId": site["siteId"],
                "hostId": site["hostId"],
                "beginTimestamp": begin_timestamp,
                "endTimestamp": end_timestamp
            }
            site_queries.append(site_query)
            
            # Show site info
            site_name = site.get('meta', {}).get('name', 'Unknown')
            print(f"  {i}. {site_name} (siteId: {site['siteId'][:20]}...)")
        
        print(f"Total queries built: {len(site_queries)}")
        
        return site_queries


def save_to_file(data: Dict, filename: str) -> None:
    """Save data to a JSON file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Data saved to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch UniFi sites and query ISP metrics"
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="Your UniFi API key from unifi.ui.com"
    )
    parser.add_argument(
        "--metric-type",
        choices=["5m", "1h"],
        default="5m",
        help="Metric interval type: 5m (5-minute) or 1h (1-hour)"
    )
    parser.add_argument(
        "--hours-back",
        type=int,
        default=24,
        help="Number of hours back to query (default: 24)"
    )
    parser.add_argument(
        "--sites-output",
        default="sites.json",
        help="Output file for sites list (default: sites.json)"
    )
    parser.add_argument(
        "--metrics-output",
        default="isp_metrics.json",
        help="Output file for ISP metrics (default: isp_metrics.json)"
    )
    parser.add_argument(
        "--generate-html",
        action="store_true",
        help="Generate HTML dashboard after fetching metrics"
    )
    parser.add_argument(
        "--html-output",
        default="isp_metrics_dashboard.html",
        help="Output HTML file (default: isp_metrics_dashboard.html)"
    )
    
    args = parser.parse_args()
    
    # Initialize API client
    client = UniFiAPIClient(args.api_key)
    
    # Step 1: Get all sites
    print("=" * 60)
    print("STEP 1: Fetching Sites")
    print("=" * 60)
    sites = client.get_all_sites()
    
    # Save sites to file
    sites_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_sites": len(sites),
        "sites": sites
    }
    save_to_file(sites_data, args.sites_output)
    
    # Step 2: Query ISP metrics for all sites
    print("\n" + "=" * 60)
    print("STEP 2: Querying ISP Metrics")
    print("=" * 60)
    
    # Calculate time range
    end_time = datetime.utcnow()
    begin_time = end_time - timedelta(hours=args.hours_back)
    
    begin_timestamp = begin_time.isoformat() + "Z"
    end_timestamp = end_time.isoformat() + "Z"
    
    print(f"Time range: {begin_timestamp} to {end_timestamp}")
    
    # Build site queries
    site_queries = client.build_site_queries(sites, begin_timestamp, end_timestamp)
    
    # Query ISP metrics
    isp_metrics = client.query_isp_metrics(
        metric_type=args.metric_type,
        sites=site_queries
    )
    
    # Save ISP metrics to file
    metrics_data = {
        "query_timestamp": datetime.utcnow().isoformat() + "Z",
        "metric_type": args.metric_type,
        "begin_timestamp": begin_timestamp,
        "end_timestamp": end_timestamp,
        "total_sites_queried": len(site_queries),
        "response": isp_metrics
    }
    save_to_file(metrics_data, args.metrics_output)
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Sites saved to: {args.sites_output}")
    print(f"ISP metrics saved to: {args.metrics_output}")
    
    # Generate HTML dashboard if requested
    if args.generate_html:
        print("\n" + "=" * 60)
        print("STEP 3: Generating HTML Dashboard")
        print("=" * 60)
        try:
            from generate_charts import generate_html_dashboard
            generate_html_dashboard(args.metrics_output, args.sites_output, args.html_output)
            print(f"HTML dashboard saved to: {args.html_output}")
        except ImportError:
            print("Error: generate_charts.py not found. Please ensure it's in the same directory.")
        except Exception as e:
            print(f"Error generating HTML dashboard: {e}")


if __name__ == "__main__":
    main()

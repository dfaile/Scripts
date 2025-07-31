#!/usr/bin/env python3

import argparse
import configparser
import sys
import json
import requests
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class Nobl9QualityGate:
    """Nobl9 Quality Gate for CI/CD integration using SLO Status API v2"""
    
    def __init__(self, organization: str, client_id: str, client_secret: str, 
                 base_url: str = "https://app.nobl9.com"):
        self.organization = organization
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.access_token = None
    
    def get_access_token(self) -> str:
        """Get access token from Nobl9 API"""
        if self.access_token:
            return self.access_token
            
        # Create Basic auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        response = requests.post(
            f"{self.base_url}/api/accessToken",
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Organization": self.organization,
                "Accept": "application/json; version=v1alpha"
            }
        )
        
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            return self.access_token
        else:
            raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")
    
    def get_slo_status(self, slo_name: str, project: str, 
                      from_time: Optional[str] = None, 
                      to_time: Optional[str] = None,
                      fields: Optional[str] = None) -> Dict[str, Any]:
        """Get SLO status using the v2 API"""
        token = self.get_access_token()
        
        # Build query parameters
        params = {}
        if from_time and to_time:
            params["from"] = from_time
            params["to"] = to_time
        if fields:
            params["fields"] = fields
        
        response = requests.get(
            f"{self.base_url}/api/v2/slos/{slo_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "Organization": self.organization,
                "Project": project
            },
            params=params
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise Exception(f"SLO '{slo_name}' not found in project '{project}'")
        elif response.status_code == 403:
            raise Exception(f"Access forbidden to SLO '{slo_name}' in project '{project}'")
        elif response.status_code == 429:
            raise Exception("API rate limit exceeded. Please wait and try again.")
        else:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
    
    def evaluate_quality_gate(self, slo_data: Dict[str, Any], 
                            threshold: float = 0.0) -> tuple[bool, float]:
        """
        Evaluate quality gate based on error budget remaining percentage
        
        Args:
            slo_data: SLO data from API
            threshold: Minimum error budget percentage required (0.0 = any remaining budget)
        
        Returns:
            tuple: (pass_gate, error_budget_percentage)
        """
        try:
            # Check if SLO has objectives
            if not slo_data.get("objectives"):
                raise Exception("SLO has no objectives defined")
            
            # Get the first objective's error budget remaining percentage
            objective = slo_data["objectives"][0]
            error_budget_percentage = objective.get("errorBudgetRemainingPercentage", 0.0)
            
            # Convert to percentage for easier reading
            error_budget_percentage_pct = error_budget_percentage * 100
            
            # Pass if error budget remaining is above threshold
            pass_gate = error_budget_percentage_pct > threshold
            
            return pass_gate, error_budget_percentage_pct
            
        except KeyError as e:
            raise Exception(f"Required field missing in SLO data: {e}")
        except Exception as e:
            raise Exception(f"Error evaluating quality gate: {e}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Nobl9 Quality Gate for CI/CD integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --slo-name "prod-latency" --project "software-slo" --client-id "your-id" --client-secret "your-secret"
  %(prog)s --slo-name "api-availability" --project "backend" --threshold 10.0 --organization "my-org"
  %(prog)s --slo-name "db-performance" --project "data" --fields "counts" --from "2024-01-25T00:00:00Z" --to "2024-01-25T23:59:59Z"
        """
    )
    
    # Required arguments
    parser.add_argument("--slo-name", required=True,
                       help="Name of the SLO to check")
    parser.add_argument("--project", required=True,
                       help="Project name containing the SLO")
    parser.add_argument("--client-id", required=True,
                       help="Nobl9 client ID")
    parser.add_argument("--client-secret", required=True,
                       help="Nobl9 client secret")
    
    # Optional arguments
    parser.add_argument("--organization", default="software",
                       help="Nobl9 organization ID (default: software)")
    parser.add_argument("--base-url", default="https://app.nobl9.com",
                       help="Nobl9 API base URL (default: https://app.nobl9.com)")
    parser.add_argument("--threshold", type=float, default=0.0,
                       help="Minimum error budget percentage required (default: 0.0)")
    parser.add_argument("--fields", 
                       help="Additional fields to request (e.g., 'counts')")
    parser.add_argument("--from", dest="from_time",
                       help="Start time for data range (RFC3339 format)")
    parser.add_argument("--to", dest="to_time",
                       help="End time for data range (RFC3339 format)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--json-output", action="store_true",
                       help="Output SLO data as JSON")
    
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_arguments()
    
    try:
        # Initialize Nobl9 client
        nobl9 = Nobl9QualityGate(
            organization=args.organization,
            client_id=args.client_id,
            client_secret=args.client_secret,
            base_url=args.base_url
        )
        
        if args.verbose:
            print(f"Checking SLO: {args.slo_name}")
            print(f"Project: {args.project}")
            print(f"Organization: {args.organization}")
            print(f"Threshold: {args.threshold}%")
        
        # Get SLO status
        slo_data = nobl9.get_slo_status(
            slo_name=args.slo_name,
            project=args.project,
            from_time=args.from_time,
            to_time=args.to_time,
            fields=args.fields
        )
        
        # Output SLO data if requested
        if args.json_output:
            print(json.dumps(slo_data, indent=2))
        
        # Evaluate quality gate
        pass_gate, error_budget_pct = nobl9.evaluate_quality_gate(
            slo_data, args.threshold
        )
        
        # Output results
        print(f"Error budget remaining: {error_budget_pct:.2f}%")
        print(f"Threshold: {args.threshold}%")
        
        if pass_gate:
            print("✅ Quality gate PASSED - proceeding with release")
            sys.exit(0)
        else:
            print("❌ Quality gate FAILED - canceling release")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
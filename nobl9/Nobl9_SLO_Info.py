#!/usr/bin/env python3

import argparse
import sys
import json
import requests
import base64
from datetime import datetime
from typing import Optional, Dict, Any

class Nobl9SLOInfo:
    """Nobl9 SLO Information Display using SLO Status API v2"""
    
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
    
    def get_slo_info(self, slo_name: str, project: str, 
                     from_time: Optional[str] = None, 
                     to_time: Optional[str] = None,
                     fields: Optional[str] = None) -> Dict[str, Any]:
        """Get SLO information using the v2 API"""
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
    
    def format_human_readable(self, slo_data: Dict[str, Any]) -> str:
        """Format SLO data in human-readable format"""
        output = []
        
        # Basic SLO Information
        output.append("=" * 60)
        output.append(f"SLO: {slo_data.get('displayName', slo_data.get('name', 'Unknown'))}")
        output.append(f"Name: {slo_data.get('name', 'Unknown')}")
        output.append(f"Description: {slo_data.get('description', 'No description')}")
        output.append("=" * 60)
        
        # Project Information
        if 'project' in slo_data:
            project = slo_data['project']
            output.append(f"Project: {project.get('displayName', project.get('name', 'Unknown'))}")
            output.append(f"Project Name: {project.get('name', 'Unknown')}")
        
        # Service Information
        if 'service' in slo_data:
            service = slo_data['service']
            output.append(f"Service: {service.get('displayName', service.get('name', 'Unknown'))}")
            output.append(f"Service Name: {service.get('name', 'Unknown')}")
        
        # Budgeting Method
        output.append(f"Budgeting Method: {slo_data.get('budgetingMethod', 'Unknown')}")
        
        # Creation Date
        if 'createdAt' in slo_data:
            created_date = datetime.fromisoformat(slo_data['createdAt'].replace('Z', '+00:00'))
            output.append(f"Created: {created_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        output.append("")
        
        # Objectives Information
        if 'objectives' in slo_data and slo_data['objectives']:
            output.append("OBJECTIVES:")
            output.append("-" * 40)
            
            for i, objective in enumerate(slo_data['objectives'], 1):
                output.append(f"Objective {i}: {objective.get('displayName', objective.get('name', 'Unknown'))}")
                output.append(f"  Name: {objective.get('name', 'Unknown')}")
                output.append(f"  Target: {objective.get('target', 'Unknown')}")
                output.append(f"  SLI Type: {objective.get('sliType', 'Unknown')}")
                
                # Reliability metrics
                reliability = objective.get('reliability', 0)
                output.append(f"  Reliability: {reliability:.4f} ({reliability*100:.2f}%)")
                
                # Error budget metrics
                error_budget_remaining = objective.get('errorBudgetRemaining', 0)
                error_budget_percentage = objective.get('errorBudgetRemainingPercentage', 0)
                output.append(f"  Error Budget Remaining: {error_budget_remaining:.2f} seconds")
                output.append(f"  Error Budget Percentage: {error_budget_percentage*100:.2f}%")
                
                # Burn rate
                burn_rate = objective.get('burnRate', 0)
                output.append(f"  Burn Rate: {burn_rate:.4f}")
                
                # Counts (if available)
                if 'counts' in objective:
                    counts = objective['counts']
                    total = counts.get('total', 0)
                    good = counts.get('good', 0)
                    bad = total - good if total > 0 else 0
                    success_rate = (good / total * 100) if total > 0 else 0
                    output.append(f"  Total Requests: {total}")
                    output.append(f"  Good Requests: {good}")
                    output.append(f"  Bad Requests: {bad}")
                    output.append(f"  Success Rate: {success_rate:.2f}%")
                
                output.append("")
        
        # Composite SLO Information
        if 'composite' in slo_data:
            composite = slo_data['composite']
            output.append("COMPOSITE SLO:")
            output.append("-" * 40)
            output.append(f"Target: {composite.get('target', 'Unknown')}")
            
            reliability = composite.get('reliability', 0)
            output.append(f"Reliability: {reliability:.4f} ({reliability*100:.2f}%)")
            
            error_budget_remaining = composite.get('errorBudgetRemaining', 0)
            error_budget_percentage = composite.get('errorBudgetRemainingPercentage', 0)
            output.append(f"Error Budget Remaining: {error_budget_remaining:.2f} seconds")
            output.append(f"Error Budget Percentage: {error_budget_percentage*100:.2f}%")
            
            burn_rate = composite.get('burnRate', 0)
            output.append(f"Burn Rate: {burn_rate:.4f}")
            
            if 'burnRateCondition' in composite:
                condition = composite['burnRateCondition']
                output.append(f"Burn Rate Condition: {condition.get('operator', 'Unknown')} {condition.get('value', 'Unknown')}")
            
            output.append("")
        
        # Labels
        if 'labels' in slo_data and slo_data['labels']:
            output.append("LABELS:")
            output.append("-" * 40)
            for key, values in slo_data['labels'].items():
                if isinstance(values, list):
                    output.append(f"  {key}: {', '.join(values)}")
                else:
                    output.append(f"  {key}: {values}")
            output.append("")
        
        # Annotations
        if 'annotations' in slo_data and slo_data['annotations']:
            output.append("ANNOTATIONS:")
            output.append("-" * 40)
            for key, value in slo_data['annotations'].items():
                output.append(f"  {key}: {value}")
            output.append("")
        
        # Status Summary
        output.append("STATUS SUMMARY:")
        output.append("-" * 40)
        
        if 'objectives' in slo_data and slo_data['objectives']:
            objective = slo_data['objectives'][0]  # Use first objective for summary
            error_budget_pct = objective.get('errorBudgetRemainingPercentage', 0) * 100
            reliability = objective.get('reliability', 0) * 100
            target = objective.get('target', 0) * 100
            
            output.append(f"Current Reliability: {reliability:.2f}%")
            output.append(f"Target: {target:.2f}%")
            output.append(f"Error Budget Remaining: {error_budget_pct:.2f}%")
            
            if error_budget_pct > 0:
                output.append("Status: ✅ Healthy (Error budget available)")
            else:
                output.append("Status: ❌ Critical (No error budget remaining)")
        else:
            output.append("Status: ⚠️ No objectives defined")
        
        return "\n".join(output)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Nobl9 SLO Information Display",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --slo-name "prod-latency" --project "software-slo" --client-id "your-id" --client-secret "your-secret"
  %(prog)s --slo-name "api-availability" --project "backend" --json-output
  %(prog)s --slo-name "db-performance" --project "data" --fields "counts" --from "2024-01-25T00:00:00Z" --to "2024-01-25T23:59:59Z"
        """
    )
    
    # Required arguments
    parser.add_argument("--slo-name", required=True,
                       help="Name of the SLO to display")
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
    parser.add_argument("--fields", 
                       help="Additional fields to request (e.g., 'counts')")
    parser.add_argument("--from", dest="from_time",
                       help="Start time for data range (RFC3339 format)")
    parser.add_argument("--to", dest="to_time",
                       help="End time for data range (RFC3339 format)")
    parser.add_argument("--json-output", action="store_true",
                       help="Output SLO data as JSON instead of human-readable format")
    parser.add_argument("--compact", action="store_true",
                       help="Show compact summary only (when not using --json-output)")
    
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_arguments()
    
    try:
        # Initialize Nobl9 client
        nobl9 = Nobl9SLOInfo(
            organization=args.organization,
            client_id=args.client_id,
            client_secret=args.client_secret,
            base_url=args.base_url
        )
        
        # Get SLO information
        slo_data = nobl9.get_slo_info(
            slo_name=args.slo_name,
            project=args.project,
            from_time=args.from_time,
            to_time=args.to_time,
            fields=args.fields
        )
        
        # Output based on format preference
        if args.json_output:
            print(json.dumps(slo_data, indent=2))
        elif args.compact:
            # Show compact summary
            if 'objectives' in slo_data and slo_data['objectives']:
                objective = slo_data['objectives'][0]
                error_budget_pct = objective.get('errorBudgetRemainingPercentage', 0) * 100
                reliability = objective.get('reliability', 0) * 100
                target = objective.get('target', 0) * 100
                
                print(f"SLO: {slo_data.get('displayName', slo_data.get('name', 'Unknown'))}")
                print(f"Reliability: {reliability:.2f}% (Target: {target:.2f}%)")
                print(f"Error Budget: {error_budget_pct:.2f}%")
                print(f"Status: {'✅ Healthy' if error_budget_pct > 0 else '❌ Critical'}")
            else:
                print(f"SLO: {slo_data.get('displayName', slo_data.get('name', 'Unknown'))}")
                print("Status: ⚠️ No objectives defined")
        else:
            # Show full human-readable format
            print(nobl9.format_human_readable(slo_data))
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 
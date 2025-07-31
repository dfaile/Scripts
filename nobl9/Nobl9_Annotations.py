#!/usr/bin/env python3

import argparse
import sys
import json
import requests
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

class Nobl9Annotations:
    """Nobl9 Annotations Management using Annotations API"""
    
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
    
    def get_slos_in_project(self, project: str) -> List[str]:
        """Get all SLO names in a project using SLO Status API v2"""
        token = self.get_access_token()
        
        response = requests.get(
            f"{self.base_url}/api/v2/slos",
            headers={
                "Authorization": f"Bearer {token}",
                "Organization": self.organization,
                "Project": project
            },
            params={"limit": 500}  # Get up to 500 SLOs
        )
        
        if response.status_code == 200:
            slos_data = response.json()
            return [slo["name"] for slo in slos_data.get("data", [])]
        else:
            raise Exception(f"Failed to get SLOs: {response.status_code} - {response.text}")
    
    def create_annotation(self, project: str, slo_name: str, annotation_name: str, 
                         description: str, start_time: str, end_time: str,
                         labels: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """Create an annotation for a specific SLO"""
        token = self.get_access_token()
        
        annotation_data = {
            "project": project,
            "slo": slo_name,
            "name": annotation_name,
            "description": description,
            "startTime": start_time,
            "endTime": end_time
        }
        
        if labels:
            annotation_data["labels"] = labels
        
        response = requests.post(
            f"{self.base_url}/api/annotations",
            headers={
                "Authorization": f"Bearer {token}",
                "Organization": self.organization,
                "Accept": "application/json; version=v1alpha",
                "Content-Type": "application/json"
            },
            json=annotation_data
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 409:
            raise Exception(f"Annotation '{annotation_name}' already exists for SLO '{slo_name}'")
        elif response.status_code == 404:
            raise Exception(f"SLO '{slo_name}' not found in project '{project}'")
        else:
            raise Exception(f"Failed to create annotation: {response.status_code} - {response.text}")
    
    def get_annotations(self, project: str, slo_name: Optional[str] = None,
                       from_time: Optional[str] = None, to_time: Optional[str] = None,
                       annotation_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get annotations with optional filtering"""
        token = self.get_access_token()
        
        params = {}
        if slo_name:
            params["slo"] = slo_name
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        if annotation_names:
            for name in annotation_names:
                params.setdefault("name", []).append(name)
        
        response = requests.get(
            f"{self.base_url}/api/annotations",
            headers={
                "Authorization": f"Bearer {token}",
                "Organization": self.organization,
                "Project": project,
                "Accept": "application/json; version=v1alpha"
            },
            params=params
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get annotations: {response.status_code} - {response.text}")
    
    def delete_annotation(self, project: str, annotation_name: str) -> bool:
        """Delete an annotation"""
        token = self.get_access_token()
        
        response = requests.delete(
            f"{self.base_url}/api/annotations/{annotation_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "Organization": self.organization,
                "Project": project,
                "Accept": "application/json; version=v1alpha"
            }
        )
        
        if response.status_code == 204:
            return True
        else:
            raise Exception(f"Failed to delete annotation: {response.status_code} - {response.text}")
    
    def upsert_annotation(self, project: str, annotation_name: str, slo_name: str,
                         description: str, start_time: str, end_time: str,
                         labels: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """Create or update an annotation"""
        token = self.get_access_token()
        
        annotation_data = {
            "project": project,
            "slo": slo_name,
            "description": description,
            "startTime": start_time,
            "endTime": end_time
        }
        
        if labels:
            annotation_data["labels"] = labels
        
        response = requests.put(
            f"{self.base_url}/api/annotations/{annotation_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "Organization": self.organization,
                "Accept": "application/json; version=v1alpha",
                "Content-Type": "application/json"
            },
            json=annotation_data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to upsert annotation: {response.status_code} - {response.text}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Nobl9 Annotations Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create annotation for specific SLO
  %(prog)s create --project "software-slo" --slo-name "prod-latency" --name "deployment-v1.2.3" --description "Production deployment" --client-id "your-id" --client-secret "your-secret"
  
  # Create annotation for all SLOs in project
  %(prog)s create --project "software-slo" --all-slos --name "maintenance-window" --description "Scheduled maintenance" --client-id "your-id" --client-secret "your-secret"
  
  # List annotations
  %(prog)s list --project "software-slo" --client-id "your-id" --client-secret "your-secret"
  
  # Delete annotation
  %(prog)s delete --project "software-slo" --name "deployment-v1.2.3" --client-id "your-id" --client-secret "your-secret"
        """
    )
    
    # Global arguments
    parser.add_argument("--organization", default="software",
                       help="Nobl9 organization ID (default: software)")
    parser.add_argument("--base-url", default="https://app.nobl9.com",
                       help="Nobl9 API base URL (default: https://app.nobl9.com)")
    parser.add_argument("--client-id", required=True,
                       help="Nobl9 client ID")
    parser.add_argument("--client-secret", required=True,
                       help="Nobl9 client secret")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create annotation(s)")
    create_parser.add_argument("--project", required=True,
                              help="Project name")
    create_parser.add_argument("--slo-name",
                              help="SLO name (use --all-slos to annotate all SLOs in project)")
    create_parser.add_argument("--all-slos", action="store_true",
                              help="Create annotation for all SLOs in the project")
    create_parser.add_argument("--name", required=True,
                              help="Annotation name")
    create_parser.add_argument("--description", required=True,
                              help="Annotation description")
    create_parser.add_argument("--start-time",
                              help="Start time (RFC3339 format, default: now)")
    create_parser.add_argument("--end-time",
                              help="End time (RFC3339 format, default: now + 5 minutes)")
    create_parser.add_argument("--duration-minutes", type=int, default=5,
                              help="Duration in minutes from now (default: 5)")
    create_parser.add_argument("--labels",
                              help="Labels as JSON string (e.g., '{\"environment\":[\"prod\"],\"team\":[\"backend\"]}')")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List annotations")
    list_parser.add_argument("--project", required=True,
                            help="Project name")
    list_parser.add_argument("--slo-name",
                            help="Filter by SLO name")
    list_parser.add_argument("--from",
                            help="Filter by start time (RFC3339 format)")
    list_parser.add_argument("--to",
                            help="Filter by end time (RFC3339 format)")
    list_parser.add_argument("--name",
                            help="Filter by annotation name(s), comma-separated")
    list_parser.add_argument("--json-output", action="store_true",
                            help="Output as JSON")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete annotation")
    delete_parser.add_argument("--project", required=True,
                              help="Project name")
    delete_parser.add_argument("--name", required=True,
                              help="Annotation name to delete")
    
    return parser.parse_args()

def format_timestamp(dt: datetime) -> str:
    """Format datetime as RFC3339 timestamp"""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    """Main function"""
    args = parse_arguments()
    
    if not args.command:
        print("Error: No command specified. Use --help for usage information.")
        sys.exit(1)
    
    try:
        # Initialize Nobl9 client
        nobl9 = Nobl9Annotations(
            organization=args.organization,
            client_id=args.client_id,
            client_secret=args.client_secret,
            base_url=args.base_url
        )
        
        if args.command == "create":
            # Parse labels if provided
            labels = None
            if hasattr(args, 'labels') and args.labels:
                try:
                    labels = json.loads(args.labels)
                except json.JSONDecodeError:
                    print("Error: Invalid JSON format for labels")
                    sys.exit(1)
            
            # Set time range
            now = datetime.utcnow()
            start_time = args.start_time if hasattr(args, 'start_time') and args.start_time else format_timestamp(now)
            end_time = args.end_time if hasattr(args, 'end_time') and args.end_time else format_timestamp(now + timedelta(minutes=args.duration_minutes))
            
            if args.all_slos:
                # Create annotation for all SLOs in project
                if args.verbose:
                    print(f"Getting all SLOs in project: {args.project}")
                
                slo_names = nobl9.get_slos_in_project(args.project)
                
                if not slo_names:
                    print(f"No SLOs found in project: {args.project}")
                    sys.exit(1)
                
                if args.verbose:
                    print(f"Found {len(slo_names)} SLOs: {', '.join(slo_names)}")
                
                success_count = 0
                for slo_name in slo_names:
                    try:
                        annotation_name = f"{args.name}-{slo_name}" if len(slo_names) > 1 else args.name
                        result = nobl9.create_annotation(
                            project=args.project,
                            slo_name=slo_name,
                            annotation_name=annotation_name,
                            description=args.description,
                            start_time=start_time,
                            end_time=end_time,
                            labels=labels
                        )
                        print(f"✅ Created annotation '{annotation_name}' for SLO '{slo_name}'")
                        success_count += 1
                    except Exception as e:
                        print(f"❌ Failed to create annotation for SLO '{slo_name}': {e}")
                
                print(f"\nSummary: Created {success_count}/{len(slo_names)} annotations")
                
            else:
                # Create annotation for specific SLO
                if not args.slo_name:
                    print("Error: Either --slo-name or --all-slos must be specified")
                    sys.exit(1)
                
                result = nobl9.create_annotation(
                    project=args.project,
                    slo_name=args.slo_name,
                    annotation_name=args.name,
                    description=args.description,
                    start_time=start_time,
                    end_time=end_time,
                    labels=labels
                )
                print(f"✅ Created annotation '{args.name}' for SLO '{args.slo_name}'")
                if args.verbose:
                    print(json.dumps(result, indent=2))
        
        elif args.command == "list":
            # Parse annotation names if provided
            annotation_names = None
            if args.name:
                annotation_names = [name.strip() for name in args.name.split(",")]
            
            annotations = nobl9.get_annotations(
                project=args.project,
                slo_name=args.slo_name,
                from_time=args.from,
                to_time=args.to,
                annotation_names=annotation_names
            )
            
            if args.json_output:
                print(json.dumps(annotations, indent=2))
            else:
                if not annotations:
                    print("No annotations found")
                else:
                    print(f"Found {len(annotations)} annotation(s):")
                    print("=" * 80)
                    for annotation in annotations:
                        print(f"Name: {annotation['name']}")
                        print(f"SLO: {annotation['slo']}")
                        print(f"Project: {annotation['project']}")
                        print(f"Description: {annotation['description']}")
                        print(f"Start Time: {annotation['startTime']}")
                        print(f"End Time: {annotation['endTime']}")
                        if 'labels' in annotation and annotation['labels']:
                            print("Labels:")
                            for key, values in annotation['labels'].items():
                                print(f"  {key}: {', '.join(values)}")
                        print("-" * 40)
        
        elif args.command == "delete":
            success = nobl9.delete_annotation(args.project, args.name)
            if success:
                print(f"✅ Deleted annotation '{args.name}'")
            else:
                print(f"❌ Failed to delete annotation '{args.name}'")
                sys.exit(1)
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 
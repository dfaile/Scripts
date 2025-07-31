# Nobl9 Quality Gate for CI/CD

This script integrates with Nobl9's SLO Status API v2 to create quality gates for CI/CD pipelines. It checks the error budget remaining for a specified SLO and determines whether to proceed with a deployment.

## Features

- Uses Nobl9 SLO Status API v2 (latest)
- Command-line argument support for CI/CD integration
- Configurable error budget thresholds with safety margins
- Support for time-range queries
- Verbose output and JSON data export options
- Proper error handling and exit codes

## Installation

```bash
pip install requests
```

## Usage

### Basic Usage

```bash
python Nobl9_QualityGate_PP.py \
  --slo-name "prod-latency" \
  --project "software-slo" \
  --client-id "your-client-id" \
  --client-secret "your-client-secret"
```

### Advanced Usage

```bash
python Nobl9_QualityGate_PP.py \
  --slo-name "api-availability" \
  --project "backend" \
  --organization "my-org" \
  --client-id "your-client-id" \
  --client-secret "your-client-secret" \
  --threshold 10.0 \
  --fields "counts" \
  --from "2024-01-25T00:00:00Z" \
  --to "2024-01-25T23:59:59Z" \
  --verbose \
  --json-output
```

## Command Line Arguments

### Required Arguments
- `--slo-name`: Name of the SLO to check
- `--project`: Project name containing the SLO
- `--client-id`: Nobl9 client ID
- `--client-secret`: Nobl9 client secret

### Optional Arguments
- `--organization`: Nobl9 organization ID (default: "software")
- `--base-url`: Nobl9 API base URL (default: "https://app.nobl9.com")
- `--threshold`: Minimum error budget percentage required (default: 0.0)
  - **0.0%**: Pass if ANY error budget remains (even 0.1%)
  - **5.0%**: Pass only if at least 5% error budget remains
  - **10.0%**: Pass only if at least 10% error budget remains
  - Use higher thresholds for production environments to maintain safety margins
- `--fields`: Additional fields to request (e.g., "counts")
- `--from`: Start time for data range (RFC3339 format)
- `--to`: End time for data range (RFC3339 format)
- `--verbose, -v`: Enable verbose output
- `--json-output`: Output SLO data as JSON

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Quality Gate Check
on: [push, pull_request]

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: pip install requests
      
      - name: Run Nobl9 Quality Gate
        run: |
          python Nobl9_QualityGate_PP.py \
            --slo-name "${{ secrets.SLO_NAME }}" \
            --project "${{ secrets.PROJECT }}" \
            --client-id "${{ secrets.NOBL9_CLIENT_ID }}" \
            --client-secret "${{ secrets.NOBL9_CLIENT_SECRET }}" \
            --organization "${{ secrets.ORGANIZATION }}" \
            --threshold 5.0
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    
    environment {
        SLO_NAME = 'prod-latency'
        PROJECT = 'software-slo'
        ORGANIZATION = 'software'
    }
    
    stages {
        stage('Quality Gate') {
            steps {
                script {
                    def result = sh(
                        script: """
                            python Nobl9_QualityGate_PP.py \
                                --slo-name "${SLO_NAME}" \
                                --project "${PROJECT}" \
                                --client-id "${NOBL9_CLIENT_ID}" \
                                --client-secret "${NOBL9_CLIENT_SECRET}" \
                                --organization "${ORGANIZATION}" \
                                --threshold 10.0
                        """,
                        returnStatus: true
                    )
                    
                    if (result != 0) {
                        error "Quality gate failed - deployment blocked"
                    }
                }
            }
        }
        
        stage('Deploy') {
            steps {
                echo "Quality gate passed - proceeding with deployment"
                // Your deployment steps here
            }
        }
    }
}
```

### GitLab CI Example

```yaml
stages:
  - quality-gate
  - deploy

quality-gate:
  stage: quality-gate
  image: python:3.9
  before_script:
    - pip install requests
  script:
    - python Nobl9_QualityGate_PP.py
      --slo-name "$SLO_NAME"
      --project "$PROJECT"
      --client-id "$NOBL9_CLIENT_ID"
      --client-secret "$NOBL9_CLIENT_SECRET"
      --organization "$ORGANIZATION"
      --threshold 5.0
  variables:
    SLO_NAME: "prod-latency"
    PROJECT: "software-slo"
    ORGANIZATION: "software"

deploy:
  stage: deploy
  script:
    - echo "Quality gate passed - deploying..."
  dependencies:
    - quality-gate
```

## Exit Codes

- `0`: Quality gate passed - proceed with deployment
- `1`: Quality gate failed - cancel deployment

## Error Handling

The script includes comprehensive error handling for:
- Authentication failures
- SLO not found
- Access forbidden
- API rate limiting
- Missing required fields
- Network errors

## Threshold Configuration

The `--threshold` parameter controls the minimum error budget percentage required for the quality gate to pass:

- **0.0% threshold**: Pass if ANY error budget remains (even 0.1%)
- **5.0% threshold**: Pass only if at least 5% error budget remains  
- **10.0% threshold**: Pass only if at least 10% error budget remains

### Recommended Thresholds by Environment

- **Production**: 10-20% (conservative safety margin)
- **Staging**: 5-10% (moderate safety margin)
- **Development**: 0% (aggressive, allow rapid iteration)

### Example Threshold Usage

```bash
# Conservative production deployment
python Nobl9_QualityGate_PP.py --threshold 15.0 --slo-name "prod-api" ...

# Moderate staging deployment  
python Nobl9_QualityGate_PP.py --threshold 5.0 --slo-name "staging-api" ...

# Aggressive development deployment
python Nobl9_QualityGate_PP.py --threshold 0.0 --slo-name "dev-api" ...
```

## Security Notes

- Store client credentials as secrets in your CI/CD platform
- Use environment variables for sensitive data
- Consider using Nobl9's service accounts for CI/CD integration
- Rotate credentials regularly

## API Rate Limits

- Access token generation: 1 request per 3 seconds
- SLO status API: 10 requests per second
- The script handles rate limiting gracefully with appropriate error messages 
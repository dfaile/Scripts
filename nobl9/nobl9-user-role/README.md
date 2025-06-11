# Nobl9 User Role Manager

A command-line tool for managing user roles in Nobl9 projects. This tool allows you to assign specific roles to users within your Nobl9 organization.

## Prerequisites

- Go 1.22 or later
- Nobl9 account 
    - Goto https://nobl9.com for information
- Nobl9 API credentials (Client ID and Client Secret)
    - Goto https://docs.nobl9.com/slos-as-code/sloctl-user-guide/configure-sloctl#prerequisites 

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/nobl9-user-role.git
cd nobl9-user-role
```

2. Install dependencies:
```bash
go mod tidy
```

3. Build the binary:
```bash
go build -o add-user-role
```

## Configuration

Set your Nobl9 API credentials as environment variables:

```bash
export NOBL9_CLIENT_ID="your_client_id"
export NOBL9_CLIENT_SECRET="your_client_secret"
```

## Usage

The tool requires three mandatory flags:

```bash
./add-user-role --project <project_name> --email <user_email> --role <role_name>
```

### Available Roles

- `project-viewer`: Read-only access to project resources
- `project-editor`: Can edit project resources
- `project-admin`: Full administrative access to project
- `organization-admin`: Organization-wide administrative access

### Example

```bash
./add-user-role --project "my-project" --email "user@example.com" --role "project-viewer"
```

### Output

On success:
```
Success: Assigned role 'project-viewer' to user 'user@example.com' in project 'my-project'
```

On error, the tool will display an appropriate error message and exit with a non-zero status code.

## Error Handling

The tool performs several validations:
- Checks for required flags
- Validates email format
- Verifies role is valid
- Ensures user exists in Nobl9
- Validates API credentials

## Building from Source

To build the binary for different platforms:

```bash
# For Linux
GOOS=linux GOARCH=amd64 go build -o add-user-role-linux

# For macOS
GOOS=darwin GOARCH=amd64 go build -o add-user-role-darwin

# For Windows
GOOS=windows GOARCH=amd64 go build -o add-user-role.exe
```

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here] 
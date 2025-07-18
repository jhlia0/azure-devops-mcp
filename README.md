# Azure DevOps MCP Server

A Model Context Protocol (MCP) server that provides seamless integration with Azure DevOps, allowing you to read backlogs, work items, and perform various queries through a standardized interface.

## Features

- **Comprehensive Work Item Management**: Query work items by ID, type, state, assignee, and more
- **Backlog Integration**: Access team backlogs and sprint planning items
- **Flexible State Filtering**: Filter work items by specific states or state categories (active, completed, review)
- **WIQL Query Support**: Execute custom Work Item Query Language queries
- **Smart Defaults**: Configurable default search parameters for streamlined workflows
- **Advanced Filtering**: Support for iteration paths, area paths, and complex multi-condition queries

## Installation

### Prerequisites

- Python 3.11 or higher
- Azure DevOps Personal Access Token (PAT)
- Access to an Azure DevOps organization and project

### Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/jhlia0/azure-devops-mcp.git
   cd mcp-server-azure-devops
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.example .env
   ```

   Edit the `.env` file with your Azure DevOps credentials. It's highly recommended to set `DEFAULT_USER` if you plan to query your own work items:

   ```bash
   ORGANIZATION=your-organization
   PROJECT=your-project
   AZURE_DEVOPS_PAT=your-personal-access-token
   DEFAULT_USER=your-email@example.com # (Optional) Recommended for personal work item queries
   ```

4. **Run the server**:
   ```bash
   python main.py
   ```

## Configuration

### Required Environment Variables

| Variable           | Description                    | Example          |
| ------------------ | ------------------------------ | ---------------- |
| `ORGANIZATION`     | Azure DevOps organization name | `mycompany`      |
| `PROJECT`          | Azure DevOps project name      | `MyProject`      |
| `AZURE_DEVOPS_PAT` | Personal Access Token          | `your-pat-token` |

### Optional Configuration

| Variable                   | Default                                    | Description                                                                       |
| -------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------- |
| `DEFAULT_TEAM`             | -                                          | Default team name for backlog queries                                             |
| `DEFAULT_USER`             | -                                          | Default user for work item queries (recommended for querying your own work items) |
| `DEFAULT_WORK_ITEM_TYPES`  | `Bug,Task,User Story,Product Backlog Item` | Default work item types                                                           |
| `DEFAULT_MAX_RESULTS`      | `100`                                      | Maximum number of results to return                                               |
| `EXCLUDE_CLOSED`           | `true`                                     | Exclude closed work items by default                                              |
| `EXCLUDE_REMOVED`          | `true`                                     | Exclude removed work items by default                                             |
| `DEFAULT_ITERATION_PATH`   | -                                          | Default iteration path for queries                                                |
| `DEFAULT_AREA_PATH`        | -                                          | Default area path for queries                                                     |
| `DEFAULT_ACTIVE_STATES`    | `Active,New,In Progress,To Do,Doing`       | Default active states                                                             |
| `DEFAULT_COMPLETED_STATES` | `Closed,Done,Resolved`                     | Default completed states                                                          |
| `DEFAULT_REVIEW_STATES`    | `Code Review,Testing,Approved`             | Default review states                                                             |

## Available MCP Tools

### Core Work Item Tools

- **`get_work_items`** - Get work items by their IDs
- **`get_work_items_by_query`** - Execute custom WIQL queries with optional project filtering
- **`get_work_items_by_type`** - Get work items by type (Bug, Task, etc.) with optional state and project filtering
- **`get_work_items_by_state`** - Get work items by specific state with additional filters and optional project filtering
- **`get_work_items_with_filters`** - Advanced filtering with multiple criteria and optional project filtering

### User-Focused Tools

- **`get_my_work_items`** - Get work items assigned to a specific user with state and optional project filtering
- **`get_active_work_items`** - Get all active work items using default filters and optional project filtering

### Backlog Tools

- **`get_backlog_items`** - Get backlog items for a team with optional project filtering
- **`get_default_backlog`** - Get backlog items using default team settings with optional project filtering

### State Management Tools

- **`get_work_items_by_state_category`** - Get work items by state category (active, completed, review) with optional project filtering
- **`get_closed_work_items`** - Get closed work items with optional filters and project filtering
- **`get_available_states`** - Get list of common work item states

### Work Item Modification Tools

- **`update_work_item_title`** - Update the title of a work item
- **`update_work_item_description`** - Update the description of a work item
- **`add_work_item_comment`** - Add a comment to a work item
- **`create_work_item`** - Create a new work item

### Utility Tools

- **`get_default_work_items`** - Get work items using all default search settings with optional project filtering
- **`get_project_info`** - Get project configuration and default settings

## Usage Examples

### Basic Queries

```python
# Get specific work items by ID
get_work_items({"ids": [1234, 5678]})

# Get all active work items
get_active_work_items()

# Get work items assigned to current user
get_my_work_items()
```

### State-Based Queries

```python
# Get work items in specific states
get_my_work_items(states=["Active", "In Progress"])

# Get work items by state category
get_work_items_by_state_category("active")

# Get bugs in specific state
get_work_items_by_type("Bug", states=["New", "Active"])
```

### Advanced Filtering

```python
# Complex multi-condition query
get_work_items_with_filters({
    "states": ["New", "Active"],
    "work_item_types": ["Bug", "Task"],
    "assigned_to": "user@example.com",
    "max_results": 50
})

# Get work items by specific state with filters
get_work_items_by_state({
    "state": "In Progress",
    "work_item_type": "User Story",
    "assigned_to": "developer@company.com"
})
```

### Custom WIQL Queries

```python
# Execute custom WIQL query
get_work_items_by_query({
    "wiql": """
    SELECT [System.Id], [System.Title], [System.State]
    FROM WorkItems
    WHERE [System.WorkItemType] = 'Bug'
    AND [System.State] = 'Active'
    ORDER BY [System.CreatedDate] DESC
    """
})

# Execute custom WIQL query with project filter
get_work_items_by_query({
    "wiql": "SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = 'Bug'",
    "project": "MyProject",
    "include_project_filter": True
})
```

### Work Item Modification

```python
# Update work item title
update_work_item_title({"id": 1234, "title": "New Title for Work Item"})

# Update work item description
update_work_item_description({"id": 1234, "description": "Updated description text."})

# Add a comment to a work item
add_work_item_comment({"id": 1234, "comment": "This is a new comment."})

# Create a new bug
create_work_item({
    "work_item_type": "Bug",
    "title": "New Bug Found",
    "description": "This is a description of the new bug.",
    "assigned_to": "user@example.com",
    "area_path": "MyProject\Area\SubArea"
})

```

## Authentication

The server uses Azure DevOps Personal Access Tokens (PAT) for authentication. To create a PAT:

1. Go to `https://dev.azure.com/{organization}/_usersSettings/tokens`
2. Click "New Token"
3. Configure the token with appropriate permissions:
   - **Work Items**: Read
   - **Project and Team**: Read
4. Copy the generated token and add it to your `.env` file

## Architecture

### Key Components

- **Configuration Layer** (`config.py`): Manages environment variables and default settings using Pydantic
- **Client Layer** (`azure_devops_client.py`): Handles Azure DevOps REST API communication
- **Server Layer** (`server.py`): Implements MCP tools and request handling
- **Entry Point** (`main.py`): Starts the FastMCP server

## Development

### Adding New Tools

1. Define request models in `server.py`
2. Implement the tool function with `@mcp.tool()` decorator
3. Add appropriate error handling and response formatting
4. Update this README with the new tool documentation

### Testing

```bash
# Install development dependencies
uv sync

# Run the server in development mode
python main.py
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify your PAT has the correct permissions and hasn't expired
2. **Project Not Found**: Check that the organization and project names are correct
3. **Network Issues**: Ensure you can access Azure DevOps from your network
4. **State Filtering**: Different projects may use different state names - check your project's work item states

### Debugging

Enable debug logging by setting the environment variable:

```bash
export DEBUG=true
python main.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:

- Check the troubleshooting section above
- Review Azure DevOps REST API documentation
- Open an issue in the project repository

## Related Projects

- [FastMCP](https://github.com/jlowin/fastmcp) - The MCP framework used by this server
- [Azure DevOps REST API](https://docs.microsoft.com/en-us/rest/api/azure/devops/) - Official API documentation

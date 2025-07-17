import asyncio
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

from src.client import client, WorkItem, BacklogItem
from config import settings


# MCP Server initialization
mcp = FastMCP("Azure DevOps MCP Server")


class GetWorkItemsRequest(BaseModel):
    """Request model for getting work items."""

    ids: List[int]


class GetWorkItemsByQueryRequest(BaseModel):
    """Request model for getting work items by WIQL query."""

    wiql: str
    project: Optional[str] = None
    include_project_filter: Optional[bool] = None


class GetBacklogItemsRequest(BaseModel):
    """Request model for getting backlog items."""

    team_name: Optional[str] = None
    project: Optional[str] = None
    include_project_filter: Optional[bool] = None


class GetWorkItemsByStateRequest(BaseModel):
    """Request model for getting work items by state."""

    state: str
    work_item_type: Optional[str] = None
    assigned_to: Optional[str] = None
    max_results: Optional[int] = None
    project: Optional[str] = None
    include_project_filter: Optional[bool] = None


class GetWorkItemsWithFiltersRequest(BaseModel):
    """Request model for getting work items with various filters."""

    states: Optional[List[str]] = None
    work_item_types: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    team_name: Optional[str] = None
    iteration_path: Optional[str] = None
    area_path: Optional[str] = None
    max_results: Optional[int] = None
    exclude_closed: Optional[bool] = None
    exclude_removed: Optional[bool] = None
    project: Optional[str] = None
    include_project_filter: Optional[bool] = None


@mcp.tool()
async def get_work_items(request: GetWorkItemsRequest) -> List[Dict[str, Any]]:
    """
    Get work items by their IDs.

    Args:
        request: Request containing list of work item IDs

    Returns:
        List of work items with their details
    """
    try:
        work_items = await client.get_work_items(request.ids)
        return [item.model_dump() for item in work_items]
    except Exception as e:
        return [{"error": f"Failed to fetch work items: {str(e)}"}]


@mcp.tool()
async def get_work_items_by_query(
    request: GetWorkItemsByQueryRequest,
) -> List[Dict[str, Any]]:
    """
    Get work items using WIQL (Work Item Query Language).

    Args:
        request: Request containing WIQL query string and optional project

    Returns:
        List of work items matching the query
    """
    try:
        project = request.project or settings.project
        wiql = request.wiql

        # If project filtering is requested and the WIQL doesn't already contain project filter
        if request.include_project_filter is True or (
            request.include_project_filter is None and settings.enable_project_filtering
        ):
            if "[System.TeamProject]" not in wiql.upper():
                # Add project filter to the query
                project_filter = settings.get_project_filter(project, True)
                if project_filter:
                    # Insert project filter after WHERE clause
                    if "WHERE" in wiql.upper():
                        wiql = wiql.replace("WHERE", f"WHERE {project_filter} AND", 1)
                    else:
                        # If no WHERE clause, add one before ORDER BY or at the end
                        if "ORDER BY" in wiql.upper():
                            wiql = wiql.replace(
                                "ORDER BY", f"WHERE {project_filter} ORDER BY", 1
                            )
                        else:
                            wiql = f"{wiql.rstrip()} WHERE {project_filter}"
        print(wiql)
        work_items = await client.get_work_items_by_wiql(wiql, project)
        return [item.model_dump() for item in work_items]
    except Exception as e:
        return [{"error": f"Failed to execute WIQL query: {str(e)}"}]


@mcp.tool()
async def get_backlog_items(request: GetBacklogItemsRequest) -> List[Dict[str, Any]]:
    """
    Get backlog items for a team or project.

    Args:
        request: Request containing optional team name and project (uses defaults if not specified)

    Returns:
        List of backlog items
    """
    try:
        team_name = request.team_name or settings.default_team
        project = request.project or settings.project

        # Try to get backlog items through the API first
        try:
            backlog_items = await client.get_backlog_items(team_name, project)
            return [item.model_dump() for item in backlog_items]
        except Exception:
            # Fallback to WIQL query with project filtering support
            conditions = [
                "[System.WorkItemType] IN ('Product Backlog Item', 'User Story', 'Feature')",
                "[System.State] <> 'Removed'",
            ]

            # Add project filter if needed
            project_filter = settings.get_project_filter(
                project, request.include_project_filter
            )
            if project_filter:
                conditions.append(project_filter)

            wiql = f"""
            SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
            FROM WorkItems
            WHERE {' AND '.join(conditions)}
            ORDER BY [Microsoft.VSTS.Common.Priority] ASC
            """

            work_items = await client.get_work_items_by_wiql(wiql, project)
            return [
                {
                    "id": item.id,
                    "title": item.title,
                    "work_item_type": item.work_item_type,
                    "state": item.state,
                    "assigned_to": item.assigned_to,
                    "priority": None,
                    "story_points": None,
                }
                for item in work_items
            ]
    except Exception as e:
        return [{"error": f"Failed to fetch backlog items: {str(e)}"}]


@mcp.tool()
async def get_active_work_items(
    project: Optional[str] = None, include_project_filter: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Get all active work items in the project using default filters.

    Args:
        project: Project name (uses default project if not specified)

    Returns:
        List of active work items
    """
    target_project = project or settings.project
    default_filters = settings.get_default_wiql_filters(
        target_project, include_project_filter
    )
    wiql = f"""
    SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
    FROM WorkItems
    WHERE [System.WorkItemType] IN ({','.join(f"'{t}'" for t in settings.default_work_item_types_list)})
    {default_filters}
    ORDER BY [System.ChangedDate] DESC
    """

    try:
        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        # Limit results to default max
        return [
            item.model_dump() for item in work_items[: settings.default_max_results]
        ]
    except Exception as e:
        return [{"error": f"Failed to fetch active work items: {str(e)}"}]


@mcp.tool()
async def get_my_work_items(
    assigned_to: Optional[str] = None,
    states: Optional[List[str]] = None,
    project: Optional[str] = None,
    include_project_filter: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Get work items assigned to a specific user.

    Args:
        assigned_to: Display name or email of the user (uses default user if not specified)
        states: List of states to filter by (e.g., ['Active', 'New', 'In Progress'])
        project: Project name (uses default project if not specified)

    Returns:
        List of work items assigned to the user
    """
    user = assigned_to or settings.default_user
    if not user:
        return [{"error": "No user specified and no default user configured"}]

    target_project = project or settings.project

    # Build state filter
    state_filter = ""
    if states:
        state_conditions = [f"[System.State] = '{state}'" for state in states]
        state_filter = f"AND ({' OR '.join(state_conditions)})"
    else:
        state_filter = settings.get_default_wiql_filters(
            target_project, include_project_filter
        )

    wiql = f"""
    SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
    FROM WorkItems
    WHERE [System.AssignedTo] = '{user}'
    AND [System.WorkItemType] IN ({','.join(f"'{t}'" for t in settings.default_work_item_types_list)})
    {state_filter}
    ORDER BY [System.ChangedDate] DESC
    """

    try:
        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        return [
            item.model_dump() for item in work_items[: settings.default_max_results]
        ]
    except Exception as e:
        return [{"error": f"Failed to fetch work items for user: {str(e)}"}]


@mcp.tool()
async def get_work_items_by_type(
    work_item_type: str,
    states: Optional[List[str]] = None,
    project: Optional[str] = None,
    include_project_filter: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Get work items by their type (e.g., Bug, Task, User Story).

    Args:
        work_item_type: Type of work item to filter by
        states: List of states to filter by (e.g., ['Active', 'New', 'In Progress'])
        project: Project name (uses default project if not specified)

    Returns:
        List of work items of the specified type
    """
    target_project = project or settings.project

    # Build state filter
    state_filter = ""
    if states:
        state_conditions = [f"[System.State] = '{state}'" for state in states]
        state_filter = f"AND ({' OR '.join(state_conditions)})"
    else:
        state_filter = settings.get_default_wiql_filters(
            target_project, include_project_filter
        )

    wiql = f"""
    SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
    FROM WorkItems
    WHERE [System.WorkItemType] = '{work_item_type}'
    {state_filter}
    ORDER BY [System.ChangedDate] DESC
    """

    try:
        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        return [
            item.model_dump() for item in work_items[: settings.default_max_results]
        ]
    except Exception as e:
        return [{"error": f"Failed to fetch work items by type: {str(e)}"}]


# Additional utility functions
@mcp.tool()
async def get_project_info() -> Dict[str, Any]:
    """
    Get basic project information and default search settings.

    Returns:
        Project configuration information including defaults
    """
    return {
        "organization": settings.organization,
        "project": settings.project,
        "api_version": settings.api_version,
        "base_url": settings.base_url,
        "default_settings": {
            "default_team": settings.default_team,
            "default_user": settings.default_user,
            "default_work_item_types": settings.default_work_item_types_list,
            "default_max_results": settings.default_max_results,
            "exclude_closed": settings.exclude_closed,
            "exclude_removed": settings.exclude_removed,
            "default_iteration_path": settings.default_iteration_path,
            "default_area_path": settings.default_area_path,
        },
    }


@mcp.tool()
async def get_default_work_items(
    project: Optional[str] = None, include_project_filter: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Get work items using all default search settings.
    This is a convenient tool that applies all configured defaults.

    Args:
        project: Project name (uses default project if not specified)

    Returns:
        List of work items matching default criteria
    """
    target_project = project or settings.project

    if settings.default_user:
        # If default user is set, get their work items
        return await get_my_work_items(
            project=target_project, include_project_filter=include_project_filter
        )
    else:
        # Otherwise get all active work items
        return await get_active_work_items(target_project, include_project_filter)


@mcp.tool()
async def get_default_backlog(
    project: Optional[str] = None, include_project_filter: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Get backlog items using default team settings.

    Args:
        project: Project name (uses default project if not specified)

    Returns:
        List of backlog items for the default team
    """
    target_project = project or settings.project
    request = GetBacklogItemsRequest(
        team_name=settings.default_team,
        project=target_project,
        include_project_filter=include_project_filter,
    )
    return await get_backlog_items(request)


@mcp.tool()
async def get_work_items_by_state(
    request: GetWorkItemsByStateRequest,
) -> List[Dict[str, Any]]:
    """
    Get work items by their state (e.g., Active, New, In Progress, Closed).

    Args:
        request: Request containing state, optional filters and project

    Returns:
        List of work items in the specified state
    """
    try:
        target_project = request.project or settings.project

        # Build WIQL query
        conditions = [f"[System.State] = '{request.state}'"]

        # Add work item type filter if specified
        if request.work_item_type:
            conditions.append(f"[System.WorkItemType] = '{request.work_item_type}'")
        else:
            # Use default work item types
            type_conditions = [
                f"[System.WorkItemType] = '{t}'"
                for t in settings.default_work_item_types_list
            ]
            conditions.append(f"({' OR '.join(type_conditions)})")

        # Add assigned to filter if specified
        if request.assigned_to:
            conditions.append(f"[System.AssignedTo] = '{request.assigned_to}'")

        # Add project filter if needed
        project_filter = settings.get_project_filter(
            target_project, request.include_project_filter
        )
        if project_filter:
            conditions.append(project_filter)

        # Add default filters (iteration, area paths)
        iteration_filter = ""
        if settings.default_iteration_path:
            iteration_filter = (
                f"AND [System.IterationPath] UNDER '{settings.default_iteration_path}'"
            )

        area_filter = ""
        if settings.default_area_path:
            area_filter = f"AND [System.AreaPath] UNDER '{settings.default_area_path}'"

        wiql = f"""
        SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
        FROM WorkItems
        WHERE {' AND '.join(conditions)}
        {iteration_filter}
        {area_filter}
        ORDER BY [System.ChangedDate] DESC
        """

        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        max_results = request.max_results or settings.default_max_results
        return [item.model_dump() for item in work_items[:max_results]]
    except Exception as e:
        return [{"error": f"Failed to fetch work items by state: {str(e)}"}]


@mcp.tool()
async def get_work_items_with_filters(
    request: GetWorkItemsWithFiltersRequest,
) -> List[Dict[str, Any]]:
    """
    Get work items with comprehensive filtering options.

    Args:
        request: Request containing various filter options and project

    Returns:
        List of work items matching the filters
    """
    try:
        target_project = request.project or settings.project
        conditions = []

        # State filter
        if request.states:
            state_conditions = [
                f"[System.State] = '{state}'" for state in request.states
            ]
            conditions.append(f"({' OR '.join(state_conditions)})")
        else:
            # Apply default exclusions
            exclude_closed = (
                request.exclude_closed
                if request.exclude_closed is not None
                else settings.exclude_closed
            )
            exclude_removed = (
                request.exclude_removed
                if request.exclude_removed is not None
                else settings.exclude_removed
            )

            if exclude_closed:
                conditions.append("[System.State] <> 'Closed'")
            if exclude_removed:
                conditions.append("[System.State] <> 'Removed'")

        # Work item type filter
        if request.work_item_types:
            type_conditions = [
                f"[System.WorkItemType] = '{t}'" for t in request.work_item_types
            ]
            conditions.append(f"({' OR '.join(type_conditions)})")
        else:
            # Use default work item types
            type_conditions = [
                f"[System.WorkItemType] = '{t}'"
                for t in settings.default_work_item_types_list
            ]
            conditions.append(f"({' OR '.join(type_conditions)})")

        # Assigned to filter
        if request.assigned_to:
            conditions.append(f"[System.AssignedTo] = '{request.assigned_to}'")

        # Iteration path filter
        iteration_path = request.iteration_path or settings.default_iteration_path
        if iteration_path:
            conditions.append(f"[System.IterationPath] UNDER '{iteration_path}'")

        # Area path filter
        area_path = request.area_path or settings.default_area_path
        if area_path:
            conditions.append(f"[System.AreaPath] UNDER '{area_path}'")

        # Project filter
        project_filter = settings.get_project_filter(
            target_project, request.include_project_filter
        )
        if project_filter:
            conditions.append(project_filter)

        # Build WIQL query
        where_clause = " AND ".join(conditions) if conditions else "1 = 1"

        wiql = f"""
        SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
        FROM WorkItems
        WHERE {where_clause}
        ORDER BY [System.ChangedDate] DESC
        """

        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        max_results = request.max_results or settings.default_max_results
        return [item.model_dump() for item in work_items[:max_results]]
    except Exception as e:
        return [{"error": f"Failed to fetch work items with filters: {str(e)}"}]


@mcp.tool()
async def get_closed_work_items(
    work_item_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    project: Optional[str] = None,
    include_project_filter: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Get closed work items.

    Args:
        work_item_type: Optional work item type filter
        assigned_to: Optional assigned to filter
        project: Project name (uses default project if not specified)

    Returns:
        List of closed work items
    """
    try:
        target_project = project or settings.project
        conditions = ["[System.State] = 'Closed'"]

        if work_item_type:
            conditions.append(f"[System.WorkItemType] = '{work_item_type}'")
        else:
            type_conditions = [
                f"[System.WorkItemType] = '{t}'"
                for t in settings.default_work_item_types_list
            ]
            conditions.append(f"({' OR '.join(type_conditions)})")

        if assigned_to:
            conditions.append(f"[System.AssignedTo] = '{assigned_to}'")

        # Add project filter if needed
        project_filter = settings.get_project_filter(
            target_project, include_project_filter
        )
        if project_filter:
            conditions.append(project_filter)

        wiql = f"""
        SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
        FROM WorkItems
        WHERE {' AND '.join(conditions)}
        ORDER BY [System.ChangedDate] DESC
        """

        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        return [
            item.model_dump() for item in work_items[: settings.default_max_results]
        ]
    except Exception as e:
        return [{"error": f"Failed to fetch closed work items: {str(e)}"}]


@mcp.tool()
async def get_available_states() -> List[Dict[str, Any]]:
    """
    Get a list of common work item states.

    Returns:
        List of common work item states
    """
    common_states = [
        {"state": "New", "description": "Newly created work items"},
        {"state": "Active", "description": "Work items being actively worked on"},
        {"state": "In Progress", "description": "Work items currently in progress"},
        {"state": "Resolved", "description": "Work items that have been resolved"},
        {"state": "Closed", "description": "Completed work items"},
        {"state": "Removed", "description": "Work items that have been removed"},
        {
            "state": "Done",
            "description": "Completed work items (alternative to Closed)",
        },
        {"state": "To Do", "description": "Work items ready to be started"},
        {"state": "Doing", "description": "Work items currently being worked on"},
        {"state": "Code Review", "description": "Work items in code review"},
        {"state": "Testing", "description": "Work items being tested"},
        {"state": "Approved", "description": "Work items that have been approved"},
        {"state": "Committed", "description": "Work items that have been committed to"},
    ]

    return common_states


@mcp.tool()
async def get_work_items_by_state_category(
    category: str,
    project: Optional[str] = None,
    include_project_filter: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Get work items by state category (active, completed, review).

    Args:
        category: State category ('active', 'completed', 'review')
        project: Project name (uses default project if not specified)

    Returns:
        List of work items in the specified state category
    """
    try:
        target_project = project or settings.project

        if category.lower() == "active":
            states = settings.default_active_states_list
        elif category.lower() == "completed":
            states = settings.default_completed_states_list
        elif category.lower() == "review":
            states = settings.default_review_states_list
        else:
            return [
                {
                    "error": f"Unknown state category: {category}. Use 'active', 'completed', or 'review'"
                }
            ]

        state_conditions = [f"[System.State] = '{state}'" for state in states]
        type_conditions = [
            f"[System.WorkItemType] = '{t}'"
            for t in settings.default_work_item_types_list
        ]

        # Add default filters
        default_filters = ""
        if settings.default_iteration_path:
            default_filters += (
                f" AND [System.IterationPath] UNDER '{settings.default_iteration_path}'"
            )
        if settings.default_area_path:
            default_filters += (
                f" AND [System.AreaPath] UNDER '{settings.default_area_path}'"
            )

        # Add project filter if needed
        project_filter = settings.get_project_filter(
            target_project, include_project_filter
        )
        if project_filter:
            default_filters += f" AND {project_filter}"

        wiql = f"""
        SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
        FROM WorkItems
        WHERE ({' OR '.join(state_conditions)})
        AND ({' OR '.join(type_conditions)})
        {default_filters}
        ORDER BY [System.ChangedDate] DESC
        """

        work_items = await client.get_work_items_by_wiql(wiql, target_project)
        return [
            item.model_dump() for item in work_items[: settings.default_max_results]
        ]
    except Exception as e:
        return [{"error": f"Failed to fetch work items by state category: {str(e)}"}]

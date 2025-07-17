import asyncio
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

from config import settings


class WorkItem(BaseModel):
    """Work item model."""

    id: int
    title: str
    work_item_type: str
    state: str
    assigned_to: Optional[str] = None
    created_date: str
    changed_date: str
    description: Optional[str] = None
    tags: Optional[str] = None


class BacklogItem(BaseModel):
    """Backlog item model."""

    id: int
    title: str
    work_item_type: str
    state: str
    priority: Optional[int] = None
    story_points: Optional[float] = None
    assigned_to: Optional[str] = None


class WorkItemLink(BaseModel):
    """Work item link model."""

    source_id: int
    target_id: int
    link_type: str
    comment: Optional[str] = None


class AzureDevOpsClient:
    """Azure DevOps API client with connection pooling."""

    def __init__(self):
        self.base_url = settings.api_base_url
        self.headers = {**settings.auth_header, "Content-Type": "application/json"}
        self.api_version = settings.api_version
        self.max_batch_size = 200  # Azure DevOps API limit
        self.organization = settings.organization
        self.default_project = settings.project
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None:
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
            timeout = httpx.Timeout(30.0, connect=10.0)
            self._client = httpx.AsyncClient(
                limits=limits, timeout=timeout, http2=True, headers=self.headers
            )
        return self._client

    async def close(self):
        """Close the HTTP client and clean up connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Azure DevOps API."""
        # Use specified project or default project
        target_project = project or self.default_project
        base_url = f"https://dev.azure.com/{self.organization}/{target_project}/_apis"
        url = f"{base_url}/{endpoint}"

        default_params = {"api-version": self.api_version}
        if params:
            default_params.update(params)

        response = await self.client.get(url, params=default_params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(
                f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.\n{exc.response.text}"
            )

        return response.json()

    async def get_work_items(
        self, ids: List[int], project: Optional[str] = None
    ) -> List[WorkItem]:
        """Get work items by IDs, handling Azure DevOps 200 item limit with batching."""
        if not ids:
            return []

        # If within limit, make single request
        if len(ids) <= self.max_batch_size:
            return await self._get_work_items_batch(ids, project)

        # Split into batches and make concurrent requests
        batches = [
            ids[i : i + self.max_batch_size]
            for i in range(0, len(ids), self.max_batch_size)
        ]

        # Execute all batches concurrently
        batch_results = await asyncio.gather(
            *[self._get_work_items_batch(batch, project) for batch in batches],
            return_exceptions=True,
        )

        # Combine results and handle any exceptions
        work_items = []
        for result in batch_results:
            if isinstance(result, Exception):
                # Log error but continue with other batches
                print(f"Error in batch: {result}")
                continue
            work_items.extend(result)

        return work_items

    async def _get_work_items_batch(
        self, ids: List[int], project: Optional[str] = None
    ) -> List[WorkItem]:
        """Get a batch of work items (200 or fewer)."""
        ids_str = ",".join(map(str, ids))
        endpoint = f"wit/workitems"
        params = {"ids": ids_str, "$expand": "fields"}

        data = await self._make_request(endpoint, params, project)

        work_items = []
        for item in data.get("value", []):
            fields = item.get("fields", {})
            work_item = WorkItem(
                id=item["id"],
                title=fields.get("System.Title", ""),
                work_item_type=fields.get("System.WorkItemType", ""),
                state=fields.get("System.State", ""),
                assigned_to=(
                    fields.get("System.AssignedTo", {}).get("displayName")
                    if fields.get("System.AssignedTo")
                    else None
                ),
                created_date=fields.get("System.CreatedDate", ""),
                changed_date=fields.get("System.ChangedDate", ""),
                description=fields.get("System.Description", ""),
                tags=fields.get("System.Tags", ""),
            )
            work_items.append(work_item)

        return work_items

    async def get_work_items_by_wiql(
        self, wiql: str, project: Optional[str] = None
    ) -> List[WorkItem]:
        """Get work items using WIQL (Work Item Query Language)."""
        data = await self.execute_wiql(wiql, project)

        work_item_refs = data.get("workItems", [])
        if not work_item_refs:
            return []

        ids = [ref["id"] for ref in work_item_refs]
        return await self.get_work_items(ids, project)

    async def get_work_item_links_by_wiql(
        self, wiql: str, project: Optional[str] = None
    ) -> List[WorkItemLink]:
        """Get work item links using WIQL (Work Item Query Language)."""
        data = await self.execute_wiql(wiql, project)

        work_item_relations = data.get("workItemRelations", [])
        if not work_item_relations:
            return []

        links = []
        for relation in work_item_relations:
            if (
                relation.get("rel")
                and relation.get("source")
                and relation.get("target")
            ):
                link = WorkItemLink(
                    source_id=relation["source"]["id"],
                    target_id=relation["target"]["id"],
                    link_type=relation["rel"],
                    comment=relation.get("attributes", {}).get("comment"),
                )
                links.append(link)

        return links

    async def execute_wiql(
        self, wiql: str, project: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute WIQL query and return raw response data."""
        endpoint = "wit/wiql"
        target_project = project or self.default_project
        base_url = f"https://dev.azure.com/{self.organization}/{target_project}/_apis"

        response = await self.client.post(
            f"{base_url}/{endpoint}",
            params={"api-version": self.api_version},
            json={"query": wiql},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(
                f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.\\n{exc.response.text}"
            )
            raise exc

        return response.json()

    async def get_backlog_items(
        self, team_name: Optional[str] = None, project: Optional[str] = None
    ) -> List[BacklogItem]:
        """Get backlog items for a team."""
        if team_name:
            endpoint = f"{team_name}/_apis/work/backlogs"
        else:
            endpoint = "work/backlogs"

        # Get backlog levels
        try:
            backlog_data = await self._make_request(endpoint, project=project)
            backlogs = backlog_data.get("value", [])

            if not backlogs:
                return []

            # Get items from the first backlog (usually Product Backlog)
            backlog_id = backlogs[0]["id"]
            items_endpoint = f"work/backlogs/{backlog_id}/workItems"
            items_data = await self._make_request(items_endpoint, project=project)

            work_item_refs = items_data.get("workItems", [])
            if not work_item_refs:
                return []

            ids = [ref["target"]["id"] for ref in work_item_refs]
            work_items = await self.get_work_items(ids, project)

            # Convert to BacklogItem
            backlog_items = []
            for item in work_items:
                # Extract additional fields specific to backlog items
                backlog_item = BacklogItem(
                    id=item.id,
                    title=item.title,
                    work_item_type=item.work_item_type,
                    state=item.state,
                    assigned_to=item.assigned_to,
                    priority=None,  # Would need to be extracted from fields
                    story_points=None,  # Would need to be extracted from fields
                )
                backlog_items.append(backlog_item)

            return backlog_items

        except Exception:
            # Fallback to WIQL query for backlog items
            wiql = """
            SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
            FROM WorkItems
            WHERE [System.WorkItemType] IN ('Product Backlog Item', 'User Story', 'Feature')
            AND [System.State] <> 'Removed'
            ORDER BY [Microsoft.VSTS.Common.Priority] ASC
            """
            work_items = await self.get_work_items_by_wiql(wiql, project)

            return [
                BacklogItem(
                    id=item.id,
                    title=item.title,
                    work_item_type=item.work_item_type,
                    state=item.state,
                    assigned_to=item.assigned_to,
                    priority=None,
                    story_points=None,
                )
                for item in work_items
            ]


# Global client instance
client = AzureDevOpsClient()


# Cleanup function for proper resource management
async def cleanup_client():
    """Cleanup the global client instance."""
    await client.close()

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


class AzureDevOpsClient:
    """Azure DevOps API client."""
    
    def __init__(self):
        self.base_url = settings.api_base_url
        self.headers = {
            **settings.auth_header,
            "Content-Type": "application/json"
        }
        self.api_version = settings.api_version
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to Azure DevOps API."""
        url = f"{self.base_url}/{endpoint}"
        
        default_params = {"api-version": self.api_version}
        if params:
            default_params.update(params)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=default_params)
            response.raise_for_status()
            return response.json()
    
    async def get_work_items(self, ids: List[int]) -> List[WorkItem]:
        """Get work items by IDs."""
        if not ids:
            return []
        
        ids_str = ",".join(map(str, ids))
        endpoint = f"wit/workitems"
        params = {"ids": ids_str, "$expand": "fields"}
        
        data = await self._make_request(endpoint, params)
        
        work_items = []
        for item in data.get("value", []):
            fields = item.get("fields", {})
            work_item = WorkItem(
                id=item["id"],
                title=fields.get("System.Title", ""),
                work_item_type=fields.get("System.WorkItemType", ""),
                state=fields.get("System.State", ""),
                assigned_to=fields.get("System.AssignedTo", {}).get("displayName") if fields.get("System.AssignedTo") else None,
                created_date=fields.get("System.CreatedDate", ""),
                changed_date=fields.get("System.ChangedDate", ""),
                description=fields.get("System.Description", ""),
                tags=fields.get("System.Tags", "")
            )
            work_items.append(work_item)
        
        return work_items
    
    async def get_work_items_by_wiql(self, wiql: str) -> List[WorkItem]:
        """Get work items using WIQL (Work Item Query Language)."""
        endpoint = "wit/wiql"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{endpoint}",
                headers=self.headers,
                params={"api-version": self.api_version},
                json={"query": wiql}
            )
            response.raise_for_status()
            data = response.json()
        
        work_item_refs = data.get("workItems", [])
        if not work_item_refs:
            return []
        
        ids = [ref["id"] for ref in work_item_refs]
        return await self.get_work_items(ids)
    
    async def get_backlog_items(self, team_name: Optional[str] = None) -> List[BacklogItem]:
        """Get backlog items for a team."""
        if team_name:
            endpoint = f"{team_name}/_apis/work/backlogs"
        else:
            endpoint = "work/backlogs"
        
        # Get backlog levels
        try:
            backlog_data = await self._make_request(endpoint)
            backlogs = backlog_data.get("value", [])
            
            if not backlogs:
                return []
            
            # Get items from the first backlog (usually Product Backlog)
            backlog_id = backlogs[0]["id"]
            items_endpoint = f"work/backlogs/{backlog_id}/workItems"
            items_data = await self._make_request(items_endpoint)
            
            work_item_refs = items_data.get("workItems", [])
            if not work_item_refs:
                return []
            
            ids = [ref["target"]["id"] for ref in work_item_refs]
            work_items = await self.get_work_items(ids)
            
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
                    story_points=None  # Would need to be extracted from fields
                )
                backlog_items.append(backlog_item)
            
            return backlog_items
            
        except Exception as e:
            # Fallback to WIQL query for backlog items
            wiql = """
            SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.AssignedTo]
            FROM WorkItems
            WHERE [System.WorkItemType] IN ('Product Backlog Item', 'User Story', 'Feature')
            AND [System.State] <> 'Removed'
            ORDER BY [Microsoft.VSTS.Common.Priority] ASC
            """
            work_items = await self.get_work_items_by_wiql(wiql)
            
            return [
                BacklogItem(
                    id=item.id,
                    title=item.title,
                    work_item_type=item.work_item_type,
                    state=item.state,
                    assigned_to=item.assigned_to,
                    priority=None,
                    story_points=None
                )
                for item in work_items
            ]


# Global client instance
client = AzureDevOpsClient()
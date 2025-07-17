from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class AzureDevOpsSettings(BaseSettings):
    """Azure DevOps configuration settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Azure DevOps configuration
    organization: str = Field(..., description="Azure DevOps organization name")
    project: str = Field(..., description="Azure DevOps project name")
    personal_access_token: str = Field(..., alias="AZURE_DEVOPS_PAT", description="Personal Access Token for Azure DevOps")
    
    # API configuration
    api_version: str = Field(default="7.1", description="Azure DevOps REST API version")
    base_url: str = Field(default="https://dev.azure.com", description="Azure DevOps base URL")
    
    # Default search settings
    default_team: Optional[str] = Field(default=None, description="Default team name for backlog queries")
    default_user: Optional[str] = Field(default=None, description="Default user for work item queries")
    default_work_item_types: str = Field(default="Bug,Task,User Story,Product Backlog Item", description="Default work item types (comma-separated)")
    default_max_results: int = Field(default=100, description="Default maximum number of results to return")
    
    # Search filters
    exclude_closed: bool = Field(default=True, description="Exclude closed work items by default")
    exclude_removed: bool = Field(default=True, description="Exclude removed work items by default")
    
    # Default iteration settings
    default_iteration_path: Optional[str] = Field(default=None, description="Default iteration path for queries")
    default_area_path: Optional[str] = Field(default=None, description="Default area path for queries")
    
    # State-specific settings
    default_active_states: str = Field(default="Active,New,In Progress,To Do,Doing", description="Default active states (comma-separated)")
    default_completed_states: str = Field(default="Closed,Done,Resolved", description="Default completed states (comma-separated)")
    default_review_states: str = Field(default="Code Review,Testing,Approved", description="Default review states (comma-separated)")
    
    # Project filtering settings
    enable_project_filtering: bool = Field(default=True, description="Enable project filtering in WIQL queries by default")
    
    @property
    def api_base_url(self) -> str:
        """Get the complete API base URL."""
        return f"{self.base_url}/{self.organization}/{self.project}/_apis"
    
    @property
    def auth_header(self) -> dict[str, str]:
        """Get authentication header for API requests."""
        import base64
        token = base64.b64encode(f":{self.personal_access_token}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    
    @property
    def default_work_item_types_list(self) -> List[str]:
        """Get default work item types as a list."""
        return [t.strip() for t in self.default_work_item_types.split(",")]
    
    @property
    def default_active_states_list(self) -> List[str]:
        """Get default active states as a list."""
        return [s.strip() for s in self.default_active_states.split(",")]
    
    @property
    def default_completed_states_list(self) -> List[str]:
        """Get default completed states as a list."""
        return [s.strip() for s in self.default_completed_states.split(",")]
    
    @property
    def default_review_states_list(self) -> List[str]:
        """Get default review states as a list."""
        return [s.strip() for s in self.default_review_states.split(",")]
    
    def get_default_state_filter(self) -> str:
        """Get default state filter for WIQL queries."""
        conditions = []
        if self.exclude_closed:
            conditions.append("[System.State] <> 'Closed'")
        if self.exclude_removed:
            conditions.append("[System.State] <> 'Removed'")
        
        if conditions:
            return " AND " + " AND ".join(conditions)
        return ""
    
    def get_project_filter(self, project: str, force_filter: Optional[bool] = None) -> str:
        """Get project filter for WIQL queries.
        
        Args:
            project: Project name to filter by
            force_filter: Override the default project filtering setting
            
        Returns:
            Project filter string or empty string if filtering is disabled
        """
        should_filter = force_filter if force_filter is not None else self.enable_project_filtering
        if should_filter and project:
            return f"[System.TeamProject] = '{project}'"
        return ""
    
    def get_default_wiql_filters(self, project: Optional[str] = None, include_project_filter: Optional[bool] = None) -> str:
        """Get default WIQL filters including state, iteration, area, and optionally project."""
        filters = []
        
        # State filters
        state_filter = self.get_default_state_filter()
        if state_filter:
            filters.append(state_filter.replace(" AND ", "", 1))
        
        # Iteration path filter
        if self.default_iteration_path:
            filters.append(f"[System.IterationPath] UNDER '{self.default_iteration_path}'")
        
        # Area path filter
        if self.default_area_path:
            filters.append(f"[System.AreaPath] UNDER '{self.default_area_path}'")
        
        # Project filter
        if project:
            project_filter = self.get_project_filter(project, include_project_filter)
            if project_filter:
                filters.append(project_filter)
        
        if filters:
            return " AND " + " AND ".join(filters)
        return ""


# Global settings instance
settings = AzureDevOpsSettings()